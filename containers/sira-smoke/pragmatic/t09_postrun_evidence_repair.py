#!/usr/bin/env python3
"""Repair the closed Retry4 evidence set without rewriting pre-termination evidence.

The live aggregate-stage producer intentionally skipped generated ``*.tar.gz``
files, but that broad rule also skipped one manifest-owned provider-authority
member.  This offline-only utility creates a fresh sidecar overlay containing
exactly that retained member and two source-derived receipts.  It never mutates
the original four-file final archive, makes no network request, and exercises
the frozen runtime loader over the exact one-file union before publishing the
overlay.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any, cast

ARCHIVE_ID = "ARCHIVE-EXP0001-PILOT-V6-0004"
OVERLAY_ID = "ARCHIVE-EXP0001-PILOT-V6-0004-POSTRUN-OVERLAY-0001"
PLAN_ID = "PLAN-EXP0001-PILOT-V6"
HOST_RUN_ID = "RUN-T09-PILOT-HOST-0004"
EXECUTED_PACKAGE_COMMIT = "2b40b8a8fc8379f7b803cc08af749849484b7986"
PROVIDER_ENTRY_PACKAGE_COMMIT = "9275bed0cce8bff5e033b94c9fcc8767af629fcd"
FROZEN_RUN_MANIFEST_SHA256 = "c633c835f8310180be8f9c7a9c05427acf6e5b6da1051f211d22c8f54e290ddc"
ORIGINAL_STAGE_SHA256 = "8b647302c6832ae42e38eb9535da18a20cba69c25891a6dfe1955f7aa66b1f95"
ORIGINAL_STAGE_BYTES = 9_623_449
ORIGINAL_STAGE_MANIFEST_SHA256 = "3a1004b0170fd506b43c9e6a3a0db5ea69f21fd28c08d118814d0ea878728283"
ORIGINAL_FINAL_MANIFEST_SHA256 = "4b7bc842064a94c856e3c5d55c027aacb497cf0006c223baac8a4abea451481b"
ORIGINAL_FINAL_IDENTITY_SHA256 = "1c0320b2ec4559223f29401e710ce22d8f7f655a7fd8fdf2de0582859c24dfb9"
ORIGINAL_CLOSEOUT_SUMMARY_SHA256 = (
    "9b4c87d91467530da4e65a62907a5a62c6ba2587c63f6b853560b3525d7f4f00"
)
AUTHORITY_SOURCE_MANIFEST_SHA256 = (
    "172c118671c56c3e812a48514fe6224cd10dd33b0ca4d0389ad4a14091ac5910"
)
MISSING_SOURCE_RELATIVE = "slot1-preentry-stage.tar.gz"
MISSING_ARCHIVE_RELATIVE = (
    "pilot-v6/slot2-authority/slot2-eligibility-source/slot1-preentry-stage.tar.gz"
)
MISSING_BYTES = 597_140
MISSING_SHA256 = "18f6c7d6bcda6f6be4c53854dc89d1fd08fb286393fba187815184db8819134f"
SLOT1_INBOUND_VERIFICATION_SHA256 = (
    "cf9f4c629952134ae1707ac6103ec1b776dd766bd3205eaedff3032b43e8917b"
)
SLOT2_ENTRY_RECEIPT_SHA256 = "fe847991eb32c4bb2eb1e7f2b7ee25a8834233c79b6d946cf687ff702a40e0c8"
SLOT2_ENTRY_SOURCE_MANIFEST_SHA256 = (
    "6733236e855274ed5f6484eaa2e34767b64e3f1bc56fd0b3e94deacbe2f79716"
)
SLOT2_CLOSEOUT_RECEIPT_SHA256 = "db815bf5290b63c972d22e0e8ef14a2ff35a941adf0ea8a95ba9cc79e8d7a45b"
SLOT2_CLOSEOUT_SOURCE_MANIFEST_SHA256 = (
    "72f99605bed91f1858890c82ecb770c04981d78e6d0c0bc6567501d6b13abc37"
)
STAGE_MANIFEST_MEMBER = "pilot-v6/evidence-stage-manifest.json"
AUTHORITY_MANIFEST_MEMBER = "pilot-v6/slot2-authority/slot2-eligibility-source/source-manifest.json"
HOST_SOURCE_RELATIVE = "containers/sira-smoke/pragmatic/t09_remote_runner.py"
TOOL_SOURCE_RELATIVE = "containers/sira-smoke/pragmatic/t09_postrun_evidence_repair.py"
ORIGINAL_FINAL_MEMBERS = {
    "archive-identity.json",
    "evidence-archive-manifest.json",
    "provider-closeout-summary.json",
    "t09-pilot-private-evidence-stage.tar.gz",
}
MAX_JSON_BYTES = 16 * 1_048_576
MAX_STAGE_MEMBERS = 2_048
MAX_STAGE_MEMBER_BYTES = 512 * 1_048_576


class EvidenceRepairError(RuntimeError):
    """Raised when immutable evidence cannot support the exact additive repair."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1_048_576):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode()


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _safe_regular(path: Path, *, mode: int = 0o600, maximum: int | None = None) -> os.stat_result:
    metadata = path.stat(follow_symlinks=False)
    if (
        path.is_symlink()
        or not stat.S_ISREG(metadata.st_mode)
        or metadata.st_uid != os.getuid()
        or metadata.st_nlink != 1
        or stat.S_IMODE(metadata.st_mode) != mode
        or (maximum is not None and metadata.st_size > maximum)
    ):
        raise EvidenceRepairError(f"unsafe private evidence file: {path.name}")
    return metadata


