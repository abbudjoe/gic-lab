"""R2 terminal characterization; phase admission/runtime execution are separate seams.

The joined harness must replace these input producers with actual retained phases.
This module deliberately proves only the actual condition_session terminal logic.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from giclab.harness.t09_provider_contracts import V16_PROVIDER_CONTRACT

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def terminal_host():
    name = "t09_terminal_characterization"
    spec = importlib.util.spec_from_file_location(
        name, ROOT / "containers/sira-smoke/pragmatic/t09_remote_runner.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
        yield module
    finally:
        sys.modules.pop(name, None)


@pytest.mark.parametrize(
    "answer,exit_code",
    [
        ("fixture answer one", 0),
        ("fixture answer two", 0),
        (None, 0),
        ("partial fixture answer", 9),
    ],
)
def test_r2_actual_host_terminal_preserves_session_answer(
    terminal_host, tmp_path, monkeypatch, answer, exit_code
):
    host = terminal_host
    contract = V16_PROVIDER_CONTRACT
    run_id = contract.run_ids[0]
    args = argparse.Namespace(
        repository=ROOT,
        artifact_root=tmp_path,
        run_id=run_id,
        package_commit="a98b4b875ab4d101709d62bc7222b5c90681a893",
    )
    # The terminal-only producer still supplies real, exact campaign control
    # ownership; adding writer admission must not bypass this retained loader.
    journal = host.EarlyCleanupJournal.initialize(
        tmp_path / "preflight-cleanup-state",
        plan_id=contract.plan_id,
        host_run_id=contract.host_run_id,
        package_commit=args.package_commit,
        plan_sha256="b" * 64,
        provider_instance_id="terminal-fixture-instance",
        provider_instance_identity_sha256="c" * 64,
        provider_started_at_epoch=1.0,
        launch_slot=1,
        replacement_eligibility_sha256=None,
        firewall_baseline_identity_sha256="d" * 64,
        clock=lambda: 2.0,
    )
    args.early_cleanup_journal = journal.root
    request = SimpleNamespace(
        deterministic_fixture=False,
        inputs={},
        expected_projection={
            "transaction_root_identity": "b" * 64,
            "session_id": f"SESSION-{run_id}",
        },
    )
    monkeypatch.setattr(host, "_load_bridge_phase", lambda *a: (contract, request))
    monkeypatch.setattr(host, "load_frozen_run_manifest", lambda *a, **kw: ({}, "a" * 64))
    monkeypatch.setattr(host, "validate_condition_session_request", lambda *a, **kw: None)
    monkeypatch.setattr(host, "_external_phase_request_clock", lambda value: value)
    calls = []

    class TerminalCapture:
        def __init__(self, **kwargs):
            self.binding = kwargs["binding"]

        def finish(self, **kwargs):
            calls.append(kwargs)

        def close(self):
            pass

        def admit_path(self, path, count):
            # This terminal-only component supplies its source producer; actual
            # shared writer admission is exercised by the separate joined path.
            assert path.is_relative_to(tmp_path) and count > 0

    monkeypatch.setattr(host, "_ConditionSessionBridge", TerminalCapture)
    commands = host.load_object(
        host._contract_paths_for(ROOT, contract)["commands"], label="test commands"
    )
    manifest = host._manifest_for_contract(commands, run_id, contract)
    attempt = tmp_path / host.manifest_output_root(manifest)

    def execute(_args, *, condition_bridge):
        raw = attempt / "raw"
        session = raw / "sira-output/session.json"
        session.parent.mkdir(parents=True)
        session.write_text(
            json.dumps(
                {
                    "history": [
                        [
                            {},
                            f"send_msg_to_user({answer!r})" if answer is not None else "noop()",
                            {},
                        ]
                    ],
                    "is_complete": answer is not None,
                    "error": "",
                    "goal": "fixture only",
                }
            )
        )
        host.write_exclusive(raw / "host-cleanup-receipt.json", {"returncode": exit_code})
        files, total = host._raw_attempt_files(raw)
        raw_manifest = {
            "schema_version": "0.1.0",
            "plan_id": contract.plan_id,
            "host_run_id": contract.host_run_id,
            "run_id": run_id,
            "package_commit": args.package_commit,
            "raw_attempt_root": "raw",
            "files": files,
            "total_bytes": total,
        }
        host.write_exclusive(attempt / "raw-attempt-manifest.json", raw_manifest)
        host.write_exclusive(
            attempt / "raw-attempt-complete.json",
            {
                "schema_version": "0.1.0",
                "plan_id": contract.plan_id,
                "host_run_id": contract.host_run_id,
                "run_id": run_id,
                "raw_attempt_complete": True,
                "empirical_attempt_consumed": True,
                "raw_manifest_sha256": host.file_sha256(attempt / "raw-attempt-manifest.json"),
                "raw_total_bytes": total,
                "raw_file_count": len(files),
                "condition_retry_permitted": False,
            },
        )
        host.validate_raw_attempt_seal(
            attempt_root=attempt, raw_root=raw, run_id=run_id, package_commit=args.package_commit
        )
        return exit_code

    monkeypatch.setattr(host, "execute_condition", execute)
    host.condition_session(args)
    assert len(calls) == 1
    assert calls[0]["answer"] == answer
    assert calls[0]["exit_code"] == exit_code
    assert calls[0]["completed"] is (answer is not None)


@pytest.mark.parametrize(
    "mutation", ["none", "bytes", "same-size", "replacement", "parent", "symlink", "missing-owner"]
)
def test_retained_source_archive_cleanup_preserves_exact_ownership(
    terminal_host, tmp_path, mutation
):
    import hashlib

    from giclab.harness.t09_cleanup_state import EarlyCleanupJournal
    from giclab.harness.t09_remote_host_phases import PhaseFile

    host = terminal_host
    root = tmp_path.resolve()
    remote = root / "remote"
    remote.mkdir(mode=0o700)
    archive = remote / "source-package.tar"
    content = b"retained transferred source fixture\n"
    archive.write_bytes(content)
    archive.chmod(0o600)
    journal = EarlyCleanupJournal.initialize(
        root / "journal",
        plan_id=V16_PROVIDER_CONTRACT.plan_id,
        host_run_id=V16_PROVIDER_CONTRACT.host_run_id,
        package_commit="a" * 40,
        plan_sha256="b" * 64,
        provider_instance_id="offline-instance",
        provider_instance_identity_sha256="c" * 64,
        provider_started_at_epoch=1.0,
        launch_slot=1,
        replacement_eligibility_sha256=None,
        firewall_baseline_identity_sha256="d" * 64,
    )
    request = SimpleNamespace(
        inputs={
            "remote_archive": PhaseFile(archive, len(content), hashlib.sha256(content).hexdigest())
        },
        binding=SimpleNamespace(local_assembly_receipt_sha256="e" * 64),
    )
    host._register_source_archive_cleanup(journal, request)
    if mutation == "bytes":
        archive.write_bytes(content + b"changed")
    elif mutation == "same-size":
        archive.write_bytes(b"X" + content[1:])
    elif mutation == "replacement":
        archive.rename(remote / "original.tar")
        archive.write_bytes(content)
        archive.chmod(0o600)
    elif mutation == "parent":
        remote.rename(root / "original-remote")
        remote.mkdir(mode=0o700)
        archive.write_bytes(content)
        archive.chmod(0o600)
    elif mutation == "symlink":
        archive.rename(remote / "original.tar")
        archive.symlink_to(remote / "original.tar")
    elif mutation == "missing-owner":
        (journal.root / "source-archive-ownership.json").unlink()
    if mutation != "none":
        with pytest.raises((host.T09HostError, OSError)):
            host._cleanup_registered_source_archive(journal)
        assert archive.exists()
    else:
        host._cleanup_registered_source_archive(journal)
        assert not archive.exists()
        version = journal.latest_version_sha256()
        host._cleanup_registered_source_archive(journal)
        assert journal.latest_version_sha256() == version


@pytest.mark.parametrize("replacement", ["symlink", "broad-parent", "oversized"])
def test_restored_state_rejects_unsafe_destination(terminal_host, tmp_path, replacement):
    import os

    parent = tmp_path / "private"
    parent.mkdir(mode=0o700)
    target = parent / "state.json"
    outside = tmp_path / "unrelated.json"
    outside.write_bytes(b"unchanged")
    document = {"state": "retained"}
    if replacement == "symlink":
        target.symlink_to(outside)
    elif replacement == "broad-parent":
        parent.chmod(0o755)
    else:
        document["state"] = "x" * terminal_host.MAX_PRIVACY_JSON_BYTES
    with pytest.raises(terminal_host.T09HostError):
        terminal_host._replace_restored_state(target, document)
    assert outside.read_bytes() == b"unchanged"
    assert not target.exists() or target.is_symlink()
    assert not tuple(parent.glob("*.restore.tmp"))
    assert os.path.lexists(outside)


def test_restored_state_uses_private_atomic_destination(terminal_host, tmp_path):
    import stat

    parent = tmp_path / "private"
    parent.mkdir(mode=0o700)
    target = parent / "state.json"
    terminal_host._replace_restored_state(target, {"state": "first"})
    terminal_host._replace_restored_state(target, {"state": "second"})
    assert json.loads(target.read_bytes()) == {"state": "second"}
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    assert not tuple(parent.glob("*.restore.tmp"))


def test_restoration_creates_private_intermediate_directories(terminal_host, tmp_path):
    import stat

    root = tmp_path / "restored"
    root.mkdir(mode=0o700)
    target = root / "pilot/runtime-budget/state.json"
    terminal_host._prepare_restoration_parent(root, target)
    terminal_host._replace_restored_state(target, {"state": "retained"})
    assert all(
        stat.S_IMODE(path.stat().st_mode) == 0o700
        for path in target.parents
        if path.is_relative_to(root)
    )
    unrelated = tmp_path / "unrelated"
    unrelated.mkdir(mode=0o700)
    (root / "alias").symlink_to(unrelated, target_is_directory=True)
    with pytest.raises(OSError):
        terminal_host._prepare_restoration_parent(root, root / "alias/never/file.json")
    assert list(unrelated.iterdir()) == []
    with pytest.raises(terminal_host.T09HostError, match="escaped"):
        terminal_host._prepare_restoration_parent(root, unrelated / "file.json")


@pytest.mark.parametrize("answer", ["retained partial answer", None])
@pytest.mark.parametrize("exit_code", [0, 9])
def test_retained_essential_terminal_uses_sealed_process_and_session(
    tmp_path, monkeypatch, answer, exit_code
):
    # Reuse only the existing source-fixture builder; seal/terminal validation run.
    spec = importlib.util.spec_from_file_location(
        "retained_failure_sources", ROOT / "tests/test_t09_retry5.py"
    )
    assert spec and spec.loader
    sources = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sources)
    host = sources._host("t09_essential_terminal_component")
    contract = sources.V8_PROVIDER_CONTRACT
    run_id = contract.run_ids[0]
    artifact = tmp_path / "artifacts"
    attempt = artifact / "artifacts/EXP-0001/pilot-v7/task-a/reactive/attempt-0005"
    raw = attempt / "raw"
    raw.mkdir(parents=True, mode=0o700)
    sources.initialize_pilot_state(
        artifact / "pilot-v7/pilot-state.json",
        provider_contract=contract,
        execution_contract_sha256="1" * 64,
        pilot_started_at_epoch=1.0,
        lambda_started_at_epoch=1.0,
    )
    sources._write_json(
        artifact / "pilot-v7/frozen-run-manifest.json",
        {"replacement_image_id": "sha256:" + "a" * 64},
    )
    manifest = {
        "run_id": run_id,
        "pair_id": "PAIR-EXP0001-PILOT-V7-TASK-A",
        "task_id": "7dcbbbdc7f1120cd",
        "condition": "reactive",
        "condition_plan_sha256": "2" * 64,
        "argv_sha256": "3" * 64,
        "permitted_condition_owned": {
            "output_root": attempt.relative_to(artifact).as_posix(),
            "raw_output_root": raw.relative_to(artifact).as_posix(),
        },
    }
    sources._write_terminal_failure_sources(
        host,
        artifact_root=artifact,
        raw_root=raw,
        run_id=run_id,
        contract_sha256="1" * 64,
        frozen_run_manifest_sha256="5" * 64,
        condition_plan_sha256="2" * 64,
        condition_argv_sha256="3" * 64,
        empirical_entry_crossed=True,
        returncode=exit_code,
        stop_reason="synthetic-infrastructure-stop",
        hard_cap_breached=False,
        tree_bytes_before_security_cleanup=0,
        tree_bytes_after_core_cleanup=0,
        core_records=[],
        core_destruction_verified=True,
    )
    session = {
        "history": [[{}, f"send_msg_to_user({answer!r})" if answer is not None else "noop()", {}]],
        "is_complete": answer is not None,
        "error": "",
        "goal": "fixture",
    }
    sources._write_json(raw / "sira-output/session.json", session)
    host.seal_essential_failure(
        artifact_root=artifact,
        attempt_root=attempt,
        raw_root=raw,
        manifest=manifest,
        package_commit="4" * 40,
        frozen_run_manifest_sha256="5" * 64,
        execution_contract_sha256="1" * 64,
        returncode=exit_code,
        stop_reason="synthetic-infrastructure-stop",
        hard_cap_breached=False,
        tree_bytes_before_security_cleanup=0,
        core_records=[],
        core_destruction_verified=True,
        empirical_entry_crossed=True,
    )
    before = {
        p.relative_to(attempt).as_posix(): host.file_sha256(p)
        for p in (attempt / "essential-failure").rglob("*")
        if p.is_file()
    }
    result = host.retained_essential_condition_completion(
        attempt_root=attempt, run_id=run_id, package_commit="4" * 40, condition_manifest=manifest
    )
    assert result["process_exit_code"] == exit_code
    assert result["completed"] is (answer is not None)
    assert result["answer"] == answer
    assert result["infrastructure_invalid"] is True
    assert result["evaluator_eligible"] is False
    assert all(host.file_sha256(attempt / name) == digest for name, digest in before.items())
    retained = attempt / "essential-failure/sira-output/session.json"
    assert retained.is_file()
    encoded = retained.read_bytes()
    retained.chmod(0o600)
    retained.write_bytes(encoded.replace(b"fixture", b"changed"))
    with pytest.raises(host.T09HostError):
        host.retained_essential_condition_completion(
            attempt_root=attempt,
            run_id=run_id,
            package_commit="4" * 40,
            condition_manifest=manifest,
        )


@pytest.mark.parametrize(
    "mutation",
    [None, "same-size-source", "same-size-payload", "wrong-size", "extra-member", "symlink"],
)
def test_retained_failure_export_copies_bound_bytes(terminal_host, tmp_path, mutation):
    """The local carrier must copy and reread bytes before its acknowledgement exists."""
    from dataclasses import replace

    from giclab.control.effects import ConditionFailureExportRequest

    host = terminal_host
    root = tmp_path / "transaction"
    root.mkdir(mode=0o700)
    source = root / "essential-failure"
    payload = source / "payload"
    source.mkdir(mode=0o700)
    payload.mkdir(mode=0o700)
    documents = {
        source / "essential-failure-manifest.json": {"test_input": "explicit envelope source"},
        source / "essential-failure-complete.json": {"test_input": "separately bound receipt"},
        payload / "source.json": {"answer": "partial retained answer", "exit_code": 9},
    }
    for path, document in documents.items():
        host.write_bytes_exclusive(path, host._failure_canonical_bytes(document))
    manifest_path = source / "essential-failure-manifest.json"
    manifest_path.write_bytes(
        host._failure_canonical_bytes(
            {
                "files": [
                    {
                        "path": "payload/source.json",
                        "bytes": (payload / "source.json").stat().st_size,
                        "sha256": host.file_sha256(payload / "source.json"),
                    }
                ],
                "payload_file_count": 1,
                "payload_total_bytes": (payload / "source.json").stat().st_size,
            }
        )
    )
    request = ConditionFailureExportRequest(
        run_id=V16_PROVIDER_CONTRACT.run_ids[0],
        essential_root=source,
        essential_manifest_path=source / "essential-failure-manifest.json",
        essential_receipt_path=source / "essential-failure-complete.json",
        essential_manifest_sha256=host.file_sha256(source / "essential-failure-manifest.json"),
        essential_receipt_sha256=host.file_sha256(source / "essential-failure-complete.json"),
        essential_file_count=3,
        essential_total_bytes=sum(path.stat().st_size for path in documents),
        export_identity="b" * 64,
    )
    if mutation == "same-size-source":
        path = request.essential_manifest_path
        path.write_bytes(path.read_bytes().replace(b"payload/source", b"payload/forged"))
    elif mutation == "same-size-payload":
        path = payload / "source.json"
        path.write_bytes(path.read_bytes().replace(b"partial", b"changed"))
    elif mutation == "wrong-size":
        request = replace(request, essential_total_bytes=request.essential_total_bytes + 1)
    elif mutation == "extra-member":
        host.write_bytes_exclusive(payload / "unexpected.json", b"{}\n")
    elif mutation == "symlink":
        (payload / "alias.json").symlink_to("source.json")
    if mutation is not None:
        with pytest.raises((ValueError, host.T09HostError)):
            host.export_retained_condition_failure_projection(request, transaction_root=root)
        assert not (source / "export-acknowledgement.json").exists()
        assert not (root / "failure-exports").exists()
        return
    receipt = host.export_retained_condition_failure_projection(request, transaction_root=root)
    destination = root / "failure-exports" / request.export_identity
    assert {path.relative_to(destination) for path in destination.rglob("*") if path.is_file()} == {
        path.relative_to(source) for path in documents
    }
    for path in documents:
        assert (destination / path.relative_to(source)).read_bytes() == path.read_bytes()
    assert receipt.export_complete and not receipt.resumed
    assert receipt.essential_file_count == 4
    assert (
        receipt.essential_total_bytes
        == sum(path.stat().st_size for path in documents) + receipt.acknowledgement_bytes
    )
    # Idempotent verification retains one acknowledgement and one exact destination.
    assert (
        host.export_retained_condition_failure_projection(request, transaction_root=root) == receipt
    )
    copied = destination / "payload/source.json"
    copied.chmod(0o600)
    copied.write_bytes(copied.read_bytes().replace(b"partial", b"changed"))
    with pytest.raises(host.T09HostError, match="changed bytes"):
        host.export_retained_condition_failure_projection(request, transaction_root=root)


def test_retained_export_ack_uses_one_bound_observation_clock(terminal_host, tmp_path):
    host = terminal_host
    contract = V16_PROVIDER_CONTRACT
    run_id = contract.run_ids[0]
    observed = host.time.time() + 86400
    archive = tmp_path / (run_id + ".tar.gz")
    archive.write_bytes(b"explicit local acknowledgement-consumer input")
    source = {
        "schema_version": "0.1.0",
        "plan_id": contract.plan_id,
        "host_run_id": contract.host_run_id,
        "run_id": run_id,
        "package_commit": "a" * 40,
        "archive_bytes": archive.stat().st_size,
        "archive_sha256": host.file_sha256(archive),
        "manifest_sha256": "b" * 64,
        "frozen_run_manifest_sha256": "c" * 64,
        "replacement_image_id": "sha256:" + "d" * 64,
        "provider_entry_receipt_sha256": "e" * 64,
        "owned_instance_identity_sha256": "f" * 64,
        "lambda_started_at_epoch": observed - 20,
        "export_completed_at_epoch": observed - 10,
    }
    assert set(source) == host._ATTEMPT_EXPORT_COMPLETION_KEYS
    completion_sha = host.hashlib.sha256(host._failure_canonical_bytes(source)).hexdigest()
    acknowledgement = {
        **source,
        "archive_path": archive.name,
        "evidence_authority": "immutable-raw-attempt",
        "empirical_entry_crossed": True,
        "export_completion_receipt_sha256": completion_sha,
        "verified_at_epoch": observed - 5,
        "maximum_cross_host_clock_skew_seconds": host.EVIDENCE_CHRONOLOGY_CLOCK_SKEW_SECONDS,
    }
    args = {
        "acknowledgement": acknowledgement,
        "acknowledgement_sha256": "0" * 64,
        "completion": source,
        "completion_sha256": completion_sha,
        "run_id": run_id,
        "package_commit": source["package_commit"],
        "evidence_authority": "immutable-raw-attempt",
        "empirical_entry_crossed": True,
        "frozen_run_manifest_sha256": source["frozen_run_manifest_sha256"],
        "replacement_image_id": source["replacement_image_id"],
        "provider_entry_receipt_sha256": source["provider_entry_receipt_sha256"],
        "owned_instance_identity_sha256": source["owned_instance_identity_sha256"],
        "lambda_started_at_epoch": source["lambda_started_at_epoch"],
        "archive": archive,
        "contract": contract,
    }
    # The normal default still rejects an acknowledgement ahead of the real clock.
    with pytest.raises(host.T09HostError, match="exact off-host"):
        host._validate_attempt_export_acknowledgement(**args)
    receipt = host._validate_attempt_export_acknowledgement(**args, clock=lambda: observed)
    assert receipt["verified_at_epoch"] == acknowledgement["verified_at_epoch"]
    for clock in (lambda: observed - 86400, lambda: float("nan")):
        with pytest.raises(host.T09HostError):
            host._validate_attempt_export_acknowledgement(**args, clock=clock)
    changed = {
        **acknowledgement,
        "verified_at_epoch": observed + host.EVIDENCE_CHRONOLOGY_CLOCK_SKEW_SECONDS + 1,
    }
    with pytest.raises(host.T09HostError, match="exact off-host"):
        host._validate_attempt_export_acknowledgement(
            **{**args, "acknowledgement": changed}, clock=lambda: observed
        )
    archive.write_bytes(archive.read_bytes().replace(b"explicit", b"corrupt!"))
    with pytest.raises(host.T09HostError, match="archive drifted"):
        host._validate_attempt_export_acknowledgement(**args, clock=lambda: observed)


@pytest.mark.parametrize("answer", ["fixture answer one", "fixture answer two", None])
@pytest.mark.parametrize("mutation", [None, "answer", "source", "extra", "process"])
def test_retained_control_projection_preserves_raw_and_rejects_drift(
    terminal_host, tmp_path, answer, mutation
):
    """Component fixture supplies source inputs; real seal/normalizer checks execute."""
    host = terminal_host
    run_id = V16_PROVIDER_CONTRACT.run_ids[0]
    commit = "a" * 40
    raw = tmp_path / "raw"
    session = raw / "sira-output/session.json"
    session.parent.mkdir(parents=True)
    host.write_exclusive(
        session,
        {
            "history": [
                [{}, f"send_msg_to_user({answer!r})" if answer is not None else "noop()", {}]
            ],
            "is_complete": answer is not None,
            "error": "",
            "goal": "component fixture",
        },
    )
    host.write_exclusive(raw / "host-cleanup-receipt.json", {"returncode": 0})
    host.write_exclusive(raw / "duplex-remote-event-journal.json", {"frames": []})
    host.write_exclusive(
        raw / "provider-call-lifecycle.json", {"authoritative": False, "calls": {}}
    )
    files, total = host._raw_attempt_files(raw)
    host.write_exclusive(
        tmp_path / "raw-attempt-manifest.json",
        {
            "schema_version": "0.1.0",
            "plan_id": V16_PROVIDER_CONTRACT.plan_id,
            "host_run_id": V16_PROVIDER_CONTRACT.host_run_id,
            "run_id": run_id,
            "package_commit": commit,
            "raw_attempt_root": "raw",
            "files": files,
            "total_bytes": total,
        },
    )
    host.write_exclusive(
        tmp_path / "raw-attempt-complete.json",
        {
            "schema_version": "0.1.0",
            "plan_id": V16_PROVIDER_CONTRACT.plan_id,
            "host_run_id": V16_PROVIDER_CONTRACT.host_run_id,
            "run_id": run_id,
            "raw_attempt_complete": True,
            "empirical_attempt_consumed": True,
            "raw_manifest_sha256": host.file_sha256(tmp_path / "raw-attempt-manifest.json"),
            "raw_total_bytes": total,
            "raw_file_count": len(files),
            "condition_retry_permitted": False,
        },
    )
    before = {p.relative_to(raw).as_posix(): p.read_bytes() for p in raw.rglob("*") if p.is_file()}
    args = dict(
        attempt_root=tmp_path,
        run_id=run_id,
        package_commit=commit,
        exit_code=0,
        process_expectations={"run_id": run_id, "retry_count": 0},
    )
    manifest = host.retained_control_projection(**args, publish=True)
    projection = manifest.parent
    assert json.loads((projection / "completion.json").read_bytes())["answer"] == answer
    assert before == {
        p.relative_to(raw).as_posix(): p.read_bytes() for p in raw.rglob("*") if p.is_file()
    }
    if mutation == "answer":
        p = projection / "completion.json"
        value = json.loads(p.read_bytes())
        value["answer"] = "forged"
        p.write_text(json.dumps(value))
    elif mutation == "source":
        session.write_bytes(
            session.read_bytes().replace(b"component fixture", b"component altered")
        )
    elif mutation == "extra":
        (projection / "unexpected.json").write_text("{}")
    elif mutation == "process":
        args["process_expectations"] = {"run_id": run_id, "retry_count": 1}
    if mutation is not None:
        with pytest.raises(host.T09HostError):
            host.retained_control_projection(**args, publish=False)
    else:
        assert host.retained_control_projection(**args, publish=False) == manifest
