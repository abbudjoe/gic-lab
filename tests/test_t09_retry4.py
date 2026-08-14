from __future__ import annotations

import importlib.util
import io
import json
import os
import subprocess
import tarfile
import time
from pathlib import Path

import pytest
import yaml

from giclab.harness import t09_pragmatic_provider as provider
from giclab.harness.lambda_campaign_lifecycle import Retry4LifecycleLimits
from giclab.harness.t09_pragmatic_provider import (
    CampaignLifecycle,
    T09ProviderError,
    validate_slot2_launch_headroom,
)
from giclab.validation import validate_instance

ROOT = Path(__file__).resolve().parents[1]
HOST_SOURCE = ROOT / "containers/sira-smoke/pragmatic/t09_remote_runner.py"
POSTRUN_REPAIR_SOURCE = ROOT / "containers/sira-smoke/pragmatic/t09_postrun_evidence_repair.py"
RUNTIME_SOURCE = ROOT / "src/giclab/harness/sira_gate_a_runtime.py"
EXPERIMENT_ROOT = ROOT / "experiments/EXP-0001-sira-simulative-vs-reactive"
SLOT1_PREENTRY_STAGE = Path(
    "/Volumes/Macintosh HD - Data/GIC-Lab/t09/sealed-artifacts/"
    ".ARCHIVE-EXP0001-PILOT-V6-0004.incoming/slot1-preentry/"
    "t09-pilot-private-evidence-stage.tar.gz"
)
PRIVATE_T09_ROOT = Path("/Volumes/Macintosh HD - Data/GIC-Lab/t09")


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


def _load_runtime(name: str) -> object:
    specification = importlib.util.spec_from_file_location(name, RUNTIME_SOURCE)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def _load_postrun_repair(name: str) -> object:
    specification = importlib.util.spec_from_file_location(name, POSTRUN_REPAIR_SOURCE)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def test_retry4_postrun_source_bundle_rejects_an_undeclared_extra(
    tmp_path: Path,
) -> None:
    repair = _load_postrun_repair("giclab_t09_retry4_postrun_source_bundle")
    source = tmp_path / "source"
    source.mkdir(mode=0o700)
    payload = source / "payload.json"
    payload.write_bytes(b"{}\n")
    payload.chmod(0o600)
    records = [
        {
            "path": "payload.json",
            "bytes": payload.stat().st_size,
            "sha256": host_hash(payload),
        }
    ]
    manifest = source / "source-manifest.json"
    manifest.write_bytes(
        repair.canonical_bytes(  # type: ignore[attr-defined]
            {
                "schema_version": "0.1.0",
                "files": records,
                "total_bytes": payload.stat().st_size,
            }
        )
    )
    manifest.chmod(0o600)
    expected = host_hash(manifest)
    repair.validate_source_bundle(  # type: ignore[attr-defined]
        source,
        expected_manifest_sha256=expected,
    )
    extra = source / "undeclared.json"
    extra.write_bytes(b"{}\n")
    extra.chmod(0o600)
    with pytest.raises(repair.EvidenceRepairError, match="member set"):  # type: ignore[attr-defined]
        repair.validate_source_bundle(  # type: ignore[attr-defined]
            source,
            expected_manifest_sha256=expected,
        )


def test_retry4_private_postrun_union_reconstructs_the_frozen_runtime() -> None:
    original = (
        PRIVATE_T09_ROOT / "sealed-artifacts/ARCHIVE-EXP0001-PILOT-V6-0004/"
        "t09-pilot-private-evidence-stage.tar.gz"
    )
    authority = PRIVATE_T09_ROOT / (
        "provider-private-v6-0004-slot2/slot2-eligibility-source/slot1-preentry-stage.tar.gz"
    )
    if not original.is_file() or not authority.is_file():
        pytest.skip("private Retry4 evidence is not present in this checkout")
    repair = _load_postrun_repair("giclab_t09_retry4_postrun_private_union")
    _stage, _authority, record_count = repair.audit_original_stage(original)  # type: ignore[attr-defined]
    union = repair.verify_union_with_frozen_runtime(  # type: ignore[attr-defined]
        repository=ROOT,
        original_stage=original,
        missing_source=authority,
    )
    assert record_count == 175
    assert union == {
        "frozen_run_manifest_sha256": (
            "c633c835f8310180be8f9c7a9c05427acf6e5b6da1051f211d22c8f54e290ddc"
        ),
        "slot2_authority_binding_sha256": (
            "21ffc161cded4d5d1011dbd8c3a367c5a871ca0f4b33ae0050ff939a9481f2dd"
        ),
        "load_frozen_run_manifest_passed": True,
        "require_image": False,
    }