def _safe_private_directory(path: Path) -> os.stat_result:
    metadata = path.stat(follow_symlinks=False)
    if (
        path.is_symlink()
        or not stat.S_ISDIR(metadata.st_mode)
        or metadata.st_uid != os.getuid()
        or stat.S_IMODE(metadata.st_mode) != 0o700
    ):
        raise EvidenceRepairError("unsafe private evidence directory")
    return metadata


def _load_json(path: Path, *, expected_sha256: str | None = None) -> dict[str, Any]:
    metadata = _safe_regular(path, maximum=MAX_JSON_BYTES)
    if expected_sha256 is not None and sha256_file(path) != expected_sha256:
        raise EvidenceRepairError(f"JSON evidence hash drifted: {path.name}")
    try:
        value = json.loads(path.read_bytes())
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise EvidenceRepairError(f"JSON evidence is malformed: {path.name}") from exc
    if not isinstance(value, dict) or metadata.st_size <= 0:
        raise EvidenceRepairError(f"JSON evidence is not an object: {path.name}")
    return cast(dict[str, Any], value)


def _write_exclusive(path: Path, value: object) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as handle:
            handle.write(canonical_bytes(value))
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        os.close(descriptor)
    os.chmod(path, 0o600)


def _copy_exclusive(
    source: Path,
    destination: Path,
    *,
    expected_bytes: int,
    expected_sha256: str,
) -> None:
    _safe_regular(source)
    descriptor = os.open(
        destination,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        try:
            with (
                source.open("rb") as incoming,
                os.fdopen(descriptor, "wb", closefd=False) as outgoing,
            ):
                shutil.copyfileobj(incoming, outgoing, length=1_048_576)
                outgoing.flush()
                os.fsync(outgoing.fileno())
        finally:
            os.close(descriptor)
    except BaseException:
        destination.unlink(missing_ok=True)
        _fsync_directory(destination.parent)
        raise
    os.chmod(destination, 0o600)
    metadata = _safe_regular(destination)
    if metadata.st_size != expected_bytes or sha256_file(destination) != expected_sha256:
        destination.unlink()
        _fsync_directory(destination.parent)
        raise EvidenceRepairError("exclusive evidence copy failed target revalidation")


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _git_bytes(repository: Path, commit: str, relative: str) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(repository), "show", f"{commit}:{relative}"],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise EvidenceRepairError(f"Git binding does not resolve: {relative}")
    return result.stdout


def validate_repair_package(repository: Path, repair_commit: str) -> dict[str, str]:
    repository = repository.resolve(strict=True)
    head = subprocess.run(
        ["git", "-C", str(repository), "rev-parse", "HEAD"],
        capture_output=True,
        check=True,
        text=True,
    ).stdout.strip()
    status = subprocess.run(
        ["git", "-C", str(repository), "status", "--porcelain"],
        capture_output=True,
        check=True,
        text=True,
    ).stdout
    ancestor = subprocess.run(
        [
            "git",
            "-C",
            str(repository),
            "merge-base",
            "--is-ancestor",
            EXECUTED_PACKAGE_COMMIT,
            repair_commit,
        ],
        check=False,
    )
    if head != repair_commit or status or ancestor.returncode != 0:
        raise EvidenceRepairError("postrun repair requires one clean descendant package")
    tool_bytes = (repository / TOOL_SOURCE_RELATIVE).read_bytes()
    runner_bytes = (repository / HOST_SOURCE_RELATIVE).read_bytes()
    if tool_bytes != _git_bytes(
        repository, repair_commit, TOOL_SOURCE_RELATIVE
    ) or runner_bytes != _git_bytes(repository, EXECUTED_PACKAGE_COMMIT, HOST_SOURCE_RELATIVE):
        raise EvidenceRepairError("postrun repair source binding drifted")
    return {
        "repair_commit": repair_commit,
        "repair_source_sha256": hashlib.sha256(tool_bytes).hexdigest(),
        "executed_runner_sha256": hashlib.sha256(runner_bytes).hexdigest(),
    }


