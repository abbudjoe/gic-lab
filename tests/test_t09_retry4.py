from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import time
from pathlib import Path

import pytest
import yaml

from giclab.harness.lambda_campaign_lifecycle import Retry4LifecycleLimits
from giclab.harness.t09_pragmatic_provider import (
    CampaignLifecycle,
    T09ProviderError,
    validate_slot2_launch_headroom,
)
from giclab.validation import validate_instance

ROOT = Path(__file__).resolve().parents[1]
HOST_SOURCE = ROOT / "containers/sira-smoke/pragmatic/t09_remote_runner.py"
EXPERIMENT_ROOT = ROOT / "experiments/EXP-0001-sira-simulative-vs-reactive"


def test_retry4_preserves_retry3_terminal_and_frozen_package_bytes() -> None:
    expected = {
        "T09_PRAGMATIC_RETRY3_DISPOSITION.json": (
            "ac116f903701daf3a0497b663b125505c1097a96e38f308126a9df0adf6896db"
        ),
        "T09_PRAGMATIC_RETRY3_TERMINAL_CONTROL.json": (
            "aaebe8bd1bb536adc75b117529e0c4b5d88391eb17aab844c64092348bd239cf"
        ),
        "run-plans/proposals/PLAN-EXP0001-PILOT-V5.yaml": (
            "e7e214500348c8b876beb034df7b592c84f5ab79788ab6f310ef187fd797613c"
        ),
        "contracts/proposals/T09_PILOT_RUNTIME_IDENTITY_V5.json": (
            "eb5e43590a7e375b9aaacf9af723c738371cd09ef1ea7be57901b815c93bf124"
        ),
        "contracts/proposals/T09_PILOT_EXECUTION_CONTRACT_V5.json": (
            "0e67e37cd3869be0d4226b134861fc174db2cec315bb86e0ea0a13a8675cc589"
        ),
        "contracts/proposals/T09_PILOT_COMMAND_MANIFESTS_V5.json": (
            "a967d21b83d1c93f5289ce30dc0c77f4974af8e3bdfc478295e30f2f05a9eb68"
        ),
    }
    assert {relative: host_hash(EXPERIMENT_ROOT / relative) for relative in expected} == expected


def test_retry4_plan_is_typed_science_locked_and_uses_fresh_identities() -> None:
    active_path = EXPERIMENT_ROOT / "run-plans/pilot.yaml"
    prior_path = EXPERIMENT_ROOT / "run-plans/proposals/PLAN-EXP0001-PILOT-V5.yaml"
    active = yaml.safe_load(active_path.read_bytes())
    prior = yaml.safe_load(prior_path.read_bytes())
    assert validate_instance(active, ROOT / "schemas/run-profile.schema.json") == []
    assert host_hash(prior_path) == (
        "e7e214500348c8b876beb034df7b592c84f5ab79788ab6f310ef187fd797613c"
    )
    assert active["plan_id"] == "PLAN-EXP0001-PILOT-V6"
    assert prior["plan_id"] == "PLAN-EXP0001-PILOT-V5"
    assert active["experiment_id"] == prior["experiment_id"] == "EXP-0001"
    assert active["model"] == prior["model"]
    for key in (
        "pair_count",
        "conditions",
        "task_family",
        "dataset_ids",
    ):
        assert active["sampling"][key] == prior["sampling"][key]
    for active_pair, prior_pair in zip(
        active["sampling"]["counterbalancing"],
        prior["sampling"]["counterbalancing"],
        strict=True,
    ):
        for key in ("task_id", "task_source", "first", "second"):
            assert active_pair[key] == prior_pair[key]
    for key in (
        "source_plan_id",
        "attempt_run_id",
        "archive_sha256",
        "public_disposition_sha256",
    ):
        assert active["historical_fixture"][key] == prior["historical_fixture"][key]
    assert active["budget"]["max_model_calls"] == prior["budget"]["max_model_calls"]
    assert active["budget"]["max_model_tokens"] == prior["budget"]["max_model_tokens"]
    assert active["budget"]["max_browser_actions"] == prior["budget"]["max_browser_actions"]
    assert active["budget"]["condition_limits"] == prior["budget"]["condition_limits"]

    v5_identifiers = {
        "PLAN-EXP0001-PILOT-V5",
        "RUN-T09-PILOT-HOST-0003",
        "QUAL-T09-PILOT-V5-IMAGE-0001",
        "QUAL-T09-PILOT-V5-IMAGE-0002",
        "RUN-T09-TASK-A-REACTIVE-0003",
        "RUN-T09-TASK-A-SIMULATIVE-0003",
        "RUN-T09-TASK-B-SIMULATIVE-0003",
        "RUN-T09-TASK-B-REACTIVE-0003",
    }
    assert not any(
        identifier in active_path.read_text(encoding="utf-8") for identifier in v5_identifiers
    )
    assert host_hash(EXPERIMENT_ROOT / "protocol.yaml") == (
        "5356fc8b3806f4135eb570f65b67da2f94463582db5e3e609320e23dbdb2a3f7"
    )
    assert host_hash(EXPERIMENT_ROOT / "config.yaml") == (
        "cf25acd90f9d73d9aef978a7d059cfbc74a1447d901f4e3d27e2b5d9f121d2ed"
    )