def test_retry4_private_clock_reconciliation_uses_the_frozen_empirical_origin() -> None:
    original = (
        PRIVATE_T09_ROOT / "sealed-artifacts/ARCHIVE-EXP0001-PILOT-V6-0004/"
        "t09-pilot-private-evidence-stage.tar.gz"
    )
    entry = PRIVATE_T09_ROOT / "provider-private-v6-0004-slot2/entry-source"
    closeout = PRIVATE_T09_ROOT / "provider-private-v6-0004-slot2/closeout-source"
    if not original.is_file() or not entry.is_dir() or not closeout.is_dir():
        pytest.skip("private Retry4 evidence is not present in this checkout")
    repair = _load_postrun_repair("giclab_t09_retry4_postrun_clock")
    receipt = repair.reconcile_clock(  # type: ignore[attr-defined]
        original_stage=original,
        entry_source_root=entry,
        closeout_source_root=closeout,
    )
    assert receipt["timing"] == {
        "slot2_owned_lambda_started_at_epoch": 1786739918.105897,
        "empirical_campaign_started_at_epoch": 1786742271.222287,
        "termination_started_at_epoch": 1786742847.94891,
        "terminal_and_zero_observed_at_epoch": 1786742951.4776971,
        "provider_preflight_seconds": 2353.116389989853,
        "empirical_to_termination_dispatch_seconds": 576.7266230583191,
        "empirical_to_terminal_and_zero_seconds": 680.255410194397,
        "slot2_owned_active_seconds": 3033.37180018425,
        "slot1_prior_active_seconds": 1385.7062721252441,
        "retry4_cumulative_active_lambda_seconds": 4419.078072309494,
    }
    assert receipt["cost"]["retry4_cumulative_lambda_cost_usd"] == pytest.approx(  # type: ignore[index]
        1.583502975910902
    )


def test_retry4_runtime_matches_the_typed_raw_attempt_root() -> None:
    runtime = _load_runtime("giclab_t09_retry4_raw_root")
    raw = "artifacts/EXP-0001/pilot-v6/task-a/reactive/attempt-0004/raw"
    assert runtime._attempt_root_matches_raw_binding(
        Path("/opt/giclab-artifacts") / raw,
        raw,
    )
    assert not runtime._attempt_root_matches_raw_binding(
        Path("/opt/giclab-artifacts/artifacts/EXP-0001/pilot-v6/task-a/reactive/attempt-0004"),
        raw,
    )


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
        materialization_policy=host.SLOT2_IMAGE_MATERIALIZATION_POLICY,
    )
    assert observed_pass_fds
    assert result["method"] == "exact-retained-image-archive-import"
    assert result["image_id"] == image_id
    assert result["image_import_count"] == 1
    assert result["build_count"] == 0


def test_retry4_sudo_docker_uses_the_live_parent_descriptor() -> None:
    host = _load_host("giclab_t09_retry4_sudo_descriptor")
    assert host.held_descriptor_docker_path(["docker"], 17) == "/proc/self/fd/17"
    assert (
        host.held_descriptor_docker_path(["sudo", "-n", "docker"], 17)
        == f"/proc/{os.getpid()}/fd/17"
    )