def _manifest_records(value: dict[str, Any], *, label: str) -> list[dict[str, Any]]:
    raw = value.get("files")
    if not isinstance(raw, list) or not raw:
        raise EvidenceRepairError(f"{label} has no file records")
    records: list[dict[str, Any]] = []
    names: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            raise EvidenceRepairError(f"{label} has a malformed file record")
        name = item.get("path")
        size = item.get("bytes")
        digest = item.get("sha256")
        relative = PurePosixPath(name) if isinstance(name, str) else PurePosixPath("/")
        if (
            not isinstance(name, str)
            or relative.is_absolute()
            or not relative.parts
            or ".." in relative.parts
            or name in names
            or type(size) is not int
            or size < 0
            or size > MAX_STAGE_MEMBER_BYTES
            or not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            raise EvidenceRepairError(f"{label} has an unsafe file record")
        names.add(name)
        records.append(cast(dict[str, Any], item))
    return records


def validate_source_bundle(
    root: Path,
    *,
    expected_manifest_sha256: str,
    allowed_receipts: tuple[str, ...] = (),
) -> dict[str, Any]:
    root = root.resolve(strict=True)
    manifest_path = root / "source-manifest.json"
    manifest = _load_json(manifest_path, expected_sha256=expected_manifest_sha256)
    records = _manifest_records(manifest, label="source manifest")
    observed: set[str] = set()
    total = 0
    for path in sorted(root.rglob("*")):
        metadata = path.stat(follow_symlinks=False)
        if stat.S_ISDIR(metadata.st_mode):
            continue
        _safe_regular(path)
        observed.add(path.relative_to(root).as_posix())
    expected = (
        {cast(str, item["path"]) for item in records}
        | {"source-manifest.json"}
        | set(allowed_receipts)
    )
    if observed != expected:
        raise EvidenceRepairError("source bundle member set drifted")
    for item in records:
        path = root.joinpath(*PurePosixPath(cast(str, item["path"])).parts)
        metadata = _safe_regular(path)
        if metadata.st_size != item["bytes"] or sha256_file(path) != item["sha256"]:
            raise EvidenceRepairError("source bundle file identity drifted")
        total += metadata.st_size
    if manifest.get("total_bytes") != total:
        raise EvidenceRepairError("source bundle total bytes drifted")
    return manifest


def audit_original_stage(path: Path) -> tuple[dict[str, Any], dict[str, Any], int]:
    metadata = _safe_regular(path)
    if metadata.st_size != ORIGINAL_STAGE_BYTES or sha256_file(path) != ORIGINAL_STAGE_SHA256:
        raise EvidenceRepairError("original aggregate stage identity drifted")
    payloads: dict[str, tuple[int, str, bytes | None]] = {}
    try:
        with tarfile.open(path, "r:gz") as handle:
            members = handle.getmembers()
            if not 1 <= len(members) <= MAX_STAGE_MEMBERS:
                raise EvidenceRepairError("aggregate stage member count is unsafe")
            for member in members:
                relative = PurePosixPath(member.name)
                if (
                    not member.isfile()
                    or relative.is_absolute()
                    or ".." in relative.parts
                    or member.name in payloads
                    or member.size > MAX_STAGE_MEMBER_BYTES
                ):
                    raise EvidenceRepairError("aggregate stage has an unsafe member")
                stream = handle.extractfile(member)
                if stream is None:
                    raise EvidenceRepairError("aggregate stage member is unreadable")
                digest = hashlib.sha256()
                retained = (
                    bytearray()
                    if member.name in {STAGE_MANIFEST_MEMBER, AUTHORITY_MANIFEST_MEMBER}
                    else None
                )
                observed_size = 0
                while chunk := stream.read(1_048_576):
                    observed_size += len(chunk)
                    digest.update(chunk)
                    if retained is not None:
                        retained.extend(chunk)
                if observed_size != member.size:
                    raise EvidenceRepairError("aggregate stage member was truncated")
                payloads[member.name] = (
                    observed_size,
                    digest.hexdigest(),
                    bytes(retained) if retained is not None else None,
                )
    except (OSError, tarfile.TarError, EOFError) as exc:
        raise EvidenceRepairError("aggregate stage cannot be audited") from exc
    if MISSING_ARCHIVE_RELATIVE in payloads:
        raise EvidenceRepairError(
            "original aggregate stage unexpectedly contains the repair member"
        )
    stage_raw = payloads.get(STAGE_MANIFEST_MEMBER)
    authority_raw = payloads.get(AUTHORITY_MANIFEST_MEMBER)
    if (
        stage_raw is None
        or authority_raw is None
        or stage_raw[2] is None
        or authority_raw[2] is None
    ):
        raise EvidenceRepairError("aggregate stage lacks a required manifest")
    if hashlib.sha256(stage_raw[2]).hexdigest() != ORIGINAL_STAGE_MANIFEST_SHA256:
        raise EvidenceRepairError("embedded aggregate-stage manifest drifted")
    if hashlib.sha256(authority_raw[2]).hexdigest() != AUTHORITY_SOURCE_MANIFEST_SHA256:
        raise EvidenceRepairError("embedded authority source manifest drifted")
    stage_manifest = cast(dict[str, Any], json.loads(stage_raw[2]))
    authority_manifest = cast(dict[str, Any], json.loads(authority_raw[2]))
    stage_records = _manifest_records(stage_manifest, label="aggregate-stage manifest")
    expected_stage = {cast(str, item["path"]) for item in stage_records} | {STAGE_MANIFEST_MEMBER}
    if set(payloads) != expected_stage or stage_manifest.get("total_bytes") != sum(
        cast(int, item["bytes"]) for item in stage_records
    ):
        raise EvidenceRepairError("aggregate-stage manifest member set drifted")
    for item in stage_records:
        observed = payloads[cast(str, item["path"])]
        if observed[:2] != (item["bytes"], item["sha256"]):
            raise EvidenceRepairError("aggregate-stage manifest record drifted")
    authority_records = _manifest_records(authority_manifest, label="authority manifest")
    missing = [item for item in authority_records if item.get("path") == MISSING_SOURCE_RELATIVE]
    if missing != [
        {"bytes": MISSING_BYTES, "path": MISSING_SOURCE_RELATIVE, "sha256": MISSING_SHA256}
    ]:
        raise EvidenceRepairError("authority manifest does not declare the exact missing member")
    return stage_manifest, authority_manifest, len(stage_records)


def validate_original_final_archive(root: Path) -> dict[str, object]:
    root = root.resolve(strict=True)
    metadata = root.stat(follow_symlinks=False)
    if (
        root.is_symlink()
        or not stat.S_ISDIR(metadata.st_mode)
        or stat.S_IMODE(metadata.st_mode) != 0o700
    ):
        raise EvidenceRepairError("original final archive root is unsafe")
    observed = {path.name for path in root.iterdir()}
    if observed != ORIGINAL_FINAL_MEMBERS:
        raise EvidenceRepairError("original four-file final archive member set drifted")
    expected = {
        "archive-identity.json": ORIGINAL_FINAL_IDENTITY_SHA256,
        "evidence-archive-manifest.json": ORIGINAL_FINAL_MANIFEST_SHA256,
        "provider-closeout-summary.json": ORIGINAL_CLOSEOUT_SUMMARY_SHA256,
        "t09-pilot-private-evidence-stage.tar.gz": ORIGINAL_STAGE_SHA256,
    }
    records: list[dict[str, object]] = []
    for name in sorted(expected):
        path = root / name
        metadata = _safe_regular(path)
        digest = sha256_file(path)
        if digest != expected[name]:
            raise EvidenceRepairError("original final archive file hash drifted")
        records.append({"path": name, "bytes": metadata.st_size, "sha256": digest})
    manifest = _load_json(
        root / "evidence-archive-manifest.json",
        expected_sha256=ORIGINAL_FINAL_MANIFEST_SHA256,
    )
    identity = _load_json(
        root / "archive-identity.json",
        expected_sha256=ORIGINAL_FINAL_IDENTITY_SHA256,
    )
    if (
        manifest.get("archive_id") != ARCHIVE_ID
        or manifest.get("payload_mode") != "aggregate-stage"
        or manifest.get("frozen_run_manifest_sha256") != FROZEN_RUN_MANIFEST_SHA256
        or manifest.get("payload_archives")
        != [
            {
                "path": "t09-pilot-private-evidence-stage.tar.gz",
                "bytes": ORIGINAL_STAGE_BYTES,
                "sha256": ORIGINAL_STAGE_SHA256,
            }
        ]
        or identity.get("archive_id") != ARCHIVE_ID
        or identity.get("manifest_sha256") != ORIGINAL_FINAL_MANIFEST_SHA256
    ):
        raise EvidenceRepairError("original final archive identity drifted")
    return {"files": records, "files_sha256": canonical_sha256(records)}


def _safe_extract_stage(source: Path, destination: Path) -> None:
    destination.mkdir(mode=0o700, parents=True, exist_ok=False)
    with tarfile.open(source, "r:gz") as handle:
        for member in handle.getmembers():
            relative = PurePosixPath(member.name)
            if not member.isfile() or relative.is_absolute() or ".." in relative.parts:
                raise EvidenceRepairError("unsafe aggregate member during reconstruction")
            target = destination.joinpath(*relative.parts)
            target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            stream = handle.extractfile(member)
            if stream is None:
                raise EvidenceRepairError("aggregate member unavailable during reconstruction")
            descriptor = os.open(
                target,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
                0o600,
            )
            try:
                with os.fdopen(descriptor, "wb", closefd=False) as outgoing:
                    shutil.copyfileobj(stream, outgoing, length=1_048_576)
                    outgoing.flush()
                    os.fsync(outgoing.fileno())
            finally:
                os.close(descriptor)
            os.chmod(target, 0o600)


def _load_host_module(repository: Path) -> Any:
    path = repository / HOST_SOURCE_RELATIVE
    specification = importlib.util.spec_from_file_location("giclab_t09_retry4_repair_host", path)
    if specification is None or specification.loader is None:
        raise EvidenceRepairError("frozen host module cannot be loaded")
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


def verify_union_with_frozen_runtime(
    *,
    repository: Path,
    original_stage: Path,
    missing_source: Path,
) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="giclab-t09-r4-reconstruction-") as raw:
        root = Path(raw) / "artifacts"
        _safe_extract_stage(original_stage, root)
        destination = root.joinpath(*PurePosixPath(MISSING_ARCHIVE_RELATIVE).parts)
        _copy_exclusive(
            missing_source,
            destination,
            expected_bytes=MISSING_BYTES,
            expected_sha256=MISSING_SHA256,
        )
        host = _load_host_module(repository)
        authority = host.slot2_authority_binding(root / "pilot-v6/slot2-authority")
        frozen, frozen_sha256 = host.load_frozen_run_manifest(
            root,
            repository=repository,
            package_commit=EXECUTED_PACKAGE_COMMIT,
            require_image=False,
        )
        if (
            frozen_sha256 != FROZEN_RUN_MANIFEST_SHA256
            or frozen.get("manifest_id") != "RUN-MANIFEST-EXP0001-PILOT-V6-0004"
            or frozen.get("plan_id") != PLAN_ID
        ):
            raise EvidenceRepairError("reconstructed frozen runtime identity drifted")
        return {
            "frozen_run_manifest_sha256": frozen_sha256,
            "slot2_authority_binding_sha256": host.canonical_sha256(authority),
            "load_frozen_run_manifest_passed": True,
            "require_image": False,
        }