def host_hash(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_host(name: str) -> object:
    specification = importlib.util.spec_from_file_location(name, HOST_SOURCE)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def test_retry4_archive_staging_is_content_addressed_and_source_path_independent(
    tmp_path: Path,
) -> None:
    host = _load_host("giclab_t09_retry4_archive_staging")
    payload = b"private-regression-fixture\n" * 17
    expected = host.hashlib.sha256(payload).hexdigest()
    source_a = tmp_path / "incoming-a/archive.tar.gz"
    source_b = tmp_path / "incoming-b/different-name.bin"
    source_a.parent.mkdir()
    source_b.parent.mkdir()
    source_a.write_bytes(payload)
    source_b.write_bytes(payload)
    target = tmp_path / "canonical/regression.tar.gz"
    target.parent.mkdir()

    source_a_before = (source_a.read_bytes(), source_a.stat().st_mode, source_a.stat().st_mtime_ns)
    receipt_a = host.stage_verified_archive(source_a, target, len(payload), expected)
    assert target.read_bytes() == payload
    target.unlink()
    receipt_b = host.stage_verified_archive(source_b, target, len(payload), expected)

    assert receipt_a == receipt_b
    assert str(source_a) not in repr(receipt_a)
    assert str(source_b) not in repr(receipt_b)
    assert receipt_a["source_absolute_path_retained"] is False
    assert receipt_a["target_rehash_verified"] is True
    assert source_a_before == (
        source_a.read_bytes(),
        source_a.stat().st_mode,
        source_a.stat().st_mtime_ns,
    )


def test_retry4_archive_staging_rejects_bad_input_and_existing_target(
    tmp_path: Path,
) -> None:
    host = _load_host("giclab_t09_retry4_archive_rejections")
    source = tmp_path / "source.bin"
    source.write_bytes(b"accepted")
    expected = host.hashlib.sha256(b"accepted").hexdigest()
    target = tmp_path / "target.bin"

    with pytest.raises(host.T09HostError, match="size"):
        host.stage_verified_archive(source, target, 7, expected)
    with pytest.raises(host.T09HostError, match="hash"):
        host.stage_verified_archive(source, target, 8, "0" * 64)
    target.write_bytes(b"do-not-overwrite")
    with pytest.raises(FileExistsError):
        host.stage_verified_archive(source, target, 8, expected)
    assert target.read_bytes() == b"do-not-overwrite"


def test_retry4_archive_staging_rejects_symlink_and_special_file(tmp_path: Path) -> None:
    host = _load_host("giclab_t09_retry4_archive_metadata")
    source = tmp_path / "source.bin"
    source.write_bytes(b"accepted")
    expected = host.hashlib.sha256(b"accepted").hexdigest()
    symlink = tmp_path / "source-link.bin"
    symlink.symlink_to(source)
    with pytest.raises(OSError):
        host.stage_verified_archive(symlink, tmp_path / "target-link.bin", 8, expected)

    fifo = tmp_path / "source.fifo"
    os.mkfifo(fifo, 0o600)
    with pytest.raises(host.T09HostError, match="regular file"):
        host.stage_verified_archive(fifo, tmp_path / "target-fifo.bin", 8, expected)


def test_retry4_archive_staging_rehashes_target_and_removes_bad_copy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    host = _load_host("giclab_t09_retry4_archive_rehash")
    payload = b"accepted"
    source = tmp_path / "source.bin"
    source.write_bytes(payload)
    target = tmp_path / "target.bin"

    def corrupt_copy(_source: int, destination: int) -> int:
        return os.write(destination, b"rejected")

    monkeypatch.setattr(host, "_copy_descriptor_exact", corrupt_copy)
    with pytest.raises(host.T09HostError, match="target revalidation"):
        host.stage_verified_archive(
            source,
            target,
            len(payload),
            host.hashlib.sha256(payload).hexdigest(),
        )
    assert not target.exists()
    assert source.read_bytes() == payload


def test_retry4_archive_staging_fsyncs_file_and_parent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    host = _load_host("giclab_t09_retry4_archive_fsync")
    payload = b"accepted"
    source = tmp_path / "source.bin"
    target = tmp_path / "target.bin"
    source.write_bytes(payload)
    observed: list[int] = []
    original = host.os.fsync

    def recording_fsync(descriptor: int) -> None:
        observed.append(descriptor)
        original(descriptor)

    monkeypatch.setattr(host.os, "fsync", recording_fsync)
    host.stage_verified_archive(
        source,
        target,
        len(payload),
        host.hashlib.sha256(payload).hexdigest(),
    )
    assert len(observed) >= 2


def _initialize_host_clock(host: object, artifact_root: Path) -> None:
    artifact_root.mkdir(mode=0o700)
    host.initialize_state(
        artifact_root,
        "1" * 64,
        lambda_started_at_epoch=time.time(),
    )


def test_retry4_image_selection_loads_exact_verified_archive_without_build(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    host = _load_host("giclab_t09_retry4_image_import")
    artifact_root = tmp_path / "artifacts"
    _initialize_host_clock(host, artifact_root)
    archive = tmp_path / "retained-image.tar"
    payload = b"retained-image"
    archive.write_bytes(payload)
    archive.chmod(0o600)
    image_id = "sha256:" + "a" * 64
    tag = "giclab/test:retry4"
    monkeypatch.setattr(host, "RETAINED_IMAGE_ARCHIVE_BYTES", len(payload))
    monkeypatch.setattr(
        host,
        "RETAINED_IMAGE_ARCHIVE_SHA256",
        host.hashlib.sha256(payload).hexdigest(),
    )
    monkeypatch.setattr(host, "RETAINED_IMAGE_ID", image_id)
    monkeypatch.setattr(host, "REPLACEMENT_IMAGE_TAG", tag)
    loaded = False
    tagged = False
    observed_pass_fds: tuple[int, ...] = ()

    def fake_image_id(_prefix: list[str], reference: str) -> str | None:
        if reference == tag:
            return image_id if tagged else None
        if reference == image_id:
            return image_id if loaded else None
        return None

    def fake_run(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        nonlocal loaded, observed_pass_fds
        assert argv[-1].startswith("/proc/self/fd/")
        observed_pass_fds = kwargs["pass_fds"]  # type: ignore[assignment]
        assert len(observed_pass_fds) == 1
        assert os.fstat(observed_pass_fds[0]).st_size == len(payload)
        loaded = True
        return subprocess.CompletedProcess(argv, 0, stdout=b"loaded\n", stderr=b"")

    def fake_logged(
        argv: list[str], *, evidence_root: Path, label: str, timeout: int
    ) -> dict[str, object]:
        nonlocal tagged
        assert timeout == 60
        if label == "docker-image-retag":
            tagged = True
        elif label == "replacement-image-inspect":
            (evidence_root / f"{label}.stdout").write_text(
                json.dumps([{"Id": image_id}]), encoding="utf-8"
            )
        return {"argv": argv, "returncode": 0}

    monkeypatch.setattr(host, "image_id_if_present", fake_image_id)
    monkeypatch.setattr(host.subprocess, "run", fake_run)
    monkeypatch.setattr(host, "run_logged", fake_logged)
    monkeypatch.setattr(
        host,
        "materialize_replacement_image",
        lambda **_kwargs: pytest.fail("fallback build must not run"),
    )
    result = host.materialize_retained_or_build_image(
        repository=ROOT,
        package_commit="2" * 40,
        artifact_root=artifact_root,
        image_archive=archive,
        prefix=["docker"],
    )
    assert observed_pass_fds
    assert result["method"] == "exact-retained-image-archive-import"
    assert result["image_id"] == image_id
    assert result["image_import_count"] == 1
    assert result["build_count"] == 0


def test_retry4_image_selection_uses_one_fallback_build_for_unavailable_archive(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    host = _load_host("giclab_t09_retry4_image_fallback")
    artifact_root = tmp_path / "artifacts"
    _initialize_host_clock(host, artifact_root)
    monkeypatch.setattr(host, "image_id_if_present", lambda _prefix, _reference: None)
    calls = 0

    def fake_build(**_kwargs: object) -> dict[str, object]:
        nonlocal calls
        calls += 1
        receipt = artifact_root / "pilot-v6/replacement-image-qualification/receipt.json"
        host.write_exclusive(receipt, {"build_count": 1})
        return {
            "qualification_id": host.QUALIFICATION_ID,
            "image_id": "sha256:" + "b" * 64,
            "build_count": 1,
        }

    monkeypatch.setattr(host, "materialize_replacement_image", fake_build)
    result = host.materialize_retained_or_build_image(
        repository=ROOT,
        package_commit="2" * 40,
        artifact_root=artifact_root,
        image_archive=tmp_path / "missing-image.tar",
        prefix=["docker"],
    )
    assert calls == 1
    assert result["image_import_count"] == 0
    assert result["build_count"] == 1
    assert result["additional_build_count"] == 0


def test_retry4_three_clock_boundaries_reproduce_retry3_and_repair_admission() -> None:
    lifecycle = Retry4LifecycleLimits()
    old_campaign_started = 1_000.0
    old_slot2_launch_remaining = 4_701.244573
    old_slot2_admission_now = (
        old_campaign_started + 14_400 - old_slot2_launch_remaining + 211.692214
    )
    old_remaining = 14_400 - (old_slot2_admission_now - old_campaign_started)
    assert old_remaining == pytest.approx(4_489.552359)
    assert old_remaining < 4_500

    slot2_launch_started = 20_000.0
    slot2_after_activation = slot2_launch_started + 211.692214
    assert lifecycle.preflight_remaining(
        launched_at_epoch=slot2_launch_started,
        now_epoch=slot2_after_activation,
    ) == pytest.approx(3_388.307786)
    assert not lifecycle.preflight_timed_out(
        launched_at_epoch=slot2_launch_started,
        now_epoch=slot2_after_activation,
    )
    assert not lifecycle.preflight_timed_out(
        launched_at_epoch=slot2_launch_started,
        now_epoch=slot2_launch_started + 3_599.999,
    )
    assert lifecycle.preflight_timed_out(
        launched_at_epoch=slot2_launch_started,
        now_epoch=slot2_launch_started + 3_600,
    )


def test_retry4_fresh_launch_clock_cumulative_accounting_and_empirical_boundaries() -> None:
    lifecycle = Retry4LifecycleLimits()
    prior_active = 3_883.230
    launch2 = 50_000.0
    now = launch2 + 332.407120
    cumulative = lifecycle.cumulative_active_seconds(
        prior_active_seconds=prior_active,
        launched_at_epoch=launch2,
        now_epoch=now,
    )
    assert cumulative == pytest.approx(4_215.637120)
    assert lifecycle.cumulative_cost_usd(cumulative_active_seconds=cumulative) == pytest.approx(
        cumulative * 1.29 / 3_600
    )
    assert lifecycle.active_caps_available(cumulative_active_seconds=21_600)
    assert not lifecycle.active_caps_available(cumulative_active_seconds=21_600.001)

    frozen_manifest_published = 60_000.0
    assert (
        lifecycle.empirical_remaining(
            empirical_started_at_epoch=frozen_manifest_published,
            now_epoch=frozen_manifest_published,
        )
        == 14_400
    )
    exact_admission = frozen_manifest_published + 14_400 - 4_500
    assert lifecycle.admit_empirical_attempt(
        empirical_started_at_epoch=frozen_manifest_published,
        now_epoch=exact_admission,
        attempt_hard_wall_seconds=3_600,
    )
    assert not lifecycle.admit_empirical_attempt(
        empirical_started_at_epoch=frozen_manifest_published,
        now_epoch=exact_admission + 0.001,
        attempt_hard_wall_seconds=3_600,
    )
    assert not lifecycle.empirical_termination_due(
        empirical_started_at_epoch=frozen_manifest_published,
        now_epoch=frozen_manifest_published + 13_499.999,
    )
    assert lifecycle.empirical_termination_due(
        empirical_started_at_epoch=frozen_manifest_published,
        now_epoch=frozen_manifest_published + 13_500,
    )


def test_retry4_slot2_launch_headroom_enforces_exact_active_caps() -> None:
    lifecycle = CampaignLifecycle(Retry4LifecycleLimits(), 1, 2, 0)
    exact = {
        "prior_lambda_duration_seconds": 3_600.0,
        "prior_lambda_cost_usd": 1.29,
    }
    projection = validate_slot2_launch_headroom(exact, lifecycle=lifecycle, now=10_000.0)
    assert projection["projected_cumulative_active_seconds"] == 21_600
    assert projection["projected_cumulative_lambda_cost_usd"] == pytest.approx(7.74)

    with pytest.raises(T09ProviderError, match="headroom"):
        validate_slot2_launch_headroom(
            {**exact, "prior_lambda_duration_seconds": 3_600.001},
            lifecycle=lifecycle,
            now=10_000.0,
        )
    with pytest.raises(T09ProviderError, match="headroom"):
        validate_slot2_launch_headroom(
            {**exact, "prior_lambda_cost_usd": 1.550001},
            lifecycle=lifecycle,
            now=10_000.0,
        )


def test_retry4_static_package_hashes_commands_and_successor_control_close() -> None:
    contracts = EXPERIMENT_ROOT / "contracts"
    plan_path = EXPERIMENT_ROOT / "run-plans/pilot.yaml"
    runtime_path = contracts / "T09_PILOT_RUNTIME_IDENTITY.json"
    execution_path = contracts / "T09_PILOT_EXECUTION_CONTRACT.json"
    commands_path = contracts / "T09_PILOT_COMMAND_MANIFESTS.json"
    control_path = EXPERIMENT_ROOT / "T09_PRAGMATIC_RETRY4_EXECUTION_CONTROL.json"
    registry = yaml.safe_load((ROOT / "experiments/registry.yaml").read_bytes())["experiments"][0]
    runtime = json.loads(runtime_path.read_text(encoding="utf-8"))
    execution = json.loads(execution_path.read_text(encoding="utf-8"))
    commands = json.loads(commands_path.read_text(encoding="utf-8"))
    control = json.loads(control_path.read_text(encoding="utf-8"))

    assert execution["plan_id"] == commands["plan_id"] == "PLAN-EXP0001-PILOT-V6"
    assert execution["contract_bindings"]["plan"] == {
        "path": plan_path.relative_to(ROOT).as_posix(),
        "sha256": host_hash(plan_path),
        "size_bytes": plan_path.stat().st_size,
    }
    assert execution["contract_bindings"]["runtime"]["sha256"] == host_hash(runtime_path)
    assert commands["execution_contract_sha256"] == host_hash(execution_path)
    assert (
        commands["reviewed_implementation_ancestor"]
        == (runtime["repository_instrumentation"]["reviewed_implementation_ancestor"])
    )
    assert len(commands["manifests"]) == 4
    assert [item["valid"] for item in commands["pair_diffs"]] == [True, True]
    assert control["successor"] == {
        "plan_id": "PLAN-EXP0001-PILOT-V6",
        "profile_path": plan_path.relative_to(ROOT).as_posix(),
        "profile_sha256": host_hash(plan_path),
        "requirements": control["successor"]["requirements"],
    }
    assert registry["current_execution_control"] == {
        "path": control_path.relative_to(ROOT).as_posix(),
        "sha256": host_hash(control_path),
    }