def test_retry4_exact_slot1_preentry_stage_is_source_reconstructable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if not SLOT1_PREENTRY_STAGE.is_file():
        pytest.skip("private source-bound slot-1 stage is not present in this checkout")
    projection = provider._retry4_slot1_failure_archive_projection(SLOT1_PREENTRY_STAGE)
    assert projection["frozen_run_manifest_sha256"] == (
        "4477f5313100422cb4415bf636e2cd476fc59a2bf1548fa3390ced7ecc306a57"
    )
    assert projection["failed_attempt_run_id"] == "RUN-T09-TASK-A-REACTIVE-0004"
    assert projection["failed_attempt_identity_consumed"] is False
    assert projection["model_metadata_requests"] == 1
    assert projection["task_model_requests"] == projection["task_browser_actions"] == 0

    tampered = tmp_path / "tampered-stage.tar.gz"
    with (
        tarfile.open(SLOT1_PREENTRY_STAGE, "r:gz") as source,
        tarfile.open(tampered, "w:gz") as target,
    ):
        for member in source.getmembers():
            if member.isdir():
                target.addfile(member)
                continue
            handle = source.extractfile(member)
            assert handle is not None
            payload = handle.read()
            if member.name == "pilot-v6/aggregate-budget.json":
                payload += b"\n"
                member.size = len(payload)
            target.addfile(member, io.BytesIO(payload))
    tampered.chmod(0o600)
    monkeypatch.setattr(provider, "RETRY4_SLOT1_FAILURE_ARCHIVE_BYTES", tampered.stat().st_size)
    monkeypatch.setattr(
        provider,
        "RETRY4_SLOT1_FAILURE_ARCHIVE_SHA256",
        host_hash(tampered),
    )
    with pytest.raises(provider.T09ProviderError, match="member drifted"):
        provider._retry4_slot1_failure_archive_projection(tampered)


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
        materialization_policy=host.SLOT1_IMAGE_MATERIALIZATION_POLICY,
    )
    assert calls == 1
    assert result["image_import_count"] == 0
    assert result["build_count"] == 1
    assert result["additional_build_count"] == 0


def test_retry4_slot2_failed_image_import_never_builds(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    host = _load_host("giclab_t09_retry4_slot2_import_only")
    artifact_root = tmp_path / "artifacts"
    _initialize_host_clock(host, artifact_root)
    monkeypatch.setattr(host, "image_id_if_present", lambda _prefix, _reference: None)
    build_calls = 0

    def forbidden_build(**_kwargs: object) -> dict[str, object]:
        nonlocal build_calls
        build_calls += 1
        return {}

    monkeypatch.setattr(host, "materialize_replacement_image", forbidden_build)
    with pytest.raises(
        host.T09HostError,
        match="slot-2 retained image is unavailable; fallback build is forbidden",
    ):
        host.materialize_retained_or_build_image(
            repository=ROOT,
            package_commit="2" * 40,
            artifact_root=artifact_root,
            image_archive=tmp_path / "missing-image.tar",
            prefix=["docker"],
            materialization_policy=host.SLOT2_IMAGE_MATERIALIZATION_POLICY,
        )
    assert build_calls == 0


def test_retry4_slot2_rejected_docker_load_never_builds(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    host = _load_host("giclab_t09_retry4_slot2_failed_load")
    artifact_root = tmp_path / "artifacts"
    _initialize_host_clock(host, artifact_root)
    archive = tmp_path / "retained-image.tar"
    payload = b"retained-image"
    archive.write_bytes(payload)
    archive.chmod(0o600)
    monkeypatch.setattr(host, "RETAINED_IMAGE_ARCHIVE_BYTES", len(payload))
    monkeypatch.setattr(
        host,
        "RETAINED_IMAGE_ARCHIVE_SHA256",
        host.hashlib.sha256(payload).hexdigest(),
    )
    monkeypatch.setattr(host, "image_id_if_present", lambda _prefix, _reference: None)
    monkeypatch.setattr(
        host.subprocess,
        "run",
        lambda argv, **_kwargs: subprocess.CompletedProcess(
            argv,
            1,
            stdout=b"",
            stderr=b"load rejected",
        ),
    )
    build_calls = 0

    def forbidden_build(**_kwargs: object) -> dict[str, object]:
        nonlocal build_calls
        build_calls += 1
        return {}

    monkeypatch.setattr(host, "materialize_replacement_image", forbidden_build)
    with pytest.raises(
        host.T09HostError,
        match="slot-2 retained image import failed; fallback build is forbidden",
    ):
        host.materialize_retained_or_build_image(
            repository=ROOT,
            package_commit="2" * 40,
            artifact_root=artifact_root,
            image_archive=archive,
            prefix=["docker"],
            materialization_policy=host.SLOT2_IMAGE_MATERIALIZATION_POLICY,
        )
    assert build_calls == 0


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
    terminal_path = EXPERIMENT_ROOT / "T09_PRAGMATIC_RETRY4_TERMINAL_CONTROL.json"
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
    assert runtime["replacement_image_policy"]["slot2_materialization_policy"] == (
        "retained-import-only"
    )
    assert runtime["replacement_image_policy"]["slot2_fallback_build_permitted"] is False
    assert execution["runtime"]["slot2_container_image_policy"] == (
        "retained-exact-archive-import-only-no-fallback-build-v1"
    )
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
        "path": terminal_path.relative_to(ROOT).as_posix(),
        "sha256": host_hash(terminal_path),
    }
    assert control_path.relative_to(ROOT).as_posix() in registry["evidence_records"]


def test_retry4_slot2_control_repair_is_a_science_locked_descendant() -> None:
    package_commit = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
        capture_output=True,
        check=True,
        text=True,
    ).stdout.strip()
    transition = provider._retry4_slot2_git_transition(ROOT, package_commit)
    assert transition["from_package_commit"] == provider.RETRY4_SLOT1_PACKAGE_COMMIT
    assert transition["to_package_commit"] == package_commit
    assert transition["scientific_contract_changed"] is False
    assert transition["scientific_projection_sha256"]
    assert set(transition["changed_paths"]).issubset(provider.RETRY4_SLOT2_TRANSITION_ALLOWED_PATHS)