def reconcile_clock(
    *,
    original_stage: Path,
    entry_source_root: Path,
    closeout_source_root: Path,
) -> dict[str, object]:
    validate_source_bundle(
        entry_source_root,
        expected_manifest_sha256=SLOT2_ENTRY_SOURCE_MANIFEST_SHA256,
        allowed_receipts=("entry-receipt.json",),
    )
    validate_source_bundle(
        closeout_source_root,
        expected_manifest_sha256=SLOT2_CLOSEOUT_SOURCE_MANIFEST_SHA256,
        allowed_receipts=("closeout-receipt.json",),
    )
    entry_path = entry_source_root / "entry-receipt.json"
    closeout_path = closeout_source_root / "closeout-receipt.json"
    entry = _load_json(entry_path, expected_sha256=SLOT2_ENTRY_RECEIPT_SHA256)
    closeout = _load_json(closeout_path, expected_sha256=SLOT2_CLOSEOUT_RECEIPT_SHA256)
    with tarfile.open(original_stage, "r:gz") as handle:
        stream = handle.extractfile("pilot-v6/frozen-run-manifest.json")
        if stream is None:
            raise EvidenceRepairError("aggregate stage lacks its frozen manifest")
        frozen_bytes = stream.read(MAX_JSON_BYTES + 1)
    if len(frozen_bytes) > MAX_JSON_BYTES or hashlib.sha256(frozen_bytes).hexdigest() != (
        FROZEN_RUN_MANIFEST_SHA256
    ):
        raise EvidenceRepairError("frozen clock source drifted")
    frozen = cast(dict[str, Any], json.loads(frozen_bytes))
    owned_started = entry.get("owned_lambda_started_at_epoch")
    empirical_started = frozen.get("campaign_started_at_epoch")
    termination_started = closeout.get("termination_started_at_epoch")
    terminal_observed = closeout.get("terminal_observed_at_epoch")
    prior_duration = closeout.get("prior_campaign_lambda_duration_seconds")
    cumulative_duration = closeout.get("lambda_duration_seconds")
    lambda_cost = closeout.get("lambda_list_cost_usd")
    numeric = (
        owned_started,
        empirical_started,
        termination_started,
        terminal_observed,
        prior_duration,
        cumulative_duration,
        lambda_cost,
    )
    if any(not isinstance(value, (int, float)) or isinstance(value, bool) for value in numeric):
        raise EvidenceRepairError("clock reconciliation input is malformed")
    owned_started_f = float(cast(int | float, owned_started))
    empirical_started_f = float(cast(int | float, empirical_started))
    termination_started_f = float(cast(int | float, termination_started))
    terminal_observed_f = float(cast(int | float, terminal_observed))
    prior_duration_f = float(cast(int | float, prior_duration))
    cumulative_duration_f = float(cast(int | float, cumulative_duration))
    lambda_cost_f = float(cast(int | float, lambda_cost))
    slot2_owned = terminal_observed_f - owned_started_f
    if (
        entry.get("package_commit") != PROVIDER_ENTRY_PACKAGE_COMMIT
        or entry.get("plan_id") != PLAN_ID
        or entry.get("host_run_id") != HOST_RUN_ID
        or entry.get("launch_slot") != 2
        or entry.get("launch_count") != 2
        or closeout.get("entry_receipt_sha256") != SLOT2_ENTRY_RECEIPT_SHA256
        or closeout.get("terminal_or_absent") is not True
        or closeout.get("zero_t09_instances") is not True
        or closeout.get("security_restored") is not True
        or closeout.get("termination_request_count") != 1
        or frozen.get("provider_entry_receipt_sha256") != SLOT2_ENTRY_RECEIPT_SHA256
        or abs(
            slot2_owned - float(cast(int | float, closeout.get("owned_lambda_duration_seconds")))
        )
        > 1e-6
        or abs(prior_duration_f + slot2_owned - cumulative_duration_f) > 1e-6
        or abs(cumulative_duration_f * 1.29 / 3_600 - lambda_cost_f) > 1e-12
    ):
        raise EvidenceRepairError("provider/frozen clock binding drifted")
    return {
        "schema_version": "0.1.0",
        "record_id": "T09-PRAGMATIC-RETRY4-SLOT2-CLOCK-RECONCILIATION-0001",
        "plan_id": PLAN_ID,
        "host_run_id": HOST_RUN_ID,
        "reconciliation_after_provider_termination": True,
        "raw_provider_receipts_preserved": True,
        "raw_closeout_campaign_elapsed_field_interpretation": (
            "slot2-owned-active-seconds-not-empirical-campaign-seconds"
        ),
        "source_bindings": {
            "frozen_run_manifest_sha256": FROZEN_RUN_MANIFEST_SHA256,
            "slot2_entry_receipt_sha256": SLOT2_ENTRY_RECEIPT_SHA256,
            "slot2_entry_source_manifest_sha256": SLOT2_ENTRY_SOURCE_MANIFEST_SHA256,
            "slot2_closeout_receipt_sha256": SLOT2_CLOSEOUT_RECEIPT_SHA256,
            "slot2_closeout_source_manifest_sha256": SLOT2_CLOSEOUT_SOURCE_MANIFEST_SHA256,
        },
        "timing": {
            "slot2_owned_lambda_started_at_epoch": owned_started_f,
            "empirical_campaign_started_at_epoch": empirical_started_f,
            "termination_started_at_epoch": termination_started_f,
            "terminal_and_zero_observed_at_epoch": terminal_observed_f,
            "provider_preflight_seconds": empirical_started_f - owned_started_f,
            "empirical_to_termination_dispatch_seconds": (
                termination_started_f - empirical_started_f
            ),
            "empirical_to_terminal_and_zero_seconds": terminal_observed_f - empirical_started_f,
            "slot2_owned_active_seconds": slot2_owned,
            "slot1_prior_active_seconds": prior_duration_f,
            "retry4_cumulative_active_lambda_seconds": cumulative_duration_f,
        },
        "cost": {
            "lambda_hourly_price_usd": 1.29,
            "retry4_cumulative_lambda_cost_usd": lambda_cost_f,
            "lambda_cost_recomputed": True,
            "lambda_cost_cap_usd": 8.0,
            "cap_respected": lambda_cost_f <= 8.0,
        },
        "source_absolute_paths_retained": False,
    }


