"""Explicit input binding tests; none of these proves live qualification."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from giclab.harness.t09_qualification_fixture import (
    GENERATOR_PATH,
    build_deterministic_qualification_archive,
    load_deterministic_qualification_archive,
)

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def host():
    name = "t09_offline_qualification_host"
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


def test_two_fresh_fixture_builds_are_byte_exact(tmp_path):
    first_root, second_root = tmp_path / "one", tmp_path / "two"
    first_root.mkdir()
    second_root.mkdir()
    first = build_deterministic_qualification_archive(ROOT, first_root)
    second = build_deterministic_qualification_archive(ROOT, second_root)
    assert first.archive_path.read_bytes() == second.archive_path.read_bytes()
    assert first.document() == second.document()
    assert first.members == second.members
    assert first.bytes < 10_000
    assert first.bytes != 3_439_137
    assert first.sha256 != "63ed19b35bcb4cb62c3796a80a48004937340eb3826f9657a1006e251772255d"
    assert first.document()["generator_path"] == GENERATOR_PATH


def test_retained_staging_copies_exact_bound_fixture(host, tmp_path):
    binding = build_deterministic_qualification_archive(ROOT, tmp_path)
    receipt, staged = host.stage_qualification_archive(
        repository=ROOT, source=binding.archive_path, fixture_binding=binding
    )
    assert staged.read_bytes() == binding.archive_path.read_bytes()
    assert receipt["bytes"] == binding.bytes
    assert receipt["sha256"] == binding.sha256
    assert receipt["archive_role"] == "deterministic-test-qualification"
    assert receipt["fixture_binding"] == binding.document()
    assert receipt["source_unchanged"] is True
    binding.validate(ROOT, archive_path=staged)


@pytest.mark.parametrize(
    "mutation", ["same-size", "one-byte", "wrong-size", "wrong-member", "wrong-binding"]
)
def test_fixture_mutation_fails_before_publication(host, tmp_path, mutation):
    binding = build_deterministic_qualification_archive(ROOT, tmp_path)
    value = binding.archive_path.read_bytes()
    if mutation == "same-size":
        binding.archive_path.write_bytes(b"x" * len(value))
    elif mutation == "one-byte":
        binding.archive_path.write_bytes(bytes([value[0] ^ 1]) + value[1:])
    elif mutation == "wrong-size":
        binding = replace(binding, bytes=binding.bytes + 1)
    elif mutation == "wrong-member":
        binding = replace(
            binding, members=(replace(binding.members[0], sha256="0" * 64), *binding.members[1:])
        )
    else:
        binding = replace(binding, fixture_id="UNTRUSTED-FIXTURE")
    with pytest.raises(ValueError, match="fixture"):
        host.stage_qualification_archive(
            repository=ROOT, source=binding.archive_path, fixture_binding=binding
        )
    assert not (tmp_path / "staged-offline-qualification-fixture.tar.gz").exists()


def test_historical_selector_cannot_fall_back_to_fixture(host, tmp_path, monkeypatch):
    binding = build_deterministic_qualification_archive(ROOT, tmp_path)
    monkeypatch.setenv("GICLAB_TEST_FIXTURE", str(binding.archive_path))
    monkeypatch.setenv("DETERMINISTIC_FIXTURE", "true")
    with pytest.raises(host.T09HostError, match="archive staging source size drifted"):
        host.stage_qualification_archive(repository=ROOT, source=binding.archive_path)
    assert host.PRIVATE_REGRESSION_ARCHIVE_BYTES == 3_439_137
    assert (
        host.PRIVATE_REGRESSION_ARCHIVE_SHA256
        == "63ed19b35bcb4cb62c3796a80a48004937340eb3826f9657a1006e251772255d"
    )


def test_staging_short_circuit_cannot_supply_a_fixture_success(host, tmp_path, monkeypatch):
    binding = build_deterministic_qualification_archive(ROOT, tmp_path)
    monkeypatch.setattr(
        host,
        "stage_verified_archive",
        lambda *args, **kwargs: {"bytes": binding.bytes, "sha256": binding.sha256},
    )
    with pytest.raises(FileNotFoundError):
        host.stage_qualification_archive(
            repository=ROOT, source=binding.archive_path, fixture_binding=binding
        )


def test_fixture_uses_retained_extraction_and_semantic_validation(host, tmp_path):
    binding = build_deterministic_qualification_archive(ROOT, tmp_path)
    staging, archive = host.stage_qualification_archive(
        repository=ROOT,
        source=binding.archive_path,
        fixture_binding=binding,
    )
    source = ROOT / "containers/sira-smoke/pragmatic/t09_real_evidence_regression.py"
    spec = importlib.util.spec_from_file_location("offline_retained_regression", source)
    assert spec and spec.loader
    regression = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(regression)
    finalizer = ROOT / "containers/sira-smoke/pragmatic/t09_evaluate_attempt.py"
    args = argparse.Namespace(
        archive=archive,
        public_disposition=tmp_path / "not-historical",
        finalizer_source=finalizer,
        finalizer_source_sha256=hashlib.sha256(finalizer.read_bytes()).hexdigest(),
        dataset=ROOT / "tests/fixtures/t09/fanout-two-task-fixture.json",
        evaluator_root=ROOT / "tests/fixtures/t09/pinned-evaluator",
        output=tmp_path / "fixture-regression.json",
    )
    result = regression.run(args, fixture_binding=binding, fixture_repository=ROOT)
    assert result["fixture_binding"] == staging["fixture_binding"]
    assert result["semantic_projection"]["provider_call_count"] == 1
    assert result["semantic_projection"]["score"] == 0.0
    assert result["historical_replay"] is False
    assert result["live_qualification"] is False
    assert args.output.is_file()
    with pytest.raises(FileNotFoundError):
        regression.run(args)  # Normal consumer still requires historical evidence.


def test_retained_qualification_consumes_real_staging_and_fixture_regression(
    host,
    tmp_path,
    monkeypatch,
):
    from giclab.harness.t09_provider_contracts import V16_PROVIDER_CONTRACT

    binding = build_deterministic_qualification_archive(ROOT, tmp_path)
    staging, archive = host.stage_qualification_archive(
        repository=ROOT,
        source=binding.archive_path,
        fixture_binding=binding,
    )
    source = ROOT / "containers/sira-smoke/pragmatic/t09_real_evidence_regression.py"
    spec = importlib.util.spec_from_file_location(
        "offline_retained_qualification_regression", source
    )
    assert spec and spec.loader
    regression = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(regression)
    invocations = []

    def container_executor(command, **kwargs):
        assert command[:2] == ["fixture-container", "run"]
        assert command[command.index("--network") + 1] == "none"
        assert kwargs["label"] == "qualified-real-regression"
        invocations.append(tuple(command))
        finalizer = ROOT / "containers/sira-smoke/pragmatic/t09_evaluate_attempt.py"
        arguments = argparse.Namespace(
            archive=archive,
            public_disposition=tmp_path / "no-historical-input",
            finalizer_source=finalizer,
            finalizer_source_sha256=hashlib.sha256(finalizer.read_bytes()).hexdigest(),
            dataset=ROOT / "tests/fixtures/t09/fanout-two-task-fixture.json",
            evaluator_root=ROOT / "tests/fixtures/t09/pinned-evaluator",
            output=kwargs["evidence_root"] / "receipt.json",
        )
        regression.run(arguments, fixture_binding=binding, fixture_repository=ROOT)

    monkeypatch.setattr(host, "run_logged", container_executor)
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    from giclab.harness.t09_sira_pilot import initialize_pilot_state

    initialize_pilot_state(
        artifacts / V16_PROVIDER_CONTRACT.control_root_name / "pilot-state.json",
        provider_contract=V16_PROVIDER_CONTRACT,
        execution_contract_sha256="a" * 64,
        pilot_started_at_epoch=1_900_000_000.0,
        lambda_started_at_epoch=1_900_000_000.0,
    )
    # These dependencies are passed to the environmental executor; they are not
    # fake phase, staging or semantic receipts.
    receipt = host.qualified_real_evidence_regression(
        repository=ROOT,
        artifact_root=artifacts,
        archive=archive,
        overlay=tmp_path,
        prefix=["fixture-container"],
        image_id="sha256:" + "d" * 64,
        image_files={},
        static_receipt={},
        cleanup_journal=None,
        contract=V16_PROVIDER_CONTRACT,
        fixture_binding=binding,
    )
    assert len(invocations) == 1
    assert receipt["fixture_binding"] == staging["fixture_binding"]
    assert receipt["source_archive_sha256"] == binding.sha256
    assert receipt["semantic_projection"]["score"] == 0.0


@pytest.mark.parametrize("mutation", [None, "same-size", "missing", "symlink"])
def test_later_phase_reopens_exact_archive_without_rebuilding(host, tmp_path, mutation):
    binding = build_deterministic_qualification_archive(ROOT, tmp_path)
    receipt, staged = host.stage_qualification_archive(
        repository=ROOT, source=binding.archive_path, fixture_binding=binding
    )
    before = staged.read_bytes()
    if mutation == "same-size":
        binding.archive_path.write_bytes(b"x" * binding.bytes)
    elif mutation == "missing":
        binding.archive_path.unlink()
    elif mutation == "symlink":
        binding.archive_path.unlink()
        binding.archive_path.symlink_to(staged)
    if mutation:
        with pytest.raises((ValueError, FileNotFoundError)):
            load_deterministic_qualification_archive(ROOT, binding.archive_path)
        assert staged.read_bytes() == before
        assert binding.archive_path.is_symlink() == (mutation == "symlink")
        assert binding.archive_path.exists() == (mutation != "missing")
    else:
        reopened = load_deterministic_qualification_archive(ROOT, binding.archive_path)
        assert reopened == binding
        reopened.validate(ROOT, archive_path=staged)
        assert receipt["fixture_binding"] == reopened.document()
        assert staged.read_bytes() == before