def test_retry4_active_slot2_entry_transition_is_source_bound() -> None:
    package_commit = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
        capture_output=True,
        check=True,
        text=True,
    ).stdout.strip()
    transition = provider.retry4_active_slot2_entry_transition(ROOT, package_commit)
    assert transition["from_package_commit"] == (provider.RETRY4_ACTIVE_SLOT2_ENTRY_PACKAGE_COMMIT)
    assert transition["to_package_commit"] == package_commit
    assert transition["scientific_contract_changed"] is False
    assert set(transition["changed_paths"]).issubset(provider.RETRY4_SLOT2_TRANSITION_ALLOWED_PATHS)


def test_retry4_provider_entry_freshness_matches_the_full_preflight_wall(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    host = _load_host("giclab_t09_retry4_entry_freshness")
    receipt = tmp_path / "entry.json"
    source = tmp_path / "source"
    source.mkdir()
    receipt.write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(host.time, "time", lambda: 10_000.0)
    monkeypatch.setattr(
        host,
        "validate_entry_receipt_source_bound",
        lambda *_args, **_kwargs: {
            "captured_at_epoch": 6_401.0,
            "owned_lambda_started_at_epoch": 6_401.0,
            "launch_slot": 2,
            "launch_count": 2,
        },
    )
    accepted = host.validate_dynamic_receipt(
        receipt,
        expected_package_commit=subprocess.run(
            ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
            capture_output=True,
            check=True,
            text=True,
        ).stdout.strip(),
        repository_root=ROOT,
        source_root=source,
    )
    assert accepted["captured_at_epoch"] == 6_401.0

    monkeypatch.setattr(
        host,
        "validate_entry_receipt_source_bound",
        lambda *_args, **_kwargs: {
            "captured_at_epoch": 6_399.0,
            "owned_lambda_started_at_epoch": 6_399.0,
            "launch_slot": 2,
            "launch_count": 2,
        },
    )
    with pytest.raises(host.T09HostError, match="stale"):
        host.validate_dynamic_receipt(
            receipt,
            expected_package_commit=subprocess.run(
                ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
                capture_output=True,
                check=True,
                text=True,
            ).stdout.strip(),
            repository_root=ROOT,
            source_root=source,
        )


def test_retry4_slot2_authority_is_minimal_bound_and_export_mode_matches(
    tmp_path: Path,
) -> None:
    host = _load_host("giclab_t09_retry4_slot2_authority")
    source = tmp_path / "provider-private"
    authority = source / "slot2-eligibility-source"
    authority.mkdir(parents=True)
    host.write_exclusive(source / "replacement-launch-eligibility.json", {"eligible": True})
    host.write_exclusive(authority / "transition.json", {"transition": True})
    nested = authority / "slot1-entry-source"
    nested.mkdir()
    host.write_exclusive(nested / "entry-receipt.json", {"entry": True})
    host.write_exclusive(nested / "source-manifest.json", {"entry_source": True})
    closeout = authority / "slot1-closeout-source"
    closeout.mkdir()
    host.write_exclusive(closeout / "closeout-receipt.json", {"closeout": True})
    host.write_exclusive(closeout / "source-manifest.json", {"closeout_source": True})
    host.write_exclusive(
        authority / "source-manifest.json",
        provider._slot2_authority_tree_manifest(authority),
    )
    host.write_exclusive(source / "unrelated-owned-state.json", {"private": True})

    destination = tmp_path / "retained"
    retained = host.retain_slot2_authority(source, destination)
    binding = host.slot2_authority_binding(destination)
    assert binding["relative_paths"] == list(retained)
    assert binding["replacement_eligibility_sha256"] == host.file_sha256(
        destination / "replacement-launch-eligibility.json"
    )
    assert not (destination / "unrelated-owned-state.json").exists()
    source_text = HOST_SOURCE.read_text(encoding="utf-8")
    assert 'transition_mode == "replacement-launch"' in source_text
    assert 'transition_mode == "slot2-replacement"' not in source_text


def test_retry4_generated_postfreeze_receipt_admits_first_condition() -> None:
    host = _load_host("giclab_t09_retry4_postfreeze_admission")
    frozen_sha = "a" * 64
    image_id = "sha256:" + "b" * 64
    postfreeze_sha = "c" * 64
    credential_scan_sha = "d" * 64
    first_pair_started = 1234.5
    frozen = {
        "first_pair_started_at_epoch": first_pair_started,
        "image_materialization_policy": host.SLOT2_IMAGE_MATERIALIZATION_POLICY,
    }
    preflight = {
        "frozen_run_manifest_sha256": frozen_sha,
        "replacement_image_id": image_id,
        "first_pair_started_at_epoch": first_pair_started,
        "empirical_entry_crossed": False,
        "postfreeze_validation_sha256": postfreeze_sha,
    }
    postfreeze = {
        "frozen_run_manifest_sha256": frozen_sha,
        "replacement_image_id": image_id,
        "image_materialization_policy": host.SLOT2_IMAGE_MATERIALIZATION_POLICY,
        "model_metadata_request_count": 1,
        "model_metadata_credential_scan_sha256": credential_scan_sha,
        "actual_credential_exposure_detected": False,
        "model_task_request_count": 0,
        "task_browser_action_count": 0,
        "first_pair_started_at_epoch": first_pair_started,
        host.POSTFREEZE_ADMISSION_FIELD: True,
    }
    host.validate_postfreeze_entry_receipts(
        preflight_receipt=preflight,
        postfreeze=postfreeze,
        frozen_manifest=frozen,
        frozen_manifest_sha256=frozen_sha,
        replacement_image_id=image_id,
        postfreeze_sha256=postfreeze_sha,
        model_metadata_credential_scan_sha256=credential_scan_sha,
    )

    drifted = {**postfreeze, host.POSTFREEZE_ADMISSION_FIELD: False}
    with pytest.raises(host.T09HostError, match="preflight and frozen runtime manifest drifted"):
        host.validate_postfreeze_entry_receipts(
            preflight_receipt=preflight,
            postfreeze=drifted,
            frozen_manifest=frozen,
            frozen_manifest_sha256=frozen_sha,
            replacement_image_id=image_id,
            postfreeze_sha256=postfreeze_sha,
            model_metadata_credential_scan_sha256=credential_scan_sha,
        )