def create_overlay(args: argparse.Namespace) -> dict[str, object]:
    repository = args.repository.resolve(strict=True)
    original_root = args.original_archive_root.resolve(strict=True)
    authority_source_root = args.authority_source_root.resolve(strict=True)
    inbound_path = args.slot1_inbound_verification.resolve(strict=True)
    entry_source_root = args.slot2_entry_source_root.resolve(strict=True)
    closeout_source_root = args.slot2_closeout_source_root.resolve(strict=True)
    output_root = args.output_root.resolve(strict=False)
    _safe_private_directory(original_root.parent)
    expected_output_root = original_root.parent / OVERLAY_ID
    input_roots = (
        repository,
        original_root,
        authority_source_root,
        inbound_path,
        entry_source_root,
        closeout_source_root,
    )
    if (
        output_root != expected_output_root
        or output_root.exists()
        or output_root.is_symlink()
        or any(
            output_root == source
            or output_root.is_relative_to(source)
            or source.is_relative_to(output_root)
            for source in input_roots
        )
    ):
        raise EvidenceRepairError("postrun overlay destination is not fresh and exact")
    package = validate_repair_package(repository, args.repair_commit)
    original = validate_original_final_archive(original_root)
    original_stage = original_root / "t09-pilot-private-evidence-stage.tar.gz"
    stage_manifest, _authority_manifest, stage_record_count = audit_original_stage(original_stage)
    validate_source_bundle(
        authority_source_root,
        expected_manifest_sha256=AUTHORITY_SOURCE_MANIFEST_SHA256,
    )
    missing_source = authority_source_root / MISSING_SOURCE_RELATIVE
    metadata = _safe_regular(missing_source)
    if metadata.st_size != MISSING_BYTES or sha256_file(missing_source) != MISSING_SHA256:
        raise EvidenceRepairError("retained missing authority member drifted")
    inbound = _load_json(inbound_path, expected_sha256=SLOT1_INBOUND_VERIFICATION_SHA256)
    if (
        inbound.get("verified_before_provider_termination") is not True
        or inbound.get("archive_bytes") != MISSING_BYTES
        or inbound.get("archive_sha256") != MISSING_SHA256
    ):
        raise EvidenceRepairError("slot-1 inbound verification does not bind the missing member")
    union = verify_union_with_frozen_runtime(
        repository=repository,
        original_stage=original_stage,
        missing_source=missing_source,
    )
    clock = reconcile_clock(
        original_stage=original_stage,
        entry_source_root=entry_source_root,
        closeout_source_root=closeout_source_root,
    )
    output_root.mkdir(mode=0o700, parents=False, exist_ok=False)
    supplement = output_root / MISSING_SOURCE_RELATIVE
    _copy_exclusive(
        missing_source,
        supplement,
        expected_bytes=MISSING_BYTES,
        expected_sha256=MISSING_SHA256,
    )
    _write_exclusive(output_root / "posttermination-clock-reconciliation.json", clock)
    repair: dict[str, object] = {
        "schema_version": "0.1.0",
        "record_id": "T09-PRAGMATIC-RETRY4-EVIDENCE-OVERLAY-0001",
        "overlay_id": OVERLAY_ID,
        "archive_id": ARCHIVE_ID,
        "plan_id": PLAN_ID,
        "host_run_id": HOST_RUN_ID,
        "repair_classification": "posttermination-additive-missing-authority-member-repair",
        "reconciliation_after_provider_termination": True,
        "pretermination_download_or_verification_claimed_for_overlay": False,
        "original_sealed_archive_preserved_byte_exact": True,
        "original_sealed_archive": original,
        "original_stage": {
            "bytes": ORIGINAL_STAGE_BYTES,
            "sha256": ORIGINAL_STAGE_SHA256,
            "manifest_sha256": ORIGINAL_STAGE_MANIFEST_SHA256,
            "manifest_record_count": stage_record_count,
            "manifest_total_bytes": stage_manifest.get("total_bytes"),
        },
        "declaring_authority_manifest_sha256": AUTHORITY_SOURCE_MANIFEST_SHA256,
        "supplement": {
            "restore_relative_path": MISSING_ARCHIVE_RELATIVE,
            "bytes": MISSING_BYTES,
            "sha256": MISSING_SHA256,
            "retained_source_metadata_valid": True,
            "copy_rehash_verified": True,
            "slot1_inbound_verification_sha256": SLOT1_INBOUND_VERIFICATION_SHA256,
            "slot1_inbound_verified_before_provider_termination": True,
        },
        "union": {
            **union,
            "original_record_count": stage_record_count,
            "reconstructed_record_count": stage_record_count + 1,
            "exact_one_member_added": True,
            "member_set_equality_verified": True,
        },
        "package_binding": package,
        "source_absolute_paths_retained": False,
        "model_requests": 0,
        "browser_actions": 0,
        "provider_mutations": 0,
    }
    _write_exclusive(output_root / "posttermination-reconstruction-receipt.json", repair)
    records = []
    for name in (
        MISSING_SOURCE_RELATIVE,
        "posttermination-clock-reconciliation.json",
        "posttermination-reconstruction-receipt.json",
    ):
        path = output_root / name
        records.append({"path": name, "bytes": path.stat().st_size, "sha256": sha256_file(path)})
    manifest = {
        "schema_version": "0.1.0",
        "overlay_id": OVERLAY_ID,
        "archive_id": ARCHIVE_ID,
        "private_access_controlled": True,
        "public_release": "blocked-pending-review",
        "files": records,
        "files_sha256": canonical_sha256(records),
        "total_bytes": sum(cast(int, item["bytes"]) for item in records),
        "original_archive_manifest_sha256": ORIGINAL_FINAL_MANIFEST_SHA256,
        "frozen_run_manifest_sha256": FROZEN_RUN_MANIFEST_SHA256,
        "union_verified_after_provider_termination": True,
    }
    _write_exclusive(output_root / "overlay-manifest.json", manifest)
    identity = {
        "schema_version": "0.1.0",
        "overlay_id": OVERLAY_ID,
        "manifest_sha256": sha256_file(output_root / "overlay-manifest.json"),
        "file_count": len(records),
        "files_sha256": manifest["files_sha256"],
        "original_archive_unchanged": validate_original_final_archive(original_root) == original,
        "created_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    }
    _write_exclusive(output_root / "overlay-identity.json", identity)
    _fsync_directory(output_root)
    observed = {path.name for path in output_root.iterdir()}
    if observed != {
        MISSING_SOURCE_RELATIVE,
        "posttermination-clock-reconciliation.json",
        "posttermination-reconstruction-receipt.json",
        "overlay-manifest.json",
        "overlay-identity.json",
    }:
        raise EvidenceRepairError("postrun overlay member set drifted")
    return {
        "overlay_id": OVERLAY_ID,
        "overlay_root": output_root.as_posix(),
        "overlay_manifest_sha256": sha256_file(output_root / "overlay-manifest.json"),
        "overlay_identity_sha256": sha256_file(output_root / "overlay-identity.json"),
        "reconstruction_receipt_sha256": sha256_file(
            output_root / "posttermination-reconstruction-receipt.json"
        ),
        "clock_reconciliation_sha256": sha256_file(
            output_root / "posttermination-clock-reconciliation.json"
        ),
        "frozen_run_manifest_sha256": FROZEN_RUN_MANIFEST_SHA256,
    }


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser()
    result.add_argument("--repository", type=Path, required=True)
    result.add_argument("--repair-commit", required=True)
    result.add_argument("--original-archive-root", type=Path, required=True)
    result.add_argument("--authority-source-root", type=Path, required=True)
    result.add_argument("--slot1-inbound-verification", type=Path, required=True)
    result.add_argument("--slot2-entry-source-root", type=Path, required=True)
    result.add_argument("--slot2-closeout-source-root", type=Path, required=True)
    result.add_argument("--output-root", type=Path, required=True)
    return result


def main() -> int:
    print(json.dumps(create_overlay(parser().parse_args()), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
