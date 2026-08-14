"""Manually supervised host runner for the locked T09 calibration pilot.

This is the smallest host overlay on the T07 pragmatic runtime. It does not call a
cloud API and is inert unless a later authorized operator invokes it on the exact
owned Lambda host. It verifies the immutable package, prepares the evaluator overlay,
runs each frozen container once in order, enforces host-visible caps, removes the
condition container, runs the exact evaluator with networking disabled, and packages
private evidence. Provider launch/termination and zero-instance verification stay in
the separately authorized manual provider lifecycle.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib.util
import ipaddress
import json
import os
import re
import resource
import shutil
import signal
import stat
import subprocess
import sys
import tarfile
import time
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import IO, Any, BinaryIO, Final, cast

from jsonschema import Draft202012Validator, FormatChecker

from giclab.harness.lambda_campaign_lifecycle import Retry4LifecycleLimits
from giclab.harness.sira_gate_a import ProviderBudgetUsage
from giclab.harness.t09_pragmatic_provider import (
    RETRY4_ACTIVE_SLOT2_ENTRY_PACKAGE_COMMIT,
    T09ProviderError,
    load_campaign_lifecycle,
    retry4_active_slot2_entry_transition,
    validate_entry_receipt_source_bound,
)
from giclab.harness.t09_pragmatic_provider import (
    validate_closeout_receipt as validate_source_bound_closeout,
)
from giclab.harness.t09_sira_pilot import (
    ATTEMPT_ORDER,
    PREENTRY_RESUME_FROM_PACKAGE_COMMIT,
    PREENTRY_RESUME_FROM_PLAN_SHA256,
    PairCheckpointInput,
    RuntimeQualification,
    T09PilotError,
    first_pair_decision,
    load_aggregate_usage,
    load_execution_contract,
    mark_actual_credential_exposure,
    mark_attempt_completed,
    mark_credential_cleanup_integrity_failure,
    mark_raw_attempt_complete,
    record_first_pair_checkpoint,
    scientific_attempt_projection,
    transition_zero_usage_preflight_state,
)

PLAN_ID: Final = "PLAN-EXP0001-PILOT-V6"
HOST_RUN_ID: Final = "RUN-T09-PILOT-HOST-0004"
ARCHIVE_ID: Final = "ARCHIVE-EXP0001-PILOT-V6-0004"
STAGE_ID: Final = "STAGE-EXP0001-PILOT-V6-0004"
QUALIFICATION_ID: Final = "QUAL-T09-PILOT-V6-IMAGE-0001"
FROZEN_RUN_MANIFEST_ID: Final = "RUN-MANIFEST-EXP0001-PILOT-V6-0004"
AUTHORIZATION_SOURCE_SHA256: Final = (
    "e3222d38c9b21091a51839122d42594d691577716bc87fd3e09296c6b766df51"
)
MODEL: Final = "gpt-4o-2024-11-20"
SERVICE_TIER: Final = "default"
HISTORICAL_IMAGE_ID: Final = (
    "sha256:035edf61718e84a8156f4f0f7817b134b0ce31488d3f0b50bbfba2b4a30cc61c"
)
T07_EXECUTION_COMMIT: Final = "5698f04dfd08bc85a66d2355b0a4bd7d3ce24a23"
SIRA_COMMIT: Final = "93fb8d72de71f9a4a13419670adeb34d93cf7acd"
SIRA_TREE: Final = "6a6d9068b94d7632d3533a3d6f013d4de6ff76e8"
REPLACEMENT_IMAGE_TAG: Final = f"giclab/t09-pilot-v6:{SIRA_COMMIT[:12]}-0001"
RETAINED_IMAGE_ARCHIVE_BYTES: Final = 1_207_128_576
RETAINED_IMAGE_ARCHIVE_SHA256: Final = (
    "623e717c2182eca9cee2f471b7ecd9a57bead2f5263dee64aa5cd954eae5ddb0"
)
RETAINED_IMAGE_ID: Final = "sha256:abe8ed38f5c5b5a0a63fa726a74034dc5c192a12c0fccfe1319f97c27ceaf0a3"
# Historical Retry 2 transition helpers remain importable for archived-receipt
# verification only.  No Retry 3 parser route invokes them.
CONTEXT_FAILURE_QUALIFICATION_ID: Final = "QUAL-T09-PILOT-V4-IMAGE-0002"
FAILED_CANDIDATE_QUALIFICATION_ID: Final = "QUAL-T09-PILOT-V4-IMAGE-0003"
PRIOR_REPLACEMENT_IMAGE_TAG: Final = f"giclab/t09-pilot-v4:{SIRA_COMMIT[:12]}-0002"
PACKAGE_TRANSITION_FROM_COMMIT: Final = "eda1d15387efbc2c269a33176f5c0e04b177e70c"
PREVIOUS_PACKAGE_TRANSITION_COMMIT: Final = "97358563139532b139a79028909671d8e76f79b7"
FAILED_CANDIDATE_OFFLINE_STDERR_SHA256: Final = (
    "ec46a5dee7f41906d4de9d335ee18de31408a2759f6390712963e18ecfd6b16c"
)
PINNED_ENV_EXAMPLE_SHA256: Final = (
    "086eb43e37d1f74131ca1290119a7a13cb7544b0d943ff726dd13a45ea282933"
)
PINNED_ENV_EXAMPLE_BYTES: Final = 178
PINNED_ENV_EXAMPLE_CONTENT: Final = (
    b"# Copy to .env and fill in the key for the provider you use.\n"
    b"OPENAI_API_KEY=\n"
    b"SIRA_API_KEY=\n\n"
    b"# Optional: set DEBUG=1 to store per-step prompts under browsing_data/<job>/.\n"
    b"DEBUG=0\n"
)
PACKAGE_TRANSITION_ALLOWED_PATHS: Final = frozenset(
    {
        "containers/sira-smoke/pragmatic/t09_remote_runner.py",
        "docs/harness/T09_PRAGMATIC_RETRY2_EXECUTION_PLAN.md",
        "experiments/EXP-0001-sira-simulative-vs-reactive/contracts/"
        "T09_PILOT_COMMAND_MANIFESTS.json",
        "experiments/EXP-0001-sira-simulative-vs-reactive/contracts/"
        "T09_PILOT_EXECUTION_CONTRACT.json",
        "experiments/EXP-0001-sira-simulative-vs-reactive/contracts/"
        "T09_PILOT_RUNTIME_IDENTITY.json",
        "experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/conditions/"
        "pilot-v6-task-0000-reactive.yaml",
        "experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/conditions/"
        "pilot-v6-task-0000-simulative.yaml",
        "experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/conditions/"
        "pilot-v6-task-0001-reactive.yaml",
        "experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/conditions/"
        "pilot-v6-task-0001-simulative.yaml",
        "schemas/t09-sira-pilot-evidence.schema.json",
        "src/giclab/harness/t09_sira_pilot.py",
        "tests/test_t09_sira_pilot.py",
    }
)
T07_RUNTIME_SHA256: Final = "c461dce20fea9e743135cad98b664213a393e46f35d1c1a8434212b2f0367dbb"
T07_RUNTIME_PREFLIGHT_SHA256: Final = (
    "0530b3ad25fac1d3f9372d31da8046bec67b6c74eea3cdd3c8d91353948f1b3d"
)
T07_ROUTING_PATCH_SHA256: Final = "4d7e2a25f4313fc754db0fa17aeda51cc5cd75a5653adaf13b01ce87a71cb8ed"
UV_URL: Final = (
    "https://files.pythonhosted.org/packages/83/eb/4e1557daf6693cb446ed28185664ad6682fd98c6d"
    "bac9e433cbc35df450a/uv-0.11.7-py3-none-manylinux_2_17_x86_64.manylinux2014_x86_64.whl"
)
UV_SHA256: Final = "4e4d5e31bea86e1b6e0f5a0f95e14e80018e6f6c0129256d2915a4b3d793644d"
EVALUATOR_DIRECT_URL_RECORD: Final = (
    "en-core-web-sm @ https://github.com/explosion/spacy-models/releases/download/"
    "en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl"
)
RUN_IDS: Final = (
    "RUN-T09-TASK-A-REACTIVE-0004",
    "RUN-T09-TASK-A-SIMULATIVE-0004",
    "RUN-T09-TASK-B-SIMULATIVE-0004",
    "RUN-T09-TASK-B-REACTIVE-0004",
)
CONTAINER_PREFIX: Final = "giclab-t09-pilot-v6-"
EXPECTED_PACKAGE_MANIFEST_SHA256: Final = (
    "4ff2603fa5e0f7033ba773decdcb86abf648dcce22e469d26bc48214e390e104"
)
EXPECTED_CHROMIUM_SHA256: Final = "0498f208c25339f386413ada7b3c35293b0b6250e67d85446ba9541d7fd636f7"
EXPECTED_UPSTREAM_RUNNER_SHA256: Final = (
    "b06793ad1b366a934b798f9f3272fc80a7104a220cb3304ab3bda2eb2a78b331"
)
BASE_IMAGE_IDENTITY: Final = (
    "mcr.microsoft.com/playwright/python:v1.39.0-jammy@"
    "sha256:96955ff5cc37e13f5f1b21f5171afb9fed7e028025aa9d81c690501cd7fa0c6c"
)
SOURCE_DATE_EPOCH: Final = 1_786_570_934
MAX_ATTEMPT_OUTPUT_BYTES: Final = 67_108_864
MAX_PILOT_DISK_BYTES: Final = 2_147_483_648
MAX_CONDITION_WALL_SECONDS: Final = 3_600
MAX_PAIR_WALL_SECONDS: Final = 7_200
MAX_TOTAL_WALL_SECONDS: Final = 14_400
MAX_PREFLIGHT_WALL_SECONDS: Final = 3_600
FAILED_PREFLIGHT_TERMINATION_DISPATCH_SECONDS: Final = 300
MAX_SUCCESSFUL_HOST_ACTIVE_SECONDS: Final = 18_000
MAX_LAMBDA_DURATION_SECONDS: Final = 21_600
MAX_LAMBDA_COST_USD: Final = 8.00
LAMBDA_HOURLY_PRICE_USD: Final = 1.29
FINALIZER_INVOCATION_TIMEOUT_SECONDS: Final = 600
ATTEMPT_EVIDENCE_EXPORT_RESERVE_SECONDS: Final = 600
PROVIDER_CLOSEOUT_RESERVE_SECONDS: Final = 900
PROVIDER_TERMINATION_CUTOFF_SECONDS: Final = 13_500
PROVIDER_TERMINATION_HANDOFF_SECONDS: Final = 60
MAX_LAMBDA_INSTANCES: Final = 1
MAX_LAMBDA_LAUNCHES: Final = 2
MAX_PERSISTENT_FILESYSTEMS: Final = 0
APPROVED_FINAL_ARCHIVE_ROOT: Final = Path(
    "/Volumes/Macintosh HD - Data/GIC-Lab/t09/sealed-artifacts"
)
_HEX64: Final = re.compile(r"[a-f0-9]{64}")
_JUPYTER_URL: Final = re.compile(
    r"https?://[^\s\"'<>]*(?:/lab(?:\?|/)|/tree(?:\?|/)|[?&]token=)[^\s\"'<>]*",
    re.IGNORECASE,
)
_CREDENTIAL_TEXT: Final = re.compile(
    r"(?:sk-[A-Za-z0-9_-]{16,}|AKIA[A-Z0-9]{16}|Bearer\s+[A-Za-z0-9._~+/=-]{16,})"
)
_IPV4_TEXT: Final = re.compile(r"(?<![A-Za-z0-9])(?:\d{1,3}\.){3}\d{1,3}(?:/\d{1,2})?")
_SENSITIVE_JSON_KEYS: Final = {
    "account_id",
    "api_key",
    "authorization",
    "cidr",
    "cloud_credential",
    "jupyter_token",
    "jupyter_url",
    "private_cidr",
    "private_ip",
    "provider_account_id",
    "provider_account_identifier",
}
MAX_PRIVACY_JSON_BYTES: Final = 16_777_216
MAX_PRIVACY_LINE_BYTES: Final = 8_388_608
MAX_PRIVACY_SCAN_CHUNK_BYTES: Final = 1_048_576
MAX_ATTEMPT_EXPORT_BYTES: Final = 100_663_296
MAX_STAGED_EVIDENCE_BYTES: Final = 536_870_912
MAX_STAGE_SECONDS: Final = 300
MAX_IMAGE_EXPORT_SECONDS: Final = 300
MAX_IMAGE_ARCHIVE_BYTES: Final = 2_147_483_648
MAX_EVALUATOR_OVERLAY_BYTES: Final = 1_073_741_824
MAX_EVALUATOR_OVERLAY_ENTRIES: Final = 100_000
MAX_PREENTRY_REPAIRS_PER_RUN: Final = 3
POSTFREEZE_ADMISSION_FIELD: Final = "fresh_empirical_campaign_headroom_passed_before_metadata_get"
SLOT1_IMAGE_MATERIALIZATION_POLICY: Final = "retained-import-or-one-fallback-build"
SLOT2_IMAGE_MATERIALIZATION_POLICY: Final = "retained-import-only"
PINNED_DATASET_SHA256: Final = "359300b029c6891567816f351bf8786e9b018d7af8a1a44b7da9ba5ef4651288"
FINALIZER_RELATIVE_PATH: Final = "containers/sira-smoke/pragmatic/t09_evaluate_attempt.py"
FINALIZER_PROJECTION_RELATIVE_PATH: Final = (
    "containers/sira-smoke/pragmatic/t09_finalizer_projection.py"
)
LOCAL_FINALIZER_QUALIFICATION_RELATIVE_PATH: Final = (
    "containers/sira-smoke/pragmatic/t09_local_finalizer_qualification.py"
)
IMAGE_ARCHIVE_PATH: Final = Path("/home/ubuntu/t09-pilot-v6-replacement-image-0001.tar")
PRIVATE_REGRESSION_ARCHIVE_PATH: Final = Path(
    "/tmp/giclab-t09-private-v4-task-a-reactive-0002.tar.gz"
)
PRIVATE_REGRESSION_ARCHIVE_BYTES: Final = 3_439_137
PRIVATE_REGRESSION_ARCHIVE_SHA256: Final = (
    "63ed19b35bcb4cb62c3796a80a48004937340eb3826f9657a1006e251772255d"
)
PREENTRY_RESUME_FROM_EXECUTION_SHA256: Final = (
    "81dea470fecaef47a3f0139ed291b214fce1eae1bfcfb38e1fb20c32e5527791"
)
PREENTRY_RESUME_FROM_RUNNER_SHA256: Final = (
    "307ff291d22c45b1740b632968a709cbc9458bfe9d5ea21c3f5cb446a2eefa7d"
)
PREENTRY_RESUME_FAILURE_CLASSIFICATION: Final = "preempirical_operator_archive_path_mismatch"
PREENTRY_RESUME_ALLOWED_PATHS: Final = frozenset(
    {
        "containers/sira-smoke/pragmatic/t09_remote_runner.py",
        "docs/harness/T09_PRAGMATIC_RETRY3_EXECUTION_PLAN.md",
        "experiments/EXP-0001-sira-simulative-vs-reactive/contracts/"
        "T09_PILOT_COMMAND_MANIFESTS.json",
        "experiments/EXP-0001-sira-simulative-vs-reactive/contracts/"
        "T09_PILOT_EXECUTION_CONTRACT.json",
        "experiments/EXP-0001-sira-simulative-vs-reactive/contracts/"
        "T09_PILOT_RUNTIME_IDENTITY.json",
        "experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/pilot.yaml",
        "experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/conditions/"
        "pilot-v6-task-0000-reactive.yaml",
        "experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/conditions/"
        "pilot-v6-task-0000-simulative.yaml",
        "experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/conditions/"
        "pilot-v6-task-0001-reactive.yaml",
        "experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/conditions/"
        "pilot-v6-task-0001-simulative.yaml",
        "src/giclab/harness/t09_sira_pilot.py",
        "tests/test_t09_retry3.py",
        "tests/test_t09_sira_pilot.py",
    }
)
ATTEMPT_EXPORT_REQUIRED_CONTROL_PATHS: Final = (
    "pilot-v6/provider-entry.json",
    "pilot-v6/frozen-run-manifest.json",
    "pilot-v6/postfreeze-validation.json",
    "pilot-v6/model-metadata-credential-scan.json",
    "pilot-v6/final-image-file-hashes/receipt.json",
    "pilot-v6/qualified-real-evidence-regression/receipt.json",
    "pilot-v6/local-finalizer-qualification.json",
    "pilot-v6/replacement-image-qualification/build-context-exclusions.json",
    "pilot-v6/pilot-state.json",
)


class T09HostError(RuntimeError):
    """The authorized host would violate its exact T09 contract."""


@contextlib.contextmanager
def hard_deadline(seconds: float, *, message: str) -> Iterator[None]:
    """Bound one synchronous evidence operation without creating a watchdog."""

    if not 0 < seconds <= MAX_CONDITION_WALL_SECONDS:
        raise T09HostError(message)
    previous_handler = signal.getsignal(signal.SIGALRM)

    def expired(_signum: int, _frame: object) -> None:
        raise T09HostError(message)

    signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")  # noqa: UP017


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1_048_576):
            digest.update(chunk)
    return digest.hexdigest()


def _open_parent_directory_no_follow(path: Path) -> tuple[int, str]:
    """Open every parent component without traversing a symlink."""

    if not path.is_absolute() or path.name in {"", ".", ".."}:
        raise T09HostError("archive staging paths must be absolute file paths")
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_CLOEXEC", 0)
    descriptor = os.open("/", flags)
    try:
        for component in path.parts[1:-1]:
            if component in {"", ".", ".."}:
                raise T09HostError("archive staging path contains an unsafe component")
            next_descriptor = os.open(
                component,
                flags | getattr(os, "O_NOFOLLOW", 0),
                dir_fd=descriptor,
            )
            os.close(descriptor)
            descriptor = next_descriptor
        return descriptor, path.name
    except BaseException:
        os.close(descriptor)
        raise


def _sha256_descriptor(descriptor: int) -> str:
    os.lseek(descriptor, 0, os.SEEK_SET)
    digest = hashlib.sha256()
    while chunk := os.read(descriptor, 1_048_576):
        digest.update(chunk)
    os.lseek(descriptor, 0, os.SEEK_SET)
    return digest.hexdigest()


def _copy_descriptor_exact(source: int, destination: int) -> int:
    copied = 0
    os.lseek(source, 0, os.SEEK_SET)
    while chunk := os.read(source, 1_048_576):
        offset = 0
        while offset < len(chunk):
            written = os.write(destination, chunk[offset:])
            if written <= 0:
                raise T09HostError("archive staging copy made no progress")
            offset += written
            copied += written
    return copied


def stage_verified_archive(
    source_path: Path,
    canonical_target_path: Path,
    expected_size: int,
    expected_sha256: str,
) -> dict[str, object]:
    """Stage one private archive by content, never by its operator pathname."""

    if (
        type(expected_size) is not int
        or expected_size <= 0
        or re.fullmatch(r"[a-f0-9]{64}", expected_sha256) is None
    ):
        raise T09HostError("archive staging expectation is invalid")
    source_parent, source_name = _open_parent_directory_no_follow(source_path)
    source_descriptor = -1
    target_parent = -1
    target_descriptor = -1
    target_name = ""
    target_created = False
    try:
        source_descriptor = os.open(
            source_name,
            os.O_RDONLY
            | getattr(os, "O_NONBLOCK", 0)
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_CLOEXEC", 0),
            dir_fd=source_parent,
        )
        source_before = os.fstat(source_descriptor)
        if not stat.S_ISREG(source_before.st_mode):
            raise T09HostError("archive staging source is not a regular file")
        if source_before.st_size != expected_size:
            raise T09HostError("archive staging source size drifted")
        if _sha256_descriptor(source_descriptor) != expected_sha256:
            raise T09HostError("archive staging source hash drifted")

        target_parent, target_name = _open_parent_directory_no_follow(canonical_target_path)
        target_descriptor = os.open(
            target_name,
            os.O_RDWR
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_CLOEXEC", 0),
            0o600,
            dir_fd=target_parent,
        )
        target_created = True
        os.fchmod(target_descriptor, 0o600)
        copied = _copy_descriptor_exact(source_descriptor, target_descriptor)
        os.fsync(target_descriptor)
        os.fsync(target_parent)
        target_metadata = os.fstat(target_descriptor)
        target_sha256 = _sha256_descriptor(target_descriptor)
        source_after = os.fstat(source_descriptor)
        source_identity_before = (
            source_before.st_dev,
            source_before.st_ino,
            source_before.st_size,
            source_before.st_mtime_ns,
            source_before.st_ctime_ns,
            source_before.st_mode,
        )
        source_identity_after = (
            source_after.st_dev,
            source_after.st_ino,
            source_after.st_size,
            source_after.st_mtime_ns,
            source_after.st_ctime_ns,
            source_after.st_mode,
        )
        if (
            copied != expected_size
            or not stat.S_ISREG(target_metadata.st_mode)
            or target_metadata.st_size != expected_size
            or stat.S_IMODE(target_metadata.st_mode) != 0o600
            or target_sha256 != expected_sha256
            or source_identity_after != source_identity_before
        ):
            raise T09HostError("archive staging target revalidation failed")
        return {
            "schema_version": "0.1.0",
            "archive_role": "historical-v4-real-evidence-regression",
            "source_provenance_category": "private-operator-run-owned-input",
            "source_absolute_path_retained": False,
            "source_no_follow_regular_file": True,
            "source_unchanged": True,
            "bytes": expected_size,
            "sha256": expected_sha256,
            "canonical_staged_destination": canonical_target_path.as_posix(),
            "exclusive_creation": True,
            "target_mode": "0600",
            "target_fsync": True,
            "parent_directory_fsync": True,
            "target_rehash_verified": True,
        }
    except BaseException:
        if target_created and target_parent >= 0 and target_name:
            with contextlib.suppress(OSError):
                os.unlink(target_name, dir_fd=target_parent)
                os.fsync(target_parent)
        raise
    finally:
        for descriptor in (target_descriptor, target_parent, source_descriptor, source_parent):
            if descriptor >= 0:
                with contextlib.suppress(OSError):
                    os.close(descriptor)


def git_file_sha256(repository: Path, commit: str, relative: str) -> str:
    retained = subprocess.run(
        ["git", "-C", str(repository), "show", f"{commit}:{relative}"],
        env=safe_environment(),
        stdin=subprocess.DEVNULL,
        capture_output=True,
        check=True,
        timeout=30,
    ).stdout
    return hashlib.sha256(retained).hexdigest()


def canonical_sha256(value: object) -> str:
    encoded = json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def load_object(path: Path, *, label: str) -> dict[str, Any]:
    value: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise T09HostError(f"{label} must be a string-keyed JSON object")
    return cast(dict[str, Any], value)


def _exact_keys(value: dict[str, Any], expected: set[str], *, label: str) -> None:
    if set(value) != expected:
        raise T09HostError(f"{label} fields drifted")


def _private_network_values(text: str) -> list[str]:
    hits: list[str] = []
    for match in _IPV4_TEXT.finditer(text):
        candidate = match.group(0)
        try:
            address = (
                ipaddress.ip_interface(candidate).ip
                if "/" in candidate
                else ipaddress.ip_address(candidate)
            )
        except ValueError:
            continue
        if not address.is_global:
            hits.append(candidate)
    return hits


def _stream_text_pattern_hits(path: Path) -> set[str]:
    labels: set[str] = set()
    overlap = b""
    with path.open("rb") as handle:
        while chunk := handle.read(MAX_PRIVACY_SCAN_CHUNK_BYTES):
            combined = overlap + chunk
            text = combined.decode("utf-8", errors="ignore")
            if _JUPYTER_URL.search(text):
                labels.add("jupyter-url")
            if _CREDENTIAL_TEXT.search(text):
                labels.add("credential-pattern")
            if _private_network_values(text):
                labels.add("private-network")
            overlap = combined[-4_096:]
    return labels


def _sensitive_json_paths(value: object, *, prefix: str = "$") -> list[str]:
    hits: list[str] = []
    if isinstance(value, dict):
        for raw_key, item in value.items():
            key = str(raw_key)
            path = f"{prefix}.{key}"
            if key.lower() in _SENSITIVE_JSON_KEYS and not (
                isinstance(item, dict)
                and item == {"reason": "structural-sensitive-field", "redacted": True}
            ):
                hits.append(path)
            hits.extend(_sensitive_json_paths(item, prefix=path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            hits.extend(_sensitive_json_paths(item, prefix=f"{prefix}[{index}]"))
    return hits


def privacy_violations(root: Path) -> list[str]:
    """Reject retained text/JSON that still contains explicitly prohibited values."""

    violations: list[str] = []
    for path in sorted(root.rglob("*")):
        if (
            not path.is_file()
            or path.is_symlink()
            or path.name.endswith(".tar.gz")
            or path.stat().st_size > MAX_PILOT_DISK_BYTES
        ):
            continue
        relative = path.relative_to(root).as_posix()
        for label in _stream_text_pattern_hits(path):
            violations.append(f"{relative}:{label}")
        if path.suffix == ".json" and path.stat().st_size <= MAX_PRIVACY_JSON_BYTES:
            try:
                value: object = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError):
                continue
            if _sensitive_json_paths(value):
                violations.append(f"{relative}:sensitive-json-field")
        elif path.suffix == ".jsonl":
            with path.open("rb") as handle:
                for raw_line in handle:
                    if len(raw_line) > MAX_PRIVACY_LINE_BYTES:
                        continue
                    try:
                        value = json.loads(raw_line)
                    except (UnicodeError, json.JSONDecodeError):
                        continue
                    if _sensitive_json_paths(value):
                        violations.append(f"{relative}:sensitive-json-field")
                        break
    return sorted(set(violations))


def write_exclusive(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    encoded = (json.dumps(value, allow_nan=False, indent=2, sort_keys=True) + "\n").encode()
    descriptor = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        offset = 0
        while offset < len(encoded):
            written = os.write(descriptor, encoded[offset:])
            if written <= 0:
                raise T09HostError("evidence write made no progress")
            offset += written
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    parent_descriptor = os.open(
        path.parent,
        os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_CLOEXEC", 0),
    )
    try:
        os.fsync(parent_descriptor)
    finally:
        os.close(parent_descriptor)


def write_bytes_exclusive(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        offset = 0
        while offset < len(value):
            written = os.write(descriptor, value[offset:])
            if written <= 0:
                raise T09HostError("binary evidence write made no progress")
            offset += written
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    parent_descriptor = os.open(
        path.parent,
        os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_CLOEXEC", 0),
    )
    try:
        os.fsync(parent_descriptor)
    finally:
        os.close(parent_descriptor)


def write_atomic(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    encoded = (json.dumps(value, allow_nan=False, indent=2, sort_keys=True) + "\n").encode()
    temporary = path.with_suffix(f".{os.getpid()}.tmp")
    descriptor = os.open(
        temporary,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        offset = 0
        while offset < len(encoded):
            written = os.write(descriptor, encoded[offset:])
            if written <= 0:
                raise T09HostError("atomic evidence write made no progress")
            offset += written
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    os.replace(temporary, path)
    parent_descriptor = os.open(
        path.parent,
        os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_CLOEXEC", 0),
    )
    try:
        os.fsync(parent_descriptor)
    finally:
        os.close(parent_descriptor)


def safe_environment() -> dict[str, str]:
    """Return the explicit nonsecret host subprocess environment."""

    environment: dict[str, str] = {}
    for name in (
        "DOCKER_CONFIG",
        "DOCKER_CONTEXT",
        "DOCKER_HOST",
        "DOCKER_TLS_VERIFY",
        "LANG",
        "LC_ALL",
        "PATH",
        "SSL_CERT_DIR",
        "SSL_CERT_FILE",
        "TMPDIR",
        "XDG_RUNTIME_DIR",
    ):
        value = os.environ.get(name)
        if value is not None:
            environment[name] = value
    environment.update(
        {
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_TERMINAL_PROMPT": "0",
            "PYTHONNOUSERSITE": "1",
        }
    )
    return environment


def output(argv: list[str], *, timeout: int = 30) -> str:
    result = subprocess.run(
        argv,
        env=safe_environment(),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
        timeout=timeout,
    )
    if result.returncode != 0:
        raise T09HostError(f"command failed ({result.returncode}): {argv[0]}")
    return result.stdout.decode("utf-8", errors="strict").strip()


def run_logged(
    argv: list[str],
    *,
    evidence_root: Path,
    label: str,
    timeout: int,
) -> None:
    evidence_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (
        (evidence_root / f"{label}.stdout").open("xb") as stdout,
        (evidence_root / f"{label}.stderr").open("xb") as stderr,
    ):
        result = subprocess.run(
            argv,
            env=safe_environment(),
            stdin=subprocess.DEVNULL,
            stdout=stdout,
            stderr=stderr,
            check=False,
            timeout=timeout,
        )
    if result.returncode != 0:
        raise T09HostError(f"command failed ({result.returncode}): {label}")


def docker_prefix() -> list[str]:
    for candidate in (["docker"], ["sudo", "-n", "docker"]):
        result = subprocess.run(
            [*candidate, "info"],
            env=safe_environment(),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=30,
        )
        if result.returncode == 0:
            return list(candidate)
    raise T09HostError("Docker is unavailable")


def image_id_if_present(prefix: list[str], reference: str) -> str | None:
    result = subprocess.run(
        [*prefix, "image", "inspect", "--format", "{{.Id}}", reference],
        env=safe_environment(),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
        timeout=30,
    )
    if result.returncode != 0:
        return None
    observed = result.stdout.decode("utf-8", errors="strict").strip()
    if re.fullmatch(r"sha256:[a-f0-9]{64}", observed) is None:
        raise T09HostError("Docker returned a malformed image identity")
    return observed


def held_descriptor_docker_path(prefix: list[str], descriptor: int) -> str:
    """Keep an already-validated archive descriptor visible across sudo Docker."""

    if descriptor < 0:
        raise T09HostError("held archive descriptor is invalid")
    if prefix == ["docker"]:
        return f"/proc/self/fd/{descriptor}"
    if prefix == ["sudo", "-n", "docker"]:
        # sudo closes inherited descriptors. Its root child can still open the
        # live parent Python process descriptor without re-resolving the private
        # operator-facing source path.
        return f"/proc/{os.getpid()}/fd/{descriptor}"
    raise T09HostError("Docker prefix cannot consume a held archive descriptor")


def _safe_extract_git_archive(archive: Path, destination: Path) -> None:
    destination.mkdir(mode=0o700)
    with tarfile.open(archive, "r:") as handle:
        members = handle.getmembers()
        for member in members:
            pure = PurePosixPath(member.name)
            if (
                pure.is_absolute()
                or not pure.parts
                or any(part in {"", ".", ".."} for part in pure.parts)
                or not (member.isfile() or member.isdir())
            ):
                raise T09HostError("historical source archive contains an unsafe member")
        handle.extractall(destination, members=members)


def _build_context_manifest(context: Path) -> dict[str, object]:
    files: list[dict[str, object]] = []
    total = 0
    for path in sorted(context.rglob("*")):
        relative = path.relative_to(context)
        lowered_parts = {part.lower() for part in relative.parts}
        if ".git" in lowered_parts or any(
            token in path.name.lower()
            for token in (".env", "credential", "api_key", "jupyter", ".token", "secret")
        ):
            raise T09HostError("replacement build context contains forbidden metadata")
        if path.is_symlink():
            raise T09HostError("replacement build context contains a symlink")
        metadata = path.stat(follow_symlinks=False)
        if path.is_dir():
            continue
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
            raise T09HostError("replacement build context contains a special or linked file")
        size = metadata.st_size
        total += size
        files.append(
            {
                "path": relative.as_posix(),
                "bytes": size,
                "mode": f"{stat.S_IMODE(metadata.st_mode):04o}",
                "mtime_epoch": int(metadata.st_mtime),
                "sha256": file_sha256(path),
            }
        )
    if not files or total > MAX_PILOT_DISK_BYTES:
        raise T09HostError("replacement build context is empty or exceeds the disk cap")
    return {
        "schema_version": "0.2.0",
        "qualification_id": QUALIFICATION_ID,
        "source_date_epoch": SOURCE_DATE_EPOCH,
        "files": files,
        "file_count": len(files),
        "total_bytes": total,
        "manifest_payload_sha256": canonical_sha256(files),
    }


def _exclude_pinned_nonruntime_env_example(
    upstream: Path,
    *,
    materialization: Path,
) -> dict[str, object]:
    """Remove only the exact pinned names-only example before fail-closed scanning."""

    path = upstream / ".env.example"
    metadata = path.stat(follow_symlinks=False)
    content = path.read_bytes()
    if (
        path.is_symlink()
        or not stat.S_ISREG(metadata.st_mode)
        or metadata.st_nlink != 1
        or metadata.st_size != PINNED_ENV_EXAMPLE_BYTES
        or content != PINNED_ENV_EXAMPLE_CONTENT
        or hashlib.sha256(content).hexdigest() != PINNED_ENV_EXAMPLE_SHA256
    ):
        raise T09HostError("pinned SiRA environment example identity or content drifted")
    receipt: dict[str, object] = {
        "schema_version": "0.1.0",
        "qualification_id": QUALIFICATION_ID,
        "source_commit": SIRA_COMMIT,
        "source_tree": SIRA_TREE,
        "path": ".env.example",
        "bytes": metadata.st_size,
        "sha256": PINNED_ENV_EXAMPLE_SHA256,
        "classification": "pinned-names-only-nonruntime-example-excluded",
        "contained_credential_value": False,
        "runtime_input": False,
        "scientific_input": False,
        "build_context_inclusion": False,
    }
    receipt_path = materialization / "build-context-exclusions.json"
    write_exclusive(receipt_path, receipt)
    path.unlink()
    directory_fd = os.open(upstream, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)
    if path.exists():
        raise T09HostError("excluded environment example still exists")
    return receipt


def _capture_optional_command(
    argv: list[str],
    *,
    evidence_root: Path,
    label: str,
) -> dict[str, object]:
    result = subprocess.run(
        argv,
        env=safe_environment(),
        stdin=subprocess.DEVNULL,
        capture_output=True,
        check=False,
        timeout=60,
    )
    receipt = {
        "argv": argv,
        "returncode": result.returncode,
        "stdout": result.stdout.decode("utf-8", errors="replace").strip(),
        "stderr": result.stderr.decode("utf-8", errors="replace").strip(),
    }
    write_exclusive(evidence_root / f"{label}.json", receipt)
    return receipt


def _copy_retained_prefix(source: Path, destination: Path, *, label: str) -> dict[str, object]:
    before = _retained_tree_manifest(source, label=label)
    shutil.copytree(source, destination, copy_function=shutil.copy2)
    after = _retained_tree_manifest(destination, label=f"copied {label}")
    if before != after:
        raise T09HostError(f"{label} changed during evidence retention")
    return before


def _slot2_authority_relative_paths(root: Path) -> tuple[str, ...]:
    """Return the exact manifest-bound slot-2 authority surface and reject extras."""

    root = root.resolve(strict=True)
    eligibility = root / "replacement-launch-eligibility.json"
    source_root = root / "slot2-eligibility-source"
    source_manifest_path = source_root / "source-manifest.json"
    source_manifest = load_object(source_manifest_path, label="slot-2 authority manifest")
    raw_files = source_manifest.get("files")
    if (
        source_manifest.get("schema_version") != "0.1.0"
        or source_manifest.get("plan_id") != PLAN_ID
        or source_manifest.get("host_run_id") != HOST_RUN_ID
        or not isinstance(raw_files, list)
        or source_manifest.get("file_count") != len(raw_files)
        or source_manifest.get("files_sha256")
        != hashlib.sha256(
            (
                json.dumps(
                    raw_files,
                    allow_nan=False,
                    ensure_ascii=False,
                    separators=(",", ":"),
                    sort_keys=True,
                )
                + "\n"
            ).encode()
        ).hexdigest()
    ):
        raise T09HostError("slot-2 authority manifest contract drifted")
    declared: list[str] = []
    total = 0
    for raw in raw_files:
        if not isinstance(raw, dict):
            raise T09HostError("slot-2 authority file record is malformed")
        relative_raw = raw.get("path")
        size = raw.get("bytes")
        digest = raw.get("sha256")
        if not isinstance(relative_raw, str):
            raise T09HostError("slot-2 authority file path is malformed")
        relative = PurePosixPath(relative_raw)
        if relative.is_absolute() or not relative.parts or ".." in relative.parts:
            raise T09HostError("slot-2 authority file escaped its source root")
        path = source_root.joinpath(*relative.parts)
        metadata = path.stat(follow_symlinks=False)
        if (
            path.is_symlink()
            or not stat.S_ISREG(metadata.st_mode)
            or metadata.st_uid != os.getuid()
            or metadata.st_nlink != 1
            or stat.S_IMODE(metadata.st_mode) != 0o600
            or type(size) is not int
            or metadata.st_size != size
            or not isinstance(digest, str)
            or re.fullmatch(r"[a-f0-9]{64}", digest) is None
            or file_sha256(path) != digest
        ):
            raise T09HostError("slot-2 authority file identity drifted")
        declared.append(relative.as_posix())
        total += metadata.st_size
    observed: set[str] = set()
    for path in source_root.rglob("*"):
        metadata = path.lstat()
        if stat.S_ISDIR(metadata.st_mode):
            continue
        if not stat.S_ISREG(metadata.st_mode) or path.is_symlink():
            raise T09HostError("slot-2 authority source contains an unsafe extra member")
        observed.add(path.relative_to(source_root).as_posix())
    expected = {*declared, "source-manifest.json"}
    if (
        len(declared) != len(set(declared))
        or observed != expected
        or source_manifest.get("total_bytes") != total
    ):
        raise T09HostError("slot-2 authority source member set drifted")
    for path in (eligibility, source_manifest_path):
        metadata = path.stat(follow_symlinks=False)
        if (
            path.is_symlink()
            or not stat.S_ISREG(metadata.st_mode)
            or metadata.st_uid != os.getuid()
            or metadata.st_nlink != 1
            or stat.S_IMODE(metadata.st_mode) != 0o600
        ):
            raise T09HostError("slot-2 authority control file is unsafe")
    return (
        "replacement-launch-eligibility.json",
        "slot2-eligibility-source/source-manifest.json",
        *(f"slot2-eligibility-source/{relative}" for relative in sorted(declared)),
    )


def retain_slot2_authority(source: Path, destination: Path) -> tuple[str, ...]:
    """Project only the source-manifest-bound authority into the pilot root."""

    source = source.resolve(strict=True)
    relative_paths = _slot2_authority_relative_paths(source)
    destination.mkdir(mode=0o700, parents=True, exist_ok=False)
    for relative in relative_paths:
        incoming = source / relative
        outgoing = destination / relative
        outgoing.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        with incoming.open("rb") as source_handle, outgoing.open("xb") as target_handle:
            shutil.copyfileobj(source_handle, target_handle, 1_048_576)
            target_handle.flush()
            os.fsync(target_handle.fileno())
        outgoing.chmod(0o600)
    if _slot2_authority_relative_paths(destination) != relative_paths:
        raise T09HostError("slot-2 authority changed during minimal retention")
    return relative_paths


def slot2_authority_binding(root: Path) -> dict[str, object]:
    """Return the exact, content-addressed slot-2 authority projection."""

    relative_paths = _slot2_authority_relative_paths(root)
    records = [
        {
            "path": relative,
            "bytes": (root / relative).stat().st_size,
            "sha256": file_sha256(root / relative),
        }
        for relative in relative_paths
    ]
    return {
        "relative_paths": list(relative_paths),
        "relative_paths_sha256": canonical_sha256(list(relative_paths)),
        "files": records,
        "files_sha256": canonical_sha256(records),
        "replacement_eligibility_sha256": file_sha256(root / "replacement-launch-eligibility.json"),
        "replacement_eligibility_source_manifest_sha256": file_sha256(
            root / "slot2-eligibility-source/source-manifest.json"
        ),
    }


def retain_prior_qualification_failures(
    *,
    artifact_root: Path,
    prior_artifact_root: Path,
    failed_candidate_root: Path,
    previous_transition_receipt: Path,
    package_transition_receipt: Path,
) -> dict[str, object]:
    destination = artifact_root / "pilot-v6/prior-qualification-failures"
    destination.mkdir(parents=True, mode=0o700)
    context_manifest = _copy_retained_prefix(
        prior_artifact_root,
        destination / "qualification-0002",
        label="context-rejection qualification prefix",
    )
    candidate_manifest = _copy_retained_prefix(
        failed_candidate_root,
        destination / "qualification-0003",
        label="offline-preflight candidate prefix",
    )
    transition_copies: dict[str, str] = {}
    for label, source in (
        ("transition-0003", previous_transition_receipt),
        ("transition-0004", package_transition_receipt),
    ):
        target = destination / f"{label}.json"
        shutil.copy2(source, target)
        metadata = target.stat(follow_symlinks=False)
        if (
            target.is_symlink()
            or not stat.S_ISREG(metadata.st_mode)
            or metadata.st_nlink != 1
            or stat.S_IMODE(metadata.st_mode) != 0o600
            or file_sha256(target) != file_sha256(source)
        ):
            raise T09HostError("package transition receipt copy drifted")
        transition_copies[label] = file_sha256(target)
    receipt: dict[str, object] = {
        "schema_version": "0.1.0",
        "plan_id": PLAN_ID,
        "host_run_id": HOST_RUN_ID,
        "accepted_qualification_id": QUALIFICATION_ID,
        "context_failure_manifest": context_manifest,
        "failed_candidate_manifest": candidate_manifest,
        "package_transition_receipts": transition_copies,
        "empirical_entry_crossed": False,
        "model_metadata_requests_before_acceptance": 0,
        "task_model_requests": 0,
        "task_browser_actions": 0,
        "additional_provider_launches": 0,
    }
    write_exclusive(destination / "retention-receipt.json", receipt)
    return receipt


def carry_forward_replacement_image(
    *,
    artifact_root: Path,
    failed_candidate_root: Path,
    prefix: list[str],
) -> dict[str, object]:
    failed = _failed_candidate_manifest(
        failed_candidate_root,
        require_image_present=True,
    )
    image_id = failed.get("replacement_image_id")
    if not isinstance(image_id, str) or image_id_if_present(prefix, image_id) != image_id:
        raise T09HostError("failed candidate image cannot be carried forward")
    source = failed_candidate_root / "pilot-v6/replacement-image-qualification"
    destination = artifact_root / "pilot-v6/replacement-image-qualification"
    _copy_retained_prefix(source, destination, label="failed candidate materialization")
    prior_receipt_path = destination / "receipt.json"
    prior_receipt = load_object(prior_receipt_path, label="carried candidate receipt")
    if (
        file_sha256(prior_receipt_path) != failed.get("materialization_receipt_sha256")
        or prior_receipt.get("image_id") != image_id
        or prior_receipt.get("build_count") != 1
    ):
        raise T09HostError("carried candidate materialization receipt drifted")
    prior_receipt_path.unlink()
    result: dict[str, object] = {
        **prior_receipt,
        "qualification_id": QUALIFICATION_ID,
        "method": "single-built-candidate-carried-forward-after-host-control-repair",
        "candidate_qualification_id": FAILED_CANDIDATE_QUALIFICATION_ID,
        "accepted_qualification_id": QUALIFICATION_ID,
        "candidate_materialization_receipt_sha256": failed["materialization_receipt_sha256"],
        "candidate_failure_manifest_sha256": canonical_sha256(failed),
        "build_count": 1,
        "additional_build_count": 0,
        "image_reused_by_exact_id": True,
        "empirical_entry_before_carry_forward": False,
    }
    write_exclusive(prior_receipt_path, result)
    return result


def materialize_replacement_image(
    *,
    repository: Path,
    artifact_root: Path,
    prefix: list[str],
) -> dict[str, object]:
    if image_id_if_present(prefix, REPLACEMENT_IMAGE_TAG) is not None:
        raise T09HostError("replacement image tag already exists; exactly one build is allowed")

    materialization = artifact_root / "pilot-v6/replacement-image-qualification"
    logs = materialization / "logs"
    work = materialization / "work"
    snapshot = work / "snapshot"
    context = work / "build-context"
    work.mkdir(parents=True, mode=0o700)
    context.mkdir(mode=0o700)
    archive = work / "t07-source.tar"
    historical_paths = [
        "containers/sira-smoke/pragmatic/Containerfile.amd64",
        "containers/sira-smoke/sira-immutable-model-routing.patch",
        "containers/sira-smoke/container_entrypoint.py",
        "containers/sira-smoke/bounded/model_preflight.py",
        "containers/sira-smoke/bounded/browser_preflight.py",
        "containers/sira-smoke/pragmatic/runtime_preflight.py",
        "containers/sira-smoke/fixtures/static.html",
        "src/giclab",
    ]
    run_logged(
        [
            "git",
            "-C",
            str(repository),
            "archive",
            "--format=tar",
            f"--output={archive}",
            T07_EXECUTION_COMMIT,
            *historical_paths,
        ],
        evidence_root=logs,
        label="historical-source-archive",
        timeout=120,
    )
    _safe_extract_git_archive(archive, snapshot)
    copies = {
        "containers/sira-smoke/pragmatic/Containerfile.amd64": "Containerfile",
        "containers/sira-smoke/sira-immutable-model-routing.patch": (
            "sira-immutable-model-routing.patch"
        ),
        "containers/sira-smoke/container_entrypoint.py": "container_entrypoint.py",
        "containers/sira-smoke/bounded/model_preflight.py": "model_preflight.py",
        "containers/sira-smoke/bounded/browser_preflight.py": "browser_preflight.py",
        "containers/sira-smoke/pragmatic/runtime_preflight.py": "runtime_preflight.py",
        "containers/sira-smoke/fixtures/static.html": "static.html",
    }
    for source, destination in copies.items():
        shutil.copy2(snapshot / source, context / destination)
    shutil.copytree(snapshot / "src/giclab", context / "giclab")
    vendor = context / "vendor"
    vendor.mkdir(mode=0o700)
    upstream = context / "upstream"
    run_logged(
        ["git", "init", str(upstream)],
        evidence_root=logs,
        label="sira-init",
        timeout=30,
    )
    run_logged(
        [
            "git",
            "-C",
            str(upstream),
            "remote",
            "add",
            "origin",
            "https://github.com/sailing-lab/sira.git",
        ],
        evidence_root=logs,
        label="sira-remote",
        timeout=30,
    )
    run_logged(
        ["git", "-C", str(upstream), "fetch", "--depth", "1", "origin", SIRA_COMMIT],
        evidence_root=logs,
        label="sira-fetch",
        timeout=300,
    )
    run_logged(
        ["git", "-C", str(upstream), "checkout", "--detach", "FETCH_HEAD"],
        evidence_root=logs,
        label="sira-checkout",
        timeout=60,
    )
    if output(["git", "-C", str(upstream), "rev-parse", "HEAD"]) != SIRA_COMMIT:
        raise T09HostError("pinned SiRA commit did not materialize")
    if output(["git", "-C", str(upstream), "rev-parse", "HEAD^{tree}"]) != SIRA_TREE:
        raise T09HostError("pinned SiRA tree did not materialize")
    # Git object/ref/log metadata is not a scientific runtime input and contains
    # fetch-time state.  Retain the verified commit/tree identities in the receipt,
    # then exclude that nondeterministic metadata from the complete build context.
    shutil.rmtree(upstream / ".git")
    exclusion = _exclude_pinned_nonruntime_env_example(
        upstream,
        materialization=materialization,
    )
    wheel = vendor / "uv-0.11.7-py3-none-manylinux_2_17_x86_64.manylinux2014_x86_64.whl"
    run_logged(
        [
            "curl",
            "--fail",
            "--location",
            "--silent",
            "--show-error",
            "--retry",
            "0",
            "--max-time",
            "300",
            "--output",
            str(wheel),
            UV_URL,
        ],
        evidence_root=logs,
        label="uv-download",
        timeout=330,
    )
    exact_files = {
        wheel: UV_SHA256,
        context / "sira-immutable-model-routing.patch": T07_ROUTING_PATCH_SHA256,
        context / "giclab/harness/sira_gate_a_runtime.py": T07_RUNTIME_SHA256,
        context / "runtime_preflight.py": T07_RUNTIME_PREFLIGHT_SHA256,
    }
    for path, expected in exact_files.items():
        if file_sha256(path) != expected:
            raise T09HostError(f"historical build input hash drifted: {path.name}")
    # Normalize the build-context clock after every source identity has been verified.
    # This reduces creation-time drift without treating bit reproduction as acceptance.
    for path in sorted(context.rglob("*"), reverse=True):
        os.utime(path, (SOURCE_DATE_EPOCH, SOURCE_DATE_EPOCH), follow_symlinks=False)
    os.utime(context, (SOURCE_DATE_EPOCH, SOURCE_DATE_EPOCH), follow_symlinks=False)
    context_manifest = _build_context_manifest(context)
    context_manifest_path = materialization / "build-context-manifest.json"
    write_exclusive(context_manifest_path, context_manifest)
    docker_version = _capture_optional_command(
        [*prefix, "version", "--format", "{{json .}}"],
        evidence_root=materialization,
        label="docker-version",
    )
    buildkit_version = _capture_optional_command(
        [*prefix, "buildx", "version"],
        evidence_root=materialization,
        label="buildkit-version",
    )
    build_argv = [
        *prefix,
        "build",
        "--pull=false",
        "--progress=plain",
        "--build-arg",
        f"RUNTIME_PREFLIGHT_SHA256={T07_RUNTIME_PREFLIGHT_SHA256}",
        "--build-arg",
        "PYTHON_RUNTIME_VERSION=3.11.14",
        "--build-arg",
        f"SOURCE_DATE_EPOCH={SOURCE_DATE_EPOCH}",
        "--tag",
        REPLACEMENT_IMAGE_TAG,
        "--file",
        str(context / "Containerfile"),
        str(context),
    ]
    write_exclusive(
        materialization / "build-command.json",
        {
            "argv": build_argv,
            "argv_sha256": canonical_sha256(build_argv),
            "source_date_epoch": SOURCE_DATE_EPOCH,
            "network_fetches": {
                "sira_commit": SIRA_COMMIT,
                "uv_wheel_url": UV_URL,
                "uv_wheel_sha256": UV_SHA256,
            },
        },
    )
    run_logged(
        build_argv,
        evidence_root=logs,
        label="docker-build",
        timeout=3_600,
    )
    built = image_id_if_present(prefix, REPLACEMENT_IMAGE_TAG)
    if built is None:
        raise T09HostError("replacement build did not create its exact image")
    run_logged(
        [*prefix, "image", "inspect", built],
        evidence_root=materialization,
        label="replacement-image-inspect",
        timeout=60,
    )
    result: dict[str, object] = {
        "schema_version": "0.1.0",
        "qualification_id": QUALIFICATION_ID,
        "method": "single-replacement-build-from-pinned-reviewed-inputs",
        "image_id": built,
        "historical_image_id": HISTORICAL_IMAGE_ID,
        "image_digest_equality_required": False,
        "base_image_identity": BASE_IMAGE_IDENTITY,
        "historical_source_commit": T07_EXECUTION_COMMIT,
        "repository_runtime_commit": output(["git", "-C", str(repository), "rev-parse", "HEAD"]),
        "sira_commit": SIRA_COMMIT,
        "sira_tree": SIRA_TREE,
        "python_version": "3.11.14",
        "containerfile_sha256": file_sha256(context / "Containerfile"),
        "build_context_manifest_sha256": file_sha256(context_manifest_path),
        "build_context_payload_sha256": context_manifest["manifest_payload_sha256"],
        "build_context_exclusions_sha256": file_sha256(
            materialization / "build-context-exclusions.json"
        ),
        "build_context_exclusion_classification": exclusion["classification"],
        "build_command_sha256": file_sha256(materialization / "build-command.json"),
        "image_inspect_sha256": file_sha256(materialization / "replacement-image-inspect.stdout"),
        "runtime_sha256": T07_RUNTIME_SHA256,
        "runtime_preflight_sha256": T07_RUNTIME_PREFLIGHT_SHA256,
        "routing_patch_sha256": T07_ROUTING_PATCH_SHA256,
        "uv_wheel_sha256": UV_SHA256,
        "sira_uv_lock_sha256": file_sha256(context / "upstream/uv.lock"),
        "entrypoint_sha256": file_sha256(context / "container_entrypoint.py"),
        "model_preflight_sha256": file_sha256(context / "model_preflight.py"),
        "browser_preflight_sha256": file_sha256(context / "browser_preflight.py"),
        "evaluator_code_sha256": file_sha256(context / "upstream/evaluation/fanout/evaluator.py"),
        "evaluator_run_sha256": file_sha256(context / "upstream/evaluation/fanout/run.py"),
        "workdir": "/opt/sira",
        "entrypoint_contract": "/opt/giclab/container_entrypoint.py",
        "runtime_environment_contract": "reviewed-Containerfile-exact-environment-v1",
        "source_date_epoch": SOURCE_DATE_EPOCH,
        "docker_version_receipt_sha256": file_sha256(materialization / "docker-version.json"),
        "docker_version_available": docker_version["returncode"] == 0,
        "buildkit_version_receipt_sha256": file_sha256(materialization / "buildkit-version.json"),
        "buildkit_version_available": buildkit_version["returncode"] == 0,
        "build_count": 1,
    }
    write_exclusive(materialization / "receipt.json", result)
    shutil.rmtree(work)
    return result


def materialize_retained_or_build_image(
    *,
    repository: Path,
    package_commit: str,
    artifact_root: Path,
    image_archive: Path,
    prefix: list[str],
    materialization_policy: str,
) -> dict[str, object]:
    """Materialize under the source-bound launch-slot policy."""

    if materialization_policy not in {
        SLOT1_IMAGE_MATERIALIZATION_POLICY,
        SLOT2_IMAGE_MATERIALIZATION_POLICY,
    }:
        raise T09HostError("image materialization policy is invalid")

    if image_id_if_present(prefix, REPLACEMENT_IMAGE_TAG) is not None:
        raise T09HostError("V6 image tag already exists before materialization")
    materialization = artifact_root / "pilot-v6/replacement-image-qualification"
    logs = materialization / "logs"
    materialization.mkdir(parents=True, mode=0o700)
    archive_valid = False
    archive_reason = "unavailable"
    archive_descriptor = -1
    archive_parent_descriptor = -1
    archive_identity: tuple[int, int, int, int, int, int] | None = None
    try:
        archive_parent_descriptor, archive_name = _open_parent_directory_no_follow(image_archive)
        archive_descriptor = os.open(
            archive_name,
            os.O_RDONLY
            | getattr(os, "O_NONBLOCK", 0)
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_CLOEXEC", 0),
            dir_fd=archive_parent_descriptor,
        )
        metadata = os.fstat(archive_descriptor)
        archive_identity = (
            metadata.st_dev,
            metadata.st_ino,
            metadata.st_size,
            metadata.st_mtime_ns,
            metadata.st_ctime_ns,
            metadata.st_mode,
        )
        archive_valid = (
            stat.S_ISREG(metadata.st_mode)
            and metadata.st_uid == os.getuid()
            and metadata.st_nlink == 1
            and stat.S_IMODE(metadata.st_mode) == 0o600
            and metadata.st_size == RETAINED_IMAGE_ARCHIVE_BYTES
            and _sha256_descriptor(archive_descriptor) == RETAINED_IMAGE_ARCHIVE_SHA256
        )
        archive_reason = "verified" if archive_valid else "identity-mismatch"
    except (FileNotFoundError, OSError, T09HostError):
        archive_reason = "unavailable-or-unsafe"
    if not archive_valid:
        if archive_descriptor >= 0:
            os.close(archive_descriptor)
            archive_descriptor = -1
        if archive_parent_descriptor >= 0:
            os.close(archive_parent_descriptor)
            archive_parent_descriptor = -1
    try:
        write_exclusive(
            materialization / "retained-image-input.json",
            {
                "schema_version": "0.1.0",
                "archive_role": "retry3-qualified-candidate-image",
                "archive_path_retained": False,
                "expected_bytes": RETAINED_IMAGE_ARCHIVE_BYTES,
                "expected_sha256": RETAINED_IMAGE_ARCHIVE_SHA256,
                "expected_image_id": RETAINED_IMAGE_ID,
                "validation": archive_reason,
                "materialization_policy": materialization_policy,
            },
        )
    except BaseException:
        if archive_descriptor >= 0:
            os.close(archive_descriptor)
        if archive_parent_descriptor >= 0:
            os.close(archive_parent_descriptor)
        raise
    if archive_valid:
        assert archive_descriptor >= 0
        assert archive_identity is not None
        try:
            try:
                load = subprocess.run(
                    [
                        *prefix,
                        "load",
                        "--input",
                        held_descriptor_docker_path(prefix, archive_descriptor),
                    ],
                    env=safe_environment(),
                    stdin=subprocess.DEVNULL,
                    capture_output=True,
                    check=False,
                    pass_fds=(archive_descriptor,),
                    timeout=min(
                        MAX_IMAGE_EXPORT_SECONDS,
                        max(1.0, preflight_seconds_remaining(artifact_root)),
                    ),
                )
            except subprocess.TimeoutExpired as exc:
                load = subprocess.CompletedProcess(
                    args=exc.cmd,
                    returncode=124,
                    stdout=exc.stdout or b"",
                    stderr=exc.stderr or b"docker load timed out",
                )
            archive_after = os.fstat(archive_descriptor)
            archive_unchanged = (
                archive_identity
                == (
                    archive_after.st_dev,
                    archive_after.st_ino,
                    archive_after.st_size,
                    archive_after.st_mtime_ns,
                    archive_after.st_ctime_ns,
                    archive_after.st_mode,
                )
                and _sha256_descriptor(archive_descriptor) == RETAINED_IMAGE_ARCHIVE_SHA256
            )
        finally:
            os.close(archive_descriptor)
            archive_descriptor = -1
            os.close(archive_parent_descriptor)
            archive_parent_descriptor = -1
        write_bytes_exclusive(logs / "docker-image-import.stdout", load.stdout)
        write_bytes_exclusive(logs / "docker-image-import.stderr", load.stderr)
        write_exclusive(
            logs / "docker-image-import.json",
            {"argv_role": "docker-load-exact-retained-archive", "returncode": load.returncode},
        )
        imported = image_id_if_present(prefix, RETAINED_IMAGE_ID)
        if load.returncode == 0 and archive_unchanged and imported == RETAINED_IMAGE_ID:
            run_logged(
                [*prefix, "tag", imported, REPLACEMENT_IMAGE_TAG],
                evidence_root=logs,
                label="docker-image-retag",
                timeout=60,
            )
            run_logged(
                [*prefix, "image", "inspect", imported],
                evidence_root=materialization,
                label="replacement-image-inspect",
                timeout=60,
            )
            context_receipt = {
                "schema_version": "0.1.0",
                "classification": "retained-image-import-no-new-build-context",
                "archive_sha256": RETAINED_IMAGE_ARCHIVE_SHA256,
                "archive_bytes": RETAINED_IMAGE_ARCHIVE_BYTES,
                "image_id": imported,
            }
            write_exclusive(materialization / "build-context-manifest.json", context_receipt)
            write_exclusive(
                materialization / "build-context-exclusions.json",
                {**context_receipt, "exclusions": "not-applicable-no-new-build"},
            )
            result: dict[str, object] = {
                "schema_version": "0.1.0",
                "qualification_id": QUALIFICATION_ID,
                "method": "exact-retained-image-archive-import",
                "image_id": imported,
                "historical_image_id": HISTORICAL_IMAGE_ID,
                "repository_runtime_commit": package_commit,
                "build_context_manifest_sha256": file_sha256(
                    materialization / "build-context-manifest.json"
                ),
                "build_context_payload_sha256": canonical_sha256(context_receipt),
                "build_context_exclusions_sha256": file_sha256(
                    materialization / "build-context-exclusions.json"
                ),
                "containerfile_sha256": None,
                "build_command_sha256": None,
                "image_inspect_sha256": file_sha256(
                    materialization / "replacement-image-inspect.stdout"
                ),
                "retained_image_archive_sha256": RETAINED_IMAGE_ARCHIVE_SHA256,
                "retained_image_archive_bytes": RETAINED_IMAGE_ARCHIVE_BYTES,
                "build_count": 0,
                "additional_build_count": 0,
                "image_import_count": 1,
                "image_materialization_policy": materialization_policy,
            }
            write_exclusive(materialization / "receipt.json", result)
            return result
        # A failed/incompatible load may have left the expected image behind.  It
        # cannot silently become the accepted image; remove only the exact known
        # candidate before the one authorized fallback build.
        if imported is not None:
            subprocess.run(
                [*prefix, "image", "rm", "--force", imported],
                env=safe_environment(),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                timeout=60,
            )
        if materialization_policy == SLOT2_IMAGE_MATERIALIZATION_POLICY:
            raise T09HostError("slot-2 retained image import failed; fallback build is forbidden")
    if archive_descriptor >= 0:
        os.close(archive_descriptor)
    if archive_parent_descriptor >= 0:
        os.close(archive_parent_descriptor)
    if materialization_policy == SLOT2_IMAGE_MATERIALIZATION_POLICY:
        raise T09HostError("slot-2 retained image is unavailable; fallback build is forbidden")
    built = materialize_replacement_image(
        repository=repository,
        artifact_root=artifact_root,
        prefix=prefix,
    )
    built["image_import_count"] = 0
    built["additional_build_count"] = 0
    built["retained_image_archive_validation"] = archive_reason
    built["image_materialization_policy"] = materialization_policy
    receipt_path = artifact_root / "pilot-v6/replacement-image-qualification/receipt.json"
    receipt_path.unlink()
    write_exclusive(receipt_path, built)
    return built


def remove_container(prefix: list[str], name: str) -> bool:
    result = subprocess.run(
        [*prefix, "rm", "--force", name],
        env=safe_environment(),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
        timeout=30,
    )
    return result.returncode == 0


def owned_containers(prefix: list[str]) -> list[str]:
    raw = output([*prefix, "ps", "--all", "--format", "{{.Names}}"])
    return sorted(name for name in raw.splitlines() if name.startswith(CONTAINER_PREFIX))


def tree_bytes(root: Path) -> int:
    total = 0
    if not root.exists():
        return 0
    for directory, _, names in os.walk(root):
        for name in names:
            path = Path(directory) / name
            if not path.is_symlink():
                try:
                    total += path.stat().st_size
                except FileNotFoundError:
                    continue
    return total


def validate_secret_metadata(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_uid != os.getuid()
            or metadata.st_nlink != 1
            or stat.S_IMODE(metadata.st_mode) != 0o600
            or not 16 <= metadata.st_size <= 16_384
        ):
            raise T09HostError("provider credential metadata is unsafe")
    finally:
        os.close(descriptor)


def validate_secret(path: Path) -> bytes:
    validate_secret_metadata(path)
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        value = os.read(descriptor, 16_385)
    finally:
        os.close(descriptor)
    if not 16 <= len(value) <= 16_384:
        raise T09HostError("provider credential is malformed")
    return value


def destroy_secret(path: Path) -> bool:
    try:
        descriptor = os.open(
            path,
            os.O_RDWR | getattr(os, "O_NOFOLLOW", 0),
        )
    except FileNotFoundError:
        return True
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
            return False
        remaining = metadata.st_size
        os.lseek(descriptor, 0, os.SEEK_SET)
        zero = b"\0" * min(65_536, max(remaining, 1))
        while remaining:
            written = os.write(descriptor, zero[: min(remaining, len(zero))])
            if written <= 0:
                return False
            remaining -= written
        os.ftruncate(descriptor, 0)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    path.unlink()
    return not path.exists()


def secret_hits(root: Path, secret: bytes) -> list[str]:
    hits: list[str] = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and not path.is_symlink() and path.stat().st_size <= MAX_PILOT_DISK_BYTES:
            with path.open("rb") as handle:
                overlap = b""
                while chunk := handle.read(1_048_576):
                    combined = overlap + chunk
                    if secret in combined:
                        hits.append(path.relative_to(root).as_posix())
                        break
                    overlap = combined[-(len(secret) - 1) :] if len(secret) > 1 else b""
    return hits


def record_preflight_credential_scan(
    *,
    artifact_root: Path,
    secret_file: Path,
    execution_contract_sha256: str,
) -> dict[str, object]:
    """Scan after the sole metadata GET and permanently stop on any exact match."""

    credential = validate_secret(secret_file)
    hits = secret_hits(artifact_root, credential)
    removed: list[dict[str, object]] = []
    for relative in hits:
        target = artifact_root / relative
        if target.is_file() and not target.is_symlink():
            removed.append(
                {
                    "path": relative,
                    "bytes": target.stat().st_size,
                    "classification": "exact-secret-bearing-artifact-removed",
                }
            )
            target.unlink()
    remaining = secret_hits(artifact_root, credential)
    credential = b""
    exposure_detected = bool(hits)
    if exposure_detected:
        mark_actual_credential_exposure(
            artifact_root / "pilot-v6/pilot-state.json",
            execution_contract_sha256=execution_contract_sha256,
        )
    receipt: dict[str, object] = {
        "schema_version": "0.1.0",
        "scan_point": "immediately-after-sole-model-metadata-get-before-freeze",
        "actual_credential_exposure_detected": exposure_detected,
        "secret_bearing_artifacts_removed": removed,
        "remaining_exact_secret_matches": remaining,
        "exact_secret_scan_passed": not exposure_detected and not remaining,
        "empirical_entry_permitted": not exposure_detected and not remaining,
        "recorded_at": utc_now(),
    }
    write_exclusive(
        artifact_root / "pilot-v6/model-metadata-credential-scan.json",
        receipt,
    )
    if exposure_detected or remaining:
        raise T09HostError(
            "model-metadata preflight exposed the exact credential; "
            "cleanup and termination are required"
        )
    return receipt


def contract_paths(repository: Path) -> dict[str, Path]:
    experiment = repository / "experiments/EXP-0001-sira-simulative-vs-reactive"
    return {
        "plan": experiment / "run-plans/pilot.yaml",
        "execution": experiment / "contracts/T09_PILOT_EXECUTION_CONTRACT.json",
        "commands": experiment / "contracts/T09_PILOT_COMMAND_MANIFESTS.json",
        "conditions": experiment / "run-plans/conditions",
        "dataset": experiment / "contracts/T09_PILOT_DATASET_CONTRACT.json",
        "evaluator": experiment / "contracts/T09_PILOT_EVALUATOR_CONTRACT.json",
        "runtime": experiment / "contracts/T09_PILOT_RUNTIME_IDENTITY.json",
        "real_regression": experiment / "T09_PRAGMATIC_RETRY4_FINALIZER_REGRESSION.json",
    }


def validate_real_evidence_regression(
    repository: Path,
    *,
    expected_finalizer_source_sha256: str | None = None,
) -> dict[str, Any]:
    """Validate the sanitized prelaunch receipt from the immutable V4 archive."""

    paths = contract_paths(repository)
    receipt = load_object(paths["real_regression"], label="real-evidence finalizer regression")
    semantic = receipt.get("semantic_projection")
    evaluator_closure = receipt.get("evaluator_closure")
    repeat_roots = receipt.get("deterministic_distinct_finalization_roots")
    if (
        receipt.get("schema_version") != "0.1.0"
        or receipt.get("receipt_id") != "T09-PRAGMATIC-RETRY4-REAL-EVIDENCE-REGRESSION-0001"
        or receipt.get("source_plan_id") != "PLAN-EXP0001-PILOT-V4"
        or receipt.get("source_run_id") != "RUN-T09-TASK-A-REACTIVE-0002"
        or receipt.get("source_archive_sha256")
        != "63ed19b35bcb4cb62c3796a80a48004937340eb3826f9657a1006e251772255d"
        or receipt.get("source_public_disposition_sha256")
        != "ecc0e135695e16f68d52b7aa85b70d42b1f1e945f7dd119fb7c7ff0e42fc8231"
        or receipt.get("finalizer_source_sha256")
        != (
            expected_finalizer_source_sha256
            if expected_finalizer_source_sha256 is not None
            else file_sha256(repository / FINALIZER_RELATIVE_PATH)
        )
        or receipt.get("dataset_sha256")
        != "359300b029c6891567816f351bf8786e9b018d7af8a1a44b7da9ba5ef4651288"
        or receipt.get("dataset_bytes") != 1_177_174
        or not isinstance(evaluator_closure, dict)
        or evaluator_closure.get("evaluator_contract_sha256") != file_sha256(paths["evaluator"])
        or evaluator_closure.get("dependency_package_manifest_sha256")
        != canonical_sha256(expected_evaluator_packages(repository))
        or not isinstance(repeat_roots, list)
        or len(repeat_roots) != 2
        or any(
            not isinstance(item, dict)
            or item.get("semantic_projection_sha256") != canonical_sha256(semantic)
            for item in repeat_roots
        )
        or repeat_roots[0].get("root") == repeat_roots[1].get("root")
        or not isinstance(semantic, dict)
        or semantic.get("task_id") != "7dcbbbdc7f1120cd"
        or semantic.get("condition") != "SIRA-REACTIVE"
        or semantic.get("model_revision") != "gpt-4o-2024-11-20"
        or semantic.get("sira_commit") != SIRA_COMMIT
        or semantic.get("task_completed") is not True
        or semantic.get("answer_produced") is not True
        or semantic.get("evaluator_valid") is not True
        or semantic.get("score") != 0.0
        or semantic.get("provider_call_count") != 52
        or semantic.get("browser_action_count") != 13
        or receipt.get("accepted_scientific_and_evaluator_fields_equal") is not True
        or receipt.get("network_disabled") is not True
        or receipt.get("additional_model_requests") != 0
        or receipt.get("additional_browser_actions") != 0
        or receipt.get("source_raw_mutated") is not False
        or receipt.get("prior_attempt_excluded_from_v6_campaign") is not True
        or receipt.get("private_source_path_retained") is not False
    ):
        raise T09HostError("real-evidence finalizer regression receipt drifted")
    return receipt


def _retained_tree_manifest(root: Path, *, label: str) -> dict[str, object]:
    files: list[dict[str, object]] = []
    total = 0
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise T09HostError(f"{label} contains a symlink")
        metadata = path.stat(follow_symlinks=False)
        if path.is_dir():
            continue
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
            raise T09HostError(f"{label} contains an unsafe file")
        total += metadata.st_size
        if total > MAX_PILOT_DISK_BYTES:
            raise T09HostError(f"{label} exceeds the retained-evidence cap")
        files.append(
            {
                "path": path.relative_to(root).as_posix(),
                "bytes": metadata.st_size,
                "sha256": file_sha256(path),
            }
        )
    if not files:
        raise T09HostError(f"{label} is empty")
    return {
        "files": files,
        "file_count": len(files),
        "total_bytes": total,
        "files_sha256": canonical_sha256(files),
    }


def _prior_qualification_failure_manifest(root: Path) -> dict[str, object]:
    if root.name != "t09-pilot-v6-output-0002":
        raise T09HostError("prior qualification root identity drifted")
    state_path = root / "pilot-v6/pilot-state.json"
    state = load_object(state_path, label="prior qualification state")
    env_example = (
        root / "pilot-v6/replacement-image-qualification/work/build-context/upstream/.env.example"
    )
    if (
        state.get("plan_id") != PLAN_ID
        or state.get("empirical_attempts_entered") != []
        or state.get("attempts_completed") != []
        or not env_example.is_file()
        or env_example.stat(follow_symlinks=False).st_size != PINNED_ENV_EXAMPLE_BYTES
        or file_sha256(env_example) != PINNED_ENV_EXAMPLE_SHA256
        or (root / "pilot-v6/frozen-run-manifest.json").exists()
        or (root / "pilot-v6/replacement-image-qualification/build-context-manifest.json").exists()
    ):
        raise T09HostError("prior qualification failure prefix is not the exact safe prefix")
    retained = _retained_tree_manifest(root, label="prior qualification prefix")
    return {
        "root_name": root.name,
        "qualification_id": CONTEXT_FAILURE_QUALIFICATION_ID,
        "classification": "preentry-pinned-names-only-env-example-rejected",
        "empirical_entry_crossed": False,
        "model_metadata_requests": 0,
        "task_model_requests": 0,
        "task_browser_actions": 0,
        "replacement_image_built": False,
        **retained,
    }


def _failed_candidate_manifest(
    root: Path,
    *,
    require_image_present: bool,
) -> dict[str, object]:
    if root.name != "t09-pilot-v6-output-0003":
        raise T09HostError("failed candidate root identity drifted")
    state = load_object(root / "pilot-v6/pilot-state.json", label="failed candidate state")
    qualification_root = root / "pilot-v6/replacement-image-qualification"
    receipt_path = qualification_root / "receipt.json"
    receipt = load_object(receipt_path, label="failed candidate materialization receipt")
    stderr_path = root / "pilot-v6/offline-runtime-preflight/offline-preflight.stderr"
    provider_entry = load_object(
        root / "pilot-v6/provider-entry.json", label="prior provider entry"
    )
    image_id = receipt.get("image_id")
    if (
        state.get("plan_id") != PLAN_ID
        or state.get("empirical_attempts_entered") != []
        or state.get("attempts_completed") != []
        or receipt.get("qualification_id") != FAILED_CANDIDATE_QUALIFICATION_ID
        or receipt.get("build_count") != 1
        or not isinstance(image_id, str)
        or re.fullmatch(r"sha256:[a-f0-9]{64}", image_id) is None
        or receipt.get("build_context_exclusions_sha256")
        != file_sha256(qualification_root / "build-context-exclusions.json")
        or file_sha256(stderr_path) != FAILED_CANDIDATE_OFFLINE_STDERR_SHA256
        or "ModuleNotFoundError: No module named 'yaml'"
        not in stderr_path.read_text(encoding="utf-8")
        or (root / "pilot-v6/frozen-run-manifest.json").exists()
        or (root / "pilot-v6/preflight.json").exists()
        or (root / "pilot-v6/model-metadata-preflight").exists()
        or (root / "pilot-v6/browser-preflight").exists()
    ):
        raise T09HostError("failed candidate prefix is not the exact safe offline failure")
    if require_image_present and (
        image_id_if_present(docker_prefix(), REPLACEMENT_IMAGE_TAG) != image_id
        or image_id_if_present(docker_prefix(), image_id) != image_id
    ):
        raise T09HostError("failed candidate image is unavailable or tag-drifted")
    retained = _retained_tree_manifest(root, label="failed candidate prefix")
    return {
        "root_name": root.name,
        "qualification_id": FAILED_CANDIDATE_QUALIFICATION_ID,
        "classification": "preentry-offline-control-interpreter-missing-pyyaml",
        "empirical_entry_crossed": False,
        "model_metadata_requests": 0,
        "task_model_requests": 0,
        "task_browser_actions": 0,
        "replacement_image_built": True,
        "replacement_image_id": image_id,
        "materialization_receipt_sha256": file_sha256(receipt_path),
        "offline_failure_stderr_sha256": file_sha256(stderr_path),
        "previous_package_transition_receipt_sha256": provider_entry.get(
            "package_transition_receipt_sha256"
        ),
        **retained,
    }


def _git_transition_fields(
    repository: Path,
    *,
    to_package_commit: str,
) -> dict[str, object]:
    ancestry = subprocess.run(
        [
            "git",
            "-C",
            str(repository),
            "merge-base",
            "--is-ancestor",
            PACKAGE_TRANSITION_FROM_COMMIT,
            to_package_commit,
        ],
        env=safe_environment(),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
        timeout=30,
    )
    if ancestry.returncode != 0:
        raise T09HostError("transition package is not a descendant of the launched package")
    changed_raw = output(
        [
            "git",
            "-C",
            str(repository),
            "diff",
            "--name-only",
            "--diff-filter=ACMRT",
            PACKAGE_TRANSITION_FROM_COMMIT,
            to_package_commit,
        ]
    )
    changed_paths = sorted(line for line in changed_raw.splitlines() if line)
    if (
        not changed_paths
        or not set(changed_paths).issubset(PACKAGE_TRANSITION_ALLOWED_PATHS)
        or "containers/sira-smoke/pragmatic/t09_remote_runner.py" not in changed_paths
        or "src/giclab/harness/t09_sira_pilot.py" not in changed_paths
    ):
        raise T09HostError("package transition changed a non-allowlisted or incomplete surface")
    deleted = output(
        [
            "git",
            "-C",
            str(repository),
            "diff",
            "--name-only",
            "--diff-filter=D",
            PACKAGE_TRANSITION_FROM_COMMIT,
            to_package_commit,
        ]
    )
    if deleted:
        raise T09HostError("package transition deleted a tracked file")
    diff = subprocess.run(
        [
            "git",
            "-C",
            str(repository),
            "diff",
            "--binary",
            PACKAGE_TRANSITION_FROM_COMMIT,
            to_package_commit,
        ],
        env=safe_environment(),
        stdin=subprocess.DEVNULL,
        capture_output=True,
        check=True,
        timeout=60,
    ).stdout
    return {
        "from_package_commit": PACKAGE_TRANSITION_FROM_COMMIT,
        "to_package_commit": to_package_commit,
        "from_package_is_ancestor": True,
        "to_package_tree": output(
            ["git", "-C", str(repository), "rev-parse", f"{to_package_commit}^{{tree}}"]
        ),
        "changed_paths": changed_paths,
        "changed_paths_sha256": canonical_sha256(changed_paths),
        "binary_diff_sha256": hashlib.sha256(diff).hexdigest(),
    }


def _validate_previous_package_transition_receipt(
    path: Path,
    *,
    repository: Path,
    entry_receipt: Path,
    entry_source_root: Path,
    prior_artifact_root: Path,
) -> dict[str, object]:
    paths = contract_paths(repository)
    plan_sha256 = file_sha256(paths["plan"])
    try:
        entry = validate_entry_receipt_source_bound(
            entry_receipt.resolve(strict=True),
            entry_source_root.resolve(strict=True),
            package_commit=PACKAGE_TRANSITION_FROM_COMMIT,
            plan_sha256=plan_sha256,
        )
    except T09ProviderError as exc:
        raise T09HostError("previous transition entry receipt is not source-bound") from exc
    prior_failure = _prior_qualification_failure_manifest(prior_artifact_root.resolve(strict=True))
    expected: dict[str, object] = {
        "schema_version": "0.1.0",
        "receipt_type": "t09-pragmatic-preentry-package-transition",
        "plan_id": PLAN_ID,
        "host_run_id": HOST_RUN_ID,
        **_git_transition_fields(
            repository,
            to_package_commit=PREVIOUS_PACKAGE_TRANSITION_COMMIT,
        ),
        "plan_sha256": plan_sha256,
        "provider_entry_receipt_sha256": file_sha256(entry_receipt),
        "provider_entry_source_manifest_sha256": entry.get("source_manifest_sha256"),
        "owned_instance_identity_sha256": entry.get("owned_instance_identity_sha256"),
        "lambda_started_at_epoch": entry.get("lambda_started_at_epoch"),
        "prior_failure": prior_failure,
        "prior_failure_sha256": canonical_sha256(prior_failure),
        "prior_qualification_id": CONTEXT_FAILURE_QUALIFICATION_ID,
        "next_qualification_id": FAILED_CANDIDATE_QUALIFICATION_ID,
        "prior_replacement_image_absent": True,
        "next_replacement_image_absent": True,
        "empirical_entry_crossed": False,
        "scientific_contract_changed": False,
        "provider_launch_reused": True,
        "additional_provider_launches": 0,
    }
    observed = load_object(path.resolve(strict=True), label="previous package transition receipt")
    created = observed.pop("created_at_epoch", None)
    metadata = path.stat(follow_symlinks=False)
    lambda_started = expected.get("lambda_started_at_epoch")
    if (
        observed != expected
        or not isinstance(created, (int, float))
        or isinstance(created, bool)
        or not isinstance(lambda_started, (int, float))
        or isinstance(lambda_started, bool)
        or not float(lambda_started) <= float(created) <= time.time()
        or not stat.S_ISREG(metadata.st_mode)
        or metadata.st_nlink != 1
        or stat.S_IMODE(metadata.st_mode) != 0o600
    ):
        raise T09HostError("previous package transition receipt drifted")
    return {**expected, "created_at_epoch": created, "receipt_sha256": file_sha256(path)}


def _package_transition_projection(
    *,
    repository: Path,
    package_commit: str,
    entry_receipt: Path,
    entry_source_root: Path,
    prior_artifact_root: Path,
    failed_candidate_root: Path,
    previous_transition_receipt: Path,
    require_candidate_present: bool,
) -> dict[str, object]:
    verify_package(repository, package_commit)
    paths = contract_paths(repository)
    plan_sha256 = file_sha256(paths["plan"])
    try:
        entry = validate_entry_receipt_source_bound(
            entry_receipt.resolve(strict=True),
            entry_source_root.resolve(strict=True),
            package_commit=PACKAGE_TRANSITION_FROM_COMMIT,
            plan_sha256=plan_sha256,
        )
    except T09ProviderError as exc:
        raise T09HostError("package transition entry receipt is not source-bound") from exc
    ancestry = subprocess.run(
        [
            "git",
            "-C",
            str(repository),
            "merge-base",
            "--is-ancestor",
            PACKAGE_TRANSITION_FROM_COMMIT,
            package_commit,
        ],
        env=safe_environment(),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
        timeout=30,
    )
    if ancestry.returncode != 0:
        raise T09HostError("replacement package is not a clean descendant of the launched package")
    failure = _prior_qualification_failure_manifest(prior_artifact_root.resolve(strict=True))
    previous_transition = _validate_previous_package_transition_receipt(
        previous_transition_receipt,
        repository=repository,
        entry_receipt=entry_receipt,
        entry_source_root=entry_source_root,
        prior_artifact_root=prior_artifact_root,
    )
    failed_candidate = _failed_candidate_manifest(
        failed_candidate_root.resolve(strict=True),
        require_image_present=require_candidate_present,
    )
    if (
        failed_candidate.get("previous_package_transition_receipt_sha256")
        != previous_transition.get("receipt_sha256")
        or image_id_if_present(docker_prefix(), PRIOR_REPLACEMENT_IMAGE_TAG) is not None
    ):
        raise T09HostError("failed candidate does not continue the exact prior transition")
    return {
        "schema_version": "0.1.0",
        "receipt_type": "t09-pragmatic-preentry-package-transition",
        "plan_id": PLAN_ID,
        "host_run_id": HOST_RUN_ID,
        **_git_transition_fields(repository, to_package_commit=package_commit),
        "plan_sha256": plan_sha256,
        "provider_entry_receipt_sha256": file_sha256(entry_receipt),
        "provider_entry_source_manifest_sha256": entry.get("source_manifest_sha256"),
        "owned_instance_identity_sha256": entry.get("owned_instance_identity_sha256"),
        "lambda_started_at_epoch": entry.get("lambda_started_at_epoch"),
        "prior_failure": failure,
        "prior_failure_sha256": canonical_sha256(failure),
        "failed_candidate": failed_candidate,
        "failed_candidate_sha256": canonical_sha256(failed_candidate),
        "previous_package_transition_receipt_sha256": previous_transition["receipt_sha256"],
        "prior_qualification_id": FAILED_CANDIDATE_QUALIFICATION_ID,
        "next_qualification_id": QUALIFICATION_ID,
        "context_failure_replacement_image_absent": True,
        "failed_candidate_replacement_image_present": True,
        "replacement_image_id": failed_candidate["replacement_image_id"],
        "replacement_image_reused_without_rebuild": True,
        "additional_replacement_image_builds": 0,
        "empirical_entry_crossed": False,
        "scientific_contract_changed": False,
        "provider_launch_reused": True,
        "additional_provider_launches": 0,
    }


def write_package_transition_receipt(args: argparse.Namespace) -> None:
    projection = _package_transition_projection(
        repository=args.repository.resolve(strict=True),
        package_commit=args.package_commit,
        entry_receipt=args.dynamic_receipt.resolve(strict=True),
        entry_source_root=args.dynamic_source_root.resolve(strict=True),
        prior_artifact_root=args.prior_artifact_root.resolve(strict=True),
        failed_candidate_root=args.failed_candidate_root.resolve(strict=True),
        previous_transition_receipt=args.previous_package_transition_receipt.resolve(strict=True),
        require_candidate_present=True,
    )
    write_exclusive(
        args.output.resolve(strict=False),
        {**projection, "created_at_epoch": time.time()},
    )


def validate_package_transition_receipt(
    path: Path,
    *,
    repository: Path,
    package_commit: str,
    entry_receipt: Path,
    entry_source_root: Path,
    prior_artifact_root: Path,
    failed_candidate_root: Path,
    previous_transition_receipt: Path,
    require_fresh: bool,
    require_candidate_present: bool,
) -> dict[str, object]:
    observed = load_object(path.resolve(strict=True), label="package transition receipt")
    created = observed.pop("created_at_epoch", None)
    expected = _package_transition_projection(
        repository=repository.resolve(strict=True),
        package_commit=package_commit,
        entry_receipt=entry_receipt.resolve(strict=True),
        entry_source_root=entry_source_root.resolve(strict=True),
        prior_artifact_root=prior_artifact_root.resolve(strict=True),
        failed_candidate_root=failed_candidate_root.resolve(strict=True),
        previous_transition_receipt=previous_transition_receipt.resolve(strict=True),
        require_candidate_present=require_candidate_present,
    )
    metadata = path.stat(follow_symlinks=False)
    lambda_started = expected.get("lambda_started_at_epoch")
    if (
        observed != expected
        or not isinstance(created, (int, float))
        or isinstance(created, bool)
        or not isinstance(lambda_started, (int, float))
        or isinstance(lambda_started, bool)
        or not float(lambda_started) <= float(created) <= time.time()
        or (require_fresh and not 0 <= time.time() - float(created) <= 1_800)
        or not stat.S_ISREG(metadata.st_mode)
        or metadata.st_nlink != 1
        or stat.S_IMODE(metadata.st_mode) != 0o600
    ):
        raise T09HostError("package transition receipt drifted or is stale")
    return {**expected, "created_at_epoch": created, "receipt_sha256": file_sha256(path)}


def validate_dynamic_receipt(
    path: Path,
    *,
    expected_package_commit: str,
    repository_root: Path | None = None,
    source_root: Path | None = None,
) -> dict[str, object]:
    """Reconstruct the receipt from retained allowlisted provider projections."""

    if repository_root is None or source_root is None:
        raise T09HostError("provider entry source bundle is required")
    repository = repository_root.resolve(strict=True)
    source = source_root.resolve(strict=True)
    plan = contract_paths(repository)["plan"]
    provider_entry_package_commit = expected_package_commit
    package_transition: dict[str, object] | None = None
    try:
        value = validate_entry_receipt_source_bound(
            path.resolve(strict=True),
            source,
            package_commit=expected_package_commit,
            plan_sha256=file_sha256(plan),
        )
    except T09ProviderError as current_error:
        try:
            value = validate_entry_receipt_source_bound(
                path.resolve(strict=True),
                source,
                package_commit=RETRY4_ACTIVE_SLOT2_ENTRY_PACKAGE_COMMIT,
                plan_sha256=file_sha256(plan),
            )
            package_transition = retry4_active_slot2_entry_transition(
                repository, expected_package_commit
            )
        except T09ProviderError:
            raise T09HostError("provider entry receipt is not source-bound") from current_error
        provider_entry_package_commit = RETRY4_ACTIVE_SLOT2_ENTRY_PACKAGE_COMMIT
        if (
            value.get("launch_slot") != 2
            or value.get("launch_count") != 2
            or package_transition.get("from_package_commit")
            != RETRY4_ACTIVE_SLOT2_ENTRY_PACKAGE_COMMIT
            or package_transition.get("to_package_commit") != expected_package_commit
        ):
            raise T09HostError(
                "active slot-2 provider package transition drifted"
            ) from current_error
    captured = value.get("captured_at_epoch")
    if (
        not isinstance(captured, (int, float))
        or isinstance(captured, bool)
        or not 0 <= time.time() - float(captured) <= MAX_PREFLIGHT_WALL_SECONDS
    ):
        raise T09HostError("provider entry receipt is stale")
    encoded = json.dumps(value, sort_keys=True)
    if (
        _CREDENTIAL_TEXT.search(encoded)
        or _JUPYTER_URL.search(encoded)
        or _private_network_values(encoded)
        or _sensitive_json_paths(value)
    ):
        raise T09HostError("provider entry receipt retained a prohibited value")
    result = dict(value)
    result["provider_preflight_started_at_epoch"] = value.get("owned_lambda_started_at_epoch")
    result["receipt_sha256"] = file_sha256(path)
    result["provider_entry_package_commit"] = provider_entry_package_commit
    result["provider_package_transition"] = package_transition
    result["provider_package_transition_sha256"] = (
        canonical_sha256(package_transition) if package_transition is not None else None
    )
    return result


def validate_provider_closeout_receipt(
    path: Path,
    *,
    expected_lambda_started_at_epoch: float,
    expected_owned_instance_identity_sha256: str,
    expected_entry_receipt_sha256: str,
    expected_package_commit: str,
    repository_root: Path | None = None,
    source_root: Path | None = None,
    entry_receipt_path: Path | None = None,
    entry_source_root: Path | None = None,
) -> dict[str, object]:
    """Reconstruct closeout from exact-target provider projections and raw hashes."""

    if any(
        item is None
        for item in (repository_root, source_root, entry_receipt_path, entry_source_root)
    ):
        raise T09HostError("provider closeout source bundles are required")
    assert repository_root is not None
    assert source_root is not None
    assert entry_receipt_path is not None
    assert entry_source_root is not None
    repository = repository_root.resolve(strict=True)
    try:
        value = validate_source_bound_closeout(
            path.resolve(strict=True),
            source_root.resolve(strict=True),
            entry_receipt_path=entry_receipt_path.resolve(strict=True),
            entry_source_root=entry_source_root.resolve(strict=True),
            package_commit=expected_package_commit,
            plan_sha256=file_sha256(contract_paths(repository)["plan"]),
            lifecycle=load_campaign_lifecycle(repository),
        )
    except T09ProviderError as exc:
        raise T09HostError("provider closeout receipt is not source-bound") from exc
    timeline = [
        value.get("lambda_started_at_epoch"),
        value.get("termination_started_at_epoch"),
        value.get("terminal_observed_at_epoch"),
        value.get("zero_instance_observed_at_epoch"),
        value.get("captured_at_epoch"),
    ]
    if any(not isinstance(item, (int, float)) or isinstance(item, bool) for item in timeline):
        raise T09HostError("provider closeout chronology is malformed")
    numeric_timeline = [float(cast(int | float, item)) for item in timeline]
    if (
        numeric_timeline != sorted(numeric_timeline)
        or abs(numeric_timeline[0] - expected_lambda_started_at_epoch) > 1.0
        or value.get("owned_instance_identity_sha256") != expected_owned_instance_identity_sha256
        or value.get("termination_target_identity_sha256")
        != expected_owned_instance_identity_sha256
        or value.get("entry_receipt_sha256") != expected_entry_receipt_sha256
        or not 0 <= time.time() - numeric_timeline[-1] <= 1_800
    ):
        raise T09HostError("provider closeout identity or chronology drifted")
    encoded = json.dumps(value, sort_keys=True)
    if (
        _CREDENTIAL_TEXT.search(encoded)
        or _JUPYTER_URL.search(encoded)
        or _private_network_values(encoded)
        or _sensitive_json_paths(value)
    ):
        raise T09HostError("provider closeout receipt retained a prohibited value")
    result = dict(value)
    result["receipt_sha256"] = file_sha256(path)
    return result


def sanitized_dynamic_receipt(_path: Path, value: dict[str, object]) -> dict[str, object]:
    """Return only the already-sanitized validator projection."""

    return dict(value)


def _runtime_budget_state(root: Path) -> dict[str, Any]:
    return load_object(root / "pilot-v6/pilot-state.json", label="pilot state")


def _received_export_ack_path(root: Path, run_id: str) -> Path:
    if run_id not in RUN_IDS:
        raise T09HostError("export acknowledgement run identity is unknown")
    return root / "pilot-v6/received-export-acknowledgements" / f"{run_id}.json"


def require_prior_export_acknowledgements(
    root: Path,
    *,
    next_attempt_index: int,
    package_commit: str,
) -> None:
    """Block empirical progression until every prior archive was verified off-host."""

    entry = load_object(root / "pilot-v6/provider-entry.json", label="provider entry")
    frozen_manifest_path = root / "pilot-v6/frozen-run-manifest.json"
    frozen_manifest = load_object(frozen_manifest_path, label="frozen run manifest")
    frozen_manifest_sha256 = file_sha256(frozen_manifest_path)
    for run_id in RUN_IDS[:next_attempt_index]:
        acknowledgement_path = _received_export_ack_path(root, run_id)
        if not acknowledgement_path.is_file():
            raise T09HostError(
                "prior attempt archive lacks its off-host verification acknowledgement"
            )
        acknowledgement = load_object(
            acknowledgement_path,
            label=f"{run_id} received export acknowledgement",
        )
        archive = root / "pilot-v6/attempt-exports" / f"{run_id}.tar.gz"
        if (
            set(acknowledgement)
            != {
                "schema_version",
                "plan_id",
                "host_run_id",
                "run_id",
                "package_commit",
                "archive_path",
                "archive_bytes",
                "archive_sha256",
                "frozen_run_manifest_sha256",
                "replacement_image_id",
                "provider_entry_receipt_sha256",
                "owned_instance_identity_sha256",
                "lambda_started_at_epoch",
                "verified_before_provider_termination",
            }
            or acknowledgement.get("schema_version") != "0.1.0"
            or acknowledgement.get("plan_id") != PLAN_ID
            or acknowledgement.get("host_run_id") != HOST_RUN_ID
            or acknowledgement.get("run_id") != run_id
            or acknowledgement.get("package_commit") != package_commit
            or acknowledgement.get("archive_path") != archive.name
            or acknowledgement.get("archive_bytes") != archive.stat().st_size
            or acknowledgement.get("archive_sha256") != file_sha256(archive)
            or acknowledgement.get("frozen_run_manifest_sha256") != frozen_manifest_sha256
            or acknowledgement.get("replacement_image_id")
            != frozen_manifest.get("replacement_image_id")
            or acknowledgement.get("provider_entry_receipt_sha256") != entry.get("receipt_sha256")
            or acknowledgement.get("owned_instance_identity_sha256")
            != entry.get("owned_instance_identity_sha256")
            or acknowledgement.get("lambda_started_at_epoch")
            != entry.get("lambda_started_at_epoch")
            or acknowledgement.get("verified_before_provider_termination") is not True
        ):
            raise T09HostError(
                "prior attempt archive lacks its exact off-host verification acknowledgement"
            )


def require_attempt_export_acknowledgement(
    root: Path,
    *,
    run_id: str,
    package_commit: str,
) -> None:
    """Require the current immutable raw export before downstream finalization."""

    try:
        attempt_index = RUN_IDS.index(run_id)
    except ValueError:
        raise T09HostError("export acknowledgement run identity is unknown") from None
    require_prior_export_acknowledgements(
        root,
        next_attempt_index=attempt_index + 1,
        package_commit=package_commit,
    )


def _active_lambda_accounting(root: Path, *, now: float) -> tuple[dict[str, Any], float, float]:
    state = _runtime_budget_state(root)
    owned_started = state.get("owned_lambda_started_at_epoch", state.get("lambda_started_at_epoch"))
    prior_duration = state.get("prior_campaign_lambda_duration_seconds", 0.0)
    prior_cost = state.get("prior_campaign_lambda_cost_usd", 0.0)
    if not all(
        isinstance(value, (int, float)) and not isinstance(value, bool)
        for value in (owned_started, prior_duration, prior_cost)
    ):
        raise T09HostError("active Lambda accounting is unavailable")
    owned_elapsed = now - float(cast(int | float, owned_started))
    active_duration = float(cast(int | float, prior_duration)) + owned_elapsed
    active_cost = float(cast(int | float, prior_cost)) + (
        owned_elapsed * LAMBDA_HOURLY_PRICE_USD / 3600.0
    )
    if min(owned_elapsed, active_duration, active_cost) < 0:
        raise T09HostError("active Lambda chronology is invalid")
    return state, active_duration, active_cost


def provider_seconds_remaining(root: Path, *, reserve_seconds: float = 0.0) -> float:
    """Return cumulative active-provider headroom, independent of offline gaps."""

    _, active_duration, active_cost = _active_lambda_accounting(root, now=time.time())
    remaining = min(
        MAX_LAMBDA_DURATION_SECONDS - active_duration,
        (MAX_LAMBDA_COST_USD - active_cost) * 3600.0 / LAMBDA_HOURLY_PRICE_USD,
    )
    if remaining + 1e-9 < reserve_seconds:
        raise T09HostError("provider duration or cost ceiling has no required reserve")
    return max(0.0, remaining - reserve_seconds)


def preflight_seconds_remaining(root: Path) -> float:
    """Return the fresh per-launch qualification window and cumulative headroom."""

    state, _, _ = _active_lambda_accounting(root, now=time.time())
    started = state.get("provider_preflight_started_at_epoch")
    if not isinstance(started, (int, float)) or isinstance(started, bool):
        raise T09HostError("provider preflight time origin is unavailable")
    lifecycle = Retry4LifecycleLimits()
    return min(
        lifecycle.preflight_remaining(
            launched_at_epoch=float(started),
            now_epoch=time.time(),
        ),
        provider_seconds_remaining(root),
    )


def scientific_seconds_remaining(root: Path, *, reserve_seconds: float = 0.0) -> float:
    """Return post-freeze empirical time plus cumulative active-provider headroom."""

    state, _, _ = _active_lambda_accounting(root, now=time.time())
    empirical_started = state.get("campaign_started_at_epoch")
    if not isinstance(empirical_started, (int, float)) or isinstance(empirical_started, bool):
        raise T09HostError("empirical campaign clock has not started")
    lifecycle = Retry4LifecycleLimits()
    empirical_remaining = lifecycle.empirical_remaining(
        empirical_started_at_epoch=float(empirical_started),
        now_epoch=time.time(),
    )
    active_remaining = provider_seconds_remaining(root)
    remaining = min(empirical_remaining, active_remaining)
    if remaining + 1e-9 < reserve_seconds:
        raise T09HostError("empirical or active-provider ceiling has no required reserve")
    return max(0.0, remaining - reserve_seconds)


def admit_next_attempt(root: Path) -> float:
    """Require only the next condition hard wall and the cleanup reserve."""

    usable = scientific_seconds_remaining(
        root,
        reserve_seconds=PROVIDER_CLOSEOUT_RESERVE_SECONDS,
    )
    if usable < MAX_CONDITION_WALL_SECONDS:
        raise T09HostError(
            "remaining campaign time cannot cover the next attempt hard wall and cleanup reserve"
        )
    return usable


def provider_termination_due(root: Path) -> bool:
    """Return whether normal provider termination must already have begun."""

    state = _runtime_budget_state(root)
    started = state.get("campaign_started_at_epoch")
    if not isinstance(started, (int, float)) or isinstance(started, bool):
        preflight_started = state.get("provider_preflight_started_at_epoch")
        if not isinstance(preflight_started, (int, float)) or isinstance(preflight_started, bool):
            raise T09HostError("provider preflight time origin is unavailable")
        return time.time() - float(preflight_started) >= MAX_PREFLIGHT_WALL_SECONDS
    return time.time() - float(started) >= PROVIDER_TERMINATION_CUTOFF_SECONDS


def container_state_receipt(prefix: list[str], name: str) -> dict[str, object]:
    raw = output([*prefix, "inspect", "--format", "{{json .State}}", name])
    try:
        value: object = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise T09HostError("container state inspection is malformed") from exc
    if not isinstance(value, dict):
        raise T09HostError("container state inspection is not an object")
    state = cast(dict[str, Any], value)
    return {
        "status": state.get("Status"),
        "running": state.get("Running"),
        "paused": state.get("Paused"),
        "restarting": state.get("Restarting"),
        "oom_killed": state.get("OOMKilled"),
        "dead": state.get("Dead"),
        "exit_code": state.get("ExitCode"),
        "started_at": state.get("StartedAt"),
        "finished_at": state.get("FinishedAt"),
        "private_network_fields_retained": False,
    }


def manifests(document: dict[str, Any]) -> list[dict[str, Any]]:
    value = document.get("manifests")
    if not isinstance(value, list) or len(value) != 4:
        raise T09HostError("exactly four command manifests are required")
    result = [item for item in value if isinstance(item, dict)]
    if len(result) != 4 or tuple(item.get("run_id") for item in result) != RUN_IDS:
        raise T09HostError("command manifest order or identities drifted")
    pair_diffs = document.get("pair_diffs")
    if (
        not isinstance(pair_diffs, list)
        or len(pair_diffs) != 2
        or any(not isinstance(item, dict) or item.get("valid") is not True for item in pair_diffs)
    ):
        raise T09HostError("command pair diffs are not valid")
    return cast(list[dict[str, Any]], result)


def manifest_for_run(document: dict[str, Any], run_id: str) -> dict[str, Any]:
    matches = [item for item in manifests(document) if item.get("run_id") == run_id]
    if len(matches) != 1:
        raise T09HostError("run command manifest is missing or duplicated")
    return matches[0]


def manifest_output_root(manifest: dict[str, Any]) -> str:
    owned = manifest.get("permitted_condition_owned")
    if not isinstance(owned, dict):
        raise T09HostError("command manifest lacks its condition-owned surface")
    output_root = owned.get("output_root")
    if not isinstance(output_root, str):
        raise T09HostError("command manifest lacks its condition-owned output root")
    relative = PurePosixPath(output_root)
    if relative.is_absolute() or ".." in relative.parts:
        raise T09HostError("condition-owned output root is unsafe")
    return output_root


def verify_package(
    repository: Path,
    package_commit: str,
    *,
    current_commit: str | None = None,
) -> dict[str, Any]:
    expected_head = package_commit if current_commit is None else current_commit
    if output(["git", "-C", str(repository), "rev-parse", "HEAD"]) != expected_head:
        raise T09HostError("repository commit does not match the authorized clean package")
    if output(["git", "-C", str(repository), "status", "--porcelain=v1"]):
        raise T09HostError("repository worktree is not clean")
    paths = contract_paths(repository)
    execution = load_object(paths["execution"], label="execution contract")
    if execution.get("authorized") is not False or execution.get("plan_id") != PLAN_ID:
        raise T09HostError("execution contract identity or authorization drifted")
    runtime = execution.get("runtime")
    if (
        not isinstance(runtime, dict)
        or runtime.get("container_image_digest") is not None
        or runtime.get("container_image_policy")
        != ("retained-exact-archive-load-or-one-fallback-build-preentry-frozen-run-manifest-v1")
        or runtime.get("historical_container_image_digest") != HISTORICAL_IMAGE_ID
    ):
        raise T09HostError("replacement image policy drifted")
    bindings = execution.get("contract_bindings")
    if not isinstance(bindings, dict):
        raise T09HostError("execution contract bindings are malformed")
    for label, raw in bindings.items():
        if not isinstance(label, str) or not isinstance(raw, dict):
            raise T09HostError("execution contract binding is malformed")
        relative = raw.get("path")
        expected_sha256 = raw.get("sha256")
        if not isinstance(relative, str) or not isinstance(expected_sha256, str):
            raise T09HostError("execution contract binding lacks path or hash")
        relative_path = Path(relative)
        if relative_path.is_absolute() or ".." in relative_path.parts:
            raise T09HostError("execution contract binding path is unsafe")
        bound = repository / relative_path
        if not bound.is_file() or file_sha256(bound) != expected_sha256:
            raise T09HostError(f"execution contract binding drifted: {label}")
        expected_size = raw.get("size_bytes")
        if expected_size is not None and bound.stat().st_size != expected_size:
            raise T09HostError(f"execution contract byte-size binding drifted: {label}")
    runtime_identity = load_object(paths["runtime"], label="runtime identity")
    base_runtime = runtime_identity.get("base_runtime")
    scientific_runtime = runtime_identity.get("scientific_runtime")
    replacement_policy = runtime_identity.get("replacement_image_policy")
    if (
        not isinstance(base_runtime, dict)
        or base_runtime.get("python_version") != "3.11.14"
        or base_runtime.get("installed_package_manifest_sha256") != EXPECTED_PACKAGE_MANIFEST_SHA256
        or base_runtime.get("chromium_sha256") != EXPECTED_CHROMIUM_SHA256
        or not isinstance(scientific_runtime, dict)
        or scientific_runtime.get("runner_sha256") != EXPECTED_UPSTREAM_RUNNER_SHA256
        or not isinstance(replacement_policy, dict)
        or replacement_policy.get("historical_image_digest") != HISTORICAL_IMAGE_ID
        or replacement_policy.get("exact_historical_digest_equality_required") is not False
        or replacement_policy.get("runtime_binding")
        != "source-derived-mode-0600-O_EXCL-frozen-run-manifest"
    ):
        raise T09HostError("runtime semantic identity drifted")
    instrumentation = runtime_identity.get("repository_instrumentation")
    files = instrumentation.get("files") if isinstance(instrumentation, dict) else None
    if not isinstance(files, list) or not files:
        raise T09HostError("runtime instrumentation bindings are missing")
    for raw in files:
        if not isinstance(raw, dict):
            raise T09HostError("runtime instrumentation binding is malformed")
        relative = raw.get("path")
        expected_sha256 = raw.get("sha256")
        if (
            not isinstance(relative, str)
            or not isinstance(expected_sha256, str)
            or Path(relative).is_absolute()
            or ".." in Path(relative).parts
        ):
            raise T09HostError("runtime instrumentation file binding drifted")
        observed_sha256 = (
            git_file_sha256(repository, package_commit, relative)
            if current_commit is not None
            and relative in {FINALIZER_RELATIVE_PATH, FINALIZER_PROJECTION_RELATIVE_PATH}
            else file_sha256(repository / relative)
        )
        if observed_sha256 != expected_sha256:
            raise T09HostError("runtime instrumentation file binding drifted")
    evaluator_contract = load_object(paths["evaluator"], label="evaluator contract")
    materialization = evaluator_contract.get("materialization")
    if not isinstance(materialization, dict):
        raise T09HostError("evaluator materialization contract is malformed")
    lock_relative = materialization.get("lock_path")
    lock_sha256 = materialization.get("lock_sha256")
    if (
        not isinstance(lock_relative, str)
        or Path(lock_relative).is_absolute()
        or ".." in Path(lock_relative).parts
        or not isinstance(lock_sha256, str)
        or not (repository / lock_relative).is_file()
        or file_sha256(repository / lock_relative) != lock_sha256
    ):
        raise T09HostError("evaluator dependency lock binding drifted")
    command_document = load_object(paths["commands"], label="command manifest set")
    if (
        command_document.get("plan_id") != PLAN_ID
        or command_document.get("execution_contract_sha256") != file_sha256(paths["execution"])
        or command_document.get("plan_sha256") != file_sha256(paths["plan"])
    ):
        raise T09HostError("command manifest package binding drifted")
    reviewed_ancestor = command_document.get("reviewed_implementation_ancestor")
    attempts = execution.get("attempts")
    bound_ancestors = (
        {item.get("giclab_commit") for item in attempts if isinstance(item, dict)}
        if isinstance(attempts, list)
        else set()
    )
    if (
        not isinstance(reviewed_ancestor, str)
        or len(reviewed_ancestor) != 40
        or any(character not in "0123456789abcdef" for character in reviewed_ancestor)
        or bound_ancestors != {reviewed_ancestor}
    ):
        raise T09HostError("reviewed implementation ancestor binding drifted")
    ancestor_check = subprocess.run(
        [
            "git",
            "-C",
            str(repository),
            "merge-base",
            "--is-ancestor",
            reviewed_ancestor,
            package_commit,
        ],
        env=safe_environment(),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
        timeout=30,
    )
    if ancestor_check.returncode != 0:
        raise T09HostError("reviewed implementation commit is not an ancestor of the package")
    for raw in files:
        assert isinstance(raw, dict)
        relative = raw["path"]
        expected_sha256 = raw["sha256"]
        historical = subprocess.run(
            ["git", "-C", str(repository), "show", f"{reviewed_ancestor}:{relative}"],
            env=safe_environment(),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=30,
        )
        if (
            historical.returncode != 0
            or hashlib.sha256(historical.stdout).hexdigest() != expected_sha256
        ):
            raise T09HostError("reviewed ancestor does not contain the selected runtime bytes")
    generator_relative = command_document.get("generator_path")
    generator_sha256 = command_document.get("generator_sha256")
    if (
        not isinstance(generator_relative, str)
        or Path(generator_relative).is_absolute()
        or ".." in Path(generator_relative).parts
        or not isinstance(generator_sha256, str)
        or not (repository / generator_relative).is_file()
        or file_sha256(repository / generator_relative) != generator_sha256
    ):
        raise T09HostError("command manifest generator binding drifted")
    for item in manifests(command_document):
        condition_path = repository / item["condition_plan_path"]
        if file_sha256(condition_path) != item.get("condition_plan_sha256"):
            raise T09HostError("condition plan hash changed")
        if item.get("execution_contract_sha256") != file_sha256(paths["execution"]):
            raise T09HostError("command execution-contract binding changed")
    return command_document


def _evaluator_package_records(
    *,
    overlay: Path,
    prefix: list[str],
    image_id: str,
    expected_packages: list[str],
) -> list[str]:
    command = [
        *prefix,
        "run",
        "--rm",
        "--network",
        "none",
        "--read-only",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges=true",
        "--user",
        "1000:1000",
        "--env",
        "HOME=/tmp",
        "--env",
        "UV_CACHE_DIR=/tmp/uv-cache",
        "--tmpfs",
        "/tmp:rw,noexec,nosuid,nodev,size=67108864,uid=1000,gid=1000,mode=0700",
        "--mount",
        f"type=bind,src={overlay},dst=/opt/evaluator,readonly",
        "--entrypoint",
        "/usr/local/bin/uv",
        image_id,
        "pip",
        "freeze",
        "--python",
        "/opt/evaluator/.venv/bin/python",
    ]
    result = subprocess.run(
        command,
        env=safe_environment(),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
        timeout=120,
    )
    if result.returncode != 0 or len(result.stdout) > 1_048_576:
        raise T09HostError("exact evaluator package manifest failed")
    try:
        raw_text = result.stdout.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise T09HostError("evaluator package manifest is not UTF-8") from exc
    return normalize_evaluator_package_records(raw_text, expected_packages=expected_packages)


def normalize_evaluator_package_records(
    raw_text: str,
    *,
    expected_packages: list[str],
) -> list[str]:
    """Normalize only the one reviewed direct URL and require exact package closure."""

    raw_packages = sorted(line.strip() for line in raw_text.splitlines() if line.strip())
    if (
        not raw_packages
        or len(raw_packages) != len(set(raw_packages))
        or any(
            len(line) > 1_024
            or any(ord(character) < 32 for character in line)
            or (
                re.fullmatch(
                    r"[A-Za-z0-9][A-Za-z0-9._-]*==[A-Za-z0-9][A-Za-z0-9.!+_-]*",
                    line,
                )
                is None
                and line != EVALUATOR_DIRECT_URL_RECORD
            )
            for line in raw_packages
        )
    ):
        raise T09HostError("evaluator package manifest is unsafe or ambiguous")
    packages = sorted(
        "en-core-web-sm==3.8.0" if line == EVALUATOR_DIRECT_URL_RECORD else line
        for line in raw_packages
    )
    if packages != expected_packages:
        raise T09HostError("realized evaluator package set differs from the reviewed contract")
    return packages


def expected_evaluator_packages(repository: Path) -> list[str]:
    contract = load_object(contract_paths(repository)["evaluator"], label="evaluator contract")
    materialization = contract.get("materialization")
    inventory = (
        materialization.get("dependency_license_inventory")
        if isinstance(materialization, dict)
        else None
    )
    if not isinstance(inventory, list) or not inventory:
        raise T09HostError("evaluator dependency license inventory is unavailable")
    packages: list[str] = []
    for item in inventory:
        if not isinstance(item, str) or item.count("|") != 1:
            raise T09HostError("evaluator dependency inventory is malformed")
        package, license_identity = item.split("|", 1)
        if (
            re.fullmatch(
                r"[A-Za-z0-9][A-Za-z0-9._-]*==[A-Za-z0-9][A-Za-z0-9.!+_-]*",
                package,
            )
            is None
            or not license_identity
        ):
            raise T09HostError("evaluator dependency inventory identity is malformed")
        packages.append(package)
    result = sorted(packages)
    if len(result) != len(set(result)):
        raise T09HostError("evaluator dependency inventory contains duplicates")
    return result


def evaluator_overlay_inventory(overlay: Path) -> dict[str, object]:
    """Manifest every realized evaluator directory, file, and symlink without following it."""

    root = overlay.resolve(strict=True)
    root_metadata = root.stat(follow_symlinks=False)
    if (
        not stat.S_ISDIR(root_metadata.st_mode)
        or root.is_symlink()
        or root_metadata.st_uid != os.getuid()
        or stat.S_IMODE(root_metadata.st_mode) != 0o700
    ):
        raise T09HostError("evaluator overlay root metadata is unsafe")
    entries: list[dict[str, object]] = []
    total_regular_bytes = 0
    for current, raw_directories, raw_files in os.walk(root, topdown=True, followlinks=False):
        current_path = Path(current)
        raw_directories.sort()
        raw_files.sort()
        names = [*raw_directories, *raw_files]
        retained_directories: list[str] = []
        for name in names:
            path = current_path / name
            metadata = path.lstat()
            relative = path.relative_to(root).as_posix()
            if not relative or relative.startswith("../"):
                raise T09HostError("evaluator overlay path escaped its root")
            record: dict[str, object] = {
                "path": relative,
                "mode": f"{stat.S_IMODE(metadata.st_mode):04o}",
            }
            if stat.S_ISDIR(metadata.st_mode):
                record["type"] = "directory"
                retained_directories.append(name)
            elif stat.S_ISREG(metadata.st_mode):
                if metadata.st_nlink != 1:
                    raise T09HostError("evaluator overlay contains a linked regular file")
                record.update(
                    {
                        "type": "file",
                        "bytes": metadata.st_size,
                        "sha256": file_sha256(path),
                    }
                )
                total_regular_bytes += metadata.st_size
            elif stat.S_ISLNK(metadata.st_mode):
                target = os.readlink(path)
                if not target or len(os.fsencode(target)) > 4_096 or "\0" in target:
                    raise T09HostError("evaluator overlay symlink target is unsafe")
                record.update({"type": "symlink", "target": target})
            else:
                raise T09HostError("evaluator overlay contains a special file")
            entries.append(record)
            if (
                len(entries) > MAX_EVALUATOR_OVERLAY_ENTRIES
                or total_regular_bytes > MAX_EVALUATOR_OVERLAY_BYTES
            ):
                raise T09HostError("evaluator overlay exceeds its frozen manifest cap")
        raw_directories[:] = retained_directories
    return {
        "root_mode": "0700",
        "entries": entries,
        "entry_count": len(entries),
        "total_regular_bytes": total_regular_bytes,
        "entries_sha256": canonical_sha256(entries),
    }


def local_dependency_tree_inventory(root: Path, *, label: str) -> dict[str, object]:
    """Hash a control-machine dependency tree without following links."""

    resolved = root.resolve(strict=True)
    root_metadata = resolved.stat(follow_symlinks=False)
    if (
        resolved.is_symlink()
        or not stat.S_ISDIR(root_metadata.st_mode)
        or root_metadata.st_uid != os.getuid()
        or root_metadata.st_mode & 0o022
    ):
        raise T09HostError(f"{label} root metadata is unsafe")
    entries: list[dict[str, object]] = []
    total_regular_bytes = 0
    for current, raw_directories, raw_files in os.walk(
        resolved,
        topdown=True,
        followlinks=False,
    ):
        current_path = Path(current)
        raw_directories.sort()
        raw_files.sort()
        retained_directories: list[str] = []
        for name in [*raw_directories, *raw_files]:
            path = current_path / name
            metadata = path.lstat()
            relative = path.relative_to(resolved).as_posix()
            record: dict[str, object] = {
                "path": relative,
                "mode": f"{stat.S_IMODE(metadata.st_mode):04o}",
            }
            if stat.S_ISDIR(metadata.st_mode):
                if metadata.st_mode & 0o022:
                    raise T09HostError(f"{label} directory is writable")
                record["type"] = "directory"
                retained_directories.append(name)
            elif stat.S_ISREG(metadata.st_mode):
                if metadata.st_nlink != 1 or metadata.st_mode & 0o022:
                    raise T09HostError(f"{label} file metadata is unsafe")
                record.update(
                    {
                        "type": "file",
                        "bytes": metadata.st_size,
                        "sha256": file_sha256(path),
                    }
                )
                total_regular_bytes += metadata.st_size
            else:
                raise T09HostError(f"{label} contains a link or special file")
            entries.append(record)
            if (
                len(entries) > MAX_EVALUATOR_OVERLAY_ENTRIES
                or total_regular_bytes > MAX_EVALUATOR_OVERLAY_BYTES
            ):
                raise T09HostError(f"{label} exceeds its manifest bound")
        raw_directories[:] = retained_directories
    return {
        "root_mode": f"{stat.S_IMODE(root_metadata.st_mode):04o}",
        "entries": entries,
        "entry_count": len(entries),
        "total_regular_bytes": total_regular_bytes,
        "entries_sha256": canonical_sha256(entries),
    }


def local_interpreter_launcher_identity(path: Path) -> dict[str, object]:
    """Recompute the qualified venv launcher and resolved executable identity."""

    if not path.is_absolute():
        raise T09HostError("qualified local interpreter launcher is not absolute")
    launcher = Path(os.path.abspath(path))
    launcher_metadata = launcher.lstat()
    if launcher_metadata.st_uid != os.getuid() or launcher_metadata.st_nlink != 1:
        raise T09HostError("qualified local interpreter launcher metadata is unsafe")
    if stat.S_ISLNK(launcher_metadata.st_mode):
        launcher_type = "symlink"
        link_target: str | None = os.readlink(launcher)
        if not link_target or len(os.fsencode(link_target)) > 4_096 or "\0" in link_target:
            raise T09HostError("qualified local interpreter link target is unsafe")
    elif stat.S_ISREG(launcher_metadata.st_mode):
        launcher_type = "regular"
        link_target = None
        if launcher_metadata.st_mode & 0o022:
            raise T09HostError("qualified local interpreter launcher is writable")
    else:
        raise T09HostError("qualified local interpreter launcher is unsafe")
    resolved_target = launcher.resolve(strict=True)
    target_metadata = resolved_target.stat(follow_symlinks=False)
    if (
        resolved_target.is_symlink()
        or not stat.S_ISREG(target_metadata.st_mode)
        or target_metadata.st_uid != os.getuid()
        or target_metadata.st_nlink != 1
        or target_metadata.st_mode & 0o022
    ):
        raise T09HostError("qualified local interpreter target metadata is unsafe")
    return {
        "interpreter": launcher.as_posix(),
        "interpreter_sha256": file_sha256(launcher),
        "interpreter_launcher_type": launcher_type,
        "interpreter_launcher_mode": f"{stat.S_IMODE(launcher_metadata.st_mode):04o}",
        "interpreter_launcher_link_target": link_target,
        "interpreter_resolved_target": resolved_target.as_posix(),
        "interpreter_resolved_target_sha256": file_sha256(resolved_target),
    }


def _valid_retained_dependency_tree(value: object) -> bool:
    """Return whether a retained local dependency-tree manifest is canonical."""

    if not isinstance(value, dict) or set(value) != {
        "root_mode",
        "entries",
        "entry_count",
        "total_regular_bytes",
        "entries_sha256",
    }:
        return False
    entries = value.get("entries")
    if (
        not isinstance(entries, list)
        or not 0 < len(entries) <= MAX_EVALUATOR_OVERLAY_ENTRIES
        or value.get("entry_count") != len(entries)
        or value.get("entries_sha256") != canonical_sha256(entries)
        or not isinstance(value.get("root_mode"), str)
        or re.fullmatch(r"0[0-7]{3}", cast(str, value["root_mode"])) is None
    ):
        return False
    paths: set[str] = set()
    total = 0
    for raw in entries:
        if not isinstance(raw, dict):
            return False
        relative = raw.get("path")
        mode = raw.get("mode")
        kind = raw.get("type")
        if (
            not isinstance(relative, str)
            or not relative
            or PurePosixPath(relative).is_absolute()
            or ".." in PurePosixPath(relative).parts
            or relative in paths
            or not isinstance(mode, str)
            or re.fullmatch(r"0[0-7]{3}", mode) is None
            or kind not in {"directory", "file"}
        ):
            return False
        paths.add(relative)
        if kind == "directory":
            if set(raw) != {"path", "mode", "type"}:
                return False
            continue
        size = raw.get("bytes")
        digest = raw.get("sha256")
        if (
            set(raw) != {"path", "mode", "type", "bytes", "sha256"}
            or type(size) is not int
            or size < 0
            or not isinstance(digest, str)
            or _HEX64.fullmatch(digest) is None
        ):
            return False
        total += size
        if total > MAX_EVALUATOR_OVERLAY_BYTES:
            return False
    return value.get("total_regular_bytes") == total


def _validate_evaluator_overlay_inventory(
    *,
    overlay: Path,
    retained: dict[str, Any],
) -> None:
    observed = evaluator_overlay_inventory(overlay)
    for field in (
        "root_mode",
        "entries",
        "entry_count",
        "total_regular_bytes",
        "entries_sha256",
    ):
        if observed.get(field) != retained.get(field):
            raise T09HostError("realized evaluator overlay changed after qualification")


def evaluator_overlay(
    *,
    repository: Path,
    artifact_root: Path,
    overlay: Path,
    prefix: list[str],
    image_id: str,
) -> dict[str, object]:
    overlay.mkdir(mode=0o700, parents=True, exist_ok=False)
    command = [
        *prefix,
        "run",
        "--rm",
        "--network",
        "bridge",
        "--user",
        "1000:1000",
        "--env",
        "UV_PROJECT_ENVIRONMENT=/opt/evaluator/.venv",
        "--env",
        "UV_CACHE_DIR=/opt/evaluator/cache",
        "--env",
        "CUDA_VISIBLE_DEVICES=",
        "--mount",
        f"type=bind,src={repository},dst=/opt/giclab-project,readonly",
        "--mount",
        f"type=bind,src={overlay},dst=/opt/evaluator",
        "--entrypoint",
        "/usr/local/bin/uv",
        image_id,
        "sync",
        "--frozen",
        "--only-group",
        "evaluator",
        "--no-install-project",
        "--project",
        "/opt/giclab-project",
        "--python",
        "/opt/sira/.venv/bin/python",
    ]
    result = subprocess.run(
        command,
        env=safe_environment(),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
        timeout=1_800,
    )
    if result.returncode != 0:
        raise T09HostError("exact evaluator overlay materialization failed")
    cache = overlay / "cache"
    if cache.exists():
        if cache.is_symlink() or not cache.is_dir():
            raise T09HostError("evaluator dependency cache has unsafe metadata")
        shutil.rmtree(cache)
    expected_packages = expected_evaluator_packages(repository)
    packages = _evaluator_package_records(
        overlay=overlay,
        prefix=prefix,
        image_id=image_id,
        expected_packages=expected_packages,
    )
    inventory = evaluator_overlay_inventory(overlay)
    manifest: dict[str, object] = {
        "schema_version": "0.1.0",
        "plan_id": PLAN_ID,
        "qualification_id": QUALIFICATION_ID,
        "replacement_image_id": image_id,
        **inventory,
        "packages": packages,
        "packages_sha256": canonical_sha256(packages),
        "reviewed_expected_packages_sha256": canonical_sha256(expected_packages),
        "lock_sha256": file_sha256(repository / "uv.lock"),
        "network_materialization_only": True,
        "runtime_mount_read_only": True,
    }
    manifest_path = artifact_root / "pilot-v6/evaluator-overlay-manifest.json"
    write_exclusive(manifest_path, manifest)
    return {
        "materialized": True,
        "network_mode": "bridge-dependency-materialization-only",
        "provider_or_model_request": False,
        "image_id": image_id,
        "lock_sha256": file_sha256(repository / "uv.lock"),
        "overlay_manifest_sha256": file_sha256(manifest_path),
        "overlay_entries_sha256": inventory["entries_sha256"],
        "overlay_package_manifest_sha256": manifest["packages_sha256"],
        "overlay_entry_count": inventory["entry_count"],
        "overlay_total_regular_bytes": inventory["total_regular_bytes"],
    }


def validate_evaluator_overlay_binding(
    *,
    artifact_root: Path,
    repository: Path,
    overlay: Path,
    prefix: list[str],
    image_id: str,
    frozen_manifest: dict[str, Any],
    verify_packages: bool,
) -> dict[str, object]:
    manifest_path = artifact_root / "pilot-v6/evaluator-overlay-manifest.json"
    retained = load_object(manifest_path, label="evaluator overlay manifest")
    if (
        frozen_manifest.get("evaluator_overlay_manifest_sha256") != file_sha256(manifest_path)
        or retained.get("schema_version") != "0.1.0"
        or retained.get("plan_id") != PLAN_ID
        or retained.get("qualification_id") != QUALIFICATION_ID
        or retained.get("replacement_image_id") != image_id
        or retained.get("entries_sha256") != frozen_manifest.get("evaluator_overlay_entries_sha256")
        or retained.get("packages_sha256")
        != frozen_manifest.get("evaluator_overlay_packages_sha256")
        or retained.get("reviewed_expected_packages_sha256")
        != canonical_sha256(expected_evaluator_packages(repository))
        or retained.get("runtime_mount_read_only") is not True
    ):
        raise T09HostError("frozen evaluator overlay binding drifted")
    _validate_evaluator_overlay_inventory(overlay=overlay, retained=retained)
    if verify_packages:
        packages = _evaluator_package_records(
            overlay=overlay,
            prefix=prefix,
            image_id=image_id,
            expected_packages=expected_evaluator_packages(repository),
        )
        if packages != retained.get("packages") or canonical_sha256(packages) != retained.get(
            "packages_sha256"
        ):
            raise T09HostError("realized evaluator package set changed after qualification")
    return {
        "overlay_manifest_sha256": file_sha256(manifest_path),
        "overlay_entries_sha256": retained["entries_sha256"],
        "overlay_packages_sha256": retained["packages_sha256"],
        "packages_recomputed": verify_packages,
    }


def gpu_snapshot() -> dict[str, object]:
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,driver_version,utilization.gpu,memory.used,memory.total",
                "--format=csv,noheader,nounits",
            ],
            env=safe_environment(),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        result = None
    rows = (
        result.stdout.decode("utf-8", errors="replace").strip().splitlines()
        if result is not None and result.returncode == 0
        else []
    )
    return {
        "captured_at": utc_now(),
        "host_gpu_visibility": "visible" if rows else "unavailable",
        "host_gpu_rows_without_unique_identifiers": rows,
        "pilot_container_gpu_device_request": "none",
        "pilot_container_cuda_visible_devices": "disabled-empty",
        "pilot_process_gpu_use": False,
        "gpu_acceleration_claim": False,
    }


def browser_lifecycle_preflight(
    *,
    artifact_root: Path,
    prefix: list[str],
    image_id: str,
) -> dict[str, object]:
    attempt = artifact_root / "pilot-v6/browser-preflight"
    attempt.mkdir(parents=True, mode=0o700)
    name = f"{CONTAINER_PREFIX}browser-preflight"
    create = [
        *prefix,
        "create",
        "--name",
        name,
        "--platform",
        "linux/amd64",
        "--network",
        "none",
        "--read-only",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges=true",
        "--shm-size",
        "1g",
        "--tmpfs",
        "/tmp:rw,noexec,nosuid,nodev,size=134217728,uid=1000,gid=1000,mode=0700",
        "--user",
        "1000:1000",
        "--env",
        "CUDA_VISIBLE_DEVICES=",
        "--mount",
        f"type=bind,src={attempt},dst=/giclab/attempt",
        "--entrypoint",
        "/opt/sira/.venv/bin/python",
        image_id,
        "/opt/giclab/browser_preflight.py",
    ]
    run_logged(create, evidence_root=attempt, label="container-create", timeout=60)
    started = False
    removed = False
    state_receipt: dict[str, object] | None = None
    try:
        run_logged(
            [*prefix, "start", name],
            evidence_root=attempt,
            label="container-start",
            timeout=60,
        )
        started = True
        deadline = time.monotonic() + 90
        record_path = attempt / "browser-preflight.json"
        while time.monotonic() < deadline and not record_path.is_file():
            time.sleep(0.25)
        if not record_path.is_file():
            raise T09HostError("browser lifecycle preflight did not produce evidence")
        record = load_object(record_path, label="browser preflight")
        if (
            record.get("network_mode") != "none"
            or record.get("source") != "local-static-file"
            or record.get("screenshot_captures") != 1
            or record.get("playwright_version") != "1.39.0"
            or record.get("chromium_revision") != "1084"
            or record.get("chromium_executable_sha256") != EXPECTED_CHROMIUM_SHA256
            or record.get("installed_package_manifest_sha256") != EXPECTED_PACKAGE_MANIFEST_SHA256
        ):
            raise T09HostError("browser lifecycle preflight identity drifted")
    finally:
        if started:
            subprocess.run(
                [*prefix, "stop", "--time", "10", name],
                env=safe_environment(),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                timeout=30,
            )
        state_receipt = container_state_receipt(prefix, name)
        removed = remove_container(prefix, name)
    residue = owned_containers(prefix)
    result = {
        "started": started,
        "local_static_page": True,
        "network_mode": "none",
        "screenshot_captured": (attempt / "browser-preflight.png").is_file(),
        "browser_cleanup_by_container_stop": True,
        "container_removed": removed,
        "owned_container_residue": residue,
        "task_browser_action": False,
        "image_id": image_id,
        "chromium_executable_sha256": EXPECTED_CHROMIUM_SHA256,
        "installed_package_manifest_sha256": EXPECTED_PACKAGE_MANIFEST_SHA256,
        "container_state": state_receipt,
    }
    if not all(
        (
            result["started"],
            result["screenshot_captured"],
            result["container_removed"],
            not residue,
        )
    ):
        raise T09HostError("browser startup or cleanup preflight failed")
    write_exclusive(attempt / "host-browser-lifecycle.json", result)
    return result


def secret_channel_preflight(
    *,
    repository: Path,
    artifact_root: Path,
    secret_file: Path,
    prefix: list[str],
    image_id: str,
) -> dict[str, Any]:
    attempt = artifact_root / "pilot-v6/secret-channel-preflight"
    attempt.mkdir(parents=True, mode=0o700)
    source = repository / "containers/sira-smoke/pragmatic/t09_secret_preflight.py"
    command = [
        *prefix,
        "run",
        "--rm",
        "--network",
        "none",
        "--read-only",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges=true",
        "--user",
        "1000:1000",
        "--mount",
        f"type=bind,src={source},dst=/opt/giclab/t09_secret_preflight.py,readonly",
        "--mount",
        f"type=bind,src={secret_file},dst=/run/secrets/sira_api_key,readonly",
        "--mount",
        f"type=bind,src={attempt},dst=/opt/giclab-evidence",
        "--entrypoint",
        "/opt/sira/.venv/bin/python",
        image_id,
        "/opt/giclab/t09_secret_preflight.py",
        "--secret",
        "/run/secrets/sira_api_key",
        "--output",
        "/opt/giclab-evidence/receipt.json",
    ]
    run_logged(command, evidence_root=attempt, label="secret-channel-probe", timeout=60)
    receipt = load_object(attempt / "receipt.json", label="secret-channel receipt")
    if (
        receipt.get("opened_read_only_without_value_read") is not True
        or receipt.get("secret_bytes_read") != 0
        or receipt.get("secret_value_or_hash_retained") is not False
        or receipt.get("container_effective_uid") != 1000
    ):
        raise T09HostError("condition-container credential channel preflight failed")
    return receipt


def offline_runtime_preflight(
    *,
    repository: Path,
    artifact_root: Path,
    overlay: Path,
    prefix: list[str],
    image_id: str,
) -> dict[str, Any]:
    paths = contract_paths(repository)
    attempt = artifact_root / "pilot-v6/offline-runtime-preflight"
    attempt.mkdir(parents=True, mode=0o700)
    source = repository / "containers/sira-smoke/pragmatic/t09_preflight.py"
    finalizer_source = repository / FINALIZER_RELATIVE_PATH
    finalizer_fixture = repository / "tests/fixtures/t09/finalizer-raw-shape"
    runtime_sha256 = file_sha256(repository / "src/giclab/harness/sira_gate_a_runtime.py")
    library_sha256 = file_sha256(repository / "src/giclab/harness/t09_sira_pilot.py")
    command = [
        *prefix,
        "run",
        "--rm",
        "--network",
        "none",
        "--read-only",
        "--user",
        "1000:1000",
        "--env",
        "PYTHONPATH=/opt/evaluator/.venv/lib/python3.11/site-packages:/opt/giclab-src",
        "--env",
        "CUDA_VISIBLE_DEVICES=",
        "--mount",
        f"type=bind,src={artifact_root},dst=/opt/giclab-artifacts",
        "--mount",
        f"type=bind,src={repository / 'src/giclab'},dst=/opt/giclab-src/giclab,readonly",
        "--mount",
        f"type=bind,src={source},dst=/opt/giclab/t09_preflight.py,readonly",
        "--mount",
        f"type=bind,src={finalizer_source},dst=/opt/giclab/t09_evaluate_attempt.py,readonly",
        "--mount",
        f"type=bind,src={finalizer_fixture},dst=/opt/giclab-finalizer-fixture,readonly",
        "--mount",
        f"type=bind,src={overlay},dst=/opt/evaluator,readonly",
        "--mount",
        f"type=bind,src={paths['execution']},dst=/opt/giclab-contracts/execution.json,readonly",
        "--mount",
        f"type=bind,src={paths['commands']},dst=/opt/giclab-contracts/commands.json,readonly",
        "--entrypoint",
        "/opt/sira/.venv/bin/python",
        image_id,
        "/opt/giclab/t09_preflight.py",
        "--execution-contract",
        "/opt/giclab-contracts/execution.json",
        "--execution-contract-sha256",
        file_sha256(paths["execution"]),
        "--command-manifests",
        "/opt/giclab-contracts/commands.json",
        "--command-manifests-sha256",
        file_sha256(paths["commands"]),
        "--runtime-adaptation-sha256",
        runtime_sha256,
        "--pilot-library-sha256",
        library_sha256,
        "--attempt-root",
        "/opt/giclab-artifacts/pilot-v6/offline-runtime-preflight",
        "--aggregate-ledger",
        "/opt/giclab-artifacts/pilot-v6/aggregate-budget.json",
        "--pilot-state",
        "/opt/giclab-artifacts/pilot-v6/pilot-state.json",
        "--evaluator-root",
        "/opt/sira/evaluation/fanout",
        "--dataset",
        "/opt/sira/data/fanout-final-dev.json",
        "--finalizer-source",
        "/opt/giclab/t09_evaluate_attempt.py",
        "--finalizer-source-sha256",
        file_sha256(finalizer_source),
        "--finalizer-raw-fixture",
        "/opt/giclab-finalizer-fixture",
    ]
    run_logged(command, evidence_root=attempt, label="offline-preflight", timeout=300)
    receipt = load_object(
        attempt / "offline-runtime-preflight.json",
        label="offline runtime preflight",
    )
    if (
        receipt.get("python_version") != "3.11.14"
        or receipt.get("command_rendering") != "passed-four-exact-pair-valid"
        or receipt.get("evaluator_loading") != "passed-exact-network-none"
        or receipt.get("task_loading") != "passed-two-exact-rows"
        or receipt.get("offline_evaluator_fixtures") != "passed-approved-exact-results"
        or not isinstance(receipt.get("finalizer_raw_fixture"), dict)
        or receipt["finalizer_raw_fixture"].get("evaluator_valid") is not True
        or receipt["finalizer_raw_fixture"].get("score") != 0.0
        or receipt.get("provider_or_task_request") is not False
        or receipt.get("browser_action") is not False
    ):
        raise T09HostError("offline runtime or evaluator fixture preflight drifted")
    return receipt


def validate_private_regression_archive(archive: Path) -> Path:
    """Validate the exact private V4 fixture without following or sharing its inode."""

    resolved = archive.resolve(strict=True)
    metadata = resolved.stat(follow_symlinks=False)
    if (
        resolved != PRIVATE_REGRESSION_ARCHIVE_PATH
        or resolved.is_symlink()
        or not stat.S_ISREG(metadata.st_mode)
        or metadata.st_uid != os.getuid()
        or metadata.st_nlink != 1
        or stat.S_IMODE(metadata.st_mode) != 0o600
        or metadata.st_size != PRIVATE_REGRESSION_ARCHIVE_BYTES
        or file_sha256(resolved) != PRIVATE_REGRESSION_ARCHIVE_SHA256
    ):
        raise T09HostError("private V4 regression archive identity drifted")
    return resolved


def qualified_real_evidence_regression(
    *,
    repository: Path,
    artifact_root: Path,
    archive: Path,
    overlay: Path,
    prefix: list[str],
    image_id: str,
    image_files: dict[str, str],
    static_receipt: dict[str, Any],
) -> dict[str, Any]:
    """Reconstruct the retained V4 raw archive inside the exact accepted image."""

    archive = validate_private_regression_archive(archive)
    paths = contract_paths(repository)
    attempt = artifact_root / "pilot-v6/qualified-real-evidence-regression"
    attempt.mkdir(parents=True, mode=0o700, exist_ok=False)
    regression_source = (
        repository / "containers/sira-smoke/pragmatic/t09_real_evidence_regression.py"
    )
    finalizer_source = repository / FINALIZER_RELATIVE_PATH
    disposition = (
        repository / "experiments/EXP-0001-sira-simulative-vs-reactive/"
        "T09_PRAGMATIC_RETRY2_DISPOSITION.json"
    )
    command = [
        *prefix,
        "run",
        "--rm",
        "--network",
        "none",
        "--read-only",
        "--user",
        "1000:1000",
        "--env",
        "PYTHONPATH=/opt/evaluator/.venv/lib/python3.11/site-packages:/opt/giclab-src",
        "--env",
        "CUDA_VISIBLE_DEVICES=",
        "--tmpfs",
        "/tmp:rw,noexec,nosuid,size=128m",
        "--mount",
        f"type=bind,src={repository / 'src/giclab'},dst=/opt/giclab-src/giclab,readonly",
        "--mount",
        f"type=bind,src={regression_source},dst=/opt/giclab/t09_real_evidence_regression.py,readonly",
        "--mount",
        f"type=bind,src={finalizer_source},dst=/opt/giclab/t09_evaluate_attempt.py,readonly",
        "--mount",
        f"type=bind,src={archive},dst=/opt/giclab-private/v4-attempt.tar.gz,readonly",
        "--mount",
        f"type=bind,src={disposition},dst=/opt/giclab-contracts/v4-disposition.json,readonly",
        "--mount",
        f"type=bind,src={paths['evaluator']},dst=/opt/giclab-contracts/evaluator.json,readonly",
        "--mount",
        f"type=bind,src={overlay},dst=/opt/evaluator,readonly",
        "--mount",
        f"type=bind,src={attempt},dst=/opt/giclab-output",
        "--entrypoint",
        "/opt/sira/.venv/bin/python",
        image_id,
        "/opt/giclab/t09_real_evidence_regression.py",
        "--archive",
        "/opt/giclab-private/v4-attempt.tar.gz",
        "--public-disposition",
        "/opt/giclab-contracts/v4-disposition.json",
        "--finalizer-source",
        "/opt/giclab/t09_evaluate_attempt.py",
        "--finalizer-source-sha256",
        file_sha256(finalizer_source),
        "--evaluator-root",
        "/opt/sira/evaluation/fanout",
        "--evaluator-contract",
        "/opt/giclab-contracts/evaluator.json",
        "--dependency-site-packages",
        "/opt/evaluator/.venv/lib/python3.11/site-packages",
        "--dataset",
        "/opt/sira/data/fanout-final-dev.json",
        "--receipt-id",
        "T09-PRAGMATIC-RETRY4-QUALIFIED-IMAGE-REGRESSION-0001",
        "--output",
        "/opt/giclab-output/receipt.json",
    ]
    run_logged(command, evidence_root=attempt, label="qualified-real-regression", timeout=300)
    receipt_path = attempt / "receipt.json"
    receipt = load_object(receipt_path, label="qualified real-evidence regression")
    interpreter = receipt.get("interpreter")
    closure = receipt.get("evaluator_closure")
    static_projection = static_receipt.get("semantic_projection")
    if (
        receipt.get("receipt_id") != "T09-PRAGMATIC-RETRY4-QUALIFIED-IMAGE-REGRESSION-0001"
        or receipt.get("source_archive_sha256")
        != "63ed19b35bcb4cb62c3796a80a48004937340eb3826f9657a1006e251772255d"
        or receipt.get("dataset_sha256")
        != "359300b029c6891567816f351bf8786e9b018d7af8a1a44b7da9ba5ef4651288"
        or receipt.get("semantic_projection") != static_projection
        or receipt.get("accepted_scientific_and_evaluator_fields_equal") is not True
        or receipt.get("network_disabled") is not True
        or receipt.get("additional_model_requests") != 0
        or receipt.get("additional_browser_actions") != 0
        or not isinstance(interpreter, dict)
        or interpreter.get("executable_sha256") != image_files.get("/opt/sira/.venv/bin/python")
        or not isinstance(closure, dict)
        or closure.get("evaluator_contract_sha256") != file_sha256(paths["evaluator"])
    ):
        raise T09HostError("qualified-image real-evidence regression drifted")
    return receipt


def final_image_runtime_preflight(
    *,
    artifact_root: Path,
    prefix: list[str],
    image_id: str,
    command_document: dict[str, Any],
) -> dict[str, Any]:
    attempt = artifact_root / "pilot-v6/final-image-runtime-preflight"
    attempt.mkdir(parents=True, mode=0o700)
    command_manifests = manifests(command_document)
    reactive = next(item for item in command_manifests if item["condition"] == "reactive")
    simulative = next(item for item in command_manifests if item["condition"] == "simulative")
    write_exclusive(
        attempt / "condition-commands-input.json",
        {"commands": {"reactive": reactive["argv"], "simulative": simulative["argv"]}},
    )
    run_logged(
        [
            *prefix,
            "run",
            "--rm",
            "--network",
            "none",
            "--read-only",
            "--user",
            "1000:1000",
            "--env",
            "CUDA_VISIBLE_DEVICES=",
            "--mount",
            f"type=bind,src={attempt},dst=/giclab/attempt",
            "--entrypoint",
            "/opt/sira/.venv/bin/python",
            image_id,
            "/opt/giclab/runtime_preflight.py",
            "--attempt-root",
            "/giclab/attempt",
        ],
        evidence_root=attempt,
        label="final-image-runtime-preflight",
        timeout=300,
    )
    receipt = load_object(attempt / "runtime-preflight.json", label="image runtime preflight")
    upstream = receipt.get("upstream_runner_import")
    if (
        receipt.get("python_version") != "3.11.14"
        or receipt.get("artifact_writer") != "passed"
        or receipt.get("budget_ledger") != "passed"
        or receipt.get("condition_command_renderer") != "passed"
        or receipt.get("owned_cleanup") != "passed"
        or not isinstance(upstream, dict)
        or upstream.get("sha256") != EXPECTED_UPSTREAM_RUNNER_SHA256
        or upstream.get("status") != "passed"
        or upstream.get("browser_or_model_action") is not False
    ):
        raise T09HostError("final replacement image runtime contract drifted")
    return receipt


def final_image_file_hashes(
    *,
    artifact_root: Path,
    prefix: list[str],
    image_id: str,
) -> dict[str, str]:
    evidence = artifact_root / "pilot-v6/final-image-file-hashes"
    expected_paths = {
        "/opt/giclab/container_entrypoint.py": (
            "2696c3d9980a6d3c14dcb55fc5b540732a953fb388c8117af020b464dfacb4da"
        ),
        "/opt/giclab/model_preflight.py": (
            "fffd46ae0b325e37c692a36f9ad05481bb4901fef3810a9a4ff2d82f510d0729"
        ),
        "/opt/giclab/browser_preflight.py": (
            "9a69d3f40e3931a817f7bf137f9fab36d14bebf93bab403511df5ffe3d34ba93"
        ),
        "/opt/giclab/runtime_preflight.py": T07_RUNTIME_PREFLIGHT_SHA256,
        "/opt/giclab-src/giclab/harness/sira_gate_a_runtime.py": T07_RUNTIME_SHA256,
        "/opt/sira/scripts/run_web_agent.py": EXPECTED_UPSTREAM_RUNNER_SHA256,
        "/opt/giclab/installed-packages.txt": EXPECTED_PACKAGE_MANIFEST_SHA256,
    }
    interpreter_path = "/opt/sira/.venv/bin/python"
    run_logged(
        [
            *prefix,
            "run",
            "--rm",
            "--network",
            "none",
            "--read-only",
            "--entrypoint",
            "/usr/bin/sha256sum",
            image_id,
            *expected_paths,
            interpreter_path,
        ],
        evidence_root=evidence,
        label="sha256sum",
        timeout=120,
    )
    observed: dict[str, str] = {}
    for line in (evidence / "sha256sum.stdout").read_text(encoding="utf-8").splitlines():
        parts = line.split("  ", 1)
        if len(parts) != 2:
            raise T09HostError("final image file-hash output is malformed")
        observed[parts[1]] = parts[0]
    if (
        set(observed) != {*expected_paths, interpreter_path}
        or any(observed.get(path) != digest for path, digest in expected_paths.items())
        or re.fullmatch(r"[a-f0-9]{64}", observed.get(interpreter_path, "")) is None
    ):
        raise T09HostError("final replacement image file identities drifted")
    write_exclusive(evidence / "receipt.json", observed)
    return observed


def model_metadata_preflight(
    *,
    artifact_root: Path,
    secret_file: Path,
    prefix: list[str],
    image_id: str,
) -> dict[str, Any]:
    attempt = artifact_root / "pilot-v6/model-metadata-preflight"
    attempt.mkdir(parents=True, mode=0o700)
    command = [
        *prefix,
        "run",
        "--rm",
        "--network",
        "bridge",
        "--read-only",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges=true",
        "--user",
        "1000:1000",
        "--mount",
        f"type=bind,src={attempt},dst=/giclab/attempt",
        "--mount",
        f"type=bind,src={secret_file},dst=/run/secrets/sira_api_key,readonly",
        "--entrypoint",
        "/opt/sira/.venv/bin/python",
        image_id,
        "/opt/giclab/container_entrypoint.py",
        "--runtime-assignment",
        "OPENAI_API_KEY",
        "--",
        "/opt/sira/.venv/bin/python",
        "/opt/giclab/model_preflight.py",
    ]
    run_logged(command, evidence_root=attempt, label="model-metadata", timeout=60)
    receipt = load_object(attempt / "model-availability.json", label="model availability")
    if (
        receipt.get("method") != "GET"
        or receipt.get("host") != "api.openai.com"
        or receipt.get("path") != f"/v1/models/{MODEL}"
        or receipt.get("model") != MODEL
        or receipt.get("available") is not True
        or receipt.get("retry_count") != 0
        or receipt.get("redirect_follow_count") != 0
    ):
        raise T09HostError("exact model metadata preflight drifted")
    return receipt


def _replacement_inspect(
    artifact_root: Path,
    *,
    expected_image_id: str,
) -> dict[str, Any]:
    inspect_path = (
        artifact_root / "pilot-v6/replacement-image-qualification/replacement-image-inspect.stdout"
    )
    value: object = json.loads(inspect_path.read_text(encoding="utf-8"))
    if not isinstance(value, list) or len(value) != 1 or not isinstance(value[0], dict):
        raise T09HostError("replacement image inspect evidence is malformed")
    inspect = cast(dict[str, Any], value[0])
    config = inspect.get("Config")
    if (
        inspect.get("Id") != expected_image_id
        or inspect.get("Architecture") != "amd64"
        or inspect.get("Os") != "linux"
        or not isinstance(config, dict)
        or config.get("User") != "1000:1000"
        or config.get("WorkingDir") != "/opt/sira"
        or config.get("Cmd") != ["/bin/bash"]
    ):
        raise T09HostError("replacement image config violates the reviewed runtime")
    environment = config.get("Env")
    expected_environment = {
        "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "PLAYWRIGHT_BROWSERS_PATH=/ms-playwright",
        "PYTHONDONTWRITEBYTECODE=1",
        "PYTHONPATH=/opt/giclab-src",
        "UV_HTTP_RETRIES=0",
        "UV_LINK_MODE=copy",
        "UV_NO_MODIFY_PATH=1",
        "UV_PYTHON_INSTALL_DIR=/opt/giclab-python",
        "UV_PYTHON_DOWNLOADS=automatic",
        "UV_PROJECT_ENVIRONMENT=/opt/sira/.venv",
    }
    if not isinstance(environment, list) or set(environment) != expected_environment:
        raise T09HostError("replacement image environment contract drifted")
    return inspect


def image_equivalence_adjudication(
    *,
    repository: Path,
    artifact_root: Path,
    image_id: str,
) -> dict[str, object]:
    historical_path = (
        repository / "experiments/EXP-0001-sira-simulative-vs-reactive/contracts/"
        "T09_PILOT_HISTORICAL_RUNTIME_EVIDENCE.json"
    )
    historical = load_object(historical_path, label="historical runtime evidence")
    replacement = _replacement_inspect(artifact_root, expected_image_id=image_id)
    historical_config = historical.get("image_inspect_projection", {}).get("Config")
    if replacement.get("Config") != historical_config:
        raise T09HostError("replacement image has a functional config difference")
    historical_layers = historical.get("image_inspect_projection", {}).get("RootFS")
    replacement_layers = replacement.get("RootFS")
    adjudication: dict[str, object] = {
        "schema_version": "0.1.0",
        "qualification_id": QUALIFICATION_ID,
        "historical_image_id": HISTORICAL_IMAGE_ID,
        "replacement_image_id": image_id,
        "historical_evidence_sha256": file_sha256(historical_path),
        "historical_source_inspect_sha256": historical.get("source_image_inspect_sha256"),
        "comparisons": {
            "config": {
                "equal": True,
                "classification": "nonfunctional_build_metadata",
            },
            "rootfs_layer_list": {
                "equal": replacement_layers == historical_layers,
                "classification": "nonfunctional_build_metadata",
                "basis": "all separately pinned final-container functional identities passed",
            },
            "image_id": {
                "equal": image_id == HISTORICAL_IMAGE_ID,
                "classification": "nonfunctional_build_metadata",
            },
            "created_and_build_metadata": {
                "classification": "nonfunctional_build_metadata",
            },
            "history_structure": {
                "classification": "historical_evidence_unavailable",
            },
        },
        "functional_runtime_difference": False,
        "exact_digest_equality_required": False,
        "cause_determinable": False,
        "cause": (
            "inspect evidence proves config equality but lacks historical image-history and "
            "build-context bytes; the exact digest cause is not determinable"
        ),
    }
    write_exclusive(artifact_root / "pilot-v6/image-equivalence-adjudication.json", adjudication)
    return adjudication


def write_frozen_run_manifest(
    *,
    repository: Path,
    artifact_root: Path,
    package_commit: str,
    dynamic: dict[str, object],
    image_materialization: dict[str, object],
    command_document: dict[str, Any],
    runtime_receipt: dict[str, Any],
    offline_receipt: dict[str, Any],
    browser_receipt: dict[str, object],
    evaluator_receipt: dict[str, object],
    file_hashes: dict[str, str],
    model_receipt: dict[str, Any],
    model_credential_scan_receipt: dict[str, object],
    adjudication: dict[str, object],
    static_real_evidence_regression: dict[str, Any],
    qualified_real_evidence_regression_receipt: dict[str, Any],
    regression_archive_staging_receipt: dict[str, object],
    local_finalizer_qualification_receipt: dict[str, Any],
    preflight_resume_transition: dict[str, Any] | None = None,
    slot2_authority: dict[str, object] | None = None,
) -> tuple[Path, dict[str, object]]:
    paths = contract_paths(repository)
    image_id = image_materialization.get("image_id")
    if not isinstance(image_id, str) or re.fullmatch(r"sha256:[a-f0-9]{64}", image_id) is None:
        raise T09HostError("qualified replacement image ID is unavailable")
    if image_id_if_present(docker_prefix(), image_id) != image_id:
        raise T09HostError("qualified replacement image is no longer loaded by exact ID")
    python_interpreter_path = "/opt/sira/.venv/bin/python"
    python_interpreter_sha256 = file_hashes.get(python_interpreter_path)
    if (
        not isinstance(python_interpreter_sha256, str)
        or re.fullmatch(r"[a-f0-9]{64}", python_interpreter_sha256) is None
    ):
        raise T09HostError("qualified Python interpreter identity is unavailable")
    runtime_state = _runtime_budget_state(artifact_root)
    empirical = runtime_state.get("empirical_attempts_entered")
    first_pair_started = runtime_state.get("first_pair_started_at_epoch")
    owned_lambda_started = dynamic.get("owned_lambda_started_at_epoch")
    if empirical != []:
        raise T09HostError("runtime cannot freeze after empirical entry")
    if (
        runtime_state.get("actual_credential_exposure_detected") is not False
        or runtime_state.get("credential_safety_stop_detected") is not False
    ):
        raise T09HostError("runtime cannot freeze after a credential safety failure")
    if (
        not isinstance(first_pair_started, (int, float))
        or isinstance(first_pair_started, bool)
        or not isinstance(owned_lambda_started, (int, float))
        or isinstance(owned_lambda_started, bool)
        or first_pair_started < owned_lambda_started
        or first_pair_started > time.time() + 30.0
    ):
        raise T09HostError("first-pair wall origin cannot be frozen")
    qualification_root = artifact_root / "pilot-v6/replacement-image-qualification"
    launch_slot = dynamic.get("launch_slot")
    expected_materialization_policy = (
        SLOT1_IMAGE_MATERIALIZATION_POLICY
        if launch_slot == 1
        else SLOT2_IMAGE_MATERIALIZATION_POLICY
        if launch_slot == 2
        else None
    )
    if launch_slot == 1:
        if slot2_authority is not None:
            raise T09HostError("first launch retained slot-2 authority")
        slot2_authority_sha256: str | None = None
    else:
        if (
            slot2_authority is None
            or slot2_authority.get("replacement_eligibility_sha256")
            != dynamic.get("replacement_eligibility_sha256")
            or slot2_authority.get("replacement_eligibility_source_manifest_sha256")
            != dynamic.get("replacement_eligibility_source_manifest_sha256")
        ):
            raise T09HostError("slot-2 authority does not bind the provider entry")
        slot2_authority_sha256 = canonical_sha256(slot2_authority)
    if image_materialization.get("image_materialization_policy") != expected_materialization_policy:
        raise T09HostError("image materialization policy drifted before freeze")
    if qualified_real_evidence_regression_receipt.get(
        "semantic_projection"
    ) != static_real_evidence_regression.get("semantic_projection"):
        raise T09HostError("static and qualified real-evidence regressions disagree")
    if preflight_resume_transition is not None:
        raise T09HostError("same-host preflight resume is permanently disabled")
    if dynamic.get("launch_slot") == 1:
        resume_fields: dict[str, object] = {
            "preflight_transition_mode": "fresh",
            "preflight_resume_source_sha256": None,
            "preflight_resume_argv_sha256": None,
            "preflight_resume_transition_sha256": None,
            "preflight_failure_prefix_manifest_sha256": None,
            "preflight_prior_package_commit": None,
            "preflight_prior_plan_sha256": None,
            "preflight_prior_state_sha256": None,
            "preflight_transition_state_sha256": None,
            "preflight_prior_aggregate_sha256": None,
            "preflight_transition_aggregate_sha256": None,
            "preflight_retained_materialization_sha256": None,
        }
    else:
        resume_fields = {
            "preflight_transition_mode": "replacement-launch",
            "preflight_resume_source_sha256": None,
            "preflight_resume_argv_sha256": None,
            "preflight_resume_transition_sha256": None,
            "preflight_failure_prefix_manifest_sha256": None,
            "preflight_prior_package_commit": None,
            "preflight_prior_plan_sha256": None,
            "preflight_prior_state_sha256": None,
            "preflight_transition_state_sha256": None,
            "preflight_prior_aggregate_sha256": None,
            "preflight_transition_aggregate_sha256": None,
            "preflight_retained_materialization_sha256": None,
        }
    manifest: dict[str, object] = {
        "schema_version": "0.1.0",
        "manifest_id": FROZEN_RUN_MANIFEST_ID,
        "plan_id": PLAN_ID,
        "host_run_id": HOST_RUN_ID,
        "qualification_id": QUALIFICATION_ID,
        "qualification_count": 1,
        "build_count": image_materialization.get("build_count"),
        "image_materialization_policy": expected_materialization_policy,
        "source_contract_sha256": AUTHORIZATION_SOURCE_SHA256,
        "clean_package_commit": package_commit,
        "plan_sha256": file_sha256(paths["plan"]),
        "execution_contract_sha256": file_sha256(paths["execution"]),
        "runtime_contract_sha256": file_sha256(paths["runtime"]),
        "command_manifests_sha256": file_sha256(paths["commands"]),
        "provider_entry_receipt_sha256": dynamic.get("receipt_sha256"),
        "owned_instance_identity_sha256": dynamic.get("owned_instance_identity_sha256"),
        "lambda_started_at_epoch": dynamic.get("provider_preflight_started_at_epoch"),
        "provider_preflight_started_at_epoch": dynamic.get("provider_preflight_started_at_epoch"),
        "campaign_started_at_epoch": runtime_state.get("campaign_started_at_epoch"),
        "owned_lambda_started_at_epoch": dynamic.get("owned_lambda_started_at_epoch"),
        "first_pair_started_at_epoch": float(first_pair_started),
        "prior_lambda_duration_seconds": dynamic.get("prior_campaign_lambda_duration_seconds"),
        "prior_lambda_cost_usd": dynamic.get("prior_campaign_lambda_cost_usd"),
        "launch_slot": dynamic.get("launch_slot"),
        "launch_count": dynamic.get("launch_count"),
        "replacement_eligibility_sha256": dynamic.get("replacement_eligibility_sha256"),
        "replacement_eligibility_source_manifest_sha256": dynamic.get(
            "replacement_eligibility_source_manifest_sha256"
        ),
        "slot2_authority_sha256": slot2_authority_sha256,
        "provider_entry_package_commit": dynamic.get("provider_entry_package_commit"),
        "provider_package_transition_sha256": dynamic.get("provider_package_transition_sha256"),
        "slot1_failure_archive_sha256": None,
        "slot1_image_archive_sha256": None,
        "slot1_entry_receipt_sha256": None,
        "slot1_closeout_receipt_sha256": None,
        "image_import_count": image_materialization.get("image_import_count", 0),
        "additional_build_count": image_materialization.get("additional_build_count", 0),
        "replacement_image_id": image_id,
        "historical_image_id": HISTORICAL_IMAGE_ID,
        "build_context_manifest_sha256": image_materialization.get("build_context_manifest_sha256"),
        "build_context_payload_sha256": image_materialization.get("build_context_payload_sha256"),
        "build_context_exclusions_sha256": image_materialization.get(
            "build_context_exclusions_sha256"
        ),
        "containerfile_sha256": image_materialization.get("containerfile_sha256"),
        "build_command_sha256": image_materialization.get("build_command_sha256"),
        "image_inspect_sha256": image_materialization.get("image_inspect_sha256"),
        "package_manifest_sha256": EXPECTED_PACKAGE_MANIFEST_SHA256,
        "chromium_executable_sha256": EXPECTED_CHROMIUM_SHA256,
        "patched_upstream_runner_sha256": EXPECTED_UPSTREAM_RUNNER_SHA256,
        "python_interpreter_path": python_interpreter_path,
        "python_interpreter_sha256": python_interpreter_sha256,
        "runtime_preflight_sha256": canonical_sha256(runtime_receipt),
        "offline_preflight_sha256": canonical_sha256(offline_receipt),
        "browser_preflight_sha256": canonical_sha256(browser_receipt),
        "evaluator_materialization_sha256": canonical_sha256(evaluator_receipt),
        "evaluator_overlay_manifest_sha256": evaluator_receipt.get("overlay_manifest_sha256"),
        "evaluator_overlay_entries_sha256": evaluator_receipt.get("overlay_entries_sha256"),
        "evaluator_overlay_packages_sha256": evaluator_receipt.get(
            "overlay_package_manifest_sha256"
        ),
        "final_image_file_hashes_sha256": canonical_sha256(file_hashes),
        "model_metadata_receipt_sha256": canonical_sha256(model_receipt),
        "model_metadata_credential_scan_sha256": canonical_sha256(model_credential_scan_receipt),
        "model_metadata_request_count": 1,
        "model_task_request_count": 0,
        "task_browser_action_count": 0,
        "actual_credential_exposure_detected": False,
        "credential_safety_stop_detected": False,
        "image_adjudication_sha256": canonical_sha256(adjudication),
        "static_real_evidence_regression_sha256": file_sha256(paths["real_regression"]),
        "regression_archive_staging_sha256": file_sha256(
            artifact_root / "pilot-v6/regression-archive-staging/receipt.json"
        ),
        "regression_archive_role": regression_archive_staging_receipt.get("archive_role"),
        "regression_archive_bytes": regression_archive_staging_receipt.get("bytes"),
        "regression_archive_sha256": regression_archive_staging_receipt.get("sha256"),
        "regression_archive_canonical_staged_destination": (
            regression_archive_staging_receipt.get("canonical_staged_destination")
        ),
        "regression_archive_source_provenance_category": (
            regression_archive_staging_receipt.get("source_provenance_category")
        ),
        "qualified_real_evidence_regression_sha256": file_sha256(
            artifact_root / "pilot-v6/qualified-real-evidence-regression/receipt.json"
        ),
        "qualified_real_evidence_semantic_sha256": qualified_real_evidence_regression_receipt.get(
            "semantic_projection_sha256"
        ),
        "local_finalizer_qualification_sha256": file_sha256(
            artifact_root / "pilot-v6/local-finalizer-qualification.json"
        ),
        "local_finalizer_interpreter_sha256": local_finalizer_qualification_receipt.get(
            "interpreter_sha256"
        ),
        "local_finalizer_interpreter_dependency_manifest_sha256": (
            local_finalizer_qualification_receipt.get("interpreter_dependency_manifest_sha256")
        ),
        "local_finalizer_interpreter_dependency_tree_sha256": (
            local_finalizer_qualification_receipt.get("interpreter_dependency_tree_sha256")
        ),
        "local_finalizer_evaluator_dependency_tree_sha256": (
            local_finalizer_qualification_receipt.get("dependency_tree_sha256")
        ),
        "command_argv_sha256s": [item["argv_sha256"] for item in manifests(command_document)],
        "pair_diffs": command_document.get("pair_diffs"),
        "attempt_order": list(RUN_IDS),
        "empirical_entry_crossed": False,
        "post_entry_code_science_image_freeze": True,
        **resume_fields,
        "source_receipts": {
            "materialization": file_sha256(qualification_root / "receipt.json"),
            "build_context": file_sha256(qualification_root / "build-context-manifest.json"),
            "build_context_exclusions": file_sha256(
                qualification_root / "build-context-exclusions.json"
            ),
            "image_inspect": file_sha256(qualification_root / "replacement-image-inspect.stdout"),
            "final_image_file_hashes": file_sha256(
                artifact_root / "pilot-v6/final-image-file-hashes/receipt.json"
            ),
            "evaluator_overlay": file_sha256(
                artifact_root / "pilot-v6/evaluator-overlay-manifest.json"
            ),
            "model_metadata_credential_scan": file_sha256(
                artifact_root / "pilot-v6/model-metadata-credential-scan.json"
            ),
            "static_real_evidence_regression": file_sha256(paths["real_regression"]),
            "regression_archive_staging": file_sha256(
                artifact_root / "pilot-v6/regression-archive-staging/receipt.json"
            ),
            "qualified_real_evidence_regression": file_sha256(
                artifact_root / "pilot-v6/qualified-real-evidence-regression/receipt.json"
            ),
            "local_finalizer_qualification": file_sha256(
                artifact_root / "pilot-v6/local-finalizer-qualification.json"
            ),
            "preflight_resume_transition": resume_fields["preflight_resume_transition_sha256"],
            "slot2_eligibility": dynamic.get("replacement_eligibility_sha256"),
            "slot2_authority_source": dynamic.get("replacement_eligibility_source_manifest_sha256"),
            "slot2_authority": slot2_authority_sha256,
            "provider_package_transition": dynamic.get("provider_package_transition_sha256"),
        },
    }
    if (
        manifest["build_count"] not in {0, 1}
        or (manifest["build_count"] == 0 and manifest["image_import_count"] != 1)
        or (manifest["build_count"] == 1 and manifest["image_import_count"] != 0)
        or (
            launch_slot == 2
            and (
                manifest["image_materialization_policy"] != SLOT2_IMAGE_MATERIALIZATION_POLICY
                or manifest["build_count"] != 0
                or manifest["image_import_count"] != 1
                or manifest["additional_build_count"] != 0
                or manifest["replacement_image_id"] != RETAINED_IMAGE_ID
            )
        )
        or not isinstance(manifest["pair_diffs"], list)
        or any(
            not isinstance(item, dict) or item.get("valid") is not True
            for item in cast(list[object], manifest["pair_diffs"])
        )
    ):
        raise T09HostError("replacement runtime cannot be frozen")
    path = artifact_root / "pilot-v6/frozen-run-manifest.json"
    write_exclusive(path, manifest)
    return path, manifest


def load_frozen_run_manifest(
    artifact_root: Path,
    *,
    repository: Path,
    package_commit: str,
    require_image: bool = True,
) -> tuple[dict[str, Any], str]:
    path = artifact_root / "pilot-v6/frozen-run-manifest.json"
    metadata = path.stat(follow_symlinks=False)
    if (
        not stat.S_ISREG(metadata.st_mode)
        or metadata.st_uid != os.getuid()
        or metadata.st_nlink != 1
        or stat.S_IMODE(metadata.st_mode) != 0o600
    ):
        raise T09HostError("frozen run manifest metadata is unsafe")
    manifest = load_object(path, label="frozen run manifest")
    try:
        typed_qualification = RuntimeQualification.from_document(manifest)
    except T09PilotError as exc:
        raise T09HostError(str(exc)) from exc
    paths = contract_paths(repository)
    provider_entry = load_object(
        artifact_root / "pilot-v6/provider-entry.json",
        label="provider entry summary",
    )
    model_credential_scan_path = artifact_root / "pilot-v6/model-metadata-credential-scan.json"
    model_credential_scan = load_object(
        model_credential_scan_path,
        label="model metadata credential scan",
    )
    archive_staging_path = artifact_root / "pilot-v6/regression-archive-staging/receipt.json"
    archive_staging = load_object(
        archive_staging_path,
        label="regression archive staging",
    )
    if archive_staging != {
        "schema_version": "0.1.0",
        "archive_role": "historical-v4-real-evidence-regression",
        "source_provenance_category": "private-operator-run-owned-input",
        "source_absolute_path_retained": False,
        "source_no_follow_regular_file": True,
        "source_unchanged": True,
        "bytes": PRIVATE_REGRESSION_ARCHIVE_BYTES,
        "sha256": PRIVATE_REGRESSION_ARCHIVE_SHA256,
        "canonical_staged_destination": PRIVATE_REGRESSION_ARCHIVE_PATH.as_posix(),
        "exclusive_creation": True,
        "target_mode": "0600",
        "target_fsync": True,
        "parent_directory_fsync": True,
        "target_rehash_verified": True,
    }:
        raise T09HostError("regression archive staging receipt drifted")
    if (
        model_credential_scan.get("actual_credential_exposure_detected") is not False
        or model_credential_scan.get("secret_bearing_artifacts_removed") != []
        or model_credential_scan.get("remaining_exact_secret_matches") != []
        or model_credential_scan.get("exact_secret_scan_passed") is not True
        or model_credential_scan.get("empirical_entry_permitted") is not True
    ):
        raise T09HostError("model metadata credential scan did not pass cleanly")
    runtime_state = _runtime_budget_state(artifact_root)
    expected = {
        "plan_id": PLAN_ID,
        "host_run_id": HOST_RUN_ID,
        "qualification_id": QUALIFICATION_ID,
        "qualification_count": 1,
        "build_count": manifest.get("build_count"),
        "image_materialization_policy": (
            SLOT1_IMAGE_MATERIALIZATION_POLICY
            if provider_entry.get("launch_slot") == 1
            else SLOT2_IMAGE_MATERIALIZATION_POLICY
        ),
        "source_contract_sha256": AUTHORIZATION_SOURCE_SHA256,
        "clean_package_commit": package_commit,
        "plan_sha256": file_sha256(paths["plan"]),
        "execution_contract_sha256": file_sha256(paths["execution"]),
        "runtime_contract_sha256": file_sha256(paths["runtime"]),
        "command_manifests_sha256": file_sha256(paths["commands"]),
        "provider_entry_receipt_sha256": provider_entry.get("receipt_sha256"),
        "owned_instance_identity_sha256": provider_entry.get("owned_instance_identity_sha256"),
        "lambda_started_at_epoch": provider_entry.get("provider_preflight_started_at_epoch"),
        "provider_preflight_started_at_epoch": provider_entry.get(
            "provider_preflight_started_at_epoch"
        ),
        "campaign_started_at_epoch": runtime_state.get("campaign_started_at_epoch"),
        "owned_lambda_started_at_epoch": provider_entry.get("owned_lambda_started_at_epoch"),
        "first_pair_started_at_epoch": runtime_state.get("first_pair_started_at_epoch"),
        "prior_lambda_duration_seconds": provider_entry.get(
            "prior_campaign_lambda_duration_seconds"
        ),
        "prior_lambda_cost_usd": provider_entry.get("prior_campaign_lambda_cost_usd"),
        "launch_slot": provider_entry.get("launch_slot"),
        "launch_count": provider_entry.get("launch_count"),
        "replacement_eligibility_sha256": provider_entry.get("replacement_eligibility_sha256"),
        "replacement_eligibility_source_manifest_sha256": provider_entry.get(
            "replacement_eligibility_source_manifest_sha256"
        ),
        "slot2_authority_sha256": manifest.get("slot2_authority_sha256"),
        "provider_entry_package_commit": provider_entry.get("provider_entry_package_commit"),
        "provider_package_transition_sha256": provider_entry.get(
            "provider_package_transition_sha256"
        ),
        "slot1_failure_archive_sha256": None,
        "slot1_image_archive_sha256": None,
        "slot1_entry_receipt_sha256": None,
        "slot1_closeout_receipt_sha256": None,
        "image_import_count": manifest.get("image_import_count"),
        "additional_build_count": 0,
        "package_manifest_sha256": EXPECTED_PACKAGE_MANIFEST_SHA256,
        "chromium_executable_sha256": EXPECTED_CHROMIUM_SHA256,
        "patched_upstream_runner_sha256": EXPECTED_UPSTREAM_RUNNER_SHA256,
        "python_interpreter_path": "/opt/sira/.venv/bin/python",
        "evaluator_overlay_manifest_sha256": manifest.get("evaluator_overlay_manifest_sha256"),
        "evaluator_overlay_entries_sha256": manifest.get("evaluator_overlay_entries_sha256"),
        "evaluator_overlay_packages_sha256": manifest.get("evaluator_overlay_packages_sha256"),
        "model_metadata_request_count": 1,
        "model_metadata_credential_scan_sha256": canonical_sha256(model_credential_scan),
        "model_task_request_count": 0,
        "task_browser_action_count": 0,
        "actual_credential_exposure_detected": False,
        "credential_safety_stop_detected": False,
        "static_real_evidence_regression_sha256": file_sha256(paths["real_regression"]),
        "regression_archive_staging_sha256": file_sha256(archive_staging_path),
        "regression_archive_role": archive_staging["archive_role"],
        "regression_archive_bytes": archive_staging["bytes"],
        "regression_archive_sha256": archive_staging["sha256"],
        "regression_archive_canonical_staged_destination": archive_staging[
            "canonical_staged_destination"
        ],
        "regression_archive_source_provenance_category": archive_staging[
            "source_provenance_category"
        ],
        "qualified_real_evidence_regression_sha256": file_sha256(
            artifact_root / "pilot-v6/qualified-real-evidence-regression/receipt.json"
        ),
        "local_finalizer_qualification_sha256": file_sha256(
            artifact_root / "pilot-v6/local-finalizer-qualification.json"
        ),
        "local_finalizer_interpreter_dependency_manifest_sha256": (
            manifest.get("local_finalizer_interpreter_dependency_manifest_sha256")
        ),
        "local_finalizer_interpreter_dependency_tree_sha256": (
            manifest.get("local_finalizer_interpreter_dependency_tree_sha256")
        ),
        "local_finalizer_evaluator_dependency_tree_sha256": (
            manifest.get("local_finalizer_evaluator_dependency_tree_sha256")
        ),
        "attempt_order": list(RUN_IDS),
        "empirical_entry_crossed": False,
        "post_entry_code_science_image_freeze": True,
    }
    if any(manifest.get(key) != value for key, value in expected.items()):
        raise T09HostError("frozen run manifest binding drifted")
    if (
        not isinstance(manifest.get("first_pair_started_at_epoch"), (int, float))
        or isinstance(manifest.get("first_pair_started_at_epoch"), bool)
        or cast(float, manifest["first_pair_started_at_epoch"])
        < cast(float, manifest["owned_lambda_started_at_epoch"])
    ):
        raise T09HostError("frozen first-pair wall origin drifted")
    source_receipts_for_transition = manifest.get("source_receipts")
    expected_transition_mode = (
        "fresh" if provider_entry.get("launch_slot") == 1 else "replacement-launch"
    )
    if (
        typed_qualification.preflight_transition_mode != expected_transition_mode
        or not isinstance(source_receipts_for_transition, dict)
        or source_receipts_for_transition.get("preflight_resume_transition") is not None
        or source_receipts_for_transition.get("slot2_eligibility")
        != typed_qualification.replacement_eligibility_sha256
        or source_receipts_for_transition.get("slot2_authority_source")
        != typed_qualification.replacement_eligibility_source_manifest_sha256
        or source_receipts_for_transition.get("slot2_authority")
        != typed_qualification.slot2_authority_sha256
        or source_receipts_for_transition.get("provider_package_transition")
        != typed_qualification.provider_package_transition_sha256
    ):
        raise T09HostError("frozen launch transition authority drifted")
    authority_root = artifact_root / "pilot-v6/slot2-authority"
    if typed_qualification.launch_slot == 1:
        if authority_root.exists() or authority_root.is_symlink():
            raise T09HostError("fresh launch retained unexpected slot-2 authority")
    else:
        authority = slot2_authority_binding(authority_root)
        if (
            canonical_sha256(authority) != typed_qualification.slot2_authority_sha256
            or authority.get("replacement_eligibility_sha256")
            != typed_qualification.replacement_eligibility_sha256
            or authority.get("replacement_eligibility_source_manifest_sha256")
            != typed_qualification.replacement_eligibility_source_manifest_sha256
        ):
            raise T09HostError("retained slot-2 authority drifted")
    file_hash_receipt_path = artifact_root / "pilot-v6/final-image-file-hashes/receipt.json"
    file_hash_receipt = load_object(file_hash_receipt_path, label="final image file hashes")
    materialization_path = artifact_root / "pilot-v6/replacement-image-qualification/receipt.json"
    materialization = load_object(materialization_path, label="image materialization")
    if (
        materialization.get("qualification_id") != QUALIFICATION_ID
        or materialization.get("image_id") != manifest.get("replacement_image_id")
        or materialization.get("build_count") != typed_qualification.build_count
        or materialization.get("image_import_count") != typed_qualification.image_import_count
        or materialization.get("additional_build_count") != 0
        or materialization.get("image_materialization_policy")
        != typed_qualification.image_materialization_policy
        or (
            typed_qualification.launch_slot == 2
            and (
                typed_qualification.image_materialization_policy
                != SLOT2_IMAGE_MATERIALIZATION_POLICY
                or typed_qualification.build_count != 0
                or typed_qualification.image_import_count != 1
                or typed_qualification.replacement_image_id != RETAINED_IMAGE_ID
            )
        )
        or (
            typed_qualification.build_count == 0
            and (
                materialization.get("method") != "exact-retained-image-archive-import"
                or materialization.get("retained_image_archive_sha256")
                != RETAINED_IMAGE_ARCHIVE_SHA256
                or materialization.get("retained_image_archive_bytes")
                != RETAINED_IMAGE_ARCHIVE_BYTES
                or materialization.get("image_id") != RETAINED_IMAGE_ID
            )
        )
    ):
        raise T09HostError("frozen image load/build materialization drifted")
    source_receipts = manifest.get("source_receipts")
    qualified_regression_path = (
        artifact_root / "pilot-v6/qualified-real-evidence-regression/receipt.json"
    )
    qualified_regression = load_object(
        qualified_regression_path,
        label="qualified real-evidence regression",
    )
    static_regression = validate_real_evidence_regression(
        repository,
        expected_finalizer_source_sha256=git_file_sha256(
            repository,
            package_commit,
            FINALIZER_RELATIVE_PATH,
        ),
    )
    local_qualification_path = artifact_root / "pilot-v6/local-finalizer-qualification.json"
    local_qualification = validate_local_finalizer_qualification(
        local_qualification_path,
        repository=repository,
        package_commit=package_commit,
        require_local_runtime=False,
    )
    if (
        not isinstance(source_receipts, dict)
        or source_receipts.get("materialization") != file_sha256(materialization_path)
        or source_receipts.get("final_image_file_hashes") != file_sha256(file_hash_receipt_path)
        or source_receipts.get("model_metadata_credential_scan")
        != file_sha256(model_credential_scan_path)
        or manifest.get("final_image_file_hashes_sha256") != canonical_sha256(file_hash_receipt)
        or file_hash_receipt.get(typed_qualification.python_interpreter_path)
        != typed_qualification.python_interpreter_sha256
        or source_receipts.get("static_real_evidence_regression")
        != file_sha256(paths["real_regression"])
        or source_receipts.get("regression_archive_staging") != file_sha256(archive_staging_path)
        or source_receipts.get("qualified_real_evidence_regression")
        != file_sha256(qualified_regression_path)
        or source_receipts.get("local_finalizer_qualification")
        != file_sha256(local_qualification_path)
        or manifest.get("local_finalizer_interpreter_sha256")
        != local_qualification.get("interpreter_sha256")
        or manifest.get("local_finalizer_interpreter_dependency_manifest_sha256")
        != local_qualification.get("interpreter_dependency_manifest_sha256")
        or manifest.get("local_finalizer_interpreter_dependency_tree_sha256")
        != local_qualification.get("interpreter_dependency_tree_sha256")
        or manifest.get("local_finalizer_evaluator_dependency_tree_sha256")
        != local_qualification.get("dependency_tree_sha256")
        or qualified_regression.get("semantic_projection")
        != static_regression.get("semantic_projection")
        or qualified_regression.get("receipt_id")
        != "T09-PRAGMATIC-RETRY4-QUALIFIED-IMAGE-REGRESSION-0001"
        or qualified_regression.get("network_disabled") is not True
        or qualified_regression.get("additional_model_requests") != 0
        or qualified_regression.get("additional_browser_actions") != 0
    ):
        raise T09HostError("frozen Python interpreter source receipt drifted")
    exclusion_path = (
        artifact_root / "pilot-v6/replacement-image-qualification/build-context-exclusions.json"
    )
    context_path = (
        artifact_root / "pilot-v6/replacement-image-qualification/build-context-manifest.json"
    )
    inspect_path = (
        artifact_root / "pilot-v6/replacement-image-qualification/replacement-image-inspect.stdout"
    )
    if (
        manifest.get("build_context_manifest_sha256") != file_sha256(context_path)
        or manifest.get("build_context_exclusions_sha256") != file_sha256(exclusion_path)
        or manifest.get("image_inspect_sha256") != file_sha256(inspect_path)
        or source_receipts.get("build_context") != file_sha256(context_path)
        or source_receipts.get("build_context_exclusions") != file_sha256(exclusion_path)
        or source_receipts.get("image_inspect") != file_sha256(inspect_path)
    ):
        raise T09HostError("frozen build-context exclusion receipt drifted")
    image_id = typed_qualification.replacement_image_id
    if (
        not isinstance(image_id, str)
        or re.fullmatch(r"sha256:[a-f0-9]{64}", image_id) is None
        or (require_image and image_id_if_present(docker_prefix(), image_id) != image_id)
    ):
        raise T09HostError("frozen replacement image is unavailable or drifted")
    pair_diffs = manifest.get("pair_diffs")
    if (
        not isinstance(pair_diffs, list)
        or len(pair_diffs) != 2
        or any(not isinstance(item, dict) or item.get("valid") is not True for item in pair_diffs)
    ):
        raise T09HostError("frozen pair diff binding drifted")
    return manifest, file_sha256(path)


def initialize_state(
    root: Path,
    execution_sha256: str,
    *,
    lambda_started_at_epoch: float,
    owned_lambda_started_at_epoch: float | None = None,
    prior_lambda_duration_seconds: float = 0.0,
    prior_lambda_cost_usd: float = 0.0,
    launch_slot: int = 1,
    replacement_eligibility_sha256: str | None = None,
    replacement_eligibility_source_manifest_sha256: str | None = None,
) -> None:
    owned_started = (
        lambda_started_at_epoch
        if owned_lambda_started_at_epoch is None
        else owned_lambda_started_at_epoch
    )
    state: dict[str, object] = {
        "schema_version": "0.2.0",
        "plan_id": PLAN_ID,
        "execution_contract_sha256": execution_sha256,
        "pilot_started_at_epoch": None,
        "lambda_started_at_epoch": lambda_started_at_epoch,
        "provider_preflight_started_at_epoch": owned_started,
        "campaign_started_at_epoch": None,
        "owned_lambda_started_at_epoch": owned_started,
        "prior_campaign_lambda_duration_seconds": prior_lambda_duration_seconds,
        "prior_campaign_lambda_cost_usd": prior_lambda_cost_usd,
        "launch_slot": launch_slot,
        "launch_count": launch_slot,
        "replacement_eligibility_sha256": replacement_eligibility_sha256,
        "replacement_eligibility_source_manifest_sha256": (
            replacement_eligibility_source_manifest_sha256
        ),
        "first_pair_started_at_epoch": None,
        "second_pair_started_at_epoch": None,
        "empirical_attempts_entered": [],
        "raw_attempts_complete": [],
        "raw_attempt_bindings": {},
        "attempts_completed": [],
        "attempt_finalizations": {},
        "attempt_finalization_history": {},
        "first_pair_decision": None,
        "first_pair_checkpoint_binding": None,
        "first_pair_selection_drift_detected": False,
        "actual_credential_exposure_detected": False,
        "credential_safety_stop_detected": False,
    }
    write_exclusive(root / "pilot-v6/pilot-state.json", state)


def schedule_empirical_campaign_start(
    root: Path,
    *,
    execution_contract_sha256: str,
    delay_seconds: float = 5.0,
) -> float:
    """Choose one near-future empirical origin before the manifest is serialized."""

    if not 1.0 <= delay_seconds <= 30.0:
        raise T09HostError("empirical clock publication delay is outside its narrow bound")
    state_path = root / "pilot-v6/pilot-state.json"
    state = load_object(state_path, label="pilot state")
    if (
        state.get("execution_contract_sha256") != execution_contract_sha256
        or state.get("pilot_started_at_epoch") is not None
        or state.get("campaign_started_at_epoch") is not None
        or state.get("first_pair_started_at_epoch") is not None
        or state.get("empirical_attempts_entered") != []
        or state.get("raw_attempts_complete") != []
        or state.get("attempts_completed") != []
    ):
        raise T09HostError("empirical campaign clock cannot be scheduled from this state")
    start = time.time() + delay_seconds
    state["pilot_started_at_epoch"] = start
    state["campaign_started_at_epoch"] = start
    state["first_pair_started_at_epoch"] = start
    write_atomic(state_path, state)
    return start


def _preflight_resume_argv() -> list[str]:
    return [Path(__file__).resolve(strict=True).as_posix(), *sys.argv[1:]]


def _preflight_resume_git_transition(
    repository: Path,
    *,
    package_commit: str,
) -> dict[str, object]:
    if (
        git_file_sha256(
            repository,
            PREENTRY_RESUME_FROM_PACKAGE_COMMIT,
            "experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/pilot.yaml",
        )
        != PREENTRY_RESUME_FROM_PLAN_SHA256
        or git_file_sha256(
            repository,
            PREENTRY_RESUME_FROM_PACKAGE_COMMIT,
            "containers/sira-smoke/pragmatic/t09_remote_runner.py",
        )
        != PREENTRY_RESUME_FROM_RUNNER_SHA256
    ):
        raise T09HostError("prior package bytes do not match the failed preflight")
    ancestry = subprocess.run(
        [
            "git",
            "-C",
            str(repository),
            "merge-base",
            "--is-ancestor",
            PREENTRY_RESUME_FROM_PACKAGE_COMMIT,
            package_commit,
        ],
        env=safe_environment(),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
        timeout=30,
    )
    if ancestry.returncode != 0:
        raise T09HostError("preflight recovery package is not a clean descendant")
    changed = output(
        [
            "git",
            "-C",
            str(repository),
            "diff",
            "--name-only",
            "--diff-filter=AM",
            PREENTRY_RESUME_FROM_PACKAGE_COMMIT,
            package_commit,
        ]
    ).splitlines()
    all_changed = output(
        [
            "git",
            "-C",
            str(repository),
            "diff",
            "--name-only",
            PREENTRY_RESUME_FROM_PACKAGE_COMMIT,
            package_commit,
        ]
    ).splitlines()
    if changed != all_changed or set(changed) != PREENTRY_RESUME_ALLOWED_PATHS:
        raise T09HostError("preflight recovery package changed an unapproved path")
    binary_diff = subprocess.run(
        [
            "git",
            "-C",
            str(repository),
            "diff",
            "--binary",
            PREENTRY_RESUME_FROM_PACKAGE_COMMIT,
            package_commit,
        ],
        env=safe_environment(),
        stdin=subprocess.DEVNULL,
        capture_output=True,
        check=True,
        timeout=60,
    ).stdout
    return {
        "prior_package_commit": PREENTRY_RESUME_FROM_PACKAGE_COMMIT,
        "package_commit": package_commit,
        "prior_package_tree": output(
            [
                "git",
                "-C",
                str(repository),
                "rev-parse",
                f"{PREENTRY_RESUME_FROM_PACKAGE_COMMIT}^{{tree}}",
            ]
        ),
        "package_tree": output(
            ["git", "-C", str(repository), "rev-parse", f"{package_commit}^{{tree}}"]
        ),
        "changed_paths": changed,
        "changed_paths_sha256": canonical_sha256(changed),
        "binary_diff_sha256": hashlib.sha256(binary_diff).hexdigest(),
        "scientific_contract_changed": False,
    }


def _validate_preflight_failure_receipts(
    *,
    failure_receipt: Path,
    failure_command_receipt: Path,
) -> dict[str, object]:
    receipts: dict[str, dict[str, Any]] = {}
    for label, path in (
        ("failure", failure_receipt.resolve(strict=True)),
        ("command", failure_command_receipt.resolve(strict=True)),
    ):
        metadata = path.stat(follow_symlinks=False)
        if (
            path.is_symlink()
            or not stat.S_ISREG(metadata.st_mode)
            or metadata.st_uid != os.getuid()
            or metadata.st_nlink != 1
            or stat.S_IMODE(metadata.st_mode) != 0o600
        ):
            raise T09HostError("preflight failure receipt metadata is unsafe")
        receipts[label] = load_object(path, label=f"preflight {label} failure receipt")
    failure = receipts["failure"]
    command = receipts["command"]
    command_argv = command.get("runner_argv")
    if (
        failure.get("classification") != PREENTRY_RESUME_FAILURE_CLASSIFICATION
        or failure.get("package_commit") != PREENTRY_RESUME_FROM_PACKAGE_COMMIT
        or failure.get("supplied_archive_sha256")
        != "63ed19b35bcb4cb62c3796a80a48004937340eb3826f9657a1006e251772255d"
        or failure.get("replacement_image_build_count") != 1
        or failure.get("empirical_attempts_entered") != 0
        or failure.get("task_model_requests") != 0
        or failure.get("task_browser_actions") != 0
        or failure.get("frozen_run_manifest_written") is not False
        or failure.get("credential_exposure") is not False
        or failure.get("condition_retry") is not False
        or failure.get("provider_launch_retry") is not False
        or not isinstance(command_argv, list)
        or not all(isinstance(item, str) for item in command_argv)
        or command.get("runner_argv_sha256") != canonical_sha256(command_argv)
        or command.get("runner_source_sha256") != PREENTRY_RESUME_FROM_RUNNER_SHA256
        or command.get("returncode") != 1
        or command.get("error_category") != "private V4 regression archive identity drifted"
        or command.get("empirical_entry_crossed") is not False
        or command.get("model_metadata_requests") != 0
        or command.get("task_browser_actions") != 0
        or command.get("supplied_archive_path") == PRIVATE_REGRESSION_ARCHIVE_PATH.as_posix()
        or "preflight" not in command_argv
    ):
        raise T09HostError("preflight failure evidence drifted")
    return {
        "failure_receipt_sha256": file_sha256(failure_receipt),
        "failure_command_receipt_sha256": file_sha256(failure_command_receipt),
        "original_failed_argv_sha256": command["runner_argv_sha256"],
        "failure_classification": PREENTRY_RESUME_FAILURE_CLASSIFICATION,
    }


def _resume_evaluator_receipt(
    *,
    repository: Path,
    artifact_root: Path,
    overlay: Path,
    prefix: list[str],
    image_id: str,
) -> dict[str, object]:
    manifest_path = artifact_root / "pilot-v6/evaluator-overlay-manifest.json"
    manifest = load_object(manifest_path, label="resumed evaluator overlay manifest")
    expected = expected_evaluator_packages(repository)
    if (
        manifest.get("plan_id") != PLAN_ID
        or manifest.get("qualification_id") != QUALIFICATION_ID
        or manifest.get("replacement_image_id") != image_id
        or manifest.get("lock_sha256") != file_sha256(repository / "uv.lock")
        or manifest.get("packages") != expected
        or manifest.get("packages_sha256") != canonical_sha256(expected)
        or manifest.get("reviewed_expected_packages_sha256") != canonical_sha256(expected)
    ):
        raise T09HostError("retained evaluator overlay manifest drifted")
    receipt = {
        "materialized": True,
        "network_mode": "bridge-dependency-materialization-only",
        "provider_or_model_request": False,
        "image_id": image_id,
        "lock_sha256": file_sha256(repository / "uv.lock"),
        "overlay_manifest_sha256": file_sha256(manifest_path),
        "overlay_entries_sha256": manifest["entries_sha256"],
        "overlay_package_manifest_sha256": manifest["packages_sha256"],
        "overlay_entry_count": manifest["entry_count"],
        "overlay_total_regular_bytes": manifest["total_regular_bytes"],
    }
    validate_evaluator_overlay_binding(
        artifact_root=artifact_root,
        repository=repository,
        overlay=overlay,
        prefix=prefix,
        image_id=image_id,
        frozen_manifest={
            "evaluator_overlay_manifest_sha256": receipt["overlay_manifest_sha256"],
            "evaluator_overlay_entries_sha256": receipt["overlay_entries_sha256"],
            "evaluator_overlay_packages_sha256": receipt["overlay_package_manifest_sha256"],
        },
        verify_packages=True,
    )
    return receipt


def prepare_preflight_resume(
    args: argparse.Namespace,
) -> tuple[
    Path,
    Path,
    dict[str, object],
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    dict[str, object],
    dict[str, object],
    dict[str, Any],
]:
    """Validate and materialize the one source-bound zero-use preflight transition."""

    raise T09HostError(
        "same-host preflight resume is permanently disabled; only source-bound slot 2 is valid"
    )

    repository = args.repository.resolve(strict=True)
    artifact_root = args.artifact_root.resolve(strict=False)
    prior_root = args.prior_artifact_root.resolve(strict=True)
    overlay = args.evaluator_overlay.resolve(strict=True)
    if artifact_root.exists() or artifact_root == prior_root:
        raise T09HostError("preflight resume requires a fresh distinct artifact root")
    prior_metadata = prior_root.stat(follow_symlinks=False)
    if (
        prior_root.name != "t09-pilot-v6-preflight-failure-0001"
        or prior_root.is_symlink()
        or not stat.S_ISDIR(prior_metadata.st_mode)
        or prior_metadata.st_uid != os.getuid()
        or stat.S_IMODE(prior_metadata.st_mode) != 0o700
    ):
        raise T09HostError("preflight failure prefix root is unsafe")
    validate_secret_metadata(args.secret_file.resolve(strict=True))
    archive = args.real_evidence_archive.resolve(strict=True)
    archive_metadata = archive.stat(follow_symlinks=False)
    if (
        archive != PRIVATE_REGRESSION_ARCHIVE_PATH
        or archive.is_symlink()
        or not stat.S_ISREG(archive_metadata.st_mode)
        or archive_metadata.st_uid != os.getuid()
        or archive_metadata.st_nlink != 1
        or stat.S_IMODE(archive_metadata.st_mode) != 0o600
        or file_sha256(archive)
        != "63ed19b35bcb4cb62c3796a80a48004937340eb3826f9657a1006e251772255d"
    ):
        raise T09HostError("exact private regression archive is unavailable for resume")
    command_document = verify_package(repository, args.package_commit)
    git_transition = _preflight_resume_git_transition(
        repository,
        package_commit=args.package_commit,
    )
    try:
        dynamic = validate_entry_receipt_source_bound(
            args.dynamic_receipt.resolve(strict=True),
            args.dynamic_source_root.resolve(strict=True),
            package_commit=PREENTRY_RESUME_FROM_PACKAGE_COMMIT,
            plan_sha256=PREENTRY_RESUME_FROM_PLAN_SHA256,
        )
    except T09ProviderError as exc:
        raise T09HostError("prior provider entry is not source-bound") from exc
    dynamic = {**dynamic, "receipt_sha256": file_sha256(args.dynamic_receipt)}
    lambda_started = dynamic.get("lambda_started_at_epoch")
    if (
        not isinstance(lambda_started, (int, float))
        or isinstance(lambda_started, bool)
        or not 0 <= time.time() - float(lambda_started) < PROVIDER_TERMINATION_CUTOFF_SECONDS
    ):
        raise T09HostError("preflight resume is outside the original campaign clock")
    pilot = prior_root / "pilot-v6"
    state_path = pilot / "pilot-state.json"
    aggregate_path = pilot / "aggregate-budget.json"
    old_state = load_object(state_path, label="failed preflight state")
    old_aggregate = load_object(aggregate_path, label="failed preflight aggregate")
    paths = contract_paths(repository)
    execution_sha256 = file_sha256(paths["execution"])
    next_state, next_aggregate = transition_zero_usage_preflight_state(
        old_state,
        old_aggregate,
        prior_execution_contract_sha256=PREENTRY_RESUME_FROM_EXECUTION_SHA256,
        next_execution_contract_sha256=execution_sha256,
    )
    absent = (
        "frozen-run-manifest.json",
        "preflight.json",
        "model-metadata-preflight.json",
        "browser-lifecycle-preflight/host-browser-lifecycle.json",
        "qualified-real-evidence-regression/receipt.json",
        "image-equivalence-adjudication.json",
    )
    if any((pilot / relative).exists() for relative in absent) or owned_containers(docker_prefix()):
        raise T09HostError("failed preflight prefix crossed a later gate")
    failure_evidence = _validate_preflight_failure_receipts(
        failure_receipt=args.failure_receipt,
        failure_command_receipt=args.failure_command_receipt,
    )
    materialization_path = pilot / "replacement-image-qualification/receipt.json"
    materialization = load_object(materialization_path, label="retained image materialization")
    image_id = materialization.get("image_id")
    if (
        materialization.get("build_count") != 1
        or materialization.get("repository_runtime_commit") != PREENTRY_RESUME_FROM_PACKAGE_COMMIT
        or not isinstance(image_id, str)
        or image_id_if_present(docker_prefix(), REPLACEMENT_IMAGE_TAG) != image_id
        or image_id_if_present(docker_prefix(), image_id) != image_id
        or materialization.get("image_inspect_sha256")
        != file_sha256(pilot / "replacement-image-qualification/replacement-image-inspect.stdout")
        or materialization.get("build_context_manifest_sha256")
        != file_sha256(pilot / "replacement-image-qualification/build-context-manifest.json")
        or materialization.get("build_context_exclusions_sha256")
        != file_sha256(pilot / "replacement-image-qualification/build-context-exclusions.json")
        or materialization.get("build_command_sha256")
        != file_sha256(pilot / "replacement-image-qualification/build-command.json")
    ):
        raise T09HostError("retained replacement image is not the one built candidate")
    static_regression = validate_real_evidence_regression(repository)
    local_qualification = validate_local_finalizer_qualification(
        args.local_finalizer_qualification,
        repository=repository,
        package_commit=args.package_commit,
        require_local_runtime=False,
    )
    artifact_root.mkdir(mode=0o700, parents=True)
    resume_root = artifact_root / "pilot-v6/preflight-resume"
    resume_root.mkdir(parents=True, mode=0o700)
    retained_prefix = _copy_retained_prefix(
        prior_root,
        resume_root / "failure-prefix",
        label="failed zero-use preflight prefix",
    )
    write_exclusive(resume_root / "failure-prefix-manifest.json", retained_prefix)
    for label, source in (
        ("operator-failure.json", args.failure_receipt.resolve(strict=True)),
        ("operator-command.json", args.failure_command_receipt.resolve(strict=True)),
    ):
        shutil.copy2(source, resume_root / label)
    for relative in ("replacement-image-qualification",):
        _copy_retained_prefix(
            pilot / relative,
            artifact_root / "pilot-v6" / relative,
            label=f"retained {relative}",
        )
    shutil.copy2(
        pilot / "evaluator-overlay-manifest.json",
        artifact_root / "pilot-v6/evaluator-overlay-manifest.json",
    )
    write_exclusive(
        artifact_root / "pilot-v6/provider-entry.json",
        sanitized_dynamic_receipt(args.dynamic_receipt, dynamic),
    )
    shutil.copy2(
        args.local_finalizer_qualification.resolve(strict=True),
        artifact_root / "pilot-v6/local-finalizer-qualification.json",
    )
    transition_state_path = resume_root / "transition-pilot-state.json"
    transition_aggregate_path = resume_root / "transition-aggregate-budget.json"
    write_exclusive(transition_state_path, next_state)
    write_exclusive(transition_aggregate_path, next_aggregate)
    shutil.copy2(transition_state_path, artifact_root / "pilot-v6/pilot-state.json")
    shutil.copy2(
        transition_aggregate_path,
        artifact_root / "pilot-v6/aggregate-budget.json",
    )
    evaluator = _resume_evaluator_receipt(
        repository=repository,
        artifact_root=artifact_root,
        overlay=overlay,
        prefix=docker_prefix(),
        image_id=image_id,
    )
    recovery_argv = _preflight_resume_argv()
    transition: dict[str, object] = {
        "schema_version": "0.1.0",
        "receipt_type": "t09-preentry-same-host-preflight-resume",
        "plan_id": PLAN_ID,
        "host_run_id": HOST_RUN_ID,
        **git_transition,
        "prior_plan_sha256": PREENTRY_RESUME_FROM_PLAN_SHA256,
        "plan_sha256": file_sha256(paths["plan"]),
        "provider_entry_receipt_sha256": file_sha256(args.dynamic_receipt),
        "provider_entry_source_manifest_sha256": dynamic.get("source_manifest_sha256"),
        "owned_instance_identity_sha256": dynamic.get("owned_instance_identity_sha256"),
        "lambda_started_at_epoch": lambda_started,
        "launch_count": 1,
        "replacement_image_id": image_id,
        "replacement_image_tag": REPLACEMENT_IMAGE_TAG,
        "build_count": 1,
        "additional_build_count": 0,
        "empirical_attempts_entered": 0,
        "raw_attempts_complete": 0,
        "attempts_completed": 0,
        "model_metadata_requests": 0,
        "task_model_requests": 0,
        "task_browser_actions": 0,
        "frozen_run_manifest_written": False,
        "failure_prefix_manifest_sha256": file_sha256(resume_root / "failure-prefix-manifest.json"),
        **failure_evidence,
        "corrected_archive_sha256": file_sha256(archive),
        "corrected_archive_mode": "0600",
        "prior_state_sha256": file_sha256(state_path),
        "transition_state_sha256": file_sha256(transition_state_path),
        "prior_aggregate_sha256": file_sha256(aggregate_path),
        "transition_aggregate_sha256": file_sha256(transition_aggregate_path),
        "retained_materialization_receipt_sha256": file_sha256(
            artifact_root / "pilot-v6/replacement-image-qualification/receipt.json"
        ),
        "recovery_source_sha256": file_sha256(Path(__file__).resolve(strict=True)),
        "recovery_argv": recovery_argv,
        "recovery_argv_sha256": canonical_sha256(recovery_argv),
        "provider_launch_reused": True,
        "additional_provider_launches": 0,
        "created_at_epoch": time.time(),
    }
    transition_path = resume_root / "transition.json"
    write_exclusive(transition_path, transition)
    transition["receipt_sha256"] = file_sha256(transition_path)
    return (
        repository,
        artifact_root,
        dynamic,
        command_document,
        static_regression,
        local_qualification,
        materialization,
        evaluator,
        transition,
    )


def resume_preflight(args: argparse.Namespace) -> None:
    raise T09HostError(
        "same-host preflight resume is permanently disabled; only source-bound slot 2 is valid"
    )
    """Resume only the exact retained zero-use preflight after source-bound repair."""

    (
        repository,
        artifact_root,
        dynamic,
        command_document,
        real_evidence_regression,
        local_finalizer_qualification,
        image_materialization,
        evaluator,
        transition,
    ) = prepare_preflight_resume(args)
    paths = contract_paths(repository)
    execution_sha256 = file_sha256(paths["execution"])
    prefix = docker_prefix()
    image_id = image_materialization.get("image_id")
    if not isinstance(image_id, str):
        raise T09HostError("resumed image materialization lacks its identity")
    credential_channel = secret_channel_preflight(
        repository=repository,
        artifact_root=artifact_root,
        secret_file=args.secret_file.resolve(strict=True),
        prefix=prefix,
        image_id=image_id,
    )
    image_files = final_image_file_hashes(
        artifact_root=artifact_root,
        prefix=prefix,
        image_id=image_id,
    )
    final_runtime = final_image_runtime_preflight(
        artifact_root=artifact_root,
        prefix=prefix,
        image_id=image_id,
        command_document=command_document,
    )
    offline = offline_runtime_preflight(
        repository=repository,
        artifact_root=artifact_root,
        overlay=args.evaluator_overlay.resolve(strict=True),
        prefix=prefix,
        image_id=image_id,
    )
    archive_staging = stage_verified_archive(
        args.real_evidence_archive,
        PRIVATE_REGRESSION_ARCHIVE_PATH,
        PRIVATE_REGRESSION_ARCHIVE_BYTES,
        PRIVATE_REGRESSION_ARCHIVE_SHA256,
    )
    write_exclusive(
        artifact_root / "pilot-v6/regression-archive-staging/receipt.json",
        archive_staging,
    )
    qualified_real_regression = qualified_real_evidence_regression(
        repository=repository,
        artifact_root=artifact_root,
        archive=PRIVATE_REGRESSION_ARCHIVE_PATH,
        overlay=args.evaluator_overlay.resolve(strict=True),
        prefix=prefix,
        image_id=image_id,
        image_files=image_files,
        static_receipt=real_evidence_regression,
    )
    browser = browser_lifecycle_preflight(
        artifact_root=artifact_root,
        prefix=prefix,
        image_id=image_id,
    )
    evaluator_overlay_verified = validate_evaluator_overlay_binding(
        artifact_root=artifact_root,
        repository=repository,
        overlay=args.evaluator_overlay.resolve(strict=True),
        prefix=prefix,
        image_id=image_id,
        frozen_manifest={
            "evaluator_overlay_manifest_sha256": evaluator["overlay_manifest_sha256"],
            "evaluator_overlay_entries_sha256": evaluator["overlay_entries_sha256"],
            "evaluator_overlay_packages_sha256": evaluator["overlay_package_manifest_sha256"],
        },
        verify_packages=True,
    )
    adjudication = image_equivalence_adjudication(
        repository=repository,
        artifact_root=artifact_root,
        image_id=image_id,
    )
    gpu = gpu_snapshot()
    lambda_started = dynamic.get("lambda_started_at_epoch")
    if not isinstance(lambda_started, (int, float)) or isinstance(lambda_started, bool):
        raise T09HostError("provider entry lacks its original campaign clock")
    lambda_elapsed = time.time() - float(lambda_started)
    if (
        lambda_elapsed >= MAX_LAMBDA_DURATION_SECONDS
        or lambda_elapsed * LAMBDA_HOURLY_PRICE_USD / 3600.0 >= MAX_LAMBDA_COST_USD
        or owned_containers(prefix)
        or _runtime_budget_state(artifact_root).get("empirical_attempts_entered") != []
        or load_aggregate_usage(
            artifact_root / "pilot-v6/aggregate-budget.json",
            contract_sha256=execution_sha256,
        )
        != ProviderBudgetUsage()
    ):
        raise T09HostError("resumed preflight lacks zero-use lifecycle headroom")
    model_metadata = model_metadata_preflight(
        artifact_root=artifact_root,
        secret_file=args.secret_file.resolve(strict=True),
        prefix=prefix,
        image_id=image_id,
    )
    model_credential_scan = record_preflight_credential_scan(
        artifact_root=artifact_root,
        secret_file=args.secret_file.resolve(strict=True),
        execution_contract_sha256=execution_sha256,
    )
    frozen_manifest_path, frozen_manifest = write_frozen_run_manifest(
        repository=repository,
        artifact_root=artifact_root,
        package_commit=args.package_commit,
        dynamic=dynamic,
        image_materialization=image_materialization,
        command_document=command_document,
        runtime_receipt=final_runtime,
        offline_receipt=offline,
        browser_receipt=browser,
        evaluator_receipt=evaluator,
        file_hashes=image_files,
        model_receipt=model_metadata,
        model_credential_scan_receipt=model_credential_scan,
        adjudication=adjudication,
        static_real_evidence_regression=real_evidence_regression,
        qualified_real_evidence_regression_receipt=qualified_real_regression,
        regression_archive_staging_receipt=archive_staging,
        local_finalizer_qualification_receipt=local_finalizer_qualification,
        preflight_resume_transition=transition,
    )
    state_path = artifact_root / "pilot-v6/pilot-state.json"
    state = load_object(state_path, label="pilot state")
    state["first_pair_started_at_epoch"] = time.time()
    write_atomic(state_path, state)
    admitted_seconds = admit_next_attempt(artifact_root)
    preflight_path = artifact_root / "pilot-v6/preflight.json"
    write_exclusive(
        preflight_path,
        {
            "schema_version": "0.1.0",
            "plan_id": PLAN_ID,
            "host_run_id": HOST_RUN_ID,
            "completed_at": utc_now(),
            "clean_package_commit": args.package_commit,
            "execution_contract_sha256": execution_sha256,
            "command_manifests_sha256": file_sha256(paths["commands"]),
            "command_argv_sha256s": [item["argv_sha256"] for item in manifests(command_document)],
            "dynamic_receipt_sha256": file_sha256(args.dynamic_receipt),
            "dynamic_receipt": sanitized_dynamic_receipt(args.dynamic_receipt, dynamic),
            "preflight_transition_mode": "same-host-resume",
            "preflight_resume_transition_sha256": transition["receipt_sha256"],
            "preflight_failure_prefix_manifest_sha256": transition[
                "failure_prefix_manifest_sha256"
            ],
            "image_materialization": image_materialization,
            "replacement_image_id": image_id,
            "frozen_run_manifest_sha256": file_sha256(frozen_manifest_path),
            "frozen_run_manifest_id": frozen_manifest["manifest_id"],
            "image_equivalence_adjudication": adjudication,
            "final_image_file_hashes": image_files,
            "final_image_runtime_preflight": final_runtime,
            "runtime_imports": "passed-by-network-none-offline-runtime-preflight",
            "evidence_write_fsync_readback": ("passed-by-network-none-offline-runtime-preflight"),
            "budget_ledger": "passed-zero-state-by-network-none-offline-runtime-preflight",
            "command_rendering": "passed-four-exact-by-network-none-offline-runtime-preflight",
            "browser_startup_screenshot_cleanup": browser,
            "evaluator_loading": "passed-exact-network-none-with-approved-fixtures",
            "real_evidence_finalizer_regression": {
                "static_receipt_sha256": file_sha256(paths["real_regression"]),
                "qualified_receipt_sha256": file_sha256(
                    artifact_root / "pilot-v6/qualified-real-evidence-regression/receipt.json"
                ),
                "semantic_projection_sha256": real_evidence_regression[
                    "semantic_projection_sha256"
                ],
                "qualified_interpreter_sha256": qualified_real_regression["interpreter"][
                    "executable_sha256"
                ],
                "accepted_scientific_and_evaluator_fields_equal": True,
                "additional_model_requests": 0,
                "additional_browser_actions": 0,
            },
            "local_post_termination_finalizer": {
                "qualification_sha256": file_sha256(
                    artifact_root / "pilot-v6/local-finalizer-qualification.json"
                ),
                "interpreter_sha256": local_finalizer_qualification["interpreter_sha256"],
                "interpreter_dependency_manifest_sha256": local_finalizer_qualification[
                    "interpreter_dependency_manifest_sha256"
                ],
                "interpreter_dependency_tree_sha256": local_finalizer_qualification[
                    "interpreter_dependency_tree_sha256"
                ],
                "evaluator_dependency_tree_sha256": local_finalizer_qualification[
                    "dependency_tree_sha256"
                ],
                "network": "socket-construction-denied",
                "provider_lifecycle_required": False,
            },
            "evaluator_overlay_revalidation": evaluator_overlay_verified,
            "task_loading": "passed-two-exact-rows-network-none",
            "model_metadata": model_metadata,
            "model_metadata_request_count": 1,
            "model_metadata_credential_scan_sha256": file_sha256(
                artifact_root / "pilot-v6/model-metadata-credential-scan.json"
            ),
            "actual_credential_exposure_detected": False,
            "model_task_request_count": 0,
            "credential_channel": credential_channel,
            "zero_prior_lambda_instances": True,
            "gpu_accounting": gpu,
            "empirical_entry_crossed": False,
            "actual_campaign_seconds_consumed_by_setup": time.time() - float(lambda_started),
            "seconds_available_after_cleanup_reserve": admitted_seconds,
        },
    )
    load_frozen_run_manifest(
        artifact_root,
        repository=repository,
        package_commit=args.package_commit,
        require_image=True,
    )
    validate_evaluator_overlay_binding(
        artifact_root=artifact_root,
        repository=repository,
        overlay=args.evaluator_overlay.resolve(strict=True),
        prefix=prefix,
        image_id=image_id,
        frozen_manifest=frozen_manifest,
        verify_packages=True,
    )
    post_state = _runtime_budget_state(artifact_root)
    if (
        post_state.get("empirical_attempts_entered") != []
        or post_state.get("raw_attempts_complete") != []
        or post_state.get("attempts_completed") != []
        or owned_containers(prefix)
    ):
        raise T09HostError("post-resume preflight zero-use validation failed")
    write_exclusive(
        artifact_root / "pilot-v6/preflight-resume/postfreeze-validation.json",
        {
            "schema_version": "0.1.0",
            "plan_id": PLAN_ID,
            "package_commit": args.package_commit,
            "frozen_run_manifest_sha256": file_sha256(frozen_manifest_path),
            "preflight_sha256": file_sha256(preflight_path),
            "evaluator_overlay_revalidated": True,
            "replacement_image_revalidated": True,
            "owned_containers_absent": True,
            "empirical_attempts_entered": 0,
            "model_metadata_request_count": 1,
            "task_model_request_count": 0,
            "task_browser_action_count": 0,
        },
    )


def preflight(args: argparse.Namespace) -> None:
    repository = args.repository.resolve(strict=True)
    artifact_root = args.artifact_root.resolve(strict=False)
    if artifact_root.exists():
        raise T09HostError("pilot artifact root must be fresh")
    validate_secret_metadata(args.secret_file.resolve(strict=True))
    dynamic = validate_dynamic_receipt(
        args.dynamic_receipt.resolve(strict=True),
        expected_package_commit=args.package_commit,
        repository_root=repository,
        source_root=args.dynamic_source_root.resolve(strict=True),
    )
    launch_slot = dynamic.get("launch_slot")
    if launch_slot not in {1, 2} or dynamic.get("launch_count") != launch_slot:
        raise T09HostError("Retry 4 entry launch identity is invalid")
    if launch_slot == 1 and (
        dynamic.get("replacement_eligibility_sha256") is not None
        or dynamic.get("replacement_eligibility_source_manifest_sha256") is not None
    ):
        raise T09HostError("first Retry 4 launch retained replacement authority")
    if launch_slot == 2 and (
        not isinstance(dynamic.get("replacement_eligibility_sha256"), str)
        or not isinstance(dynamic.get("replacement_eligibility_source_manifest_sha256"), str)
    ):
        raise T09HostError("second Retry 4 launch lacks exact replacement authority")
    image_materialization_policy = (
        SLOT1_IMAGE_MATERIALIZATION_POLICY
        if launch_slot == 1
        else SLOT2_IMAGE_MATERIALIZATION_POLICY
    )
    paths = contract_paths(repository)
    prefix = docker_prefix()
    if owned_containers(prefix):
        raise T09HostError("owned pilot containers already exist")
    artifact_root.mkdir(mode=0o700, parents=True)
    slot2_authority: dict[str, object] | None = None
    if launch_slot == 1:
        if args.slot2_authority_root is not None:
            raise T09HostError("first launch received slot-2 authority")
    else:
        if args.slot2_authority_root is None:
            raise T09HostError("second launch lacks its retained authority root")
        retained_authority_root = artifact_root / "pilot-v6/slot2-authority"
        retain_slot2_authority(
            args.slot2_authority_root.resolve(strict=True), retained_authority_root
        )
        slot2_authority = slot2_authority_binding(retained_authority_root)
        if slot2_authority.get("replacement_eligibility_sha256") != dynamic.get(
            "replacement_eligibility_sha256"
        ) or slot2_authority.get("replacement_eligibility_source_manifest_sha256") != dynamic.get(
            "replacement_eligibility_source_manifest_sha256"
        ):
            raise T09HostError("retained slot-2 authority does not match provider entry")
    lambda_started_raw = dynamic["provider_preflight_started_at_epoch"]
    if not isinstance(lambda_started_raw, (int, float)) or isinstance(lambda_started_raw, bool):
        raise T09HostError("provider entry receipt lacks the billable time origin")
    lambda_started = float(lambda_started_raw)
    owned_lambda_started_raw = dynamic.get("owned_lambda_started_at_epoch")
    prior_lambda_duration_raw = dynamic.get("prior_campaign_lambda_duration_seconds")
    prior_lambda_cost_raw = dynamic.get("prior_campaign_lambda_cost_usd")
    if not all(
        isinstance(value, (int, float)) and not isinstance(value, bool)
        for value in (
            owned_lambda_started_raw,
            prior_lambda_duration_raw,
            prior_lambda_cost_raw,
        )
    ):
        raise T09HostError("slot-2 entry lacks active Lambda accounting")
    assert isinstance(owned_lambda_started_raw, (int, float))
    assert isinstance(prior_lambda_duration_raw, (int, float))
    assert isinstance(prior_lambda_cost_raw, (int, float))
    execution_sha256 = file_sha256(paths["execution"])
    initialize_state(
        artifact_root,
        execution_sha256,
        lambda_started_at_epoch=lambda_started,
        owned_lambda_started_at_epoch=float(owned_lambda_started_raw),
        prior_lambda_duration_seconds=float(prior_lambda_duration_raw),
        prior_lambda_cost_usd=float(prior_lambda_cost_raw),
        launch_slot=launch_slot,
        replacement_eligibility_sha256=cast(
            str | None, dynamic.get("replacement_eligibility_sha256")
        ),
        replacement_eligibility_source_manifest_sha256=cast(
            str | None, dynamic.get("replacement_eligibility_source_manifest_sha256")
        ),
    )
    write_exclusive(
        artifact_root / "pilot-v6/provider-entry.json",
        sanitized_dynamic_receipt(args.dynamic_receipt, dynamic),
    )
    command_document = verify_package(repository, args.package_commit)
    real_evidence_regression = validate_real_evidence_regression(repository)
    local_finalizer_qualification = validate_local_finalizer_qualification(
        args.local_finalizer_qualification,
        repository=repository,
        package_commit=args.package_commit,
        require_local_runtime=False,
    )
    write_exclusive(
        artifact_root / "pilot-v6/local-finalizer-qualification.json",
        local_finalizer_qualification,
    )
    image_materialization = materialize_retained_or_build_image(
        repository=repository,
        package_commit=args.package_commit,
        artifact_root=artifact_root,
        image_archive=args.replacement_image_archive,
        prefix=prefix,
        materialization_policy=image_materialization_policy,
    )
    image_id = image_materialization.get("image_id")
    if not isinstance(image_id, str):
        raise T09HostError("replacement image materialization lacks its identity")
    credential_channel = secret_channel_preflight(
        repository=repository,
        artifact_root=artifact_root,
        secret_file=args.secret_file.resolve(strict=True),
        prefix=prefix,
        image_id=image_id,
    )
    evaluator = evaluator_overlay(
        repository=repository,
        artifact_root=artifact_root,
        overlay=args.evaluator_overlay.resolve(strict=False),
        prefix=prefix,
        image_id=image_id,
    )
    image_files = final_image_file_hashes(
        artifact_root=artifact_root,
        prefix=prefix,
        image_id=image_id,
    )
    final_runtime = final_image_runtime_preflight(
        artifact_root=artifact_root,
        prefix=prefix,
        image_id=image_id,
        command_document=command_document,
    )
    offline = offline_runtime_preflight(
        repository=repository,
        artifact_root=artifact_root,
        overlay=args.evaluator_overlay.resolve(strict=True),
        prefix=prefix,
        image_id=image_id,
    )
    archive_staging = stage_verified_archive(
        args.real_evidence_archive,
        PRIVATE_REGRESSION_ARCHIVE_PATH,
        PRIVATE_REGRESSION_ARCHIVE_BYTES,
        PRIVATE_REGRESSION_ARCHIVE_SHA256,
    )
    write_exclusive(
        artifact_root / "pilot-v6/regression-archive-staging/receipt.json",
        archive_staging,
    )
    qualified_real_regression = qualified_real_evidence_regression(
        repository=repository,
        artifact_root=artifact_root,
        archive=PRIVATE_REGRESSION_ARCHIVE_PATH,
        overlay=args.evaluator_overlay.resolve(strict=True),
        prefix=prefix,
        image_id=image_id,
        image_files=image_files,
        static_receipt=real_evidence_regression,
    )
    browser = browser_lifecycle_preflight(
        artifact_root=artifact_root,
        prefix=prefix,
        image_id=image_id,
    )
    evaluator_overlay_verified = validate_evaluator_overlay_binding(
        artifact_root=artifact_root,
        repository=repository,
        overlay=args.evaluator_overlay.resolve(strict=True),
        prefix=prefix,
        image_id=image_id,
        frozen_manifest={
            "evaluator_overlay_manifest_sha256": evaluator["overlay_manifest_sha256"],
            "evaluator_overlay_entries_sha256": evaluator["overlay_entries_sha256"],
            "evaluator_overlay_packages_sha256": evaluator["overlay_package_manifest_sha256"],
        },
        verify_packages=True,
    )
    adjudication = image_equivalence_adjudication(
        repository=repository,
        artifact_root=artifact_root,
        image_id=image_id,
    )
    gpu = gpu_snapshot()
    preflight_elapsed = time.time() - lambda_started
    owned_lambda_elapsed = time.time() - float(owned_lambda_started_raw)
    active_lambda_duration = float(prior_lambda_duration_raw) + owned_lambda_elapsed
    active_lambda_cost = float(prior_lambda_cost_raw) + (
        owned_lambda_elapsed * LAMBDA_HOURLY_PRICE_USD / 3600.0
    )
    if (
        preflight_elapsed >= MAX_PREFLIGHT_WALL_SECONDS
        or active_lambda_duration >= MAX_LAMBDA_DURATION_SECONDS
        or active_lambda_cost >= MAX_LAMBDA_COST_USD
    ):
        raise T09HostError("preflight consumed its wall or cumulative Lambda ceiling")
    remaining_before_metadata = preflight_seconds_remaining(artifact_root)
    active_headroom_before_metadata = provider_seconds_remaining(artifact_root)
    if remaining_before_metadata <= 0:
        raise T09HostError("provider preflight wall is exhausted before model metadata")
    if active_headroom_before_metadata < MAX_TOTAL_WALL_SECONDS:
        raise T09HostError(
            "cumulative active-provider headroom cannot cover the fresh empirical campaign"
        )
    # This is the one authorized provider metadata GET and is intentionally the last
    # fallible functional gate before the immutable run manifest is written.
    model_metadata = model_metadata_preflight(
        artifact_root=artifact_root,
        secret_file=args.secret_file.resolve(strict=True),
        prefix=prefix,
        image_id=image_id,
    )
    model_credential_scan = record_preflight_credential_scan(
        artifact_root=artifact_root,
        secret_file=args.secret_file.resolve(strict=True),
        execution_contract_sha256=execution_sha256,
    )
    empirical_start = schedule_empirical_campaign_start(
        artifact_root,
        execution_contract_sha256=execution_sha256,
    )
    frozen_manifest_path, frozen_manifest = write_frozen_run_manifest(
        repository=repository,
        artifact_root=artifact_root,
        package_commit=args.package_commit,
        dynamic=dynamic,
        image_materialization=image_materialization,
        command_document=command_document,
        runtime_receipt=final_runtime,
        offline_receipt=offline,
        browser_receipt=browser,
        evaluator_receipt=evaluator,
        file_hashes=image_files,
        model_receipt=model_metadata,
        model_credential_scan_receipt=model_credential_scan,
        adjudication=adjudication,
        static_real_evidence_regression=real_evidence_regression,
        qualified_real_evidence_regression_receipt=qualified_real_regression,
        regression_archive_staging_receipt=archive_staging,
        local_finalizer_qualification_receipt=local_finalizer_qualification,
        slot2_authority=slot2_authority,
    )
    manifest_published_at = time.time()
    if manifest_published_at > empirical_start:
        raise T09HostError("frozen manifest publication missed the empirical clock boundary")
    time.sleep(max(0.0, empirical_start - manifest_published_at))
    loaded_manifest, loaded_manifest_sha256 = load_frozen_run_manifest(
        artifact_root,
        repository=repository,
        package_commit=args.package_commit,
        require_image=True,
    )
    if loaded_manifest != frozen_manifest or loaded_manifest_sha256 != file_sha256(
        frozen_manifest_path
    ):
        raise T09HostError("post-freeze manifest revalidation drifted")
    admitted_seconds = admit_next_attempt(artifact_root)
    postfreeze_path = artifact_root / "pilot-v6/postfreeze-validation.json"
    write_exclusive(
        postfreeze_path,
        {
            "schema_version": "0.1.0",
            "plan_id": PLAN_ID,
            "host_run_id": HOST_RUN_ID,
            "package_commit": args.package_commit,
            "frozen_run_manifest_sha256": loaded_manifest_sha256,
            "replacement_image_id": image_id,
            "image_materialization_policy": frozen_manifest["image_materialization_policy"],
            "replacement_eligibility_sha256": dynamic.get("replacement_eligibility_sha256"),
            "first_pair_started_at_epoch": frozen_manifest["first_pair_started_at_epoch"],
            "empirical_campaign_started_at_epoch": empirical_start,
            "frozen_manifest_published_before_empirical_clock": True,
            "model_metadata_request_count": 1,
            "model_metadata_credential_scan_sha256": file_sha256(
                artifact_root / "pilot-v6/model-metadata-credential-scan.json"
            ),
            "actual_credential_exposure_detected": False,
            "model_task_request_count": 0,
            "task_browser_action_count": 0,
            POSTFREEZE_ADMISSION_FIELD: True,
            "active_provider_seconds_available_before_metadata_get": (
                active_headroom_before_metadata
            ),
            "completed_at_epoch": time.time(),
        },
    )
    write_exclusive(
        artifact_root / "pilot-v6/preflight.json",
        {
            "schema_version": "0.1.0",
            "plan_id": PLAN_ID,
            "host_run_id": HOST_RUN_ID,
            "completed_at": utc_now(),
            "clean_package_commit": args.package_commit,
            "execution_contract_sha256": execution_sha256,
            "command_manifests_sha256": file_sha256(paths["commands"]),
            "command_argv_sha256s": [item["argv_sha256"] for item in manifests(command_document)],
            "dynamic_receipt_sha256": file_sha256(args.dynamic_receipt),
            "dynamic_receipt": sanitized_dynamic_receipt(args.dynamic_receipt, dynamic),
            "image_materialization": image_materialization,
            "replacement_image_id": image_id,
            "frozen_run_manifest_sha256": file_sha256(frozen_manifest_path),
            "frozen_run_manifest_id": frozen_manifest["manifest_id"],
            "postfreeze_validation_sha256": file_sha256(postfreeze_path),
            "replacement_eligibility_sha256": dynamic.get("replacement_eligibility_sha256"),
            "replacement_eligibility_source_manifest_sha256": dynamic.get(
                "replacement_eligibility_source_manifest_sha256"
            ),
            "first_pair_started_at_epoch": frozen_manifest["first_pair_started_at_epoch"],
            "image_equivalence_adjudication": adjudication,
            "final_image_file_hashes": image_files,
            "final_image_runtime_preflight": final_runtime,
            "runtime_imports": "passed-by-network-none-offline-runtime-preflight",
            "evidence_write_fsync_readback": "passed-by-network-none-offline-runtime-preflight",
            "budget_ledger": "passed-zero-state-by-network-none-offline-runtime-preflight",
            "command_rendering": "passed-four-exact-by-network-none-offline-runtime-preflight",
            "browser_startup_screenshot_cleanup": browser,
            "evaluator_loading": "passed-exact-network-none-with-approved-fixtures",
            "real_evidence_finalizer_regression": {
                "static_receipt_sha256": file_sha256(paths["real_regression"]),
                "qualified_receipt_sha256": file_sha256(
                    artifact_root / "pilot-v6/qualified-real-evidence-regression/receipt.json"
                ),
                "semantic_projection_sha256": real_evidence_regression[
                    "semantic_projection_sha256"
                ],
                "qualified_interpreter_sha256": qualified_real_regression["interpreter"][
                    "executable_sha256"
                ],
                "accepted_scientific_and_evaluator_fields_equal": True,
                "additional_model_requests": 0,
                "additional_browser_actions": 0,
            },
            "local_post_termination_finalizer": {
                "qualification_sha256": file_sha256(
                    artifact_root / "pilot-v6/local-finalizer-qualification.json"
                ),
                "interpreter_sha256": local_finalizer_qualification["interpreter_sha256"],
                "interpreter_dependency_manifest_sha256": local_finalizer_qualification[
                    "interpreter_dependency_manifest_sha256"
                ],
                "interpreter_dependency_tree_sha256": local_finalizer_qualification[
                    "interpreter_dependency_tree_sha256"
                ],
                "evaluator_dependency_tree_sha256": local_finalizer_qualification[
                    "dependency_tree_sha256"
                ],
                "network": "socket-construction-denied",
                "provider_lifecycle_required": False,
            },
            "evaluator_overlay_revalidation": evaluator_overlay_verified,
            "task_loading": "passed-two-exact-rows-network-none",
            "model_metadata": model_metadata,
            "model_metadata_credential_scan": model_credential_scan,
            "model_metadata_request_count": 1,
            "model_task_request_count": 0,
            "credential_channel": credential_channel,
            "zero_prior_lambda_instances": True,
            "gpu_accounting": gpu,
            "empirical_entry_crossed": False,
            "actual_campaign_seconds_consumed_by_setup": time.time() - lambda_started,
            "actual_active_lambda_seconds_before_attempt": (
                float(prior_lambda_duration_raw) + time.time() - float(owned_lambda_started_raw)
            ),
            "seconds_available_after_cleanup_reserve": admitted_seconds,
        },
    )


def preflight_with_deadline(args: argparse.Namespace) -> None:
    """Apply the per-launch preflight clock and retain one concise failure receipt."""

    repository = args.repository.resolve(strict=True)
    dynamic = validate_dynamic_receipt(
        args.dynamic_receipt.resolve(strict=True),
        expected_package_commit=args.package_commit,
        repository_root=repository,
        source_root=args.dynamic_source_root.resolve(strict=True),
    )
    started = dynamic.get("provider_preflight_started_at_epoch")
    prior_duration = dynamic.get("prior_campaign_lambda_duration_seconds")
    prior_cost = dynamic.get("prior_campaign_lambda_cost_usd")
    if not all(
        isinstance(value, (int, float)) and not isinstance(value, bool)
        for value in (started, prior_duration, prior_cost)
    ):
        raise T09HostError("provider entry lacks Retry 4 clock accounting")
    assert isinstance(started, (int, float))
    assert isinstance(prior_duration, (int, float))
    assert isinstance(prior_cost, (int, float))
    now = time.time()
    current_elapsed = now - float(started)
    active_elapsed = float(prior_duration) + current_elapsed
    active_cost = float(prior_cost) + current_elapsed * LAMBDA_HOURLY_PRICE_USD / 3600.0
    deadline = min(
        MAX_PREFLIGHT_WALL_SECONDS - current_elapsed,
        MAX_LAMBDA_DURATION_SECONDS - active_elapsed,
        (MAX_LAMBDA_COST_USD - active_cost) * 3600.0 / LAMBDA_HOURLY_PRICE_USD,
    )
    if deadline <= 0:
        raise T09HostError("provider preflight or cumulative active cap is exhausted")
    try:
        with hard_deadline(deadline, message="provider preflight wall expired"):
            preflight(args)
    except BaseException as exc:
        root = args.artifact_root.resolve(strict=False)
        if root.is_dir():
            receipt = root / "pilot-v6/preflight-failure.json"
            if not receipt.exists():
                failed_at = time.time()
                write_exclusive(
                    receipt,
                    {
                        "schema_version": "0.1.0",
                        "plan_id": PLAN_ID,
                        "host_run_id": HOST_RUN_ID,
                        "package_commit": args.package_commit,
                        "launch_slot": dynamic.get("launch_slot"),
                        "provider_preflight_started_at_epoch": float(started),
                        "failed_at_epoch": failed_at,
                        "elapsed_seconds": failed_at - float(started),
                        "failure_type": type(exc).__name__,
                        "failure_message": str(exc)[:1024],
                        "empirical_attempts_entered": 0,
                        "termination_dispatch_required": True,
                        "termination_dispatch_deadline_epoch": (
                            failed_at + FAILED_PREFLIGHT_TERMINATION_DISPATCH_SECONDS
                        ),
                    },
                )
        raise


def container_create_argv(
    *,
    args: argparse.Namespace,
    manifest: dict[str, Any],
    attempt_root: Path,
    container_name: str,
    image_id: str,
) -> list[str]:
    repository = args.repository.resolve(strict=True)
    paths = contract_paths(repository)
    artifact_root = args.artifact_root.resolve(strict=True)
    prefix = docker_prefix()
    return [
        *prefix,
        "create",
        "--name",
        container_name,
        "--platform",
        "linux/amd64",
        "--network",
        "bridge",
        "--ipc",
        "private",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges=true",
        "--read-only",
        "--init",
        "--restart",
        "no",
        "--cpus",
        "2.0",
        "--memory",
        "4g",
        "--memory-swap",
        "4g",
        "--pids-limit",
        "512",
        "--shm-size",
        "1g",
        "--tmpfs",
        "/tmp:rw,noexec,nosuid,nodev,size=134217728,uid=1000,gid=1000,mode=0700",
        "--user",
        "1000:1000",
        "--env",
        "CUDA_VISIBLE_DEVICES=",
        "--mount",
        f"type=bind,src={artifact_root},dst=/opt/giclab-artifacts",
        "--mount",
        f"type=bind,src={repository / 'src/giclab'},dst=/opt/giclab-src/giclab,readonly",
        "--mount",
        f"type=bind,src={paths['execution']},dst=/opt/giclab-contracts/execution.json,readonly",
        "--mount",
        f"type=bind,src={paths['conditions']},dst=/opt/giclab-contracts/conditions,readonly",
        "--mount",
        f"type=bind,src={args.secret_file.resolve(strict=True)},dst=/run/secrets/sira_api_key,readonly",
        "--label",
        f"org.giclab.t09.plan={PLAN_ID}",
        "--label",
        f"org.giclab.t09.run={manifest['run_id']}",
        "--entrypoint",
        "/opt/sira/.venv/bin/python",
        image_id,
        "/opt/giclab/container_entrypoint.py",
        "--runtime-assignment",
        "SIRA_API_KEY",
        "--",
        *cast(list[str], manifest["argv"]),
    ]


def _limit_file_size() -> None:
    per_stream = MAX_ATTEMPT_OUTPUT_BYTES // 2
    resource.setrlimit(resource.RLIMIT_FSIZE, (per_stream, per_stream))


def run_attached_with_caps(
    *,
    prefix: list[str],
    name: str,
    attempt_root: Path,
    pilot_root: Path,
    attempt_started: float,
    pair_started_at_epoch: float,
    pilot_started_at_epoch: float,
    owned_lambda_started_at_epoch: float,
    prior_lambda_duration_seconds: float,
    prior_lambda_cost_usd: float,
) -> tuple[int, float, str | None, bool]:
    stdout_path = attempt_root / "condition.stdout"
    stderr_path = attempt_root / "condition.stderr"
    stop_reason: str | None = None
    hard_cap_breached = False
    with stdout_path.open("xb") as stdout, stderr_path.open("xb") as stderr:
        process = subprocess.Popen(
            [*prefix, "start", "--attach", name],
            env=safe_environment(),
            stdin=subprocess.DEVNULL,
            stdout=stdout,
            stderr=stderr,
            preexec_fn=_limit_file_size,
        )
        while process.poll() is None:
            now_wall = time.time()
            elapsed = time.monotonic() - attempt_started
            campaign_elapsed = now_wall - pilot_started_at_epoch
            owned_lambda_elapsed = now_wall - owned_lambda_started_at_epoch
            active_lambda_duration = prior_lambda_duration_seconds + owned_lambda_elapsed
            active_lambda_cost = prior_lambda_cost_usd + (
                owned_lambda_elapsed * LAMBDA_HOURLY_PRICE_USD / 3600.0
            )
            if elapsed > MAX_CONDITION_WALL_SECONDS:
                stop_reason = "condition_wall_budget_stop"
            elif now_wall - pair_started_at_epoch > MAX_PAIR_WALL_SECONDS:
                stop_reason = "pair_wall_budget_stop"
            elif campaign_elapsed > MAX_TOTAL_WALL_SECONDS:
                stop_reason = "campaign_total_wall_budget_stop"
            elif active_lambda_duration > (
                MAX_LAMBDA_DURATION_SECONDS - PROVIDER_CLOSEOUT_RESERVE_SECONDS
            ):
                stop_reason = "lambda_duration_budget_stop"
            elif campaign_elapsed > (
                PROVIDER_TERMINATION_CUTOFF_SECONDS
                - ATTEMPT_EVIDENCE_EXPORT_RESERVE_SECONDS
                - PROVIDER_TERMINATION_HANDOFF_SECONDS
            ):
                stop_reason = "provider_termination_handoff_budget_stop"
            elif (
                active_lambda_cost
                + (PROVIDER_CLOSEOUT_RESERVE_SECONDS * LAMBDA_HOURLY_PRICE_USD / 3600.0)
                > MAX_LAMBDA_COST_USD
            ):
                stop_reason = "lambda_cost_budget_stop"
            elif tree_bytes(attempt_root) > MAX_ATTEMPT_OUTPUT_BYTES:
                stop_reason = "attempt_output_bytes"
                hard_cap_breached = True
            elif tree_bytes(pilot_root) > MAX_PILOT_DISK_BYTES:
                stop_reason = "pilot_disk_bytes"
                hard_cap_breached = True
            if stop_reason is not None:
                subprocess.run(
                    [*prefix, "stop", "--time", "30", name],
                    env=safe_environment(),
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                    timeout=60,
                )
                break
            time.sleep(0.25)
        try:
            returncode = process.wait(timeout=60)
        except subprocess.TimeoutExpired:
            process.kill()
            returncode = process.wait(timeout=30)
    return returncode, time.monotonic() - attempt_started, stop_reason, hard_cap_breached


def evaluator_argv(
    *,
    args: argparse.Namespace,
    manifest: dict[str, Any],
    attempt_root: Path,
    cleanup_receipt: Path,
    image_id: str,
    frozen_run_manifest_sha256: str,
    finalizer_commit: str,
    finalizer_source: Path,
    finalizer_source_sha256: str,
    finalizer_projection_source_sha256: str,
    finalizer_projection: Any,
    invocation: int,
    evaluator_revalidation_path: Path,
) -> tuple[list[str], Path, dict[str, str]]:
    repository = args.repository.resolve(strict=True)
    paths = contract_paths(repository)
    artifact_root = args.artifact_root.resolve(strict=True)
    finalizer_source = finalizer_source.resolve(strict=True)
    finalizer_sha256 = file_sha256(finalizer_source)
    if finalizer_sha256 != finalizer_source_sha256:
        raise T09HostError("validated finalizer source changed before projection")
    frozen_manifest = load_object(
        artifact_root / "pilot-v6/frozen-run-manifest.json", label="frozen run manifest"
    )
    finalizer_closure = {
        "finalizer_execution_mode": "qualified-image",
        "finalizer_runtime_qualification_sha256": frozen_run_manifest_sha256,
        "finalizer_commit": finalizer_commit,
        "finalizer_source_sha256": finalizer_sha256,
        "finalizer_projection_source_sha256": finalizer_projection_source_sha256,
        "scientific_package_commit": args.package_commit,
        "pilot_library_sha256": file_sha256(repository / "src/giclab/harness/t09_sira_pilot.py"),
        "interpreter": "/opt/sira/.venv/bin/python",
        "interpreter_sha256": cast(str, frozen_manifest["python_interpreter_sha256"]),
        "interpreter_dependency_manifest_sha256": cast(
            str, frozen_manifest["package_manifest_sha256"]
        ),
        "replacement_image_id": image_id,
        "execution_contract_sha256": file_sha256(paths["execution"]),
        "command_manifests_sha256": file_sha256(paths["commands"]),
        "dataset_contract_sha256": file_sha256(paths["dataset"]),
        "evaluator_contract_sha256": file_sha256(paths["evaluator"]),
        "score_schema_sha256": file_sha256(repository / "schemas/t09-sira-pilot-score.schema.json"),
        "evidence_schema_sha256": file_sha256(
            repository / "schemas/t09-sira-pilot-evidence.schema.json"
        ),
        "evaluator_overlay_entries_sha256": cast(
            str, frozen_manifest["evaluator_overlay_entries_sha256"]
        ),
        "evaluator_overlay_packages_sha256": cast(
            str, frozen_manifest["evaluator_overlay_packages_sha256"]
        ),
    }
    dependency_manifest_sha256 = canonical_sha256(finalizer_closure)
    output_root = manifest_output_root(manifest)
    owned = cast(dict[str, Any], manifest["permitted_condition_owned"])
    raw_output_root = cast(str, owned["raw_output_root"])
    finalized_output_root = cast(str, owned["finalized_output_root"])
    raw_root = (artifact_root / raw_output_root).resolve(strict=True)
    finalized_base = (artifact_root / finalized_output_root).resolve(strict=False)
    finalized_base.mkdir(parents=True, mode=0o700, exist_ok=True)
    invocation_name = f"{finalizer_sha256}-invocation-{invocation:04d}"
    finalized_root = finalized_base / invocation_name
    finalized_root.mkdir(mode=0o700, exist_ok=False)
    control_root = (artifact_root / "pilot-v6").resolve(strict=True)
    projected = finalizer_projection.build_finalizer_argv(
        docker_prefix=docker_prefix(),
        artifact_root=str(artifact_root),
        raw_root=str(raw_root),
        finalized_root=str(finalized_root),
        control_root=str(control_root),
        giclab_source_root=str(repository / "src/giclab"),
        finalizer_source=str(finalizer_source),
        evaluator_overlay=str(args.evaluator_overlay.resolve(strict=True)),
        execution_contract=str(paths["execution"]),
        command_manifests=str(paths["commands"]),
        condition_plans=str(paths["conditions"]),
        schemas_root=str(repository / "schemas"),
        image_id=image_id,
        condition_plan_name=Path(cast(str, manifest["condition_plan_path"])).name,
        output_root=output_root,
        raw_output_root=raw_output_root,
        finalized_output_relative=finalized_root.relative_to(artifact_root).as_posix(),
        run_id=cast(str, manifest["run_id"]),
        package_commit=args.package_commit,
        finalizer_commit=finalizer_commit,
        finalizer_source_sha256=finalizer_sha256,
        finalizer_projection_source_sha256=finalizer_projection_source_sha256,
        finalizer_dependency_manifest_sha256=dependency_manifest_sha256,
        frozen_run_manifest_sha256=frozen_run_manifest_sha256,
        evaluator_revalidation_relative=evaluator_revalidation_path.relative_to(
            artifact_root
        ).as_posix(),
        execution_contract_sha256=file_sha256(paths["execution"]),
        command_manifests_sha256=file_sha256(paths["commands"]),
    )
    _validate_projected_finalizer_argv(
        projected,
        docker_prefix_tokens=docker_prefix(),
        image_id=image_id,
        expected_mounts={
            f"type=bind,src={artifact_root},dst=/opt/giclab-artifacts,readonly",
            f"type=bind,src={raw_root},dst=/opt/giclab-raw,readonly",
            f"type=bind,src={finalized_root},dst=/opt/giclab-finalized",
            f"type=bind,src={control_root},dst=/opt/giclab-control,readonly",
            f"type=bind,src={repository / 'src/giclab'},dst=/opt/giclab-src/giclab,readonly",
            f"type=bind,src={finalizer_source},dst=/opt/giclab/t09_evaluate_attempt.py,readonly",
            f"type=bind,src={args.evaluator_overlay.resolve(strict=True)},dst=/opt/evaluator,readonly",
            f"type=bind,src={paths['execution']},dst=/opt/giclab-contracts/execution.json,readonly",
            f"type=bind,src={paths['commands']},dst=/opt/giclab-contracts/T09_PILOT_COMMAND_MANIFESTS.json,readonly",
            f"type=bind,src={paths['conditions']},dst=/opt/giclab-contracts/conditions,readonly",
            f"type=bind,src={repository / 'schemas'},dst=/opt/giclab-schemas,readonly",
        },
        required_pairs={
            "--run-id": cast(str, manifest["run_id"]),
            "--package-commit": args.package_commit,
            "--finalizer-commit": finalizer_commit,
            "--finalizer-execution-mode": "qualified-image",
            "--finalizer-source-sha256": finalizer_sha256,
            "--finalizer-projection-source-sha256": finalizer_projection_source_sha256,
            "--finalizer-dependency-manifest-sha256": dependency_manifest_sha256,
            "--finalizer-runtime-qualification": "/opt/giclab-control/frozen-run-manifest.json",
            "--finalizer-runtime-qualification-sha256": frozen_run_manifest_sha256,
            "--raw-attempt-root": "/opt/giclab-raw",
            "--finalized-attempt-root": "/opt/giclab-finalized",
            "--replacement-image-id": image_id,
        },
    )
    return projected, finalized_root, finalizer_closure


def _validate_projected_finalizer_argv(
    argv: object,
    *,
    docker_prefix_tokens: list[str],
    image_id: str,
    expected_mounts: set[str],
    required_pairs: dict[str, str],
) -> None:
    """Keep empirical/provider authority frozen while invocation details are repairable."""

    if not isinstance(argv, list) or not argv or not all(isinstance(item, str) for item in argv):
        raise T09HostError("downstream finalizer projection did not return string argv")
    projected = cast(list[str], argv)
    if projected[: len(docker_prefix_tokens)] != docker_prefix_tokens:
        raise T09HostError("downstream finalizer changed the exact container transport")
    suffix = projected[len(docker_prefix_tokens) :]
    if suffix[:2] != ["run", "--rm"] or suffix.count("--read-only") != 1:
        raise T09HostError("downstream finalizer container is not ephemeral/read-only")
    if suffix.count("--network") != 1 or suffix[suffix.index("--network") + 1] != "none":
        raise T09HostError("downstream finalizer network must be exactly none")
    if suffix.count("--entrypoint") != 1:
        raise T09HostError("downstream finalizer entrypoint is ambiguous")
    entrypoint_index = suffix.index("--entrypoint")
    if suffix[entrypoint_index + 1 : entrypoint_index + 4] != [
        "/opt/sira/.venv/bin/python",
        image_id,
        "/opt/giclab/t09_evaluate_attempt.py",
    ]:
        raise T09HostError("downstream finalizer interpreter/image/source drifted")
    mounts = {suffix[index + 1] for index, value in enumerate(suffix[:-1]) if value == "--mount"}
    if mounts != expected_mounts or sum(value == "--mount" for value in suffix) != len(
        expected_mounts
    ):
        raise T09HostError("downstream finalizer mount ownership drifted")
    writable = [mount for mount in mounts if not mount.endswith(",readonly")]
    if len(writable) != 1 or "dst=/opt/giclab-finalized" not in writable[0]:
        raise T09HostError("downstream finalizer has unexpected write authority")
    for flag, expected in required_pairs.items():
        if suffix.count(flag) != 1 or suffix[suffix.index(flag) + 1] != expected:
            raise T09HostError(f"downstream finalizer {flag} binding drifted")


def local_evaluator_invocation(
    *,
    args: argparse.Namespace,
    manifest: dict[str, Any],
    frozen_manifest: dict[str, Any],
    frozen_run_manifest_sha256: str,
    finalizer_commit: str,
    finalizer_source: Path,
    finalizer_source_sha256: str,
    finalizer_projection_source_sha256: str,
    finalizer_projection: Any,
    invocation: int,
    evaluator_revalidation_path: Path,
    local_qualification_path: Path,
    local_qualification: dict[str, Any],
) -> tuple[list[str], dict[str, str], Path, dict[str, str]]:
    """Project and validate one provider-independent local finalizer invocation."""

    repository = args.repository.resolve(strict=True)
    artifact_root = args.artifact_root.resolve(strict=True)
    paths = contract_paths(repository)
    finalizer_source = finalizer_source.resolve(strict=True)
    output_root = manifest_output_root(manifest)
    owned = cast(dict[str, Any], manifest["permitted_condition_owned"])
    raw_output_root = cast(str, owned["raw_output_root"])
    finalized_output_root = cast(str, owned["finalized_output_root"])
    raw_root = (artifact_root / raw_output_root).resolve(strict=True)
    finalized_base = (artifact_root / finalized_output_root).resolve(strict=False)
    finalized_base.mkdir(parents=True, mode=0o700, exist_ok=True)
    invocation_name = f"{finalizer_source_sha256}-invocation-{invocation:04d}"
    finalized_root = finalized_base / invocation_name
    finalized_root.mkdir(mode=0o700, exist_ok=False)
    interpreter = cast(str, local_qualification["interpreter"])
    interpreter_sha256 = cast(str, local_qualification["interpreter_sha256"])
    site_packages = cast(str, local_qualification["dependency_site_packages"])
    local_dependency_tree = cast(dict[str, Any], local_qualification["dependency_tree"])
    closure = {
        "finalizer_execution_mode": "qualified-local",
        "finalizer_runtime_qualification_sha256": file_sha256(local_qualification_path),
        "finalizer_commit": finalizer_commit,
        "finalizer_source_sha256": finalizer_source_sha256,
        "finalizer_projection_source_sha256": finalizer_projection_source_sha256,
        "scientific_package_commit": args.package_commit,
        "pilot_library_sha256": file_sha256(repository / "src/giclab/harness/t09_sira_pilot.py"),
        "interpreter": interpreter,
        "interpreter_sha256": interpreter_sha256,
        "interpreter_dependency_manifest_sha256": cast(
            str, local_qualification["interpreter_dependency_tree_sha256"]
        ),
        "replacement_image_id": cast(str, frozen_manifest["replacement_image_id"]),
        "execution_contract_sha256": file_sha256(paths["execution"]),
        "command_manifests_sha256": file_sha256(paths["commands"]),
        "dataset_contract_sha256": file_sha256(paths["dataset"]),
        "evaluator_contract_sha256": file_sha256(paths["evaluator"]),
        "score_schema_sha256": file_sha256(repository / "schemas/t09-sira-pilot-score.schema.json"),
        "evidence_schema_sha256": file_sha256(
            repository / "schemas/t09-sira-pilot-evidence.schema.json"
        ),
        "evaluator_overlay_entries_sha256": cast(str, local_dependency_tree["entries_sha256"]),
        "evaluator_overlay_packages_sha256": cast(
            str, local_qualification["dependency_package_manifest_sha256"]
        ),
    }
    dependency_manifest_sha256 = canonical_sha256(closure)
    projected = finalizer_projection.build_local_finalizer_invocation(
        interpreter=interpreter,
        dependency_site_packages=site_packages,
        repository_source_root=str(repository / "src"),
        finalizer_source=str(finalizer_source),
        execution_contract=str(paths["execution"]),
        execution_contract_sha256=file_sha256(paths["execution"]),
        command_manifests=str(paths["commands"]),
        command_manifests_sha256=file_sha256(paths["commands"]),
        condition_plan=str(
            paths["conditions"] / Path(cast(str, manifest["condition_plan_path"])).name
        ),
        raw_root=str(raw_root),
        raw_output_relative=raw_output_root,
        finalized_root=str(finalized_root),
        finalized_output_relative=finalized_root.relative_to(artifact_root).as_posix(),
        artifact_root=str(artifact_root),
        raw_attempt_manifest=str(artifact_root / output_root / "raw-attempt-manifest.json"),
        raw_attempt_receipt=str(artifact_root / output_root / "raw-attempt-complete.json"),
        run_id=cast(str, manifest["run_id"]),
        package_commit=args.package_commit,
        finalizer_commit=finalizer_commit,
        finalizer_source_sha256=finalizer_source_sha256,
        finalizer_projection_source_sha256=finalizer_projection_source_sha256,
        finalizer_dependency_manifest_sha256=dependency_manifest_sha256,
        frozen_run_manifest=str(artifact_root / "pilot-v6/frozen-run-manifest.json"),
        frozen_run_manifest_sha256=frozen_run_manifest_sha256,
        replacement_image_id=cast(str, frozen_manifest["replacement_image_id"]),
        host_cleanup_receipt=str(raw_root / "host-cleanup-receipt.json"),
        evaluator_root=str(args.local_evaluator_root.resolve(strict=True)),
        evaluator_overlay_revalidation=str(evaluator_revalidation_path),
        dataset=str(args.local_dataset.resolve(strict=True)),
        score_schema=str(repository / "schemas/t09-sira-pilot-score.schema.json"),
        evidence_schema=str(repository / "schemas/t09-sira-pilot-evidence.schema.json"),
        runtime_qualification=str(local_qualification_path),
        runtime_qualification_sha256=file_sha256(local_qualification_path),
    )
    if not isinstance(projected, dict) or set(projected) != {"argv", "environment", "network"}:
        raise T09HostError("local finalizer projection returned an invalid surface")
    argv = projected.get("argv")
    environment = projected.get("environment")
    expected_environment = {
        "PYTHONPATH": f"{site_packages}:{repository / 'src'}",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONNOUSERSITE": "1",
        "CUDA_VISIBLE_DEVICES": "",
    }
    if (
        not isinstance(argv, list)
        or not all(isinstance(item, str) for item in argv)
        or argv[:2] != [interpreter, str(finalizer_source)]
        or environment != expected_environment
        or projected.get("network") != "socket-construction-denied"
    ):
        raise T09HostError("local finalizer interpreter/environment projection drifted")
    required_pairs = {
        "--finalizer-execution-mode": "qualified-local",
        "--finalizer-source-sha256": finalizer_source_sha256,
        "--finalizer-projection-source-sha256": finalizer_projection_source_sha256,
        "--finalizer-dependency-manifest-sha256": dependency_manifest_sha256,
        "--finalizer-runtime-qualification-sha256": file_sha256(local_qualification_path),
        "--run-id": cast(str, manifest["run_id"]),
        "--raw-attempt-root": str(raw_root),
        "--finalized-attempt-root": str(finalized_root),
    }
    typed_argv = cast(list[str], argv)
    for flag, expected in required_pairs.items():
        if typed_argv.count(flag) != 1 or typed_argv[typed_argv.index(flag) + 1] != expected:
            raise T09HostError(f"local finalizer {flag} binding drifted")
    return typed_argv, expected_environment, finalized_root, closure


def preentry_prefix_inventory(attempt_root: Path) -> list[dict[str, object]]:
    """Bind every preserved pre-entry byte except the self-describing receipt."""

    root = attempt_root.resolve(strict=True)
    if root != attempt_root or root.is_symlink() or not root.is_dir():
        raise T09HostError("pre-entry attempt root metadata is unsafe")
    entries: list[dict[str, object]] = []
    total_bytes = 0
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if relative == "preentry-condition-failure.json":
            continue
        metadata = path.lstat()
        record: dict[str, object] = {
            "path": relative,
            "mode": f"{stat.S_IMODE(metadata.st_mode):04o}",
        }
        if stat.S_ISDIR(metadata.st_mode):
            record["type"] = "directory"
        elif stat.S_ISREG(metadata.st_mode):
            if metadata.st_nlink != 1:
                raise T09HostError("pre-entry prefix contains a linked regular file")
            record.update(
                {
                    "type": "file",
                    "bytes": metadata.st_size,
                    "sha256": file_sha256(path),
                }
            )
            total_bytes += metadata.st_size
        else:
            raise T09HostError("pre-entry prefix contains a symlink or special file")
        entries.append(record)
        if len(entries) > MAX_EVALUATOR_OVERLAY_ENTRIES or total_bytes > MAX_ATTEMPT_OUTPUT_BYTES:
            raise T09HostError("pre-entry prefix exceeds its bounded repair surface")
    return entries


def prepare_condition_attempt_root(
    *,
    artifact_root: Path,
    manifest: dict[str, Any],
    pilot_state: dict[str, Any],
    package_commit: str,
    frozen_run_manifest_sha256: str,
) -> tuple[Path, Path]:
    """Open a fresh root, preserving only source-marked failures from before entry."""

    run_id = cast(str, manifest["run_id"])
    attempt_root = artifact_root / manifest_output_root(manifest)
    if attempt_root.exists() or attempt_root.is_symlink():
        entered = pilot_state.get("empirical_attempts_entered")
        completed = pilot_state.get("attempts_completed")
        receipt = attempt_root / "preentry-condition-failure.json"
        retained = (
            load_object(receipt, label="pre-entry condition failure")
            if (not attempt_root.is_symlink() and receipt.is_file() and not receipt.is_symlink())
            else {}
        )
        observed_prefix = (
            preentry_prefix_inventory(attempt_root)
            if not attempt_root.is_symlink() and attempt_root.is_dir()
            else []
        )
        if (
            attempt_root.is_symlink()
            or not attempt_root.is_dir()
            or not isinstance(entered, list)
            or not isinstance(completed, list)
            or run_id in entered
            or run_id in completed
            or not receipt.is_file()
            or receipt.is_symlink()
            or retained.get("schema_version") != "0.1.0"
            or retained.get("plan_id") != PLAN_ID
            or retained.get("host_run_id") != HOST_RUN_ID
            or retained.get("run_id") != run_id
            or retained.get("clean_package_commit") != package_commit
            or retained.get("execution_contract_sha256")
            != pilot_state.get("execution_contract_sha256")
            or retained.get("frozen_run_manifest_sha256") != frozen_run_manifest_sha256
            or retained.get("condition_plan_sha256") != manifest.get("condition_plan_sha256")
            or retained.get("condition_argv_sha256") != manifest.get("argv_sha256")
            or retained.get("empirical_entry_crossed") is not False
            or retained.get("attempt_identity_consumed") is not False
            or retained.get("container_absent") is not True
            or retained.get("remaining_exact_secret_matches") != []
            or retained.get("secret_bearing_artifacts_removed") != []
            or retained.get("actual_credential_exposure_detected") is not False
            or retained.get("credential_cleanup_integrity_failure") is not False
            or retained.get("structural_privacy_violations") != []
            or retained.get("retry_same_frozen_condition_permitted") is not True
            or retained.get("failure_prefix_entries") != observed_prefix
            or retained.get("failure_prefix_entries_sha256") != canonical_sha256(observed_prefix)
            or privacy_violations(attempt_root)
        ):
            raise T09HostError("existing attempt root is not a repairable pre-entry prefix")
        repair_root = artifact_root / "pilot-v6/preentry-condition-repairs" / run_id
        repair_root.mkdir(mode=0o700, parents=True, exist_ok=True)
        existing = sorted(path for path in repair_root.iterdir() if path.is_dir())
        if len(existing) >= MAX_PREENTRY_REPAIRS_PER_RUN:
            raise T09HostError("pre-entry condition repair limit reached")
        destination = repair_root / f"repair-{len(existing) + 1:02d}"
        if destination.exists() or destination.is_symlink():
            raise T09HostError("pre-entry repair identity is not fresh")
        os.replace(attempt_root, destination)
    attempt_root.mkdir(parents=True, mode=0o700, exist_ok=False)
    owned = manifest.get("permitted_condition_owned")
    if not isinstance(owned, dict):
        raise T09HostError("command manifest lacks its condition-owned roots")
    raw_relative = owned.get("raw_output_root")
    if not isinstance(raw_relative, str):
        raise T09HostError("command manifest lacks its raw output root")
    raw_root = artifact_root / raw_relative
    if raw_root.parent != attempt_root or raw_root.name != "raw":
        raise T09HostError("raw condition root is not the exact owned child")
    raw_root.mkdir(mode=0o700, exist_ok=False)
    return attempt_root, raw_root


def record_preentry_condition_failure(
    *,
    pilot_state_path: Path,
    attempt_root: Path,
    secret_file: Path,
    prefix: list[str],
    container_name: str,
    run_id: str,
    reason: str,
    returncode: int | None,
    package_commit: str,
    execution_contract_sha256: str,
    frozen_run_manifest_sha256: str,
    condition_plan_sha256: str,
    condition_argv_sha256: str,
    actual_credential_exposure_detected: bool = False,
    credential_cleanup_integrity_failure: bool = False,
) -> None:
    """Seal a value-safe, non-consumed condition prefix for an autonomous retry."""

    with contextlib.suppress(OSError, subprocess.SubprocessError, T09HostError):
        remove_container(prefix, container_name)
    credential = validate_secret(secret_file)
    matching = secret_hits(attempt_root, credential)
    removed: list[str] = []
    for relative in matching:
        target = attempt_root / relative
        if target.is_file() and not target.is_symlink():
            target.unlink()
            removed.append(relative)
    remaining = secret_hits(attempt_root, credential)
    credential = b""
    exposure_detected = actual_credential_exposure_detected or bool(matching)
    if exposure_detected:
        mark_actual_credential_exposure(
            pilot_state_path,
            execution_contract_sha256=execution_contract_sha256,
        )
    if credential_cleanup_integrity_failure:
        mark_credential_cleanup_integrity_failure(
            pilot_state_path,
            execution_contract_sha256=execution_contract_sha256,
        )
    residue = [name for name in owned_containers(prefix) if name == container_name]
    privacy = privacy_violations(attempt_root)
    failure_prefix_entries = preentry_prefix_inventory(attempt_root)
    write_exclusive(
        attempt_root / "preentry-condition-failure.json",
        {
            "schema_version": "0.1.0",
            "plan_id": PLAN_ID,
            "host_run_id": HOST_RUN_ID,
            "run_id": run_id,
            "clean_package_commit": package_commit,
            "execution_contract_sha256": execution_contract_sha256,
            "frozen_run_manifest_sha256": frozen_run_manifest_sha256,
            "condition_plan_sha256": condition_plan_sha256,
            "condition_argv_sha256": condition_argv_sha256,
            "empirical_entry_crossed": False,
            "attempt_identity_consumed": False,
            "reason": reason,
            "returncode": returncode,
            "container_absent": not residue,
            "secret_bearing_artifacts_removed": removed,
            "actual_credential_exposure_detected": exposure_detected,
            "credential_cleanup_integrity_failure": credential_cleanup_integrity_failure,
            "remaining_exact_secret_matches": remaining,
            "structural_privacy_violations": privacy,
            "failure_prefix_entries": failure_prefix_entries,
            "failure_prefix_entries_sha256": canonical_sha256(failure_prefix_entries),
            "retry_same_frozen_condition_permitted": (
                not exposure_detected
                and not credential_cleanup_integrity_failure
                and not residue
                and not remaining
            ),
            "recorded_at": utc_now(),
        },
    )
    if exposure_detected or credential_cleanup_integrity_failure or residue or remaining:
        raise T09HostError(
            "pre-entry failure cleanup detected an actual credential exposure or residue"
        )


def _raw_attempt_files(raw_root: Path) -> tuple[list[dict[str, object]], int]:
    """Inventory every regular raw byte without following links or special files."""

    files: list[dict[str, object]] = []
    total = 0
    for path in sorted(raw_root.rglob("*")):
        metadata = path.lstat()
        relative = path.relative_to(raw_root).as_posix()
        if stat.S_ISDIR(metadata.st_mode):
            continue
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1 or path.is_symlink():
            raise T09HostError(f"raw attempt contains an unsafe artifact category: {relative}")
        total += metadata.st_size
        if total > MAX_ATTEMPT_OUTPUT_BYTES:
            raise T09HostError("raw attempt exceeds its hard byte cap")
        files.append(
            {
                "path": relative,
                "bytes": metadata.st_size,
                "sha256": file_sha256(path),
            }
        )
    return files, total


def seal_raw_attempt(
    *,
    artifact_root: Path,
    attempt_root: Path,
    raw_root: Path,
    manifest: dict[str, Any],
    package_commit: str,
    frozen_run_manifest_sha256: str,
    execution_contract_sha256: str,
) -> tuple[Path, Path]:
    """Seal one consumed condition before any fallible evaluator invocation."""

    run_id = cast(str, manifest["run_id"])
    required = {
        "attempt-wall.json",
        "condition.stderr",
        "condition.stdout",
        "container-command.json",
        "container-state.json",
        "gpu-accounting.json",
        "host-cleanup-receipt.json",
        "evaluator-overlay-binding.json",
        "normalized-events.jsonl",
        "provider-budget.json",
        "runtime-reconstruction-binding.json",
        "runtime-environment.json",
    }
    missing = sorted(name for name in required if not (raw_root / name).is_file())
    cleanup = load_object(raw_root / "host-cleanup-receipt.json", label="host cleanup")
    state = load_object(artifact_root / "pilot-v6/pilot-state.json", label="pilot state")
    entered = state.get("empirical_attempts_entered")
    exposure_detected = cleanup.get("actual_credential_exposure_detected")
    cleanup_integrity_failure = cleanup.get("runtime_secret_cleanup_malformed")
    events_path = raw_root / "normalized-events.jsonl"
    source_grounded_events = 0
    try:
        with events_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                event: object = json.loads(line)
                if not isinstance(event, dict):
                    raise T09HostError("raw normalized event is not an object")
                if event.get("kind") in {
                    "provider-call-failed",
                    "provider-call-receipt",
                    "requested-browser-action",
                    "post-action-result",
                }:
                    source_grounded_events += 1
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise T09HostError("raw normalized events are not reconstructable") from exc
    budget = load_object(raw_root / "provider-budget.json", label="raw provider budget")
    evaluator_binding = load_object(
        raw_root / "evaluator-overlay-binding.json", label="raw evaluator overlay binding"
    )
    runtime_binding = load_object(
        raw_root / "runtime-reconstruction-binding.json",
        label="raw runtime reconstruction binding",
    )
    runtime_cleanup_path = raw_root / "runtime-cleanup.json"
    session_paths = sorted(
        path
        for path in (raw_root / "sira-output").glob("*.json")
        if path.name != "output.jsonl" and path.is_file() and not path.is_symlink()
    )
    if len(session_paths) == 1:
        reconstructable_disposition = "one-session-evaluator-ready"
    elif not session_paths:
        reconstructable_disposition = "deterministic-invalid-infrastructure-missing-session"
    else:
        reconstructable_disposition = "deterministic-invalid-infrastructure-duplicate-session"
    structural_privacy_findings = privacy_violations(raw_root)
    if (
        missing
        or not isinstance(entered, list)
        or run_id not in entered
        or cleanup.get("container_removed") is not True
        or cleanup.get("owned_container_residue") != []
        or cleanup.get("secret_scan_passed") is not True
        or cleanup.get("secret_matching_paths") != []
        or not isinstance(exposure_detected, bool)
        or not isinstance(cleanup_integrity_failure, bool)
        or state.get("actual_credential_exposure_detected") is not exposure_detected
        or state.get("credential_safety_stop_detected")
        is not (exposure_detected or cleanup_integrity_failure)
        or budget.get("unreconciled_provider_attempts") != 0
        or evaluator_binding.get("run_id") != run_id
        or evaluator_binding.get("frozen_run_manifest_sha256") != frozen_run_manifest_sha256
        or evaluator_binding.get("condition_mount_policy") != "read-only"
        or runtime_binding.get("run_id") != run_id
        or runtime_binding.get("runtime_cleanup_present") != runtime_cleanup_path.is_file()
        or runtime_binding.get("runtime_cleanup_sha256")
        != (file_sha256(runtime_cleanup_path) if runtime_cleanup_path.is_file() else None)
        or runtime_binding.get("host_cleanup_receipt_sha256")
        != file_sha256(raw_root / "host-cleanup-receipt.json")
        or runtime_binding.get("container_state_sha256")
        != file_sha256(raw_root / "container-state.json")
        or runtime_binding.get("host_teardown_is_source_grounded_fallback") is not True
        or source_grounded_events == 0
    ):
        category = "missing=" + ",".join(missing) if missing else "cleanup-or-reconciliation"
        raise T09HostError(f"raw attempt is not reconstructable: {category}")
    files, total = _raw_attempt_files(raw_root)
    raw_manifest_path = attempt_root / "raw-attempt-manifest.json"
    raw_receipt_path = attempt_root / "raw-attempt-complete.json"
    raw_manifest: dict[str, object] = {
        "schema_version": "0.1.0",
        "plan_id": PLAN_ID,
        "host_run_id": HOST_RUN_ID,
        "run_id": run_id,
        "package_commit": package_commit,
        "execution_contract_sha256": execution_contract_sha256,
        "frozen_run_manifest_sha256": frozen_run_manifest_sha256,
        "condition_plan_sha256": manifest["condition_plan_sha256"],
        "condition_argv_sha256": manifest["argv_sha256"],
        "raw_attempt_root": "raw",
        "files": files,
        "total_bytes": total,
        "condition_writers_closed": True,
        "raw_source_mutable_by_finalizer": False,
        "source_grounded_empirical_event_count": source_grounded_events,
        "retained_session_count": len(session_paths),
        "reconstructable_disposition": reconstructable_disposition,
        "actual_credential_exposure_detected": exposure_detected,
        "credential_cleanup_integrity_failure": cleanup_integrity_failure,
        "credential_cleanup_clean": not exposure_detected and not cleanup_integrity_failure,
        "structural_privacy_findings": structural_privacy_findings,
        "public_release_clearance": (
            not structural_privacy_findings
            and not exposure_detected
            and not cleanup_integrity_failure
        ),
        "private_access_controlled": True,
    }
    if raw_manifest_path.exists():
        if load_object(raw_manifest_path, label="resumed raw manifest") != raw_manifest:
            raise T09HostError("retained raw manifest drifted during seal resumption")
    else:
        if raw_receipt_path.exists():
            raise T09HostError("raw receipt exists without its source manifest")
        write_exclusive(raw_manifest_path, raw_manifest)
    raw_receipt: dict[str, object] = {
        "schema_version": "0.1.0",
        "plan_id": PLAN_ID,
        "host_run_id": HOST_RUN_ID,
        "run_id": run_id,
        "raw_attempt_complete": True,
        "empirical_attempt_consumed": True,
        "condition_terminated": True,
        "container_and_browser_cleanup_clean": True,
        "credential_cleanup_clean": not exposure_detected and not cleanup_integrity_failure,
        "actual_credential_exposure_detected": exposure_detected,
        "credential_cleanup_integrity_failure": cleanup_integrity_failure,
        "raw_manifest_path": raw_manifest_path.name,
        "raw_manifest_sha256": file_sha256(raw_manifest_path),
        "raw_total_bytes": total,
        "raw_file_count": len(files),
        "source_grounded_empirical_event_count": source_grounded_events,
        "retained_session_count": len(session_paths),
        "reconstructable_disposition": reconstructable_disposition,
        "structural_privacy_findings": structural_privacy_findings,
        "public_release_clearance": (
            not structural_privacy_findings
            and not exposure_detected
            and not cleanup_integrity_failure
        ),
        "finalizer_network_policy": "none",
        "condition_retry_permitted": False,
        "recorded_at": utc_now(),
    }
    if raw_receipt_path.exists():
        retained_receipt = load_object(raw_receipt_path, label="resumed raw receipt")
        retained_recorded_at = retained_receipt.pop("recorded_at", None)
        expected_without_time = dict(raw_receipt)
        expected_without_time.pop("recorded_at")
        if not isinstance(retained_recorded_at, str) or retained_receipt != expected_without_time:
            raise T09HostError("retained raw receipt drifted during seal resumption")
    else:
        write_exclusive(raw_receipt_path, raw_receipt)
    validate_raw_attempt_seal(
        attempt_root=attempt_root,
        raw_root=raw_root,
        run_id=run_id,
        package_commit=package_commit,
    )
    mark_raw_attempt_complete(
        artifact_root / "pilot-v6/pilot-state.json",
        execution_contract_sha256=execution_contract_sha256,
        run_id=run_id,
        raw_manifest_sha256=file_sha256(raw_manifest_path),
        raw_receipt_sha256=file_sha256(raw_receipt_path),
    )
    return raw_manifest_path, raw_receipt_path


def validate_raw_attempt_seal(
    *,
    attempt_root: Path,
    raw_root: Path,
    run_id: str,
    package_commit: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Reconstruct a raw seal from current bytes before export or finalization."""

    manifest_path = attempt_root / "raw-attempt-manifest.json"
    receipt_path = attempt_root / "raw-attempt-complete.json"
    manifest = load_object(manifest_path, label="raw attempt manifest")
    receipt = load_object(receipt_path, label="raw attempt receipt")
    observed_files, observed_total = _raw_attempt_files(raw_root)
    if (
        manifest.get("schema_version") != "0.1.0"
        or manifest.get("plan_id") != PLAN_ID
        or manifest.get("host_run_id") != HOST_RUN_ID
        or manifest.get("run_id") != run_id
        or manifest.get("package_commit") != package_commit
        or manifest.get("raw_attempt_root") != "raw"
        or manifest.get("files") != observed_files
        or manifest.get("total_bytes") != observed_total
        or receipt.get("schema_version") != "0.1.0"
        or receipt.get("plan_id") != PLAN_ID
        or receipt.get("host_run_id") != HOST_RUN_ID
        or receipt.get("run_id") != run_id
        or receipt.get("raw_attempt_complete") is not True
        or receipt.get("empirical_attempt_consumed") is not True
        or receipt.get("raw_manifest_sha256") != file_sha256(manifest_path)
        or receipt.get("raw_total_bytes") != observed_total
        or receipt.get("raw_file_count") != len(observed_files)
        or receipt.get("source_grounded_empirical_event_count")
        != manifest.get("source_grounded_empirical_event_count")
        or receipt.get("retained_session_count") != manifest.get("retained_session_count")
        or receipt.get("reconstructable_disposition") != manifest.get("reconstructable_disposition")
        or receipt.get("actual_credential_exposure_detected")
        != manifest.get("actual_credential_exposure_detected")
        or receipt.get("credential_cleanup_integrity_failure")
        != manifest.get("credential_cleanup_integrity_failure")
        or receipt.get("credential_cleanup_clean") != manifest.get("credential_cleanup_clean")
        or receipt.get("structural_privacy_findings") != manifest.get("structural_privacy_findings")
        or receipt.get("public_release_clearance") != manifest.get("public_release_clearance")
        or receipt.get("condition_retry_permitted") is not False
    ):
        raise T09HostError("raw attempt seal no longer reconstructs from exact bytes")
    return manifest, receipt


def validate_live_frozen_state_binding(
    state: dict[str, Any],
    frozen_manifest: dict[str, Any],
) -> None:
    """Keep mutable scientific admission state bound to the immutable V6 freeze."""

    expected = {
        "execution_contract_sha256": frozen_manifest.get("execution_contract_sha256"),
        "pilot_started_at_epoch": frozen_manifest.get("campaign_started_at_epoch"),
        "campaign_started_at_epoch": frozen_manifest.get("campaign_started_at_epoch"),
        "lambda_started_at_epoch": frozen_manifest.get("lambda_started_at_epoch"),
        "owned_lambda_started_at_epoch": frozen_manifest.get("owned_lambda_started_at_epoch"),
        "prior_campaign_lambda_duration_seconds": frozen_manifest.get(
            "prior_lambda_duration_seconds"
        ),
        "prior_campaign_lambda_cost_usd": frozen_manifest.get("prior_lambda_cost_usd"),
        "launch_slot": frozen_manifest.get("launch_slot"),
        "launch_count": frozen_manifest.get("launch_count"),
        "replacement_eligibility_sha256": frozen_manifest.get("replacement_eligibility_sha256"),
        "replacement_eligibility_source_manifest_sha256": frozen_manifest.get(
            "replacement_eligibility_source_manifest_sha256"
        ),
        "first_pair_started_at_epoch": frozen_manifest.get("first_pair_started_at_epoch"),
        "actual_credential_exposure_detected": False,
        "credential_safety_stop_detected": False,
    }
    if any(state.get(key) != value for key, value in expected.items()):
        raise T09HostError("live state drifted from the frozen admission authority")


def validate_postfreeze_entry_receipts(
    *,
    preflight_receipt: dict[str, Any],
    postfreeze: dict[str, Any],
    frozen_manifest: dict[str, Any],
    frozen_manifest_sha256: str,
    replacement_image_id: str,
    postfreeze_sha256: str,
    model_metadata_credential_scan_sha256: str,
) -> None:
    """Validate the one exact completion receipt that admits empirical entry."""

    if (
        preflight_receipt.get("frozen_run_manifest_sha256") != frozen_manifest_sha256
        or preflight_receipt.get("replacement_image_id") != replacement_image_id
        or preflight_receipt.get("first_pair_started_at_epoch")
        != frozen_manifest.get("first_pair_started_at_epoch")
        or preflight_receipt.get("empirical_entry_crossed") is not False
        or preflight_receipt.get("postfreeze_validation_sha256") != postfreeze_sha256
        or postfreeze.get("frozen_run_manifest_sha256") != frozen_manifest_sha256
        or postfreeze.get("replacement_image_id") != replacement_image_id
        or frozen_manifest.get("image_materialization_policy")
        not in {
            SLOT1_IMAGE_MATERIALIZATION_POLICY,
            SLOT2_IMAGE_MATERIALIZATION_POLICY,
        }
        or postfreeze.get("image_materialization_policy")
        != frozen_manifest.get("image_materialization_policy")
        or postfreeze.get("model_metadata_request_count") != 1
        or postfreeze.get("model_metadata_credential_scan_sha256")
        != model_metadata_credential_scan_sha256
        or postfreeze.get("actual_credential_exposure_detected") is not False
        or postfreeze.get("model_task_request_count") != 0
        or postfreeze.get("task_browser_action_count") != 0
        or postfreeze.get("first_pair_started_at_epoch")
        != frozen_manifest.get("first_pair_started_at_epoch")
        or postfreeze.get(POSTFREEZE_ADMISSION_FIELD) is not True
    ):
        raise T09HostError("preflight and frozen runtime manifest drifted")


def execute_condition(args: argparse.Namespace) -> int:
    attempt_started = time.monotonic()
    attempt_started_epoch = time.time()
    repository = args.repository.resolve(strict=True)
    artifact_root = args.artifact_root.resolve(strict=True)
    admit_next_attempt(artifact_root)
    verify_package(repository, args.package_commit)
    frozen_manifest, frozen_manifest_sha256 = load_frozen_run_manifest(
        artifact_root,
        repository=repository,
        package_commit=args.package_commit,
    )
    image_id = cast(str, frozen_manifest["replacement_image_id"])
    prefix = docker_prefix()
    validate_evaluator_overlay_binding(
        artifact_root=artifact_root,
        repository=repository,
        overlay=args.evaluator_overlay.resolve(strict=True),
        prefix=prefix,
        image_id=image_id,
        frozen_manifest=frozen_manifest,
        verify_packages=False,
    )
    paths = contract_paths(repository)
    command_document = load_object(paths["commands"], label="command manifest set")
    manifest = manifest_for_run(command_document, args.run_id)
    preflight_path = artifact_root / "pilot-v6/preflight.json"
    if not preflight_path.is_file():
        raise T09HostError("exact preflight did not complete")
    preflight_receipt = load_object(preflight_path, label="exact preflight")
    postfreeze_path = artifact_root / "pilot-v6/postfreeze-validation.json"
    if not postfreeze_path.is_file():
        raise T09HostError("post-freeze validation did not publish its final completion receipt")
    postfreeze = load_object(postfreeze_path, label="post-freeze validation")
    validate_postfreeze_entry_receipts(
        preflight_receipt=preflight_receipt,
        postfreeze=postfreeze,
        frozen_manifest=frozen_manifest,
        frozen_manifest_sha256=frozen_manifest_sha256,
        replacement_image_id=image_id,
        postfreeze_sha256=file_sha256(postfreeze_path),
        model_metadata_credential_scan_sha256=file_sha256(
            artifact_root / "pilot-v6/model-metadata-credential-scan.json"
        ),
    )
    state = load_object(artifact_root / "pilot-v6/pilot-state.json", label="pilot state")
    entered = state.get("empirical_attempts_entered")
    completed = state.get("attempts_completed")
    if not isinstance(entered, list) or not isinstance(completed, list):
        raise T09HostError("pilot attempt state is malformed")
    validate_live_frozen_state_binding(state, frozen_manifest)
    expected_index = len(entered)
    if expected_index >= len(RUN_IDS) or RUN_IDS[expected_index] != args.run_id:
        raise T09HostError("condition would violate frozen order or zero retry")
    if len(entered) == 2 and state.get("first_pair_decision") != "continue-to-task-b":
        raise T09HostError("Task B is blocked by the first-pair checkpoint")
    checkpoint_binding = state.get("first_pair_checkpoint_binding")
    if expected_index >= 2 and (
        not isinstance(checkpoint_binding, dict)
        or checkpoint_binding.get("first_pair_started_at_epoch")
        != frozen_manifest.get("first_pair_started_at_epoch")
        or checkpoint_binding.get("second_pair_started_at_epoch")
        != state.get("second_pair_started_at_epoch")
    ):
        raise T09HostError("Task B pair-wall origin drifted from the checkpoint")
    require_prior_export_acknowledgements(
        artifact_root,
        next_attempt_index=expected_index,
        package_commit=args.package_commit,
    )
    started_epoch = state.get("campaign_started_at_epoch")
    owned_lambda_started_epoch = state.get("owned_lambda_started_at_epoch")
    prior_lambda_duration = state.get("prior_campaign_lambda_duration_seconds")
    prior_lambda_cost = state.get("prior_campaign_lambda_cost_usd")
    pair_field = (
        "first_pair_started_at_epoch" if expected_index < 2 else "second_pair_started_at_epoch"
    )
    pair_started_epoch = state.get(pair_field)
    if not all(
        isinstance(value, (int, float)) and not isinstance(value, bool)
        for value in (
            started_epoch,
            pair_started_epoch,
            owned_lambda_started_epoch,
            prior_lambda_duration,
            prior_lambda_cost,
        )
    ):
        raise T09HostError("pilot, pair, or Lambda wall origin is unavailable")
    assert isinstance(started_epoch, (int, float))
    assert isinstance(pair_started_epoch, (int, float))
    assert isinstance(owned_lambda_started_epoch, (int, float))
    assert isinstance(prior_lambda_duration, (int, float))
    assert isinstance(prior_lambda_cost, (int, float))
    total_elapsed = time.time() - float(started_epoch)
    if total_elapsed >= MAX_TOTAL_WALL_SECONDS:
        raise T09HostError("total pilot wall cap reached")
    pair_elapsed = time.time() - float(pair_started_epoch)
    owned_lambda_elapsed = time.time() - float(owned_lambda_started_epoch)
    lambda_elapsed = float(prior_lambda_duration) + owned_lambda_elapsed
    lambda_cost = float(prior_lambda_cost) + (
        owned_lambda_elapsed * LAMBDA_HOURLY_PRICE_USD / 3600.0
    )
    if pair_elapsed >= MAX_PAIR_WALL_SECONDS:
        raise T09HostError("pair wall cap reached")
    if lambda_elapsed >= MAX_LAMBDA_DURATION_SECONDS:
        raise T09HostError("Lambda duration cap reached")
    if lambda_cost >= MAX_LAMBDA_COST_USD:
        raise T09HostError("Lambda cost cap reached")

    attempt_root, raw_root = prepare_condition_attempt_root(
        artifact_root=artifact_root,
        manifest=manifest,
        pilot_state=state,
        package_commit=args.package_commit,
        frozen_run_manifest_sha256=frozen_manifest_sha256,
    )
    gpu_before = gpu_snapshot()
    name = f"{CONTAINER_PREFIX}{expected_index + 1:02d}"
    create_argv = container_create_argv(
        args=args,
        manifest=manifest,
        attempt_root=raw_root,
        container_name=name,
        image_id=image_id,
    )
    write_exclusive(
        raw_root / "container-command.json",
        {
            "schema_version": "0.1.0",
            "run_id": args.run_id,
            "docker_create_argv": create_argv,
            "docker_create_argv_sha256": canonical_sha256(create_argv),
            "condition_argv_sha256": manifest["argv_sha256"],
            "replacement_image_id": image_id,
            "frozen_run_manifest_sha256": frozen_manifest_sha256,
        },
    )
    write_exclusive(
        raw_root / "evaluator-overlay-binding.json",
        {
            "schema_version": "0.1.0",
            "run_id": args.run_id,
            "frozen_run_manifest_sha256": frozen_manifest_sha256,
            "evaluator_contract_sha256": file_sha256(paths["evaluator"]),
            "overlay_manifest_sha256": frozen_manifest["evaluator_overlay_manifest_sha256"],
            "overlay_entries_sha256": frozen_manifest["evaluator_overlay_entries_sha256"],
            "overlay_packages_sha256": frozen_manifest["evaluator_overlay_packages_sha256"],
            "condition_mount_policy": "read-only",
        },
    )
    write_exclusive(
        raw_root / "attempt-wall.json",
        {
            "schema_version": "0.1.0",
            "run_id": args.run_id,
            "attempt_started_at_epoch": attempt_started_epoch,
            "condition_hard_deadline_epoch": (attempt_started_epoch + MAX_CONDITION_WALL_SECONDS),
            "evidence_handoff_deadline_epoch": (
                attempt_started_epoch
                + MAX_CONDITION_WALL_SECONDS
                + ATTEMPT_EVIDENCE_EXPORT_RESERVE_SECONDS
            ),
            "condition_hard_wall_seconds": MAX_CONDITION_WALL_SECONDS,
            "post_condition_evaluator_and_export_seconds": (
                ATTEMPT_EVIDENCE_EXPORT_RESERVE_SECONDS
            ),
        },
    )
    created = subprocess.run(
        create_argv,
        env=safe_environment(),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
        timeout=60,
    )
    if created.returncode != 0:
        record_preentry_condition_failure(
            pilot_state_path=artifact_root / "pilot-v6/pilot-state.json",
            attempt_root=attempt_root,
            secret_file=args.secret_file.resolve(strict=True),
            prefix=prefix,
            container_name=name,
            run_id=args.run_id,
            reason="container-create-failed-before-empirical-entry",
            returncode=created.returncode,
            package_commit=args.package_commit,
            execution_contract_sha256=cast(str, state["execution_contract_sha256"]),
            frozen_run_manifest_sha256=frozen_manifest_sha256,
            condition_plan_sha256=cast(str, manifest["condition_plan_sha256"]),
            condition_argv_sha256=cast(str, manifest["argv_sha256"]),
        )
        raise T09HostError("condition container creation failed before empirical entry")
    started_at = utc_now()
    returncode = 125
    wall = 0.0
    stop_reason: str | None = None
    hard_cap_breached = False
    container_removed = False
    container_state: dict[str, object] | None = None
    runner_exception: Exception | None = None
    try:
        try:
            returncode, wall, stop_reason, hard_cap_breached = run_attached_with_caps(
                prefix=prefix,
                name=name,
                attempt_root=raw_root,
                pilot_root=artifact_root,
                attempt_started=attempt_started,
                pair_started_at_epoch=float(pair_started_epoch),
                pilot_started_at_epoch=float(started_epoch),
                owned_lambda_started_at_epoch=float(owned_lambda_started_epoch),
                prior_lambda_duration_seconds=float(prior_lambda_duration),
                prior_lambda_cost_usd=float(prior_lambda_cost),
            )
        except Exception as exc:  # Preserve the exact pre-entry/empirical disposition.
            runner_exception = exc
            returncode = 125
            wall = time.monotonic() - attempt_started
            stop_reason = "host-runner-exception"
            hard_cap_breached = True
    finally:
        try:
            container_state = container_state_receipt(prefix, name)
        except T09HostError as exc:
            container_state = {
                "status": "inspection-unavailable",
                "running": None,
                "inspection_error_type": type(exc).__name__,
                "private_network_fields_retained": False,
            }
        write_exclusive(raw_root / "container-state.json", container_state)
        container_removed = remove_container(prefix, name)
    gpu_after = gpu_snapshot()
    write_exclusive(
        raw_root / "gpu-accounting.json",
        {
            "schema_version": "0.1.0",
            "run_id": args.run_id,
            "before": gpu_before,
            "after": gpu_after,
            "pilot_container_gpu_device_request": "none",
            "pilot_container_cuda_visible_devices": "disabled-empty",
            "pilot_process_gpu_use": False,
            "gpu_acceleration_claim": False,
            "selected_a10_reason": (
                "reuses the already-qualified T07 Lambda shape and browser runtime; "
                "GPU computation is not required"
            ),
        },
    )
    credential_bytes = validate_secret(args.secret_file.resolve(strict=True))
    runtime_cleanup_path = raw_root / "runtime-cleanup.json"
    runtime_removed_secret_artifacts: list[str] = []
    runtime_secret_cleanup_malformed = False
    if runtime_cleanup_path.is_file() and not runtime_cleanup_path.is_symlink():
        runtime_cleanup = load_object(runtime_cleanup_path, label="runtime cleanup")
        runtime_secret_cleanup = runtime_cleanup.get("secret_cleanup")
        runtime_removed_raw = (
            runtime_secret_cleanup.get("secret_bearing_artifacts_removed")
            if isinstance(runtime_secret_cleanup, dict)
            else None
        )
        if isinstance(runtime_removed_raw, list) and all(
            isinstance(item, str) for item in runtime_removed_raw
        ):
            runtime_removed_secret_artifacts = cast(list[str], runtime_removed_raw)
        else:
            runtime_secret_cleanup_malformed = True
    hits = secret_hits(raw_root, credential_bytes)
    removed_secret_artifacts: list[str] = []
    for relative in hits:
        target = raw_root / relative
        if target.is_file() and not target.is_symlink():
            target.unlink()
            removed_secret_artifacts.append(relative)
    remaining_hits = secret_hits(raw_root, credential_bytes)
    credential_bytes = b""
    actual_credential_exposure_detected = bool(hits or runtime_removed_secret_artifacts)
    if actual_credential_exposure_detected:
        mark_actual_credential_exposure(
            artifact_root / "pilot-v6/pilot-state.json",
            execution_contract_sha256=cast(str, state["execution_contract_sha256"]),
        )
    if runtime_secret_cleanup_malformed:
        mark_credential_cleanup_integrity_failure(
            artifact_root / "pilot-v6/pilot-state.json",
            execution_contract_sha256=cast(str, state["execution_contract_sha256"]),
        )
    residue = owned_containers(prefix)
    cleanup_receipt = raw_root / "host-cleanup-receipt.json"
    write_exclusive(
        cleanup_receipt,
        {
            "schema_version": "0.1.0",
            "run_id": args.run_id,
            "returncode": returncode,
            "container_removed": container_removed and not residue,
            "owned_container_residue": residue,
            "container_state_receipt": "container-state.json",
            "secret_scan_passed": not remaining_hits,
            "secret_bearing_artifacts_removed": removed_secret_artifacts,
            "runtime_secret_bearing_artifacts_removed": runtime_removed_secret_artifacts,
            "runtime_secret_cleanup_malformed": runtime_secret_cleanup_malformed,
            "secret_matching_paths": remaining_hits,
            "actual_credential_exposure_detected": actual_credential_exposure_detected,
            "campaign_continuation_permitted": (
                not actual_credential_exposure_detected
                and not runtime_secret_cleanup_malformed
                and not residue
                and not remaining_hits
            ),
            "stop_reason": stop_reason,
            "hard_cap_breached": hard_cap_breached,
            "runner_exception_type": (
                type(runner_exception).__name__ if runner_exception is not None else None
            ),
            "timing": {
                "started_at": started_at,
                "stopped_at": utc_now(),
                "wall_seconds": wall,
            },
        },
    )
    write_exclusive(
        raw_root / "runtime-reconstruction-binding.json",
        {
            "schema_version": "0.1.0",
            "run_id": args.run_id,
            "runtime_cleanup_present": runtime_cleanup_path.is_file(),
            "runtime_cleanup_sha256": (
                file_sha256(runtime_cleanup_path) if runtime_cleanup_path.is_file() else None
            ),
            "host_cleanup_receipt_sha256": file_sha256(cleanup_receipt),
            "container_state_sha256": file_sha256(raw_root / "container-state.json"),
            "host_teardown_is_source_grounded_fallback": True,
        },
    )
    state_after_condition = load_object(
        artifact_root / "pilot-v6/pilot-state.json", label="post-condition pilot state"
    )
    entered_after_condition = state_after_condition.get("empirical_attempts_entered")
    if not isinstance(entered_after_condition, list):
        raise T09HostError("post-condition empirical state is malformed")
    if args.run_id not in entered_after_condition:
        record_preentry_condition_failure(
            pilot_state_path=artifact_root / "pilot-v6/pilot-state.json",
            attempt_root=attempt_root,
            secret_file=args.secret_file.resolve(strict=True),
            prefix=prefix,
            container_name=name,
            run_id=args.run_id,
            reason="condition-runtime-ended-before-first-model-request-or-browser-action",
            returncode=returncode,
            package_commit=args.package_commit,
            execution_contract_sha256=cast(str, state["execution_contract_sha256"]),
            frozen_run_manifest_sha256=frozen_manifest_sha256,
            condition_plan_sha256=cast(str, manifest["condition_plan_sha256"]),
            condition_argv_sha256=cast(str, manifest["argv_sha256"]),
            actual_credential_exposure_detected=actual_credential_exposure_detected,
            credential_cleanup_integrity_failure=runtime_secret_cleanup_malformed,
        )
        if runner_exception is not None:
            raise T09HostError(
                "condition host runner failed before empirical entry"
            ) from runner_exception
        raise T09HostError("condition ended before empirical entry; frozen retry remains permitted")
    seal_raw_attempt(
        artifact_root=artifact_root,
        attempt_root=attempt_root,
        raw_root=raw_root,
        manifest=manifest,
        package_commit=args.package_commit,
        frozen_run_manifest_sha256=frozen_manifest_sha256,
        execution_contract_sha256=cast(str, state["execution_contract_sha256"]),
    )
    if actual_credential_exposure_detected or runtime_secret_cleanup_malformed:
        raise T09HostError(
            "credential cleanup was unsafe or unreconstructable; campaign continuation is forbidden"
        )
    return returncode


def validate_finalizer_source(
    *,
    repository: Path,
    package_commit: str,
    finalizer_commit: str,
    source: Path,
    projection_source: Path,
) -> tuple[str, str, Any]:
    """Bind downstream-repairable bytes without changing the frozen worktree."""

    if re.fullmatch(r"[a-f0-9]{40}", finalizer_commit) is None:
        raise T09HostError("finalizer commit is malformed")
    sources = {
        FINALIZER_RELATIVE_PATH: source.resolve(strict=True),
        FINALIZER_PROJECTION_RELATIVE_PATH: projection_source.resolve(strict=True),
    }
    for path in sources.values():
        metadata = path.stat(follow_symlinks=False)
        if (
            path.is_symlink()
            or not stat.S_ISREG(metadata.st_mode)
            or metadata.st_nlink != 1
            or metadata.st_mode & 0o022
            or not 0 < metadata.st_size <= 1_048_576
        ):
            raise T09HostError("downstream finalizer source metadata is unsafe")
    environment = safe_environment()
    ancestry = subprocess.run(
        [
            "git",
            "-C",
            str(repository),
            "merge-base",
            "--is-ancestor",
            package_commit,
            finalizer_commit,
        ],
        env=environment,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
        timeout=30,
    )
    if ancestry.returncode != 0:
        raise T09HostError("finalizer commit is not a descendant of the frozen package")
    if finalizer_commit != package_commit:
        changed = output(
            [
                "git",
                "-C",
                str(repository),
                "diff",
                "--name-only",
                package_commit,
                finalizer_commit,
            ]
        ).splitlines()
        allowed = {
            FINALIZER_RELATIVE_PATH,
            FINALIZER_PROJECTION_RELATIVE_PATH,
            "tests/test_t09_sira_pilot.py",
            "tests/test_t09_retry3.py",
        }
        if not set(changed).intersection(
            {FINALIZER_RELATIVE_PATH, FINALIZER_PROJECTION_RELATIVE_PATH}
        ) or not set(changed).issubset(allowed):
            raise T09HostError("post-entry finalizer commit changed a non-downstream surface")
    for relative, path in sources.items():
        retained = subprocess.run(
            ["git", "-C", str(repository), "show", f"{finalizer_commit}:{relative}"],
            env=environment,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            check=True,
            timeout=30,
        ).stdout
        if retained != path.read_bytes():
            raise T09HostError("downstream finalizer bytes do not match their Git commit")
    specification = importlib.util.spec_from_file_location(
        "giclab_t09_finalizer_projection", sources[FINALIZER_PROJECTION_RELATIVE_PATH]
    )
    if specification is None or specification.loader is None:
        raise T09HostError("downstream finalizer projection cannot be loaded")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    if (
        not callable(getattr(module, "build_finalizer_argv", None))
        or not callable(getattr(module, "build_local_finalizer_invocation", None))
        or not callable(getattr(module, "build_completion_projection", None))
    ):
        raise T09HostError("downstream finalizer projection API is incomplete")
    return (
        file_sha256(sources[FINALIZER_RELATIVE_PATH]),
        file_sha256(sources[FINALIZER_PROJECTION_RELATIVE_PATH]),
        module,
    )


def validate_local_finalizer_qualification(
    path: Path,
    *,
    repository: Path,
    package_commit: str,
    require_local_runtime: bool,
    evaluator_root: Path | None = None,
    dataset: Path | None = None,
) -> dict[str, Any]:
    """Validate the prelaunch absolute local analysis closure."""

    qualification_path = path.resolve(strict=True)
    metadata = qualification_path.stat(follow_symlinks=False)
    receipt = load_object(qualification_path, label="local finalizer qualification")
    execution_path = contract_paths(repository)["execution"]
    execution = load_object(execution_path, label="local finalizer execution contract")
    runtime = execution.get("runtime")
    base_packages = (
        runtime.get("local_finalizer_base_packages") if isinstance(runtime, dict) else None
    )
    packages = receipt.get("dependency_package_manifest")
    base_dependency_tree = receipt.get("interpreter_dependency_tree")
    evaluator_dependency_tree = receipt.get("dependency_tree")
    sources = receipt.get("source_sha256s")
    if (
        qualification_path.is_symlink()
        or not stat.S_ISREG(metadata.st_mode)
        or metadata.st_nlink != 1
        or stat.S_IMODE(metadata.st_mode) != 0o600
        or receipt.get("schema_version") != "0.1.0"
        or receipt.get("qualification_id") != "QUAL-T09-PILOT-V6-LOCAL-FINALIZER-0001"
        or receipt.get("plan_id") != PLAN_ID
        or receipt.get("package_commit") != package_commit
        or receipt.get("python_version") != "3.11.14"
        or receipt.get("execution_contract_sha256") != file_sha256(execution_path)
        or not isinstance(base_packages, list)
        or not base_packages
        or base_packages != sorted(base_packages)
        or len(base_packages) != len(set(base_packages))
        or receipt.get("interpreter_dependency_manifest") != base_packages
        or receipt.get("interpreter_dependency_manifest_sha256") != canonical_sha256(base_packages)
        or not _valid_retained_dependency_tree(base_dependency_tree)
        or receipt.get("interpreter_dependency_tree_sha256")
        != canonical_sha256(base_dependency_tree)
        or packages != expected_evaluator_packages(repository)
        or receipt.get("dependency_package_manifest_sha256") != canonical_sha256(packages)
        or not _valid_retained_dependency_tree(evaluator_dependency_tree)
        or receipt.get("dependency_tree_sha256") != canonical_sha256(evaluator_dependency_tree)
        or receipt.get("evaluator_contract_sha256")
        != file_sha256(contract_paths(repository)["evaluator"])
        or receipt.get("dataset_sha256") != PINNED_DATASET_SHA256
        or receipt.get("real_evidence_regression_sha256")
        != file_sha256(contract_paths(repository)["real_regression"])
        or receipt.get("real_evidence_regression_passed") is not True
        or receipt.get("network_policy") != "socket-construction-denied"
        or receipt.get("model_requests") != 0
        or receipt.get("browser_actions") != 0
        or not isinstance(sources, dict)
        or sources.get("finalizer")
        != git_file_sha256(repository, package_commit, FINALIZER_RELATIVE_PATH)
        or sources.get("projection")
        != git_file_sha256(repository, package_commit, FINALIZER_PROJECTION_RELATIVE_PATH)
        or sources.get("qualification")
        != file_sha256(repository / LOCAL_FINALIZER_QUALIFICATION_RELATIVE_PATH)
    ):
        raise T09HostError("local finalizer qualification binding drifted")
    interpreter_value = receipt.get("interpreter")
    interpreter_site_value = receipt.get("interpreter_site_packages")
    site_value = receipt.get("dependency_site_packages")
    evaluator_root_value = receipt.get("evaluator_root")
    dataset_value = receipt.get("dataset")
    interpreter_sha256 = receipt.get("interpreter_sha256")
    launcher_type = receipt.get("interpreter_launcher_type")
    launcher_mode = receipt.get("interpreter_launcher_mode")
    launcher_link_target = receipt.get("interpreter_launcher_link_target")
    resolved_target_value = receipt.get("interpreter_resolved_target")
    resolved_target_sha256 = receipt.get("interpreter_resolved_target_sha256")
    if (
        not isinstance(interpreter_value, str)
        or not Path(interpreter_value).is_absolute()
        or not isinstance(interpreter_site_value, str)
        or not Path(interpreter_site_value).is_absolute()
        or not isinstance(site_value, str)
        or not Path(site_value).is_absolute()
        or not isinstance(interpreter_sha256, str)
        or _HEX64.fullmatch(interpreter_sha256) is None
        or launcher_type not in {"regular", "symlink"}
        or not isinstance(launcher_mode, str)
        or re.fullmatch(r"0[0-7]{3}", launcher_mode) is None
        or (launcher_type == "regular" and launcher_link_target is not None)
        or (
            launcher_type == "symlink"
            and (not isinstance(launcher_link_target, str) or not launcher_link_target)
        )
        or not isinstance(resolved_target_value, str)
        or not Path(resolved_target_value).is_absolute()
        or not isinstance(resolved_target_sha256, str)
        or _HEX64.fullmatch(resolved_target_sha256) is None
        or not isinstance(evaluator_root_value, str)
        or not Path(evaluator_root_value).is_absolute()
        or not isinstance(dataset_value, str)
        or not Path(dataset_value).is_absolute()
    ):
        raise T09HostError("local finalizer absolute runtime identity is malformed")
    if require_local_runtime:
        interpreter = Path(interpreter_value)
        observed_interpreter_identity = local_interpreter_launcher_identity(interpreter)
        interpreter_site_packages = Path(interpreter_site_value).resolve(strict=True)
        site_packages = Path(site_value).resolve(strict=True)
        qualified_evaluator_root = Path(evaluator_root_value).resolve(strict=True)
        qualified_dataset = Path(dataset_value).resolve(strict=True)
        if (
            observed_interpreter_identity
            != {
                "interpreter": interpreter_value,
                "interpreter_sha256": interpreter_sha256,
                "interpreter_launcher_type": launcher_type,
                "interpreter_launcher_mode": launcher_mode,
                "interpreter_launcher_link_target": launcher_link_target,
                "interpreter_resolved_target": resolved_target_value,
                "interpreter_resolved_target_sha256": resolved_target_sha256,
            }
            or interpreter_site_packages.as_posix() != interpreter_site_value
            or site_packages.as_posix() != site_value
            or interpreter_site_packages.is_symlink()
            or not interpreter_site_packages.is_dir()
            or site_packages.is_symlink()
            or not site_packages.is_dir()
            or evaluator_root is None
            or dataset is None
            or evaluator_root.resolve(strict=True) != qualified_evaluator_root
            or dataset.resolve(strict=True) != qualified_dataset
            or file_sha256(qualified_dataset) != PINNED_DATASET_SHA256
        ):
            raise T09HostError("qualified local finalizer runtime is unavailable")
        evaluator_contract = load_object(
            contract_paths(repository)["evaluator"], label="evaluator contract"
        )
        identity = evaluator_contract.get("identity")
        evaluator_files = identity.get("files") if isinstance(identity, dict) else None
        observed_files: list[dict[str, str]] = []
        if not isinstance(evaluator_files, list):
            raise T09HostError("qualified local evaluator source inventory is unavailable")
        for raw in evaluator_files:
            if not isinstance(raw, dict):
                raise T09HostError("qualified local evaluator source binding is malformed")
            source_path = raw.get("path")
            expected_sha256 = raw.get("sha256")
            prefix = "evaluation/fanout/"
            if (
                not isinstance(source_path, str)
                or not source_path.startswith(prefix)
                or not isinstance(expected_sha256, str)
            ):
                raise T09HostError("qualified local evaluator source identity is malformed")
            source = (qualified_evaluator_root / source_path.removeprefix(prefix)).resolve(
                strict=True
            )
            try:
                source.relative_to(qualified_evaluator_root)
            except ValueError:
                raise T09HostError("qualified local evaluator source escaped its root") from None
            if source.is_symlink() or file_sha256(source) != expected_sha256:
                raise T09HostError("qualified local evaluator source bytes changed")
            observed_files.append({"path": source_path, "sha256": expected_sha256})
        if receipt.get("evaluator_files") != observed_files or receipt.get(
            "evaluator_files_sha256"
        ) != canonical_sha256(observed_files):
            raise T09HostError("qualified local evaluator source manifest changed")
        probe = subprocess.run(
            [
                interpreter.as_posix(),
                "-I",
                "-c",
                (
                    "import importlib.metadata,json,re,sys;"
                    "p=sys.argv[1];"
                    "r=sorted((re.sub(r'[-_.]+','-',d.metadata['Name']).lower()+'=='+d.version) "
                    "for d in importlib.metadata.distributions(path=[p]));"
                    "print(json.dumps(r,separators=(',',':')))"
                ),
                site_packages.as_posix(),
            ],
            env=safe_environment(),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            check=False,
            timeout=60,
        )
        try:
            realized: object = json.loads(probe.stdout)
        except json.JSONDecodeError as exc:
            raise T09HostError("local evaluator package probe is malformed") from exc
        if probe.returncode != 0 or realized != packages:
            raise T09HostError("qualified local evaluator packages changed")
        base_probe = subprocess.run(
            [
                interpreter.as_posix(),
                "-I",
                "-c",
                (
                    "import importlib.metadata,json,re,sysconfig;"
                    "p=sysconfig.get_paths()['purelib'];"
                    "r=sorted((re.sub(r'[-_.]+','-',d.metadata['Name']).lower()+'=='+d.version) "
                    "for d in importlib.metadata.distributions(path=[p]));"
                    "print(json.dumps({'site_packages':p,'packages':r},separators=(',',':')))"
                ),
            ],
            env=safe_environment(),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            check=False,
            timeout=60,
        )
        try:
            realized_base: object = json.loads(base_probe.stdout)
        except json.JSONDecodeError as exc:
            raise T09HostError("local finalizer base-package probe is malformed") from exc
        if base_probe.returncode != 0 or realized_base != {
            "site_packages": interpreter_site_value,
            "packages": base_packages,
        }:
            raise T09HostError("qualified local finalizer base packages changed")
        observed_base_tree = local_dependency_tree_inventory(
            interpreter_site_packages,
            label="qualified local finalizer base dependency tree",
        )
        observed_evaluator_tree = local_dependency_tree_inventory(
            site_packages,
            label="qualified local evaluator dependency tree",
        )
        if (
            observed_base_tree != base_dependency_tree
            or canonical_sha256(observed_base_tree)
            != receipt.get("interpreter_dependency_tree_sha256")
            or observed_evaluator_tree != evaluator_dependency_tree
            or canonical_sha256(observed_evaluator_tree) != receipt.get("dependency_tree_sha256")
        ):
            raise T09HostError("qualified local dependency bytes changed")
    return receipt


def _schema_errors(document: object, schema: dict[str, Any]) -> list[str]:
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    return sorted(
        f"{'/'.join(str(part) for part in error.absolute_path) or '$'}: {error.message}"
        for error in validator.iter_errors(document)
    )


def validate_finalized_attempt(
    *,
    repository: Path,
    finalized_root: Path,
    run_id: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, object], list[dict[str, object]]]:
    """Independently schema-check downstream output before frozen-state selection."""

    outcome = load_object(finalized_root / "attempt-outcome.json", label="attempt outcome")
    evidence = load_object(finalized_root / "evidence-index.json", label="evidence index")
    semantic_projection = load_object(
        finalized_root / "semantic-projection.json", label="attempt semantic projection"
    )
    score_schema = load_object(
        repository / "schemas/t09-sira-pilot-score.schema.json", label="score schema"
    )
    evidence_schema = load_object(
        repository / "schemas/t09-sira-pilot-evidence.schema.json", label="evidence schema"
    )
    properties = evidence_schema.get("properties")
    if not isinstance(properties, dict):
        raise T09HostError("evidence schema properties are unavailable")
    properties["outcome"] = score_schema
    errors = [*_schema_errors(outcome, score_schema), *_schema_errors(evidence, evidence_schema)]
    identity = evidence.get("identity")
    if (
        errors
        or evidence.get("outcome") != outcome
        or semantic_projection != scientific_attempt_projection(evidence)
        or not isinstance(identity, dict)
        or identity.get("run_id") != run_id
    ):
        raise T09HostError("finalized attempt failed its independent schema/identity gate")
    files: list[dict[str, object]] = []
    total = 0
    for path in sorted(finalized_root.rglob("*")):
        if not path.is_file() or path.is_symlink() or path.name == "finalization-complete.json":
            continue
        size = path.stat().st_size
        total += size
        if total > MAX_ATTEMPT_OUTPUT_BYTES:
            raise T09HostError("finalized attempt exceeds its bounded output surface")
        files.append(
            {
                "path": path.relative_to(finalized_root).as_posix(),
                "bytes": size,
                "sha256": file_sha256(path),
            }
        )
    return outcome, evidence, semantic_projection, files


def validate_selected_finalization(
    *,
    repository: Path,
    artifact_root: Path,
    contract: Any,
    run_id: str,
    package_commit: str,
    selection: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Reconstruct a selected derived result from immutable raw and output bytes."""

    expected_keys = {
        "finalizer_execution_mode",
        "finalizer_runtime_qualification_sha256",
        "finalizer_source_sha256",
        "finalizer_projection_source_sha256",
        "finalizer_commit",
        "finalizer_dependency_manifest_sha256",
        "evaluator_contract_sha256",
        "interpreter",
        "interpreter_sha256",
        "semantic_projection_sha256",
        "finalized_output_root",
        "finalization_complete_sha256",
    }
    relative = selection.get("finalized_output_root")
    if set(selection) != expected_keys or not isinstance(relative, str):
        raise T09HostError("selected finalization closure is malformed")
    execution_mode_value = selection.get("finalizer_execution_mode")
    execution_mode = execution_mode_value if isinstance(execution_mode_value, str) else ""
    expected_network = {
        "qualified-image": "none",
        "qualified-local": "socket-construction-denied",
    }.get(execution_mode)
    if expected_network is None:
        raise T09HostError("selected finalization execution mode is invalid")
    finalized_root = (artifact_root / relative).resolve(strict=True)
    try:
        finalized_root.relative_to(artifact_root)
    except ValueError:
        raise T09HostError("selected finalization escaped the artifact root") from None
    attempt = contract.attempt(run_id)
    if finalized_root.parent != (artifact_root / attempt.finalized_output_root).resolve(
        strict=True
    ):
        raise T09HostError("selected finalization is outside its condition-owned derived root")
    attempt_root = (artifact_root / attempt.output_root).resolve(strict=True)
    raw_root = (artifact_root / attempt.raw_output_root).resolve(strict=True)
    raw_manifest, raw_receipt = validate_raw_attempt_seal(
        attempt_root=attempt_root,
        raw_root=raw_root,
        run_id=run_id,
        package_commit=package_commit,
    )
    outcome, evidence, semantic_projection, output_files = validate_finalized_attempt(
        repository=repository,
        finalized_root=finalized_root,
        run_id=run_id,
    )
    completion_path = finalized_root / "finalization-complete.json"
    metadata = completion_path.stat(follow_symlinks=False)
    completion = load_object(completion_path, label="selected finalization completion")
    closure = completion.get("finalizer_closure")
    expected_closure_fields = {
        "finalizer_execution_mode",
        "finalizer_runtime_qualification_sha256",
        "finalizer_commit",
        "finalizer_source_sha256",
        "finalizer_projection_source_sha256",
        "scientific_package_commit",
        "pilot_library_sha256",
        "interpreter",
        "interpreter_sha256",
        "interpreter_dependency_manifest_sha256",
        "replacement_image_id",
        "execution_contract_sha256",
        "command_manifests_sha256",
        "dataset_contract_sha256",
        "evaluator_contract_sha256",
        "score_schema_sha256",
        "evidence_schema_sha256",
        "evaluator_overlay_entries_sha256",
        "evaluator_overlay_packages_sha256",
    }
    if (
        completion_path.is_symlink()
        or not stat.S_ISREG(metadata.st_mode)
        or metadata.st_nlink != 1
        or stat.S_IMODE(metadata.st_mode) != 0o600
        or selection.get("finalization_complete_sha256") != file_sha256(completion_path)
        or completion.get("schema_version") != "0.1.0"
        or completion.get("plan_id") != PLAN_ID
        or completion.get("host_run_id") != HOST_RUN_ID
        or completion.get("run_id") != run_id
        or completion.get("raw_manifest_sha256_before")
        != file_sha256(attempt_root / "raw-attempt-manifest.json")
        or completion.get("raw_manifest_sha256_after")
        != file_sha256(attempt_root / "raw-attempt-manifest.json")
        or completion.get("raw_receipt_sha256")
        != file_sha256(attempt_root / "raw-attempt-complete.json")
        or completion.get("raw_manifest_payload_sha256") != canonical_sha256(raw_manifest)
        or completion.get("raw_receipt_payload_sha256") != canonical_sha256(raw_receipt)
        or completion.get("output_files") != output_files
        or completion.get("output_files_sha256") != canonical_sha256(output_files)
        or completion.get("outcome_sha256") != file_sha256(finalized_root / "attempt-outcome.json")
        or completion.get("evidence_index_sha256")
        != file_sha256(finalized_root / "evidence-index.json")
        or completion.get("semantic_projection_file_sha256")
        != file_sha256(finalized_root / "semantic-projection.json")
        or completion.get("semantic_projection_sha256") != canonical_sha256(semantic_projection)
        or not isinstance(closure, dict)
        or set(closure) != expected_closure_fields
        or closure.get("scientific_package_commit") != package_commit
        or completion.get("finalizer_dependency_manifest_sha256") != canonical_sha256(closure)
        or selection.get("finalizer_dependency_manifest_sha256") != canonical_sha256(closure)
        or selection.get("finalizer_execution_mode") != closure.get("finalizer_execution_mode")
        or selection.get("finalizer_runtime_qualification_sha256")
        != closure.get("finalizer_runtime_qualification_sha256")
        or selection.get("finalizer_source_sha256") != closure.get("finalizer_source_sha256")
        or selection.get("finalizer_projection_source_sha256")
        != closure.get("finalizer_projection_source_sha256")
        or selection.get("finalizer_commit") != closure.get("finalizer_commit")
        or selection.get("evaluator_contract_sha256") != closure.get("evaluator_contract_sha256")
        or selection.get("interpreter") != closure.get("interpreter")
        or selection.get("interpreter_sha256") != closure.get("interpreter_sha256")
        or selection.get("semantic_projection_sha256") != canonical_sha256(semantic_projection)
        or completion.get("network") != expected_network
        or completion.get("additional_model_calls") != 0
        or completion.get("additional_browser_actions") != 0
        or completion.get("raw_source_mutated") is not False
        or completion.get("output_schema_valid") is not True
    ):
        raise T09HostError("selected finalization no longer reconstructs from exact bytes")
    return outcome, evidence


def finalize_attempt(args: argparse.Namespace) -> dict[str, object]:
    """Run one pure network-none finalizer, then select it from frozen supervisor code."""

    repository = args.repository.resolve(strict=True)
    artifact_root = args.artifact_root.resolve(strict=True)
    source_sha256, projection_source_sha256, projection_module = validate_finalizer_source(
        repository=repository,
        package_commit=args.package_commit,
        finalizer_commit=args.finalizer_commit,
        source=args.finalizer_source,
        projection_source=args.finalizer_projection_source,
    )
    verify_package(
        repository,
        args.package_commit,
        current_commit=args.finalizer_commit,
    )
    local_mode = args.finalizer_execution_mode == "qualified-local"
    if local_mode != (
        args.local_finalizer_qualification is not None
        and args.local_evaluator_root is not None
        and args.local_dataset is not None
    ):
        raise T09HostError("local finalizer arguments are incomplete or supplied to image mode")
    frozen_manifest, frozen_manifest_sha256 = load_frozen_run_manifest(
        artifact_root,
        repository=repository,
        package_commit=args.package_commit,
        require_image=not local_mode,
    )
    image_id = cast(str, frozen_manifest["replacement_image_id"])
    paths = contract_paths(repository)
    contract = load_execution_contract(
        paths["execution"], expected_sha256=file_sha256(paths["execution"])
    )
    command_document = load_object(paths["commands"], label="command manifest set")
    manifest = manifest_for_run(command_document, args.run_id)
    attempt = contract.attempt(args.run_id)
    attempt_root = (artifact_root / manifest_output_root(manifest)).resolve(strict=True)
    raw_root = (artifact_root / attempt.raw_output_root).resolve(strict=True)
    raw_manifest, raw_receipt = validate_raw_attempt_seal(
        attempt_root=attempt_root,
        raw_root=raw_root,
        run_id=args.run_id,
        package_commit=args.package_commit,
    )
    raw_manifest_sha256_before = file_sha256(attempt_root / "raw-attempt-manifest.json")
    raw_receipt_sha256_before = file_sha256(attempt_root / "raw-attempt-complete.json")
    state = _runtime_budget_state(artifact_root)
    raw_complete = state.get("raw_attempts_complete")
    if not isinstance(raw_complete, list) or args.run_id not in raw_complete:
        raise T09HostError("frozen supervisor has not accepted the raw attempt seal")
    require_attempt_export_acknowledgement(
        artifact_root,
        run_id=args.run_id,
        package_commit=args.package_commit,
    )
    finalization_log_base = attempt_root / "finalizer-invocations"
    finalization_log_base.mkdir(mode=0o700, exist_ok=True)
    existing = sorted(path for path in finalization_log_base.iterdir() if path.is_dir())
    expected_names = [f"invocation-{index:04d}" for index in range(1, len(existing) + 1)]
    if [path.name for path in existing] != expected_names:
        raise T09HostError("downstream finalizer invocation history is not contiguous")
    invocation = len(existing) + 1
    invocation_log = finalization_log_base / f"invocation-{invocation:04d}"
    invocation_log.mkdir(mode=0o700, exist_ok=False)
    local_qualification: dict[str, Any] | None = None
    if local_mode:
        assert args.local_finalizer_qualification is not None
        local_qualification = validate_local_finalizer_qualification(
            args.local_finalizer_qualification,
            repository=repository,
            package_commit=args.package_commit,
            require_local_runtime=True,
            evaluator_root=args.local_evaluator_root,
            dataset=args.local_dataset,
        )
        retained_qualification_path = artifact_root / "pilot-v6/local-finalizer-qualification.json"
        if load_object(
            retained_qualification_path, label="retained local qualification"
        ) != local_qualification or file_sha256(retained_qualification_path) != frozen_manifest.get(
            "local_finalizer_qualification_sha256"
        ):
            raise T09HostError("local finalizer qualification differs from the frozen run")
        local_evaluator_tree = cast(dict[str, Any], local_qualification["dependency_tree"])
        overlay_revalidation = {
            "overlay_manifest_sha256": file_sha256(args.local_finalizer_qualification),
            "overlay_entries_sha256": local_evaluator_tree["entries_sha256"],
            "overlay_packages_sha256": local_qualification["dependency_package_manifest_sha256"],
            "packages_recomputed": True,
            "dependency_bytes_recomputed": True,
            "interpreter_dependency_tree_sha256": local_qualification[
                "interpreter_dependency_tree_sha256"
            ],
            "evaluator_dependency_tree_sha256": local_qualification["dependency_tree_sha256"],
            "local_runtime_qualification_sha256": file_sha256(args.local_finalizer_qualification),
        }
    else:
        overlay_revalidation = validate_evaluator_overlay_binding(
            artifact_root=artifact_root,
            repository=repository,
            overlay=args.evaluator_overlay.resolve(strict=True),
            prefix=docker_prefix(),
            image_id=image_id,
            frozen_manifest=frozen_manifest,
            verify_packages=True,
        )
    overlay_path = invocation_log / "evaluator-overlay-revalidation.json"
    write_exclusive(overlay_path, overlay_revalidation)
    projected_environment: dict[str, str] = {}
    if local_mode:
        assert local_qualification is not None
        assert args.local_finalizer_qualification is not None
        finalizer, projected_environment, finalized_root, closure = local_evaluator_invocation(
            args=args,
            manifest=manifest,
            frozen_manifest=frozen_manifest,
            frozen_run_manifest_sha256=frozen_manifest_sha256,
            finalizer_commit=args.finalizer_commit,
            finalizer_source=args.finalizer_source,
            finalizer_source_sha256=source_sha256,
            finalizer_projection_source_sha256=projection_source_sha256,
            finalizer_projection=projection_module,
            invocation=invocation,
            evaluator_revalidation_path=overlay_path,
            local_qualification_path=args.local_finalizer_qualification.resolve(strict=True),
            local_qualification=local_qualification,
        )
    else:
        finalizer, finalized_root, closure = evaluator_argv(
            args=args,
            manifest=manifest,
            attempt_root=attempt_root,
            cleanup_receipt=raw_root / "host-cleanup-receipt.json",
            image_id=image_id,
            frozen_run_manifest_sha256=frozen_manifest_sha256,
            finalizer_commit=args.finalizer_commit,
            finalizer_source=args.finalizer_source,
            finalizer_source_sha256=source_sha256,
            finalizer_projection_source_sha256=projection_source_sha256,
            finalizer_projection=projection_module,
            invocation=invocation,
            evaluator_revalidation_path=overlay_path,
        )
    write_exclusive(
        invocation_log / "command.json",
        {
            "schema_version": "0.1.0",
            "run_id": args.run_id,
            "argv": finalizer,
            "argv_sha256": canonical_sha256(finalizer),
            "network": "socket-construction-denied" if local_mode else "none",
            "raw_mount": "readonly",
            "finalizer_closure": closure,
            "finalizer_dependency_manifest_sha256": canonical_sha256(closure),
        },
    )
    remaining = (
        float(FINALIZER_INVOCATION_TIMEOUT_SECONDS)
        if local_mode
        else scientific_seconds_remaining(
            artifact_root, reserve_seconds=PROVIDER_CLOSEOUT_RESERVE_SECONDS
        )
    )
    if remaining <= 1:
        raise T09HostError("campaign has no downstream finalization time before cleanup reserve")
    stdout_path = invocation_log / "stdout"
    stderr_path = invocation_log / "stderr"
    with stdout_path.open("xb") as stdout, stderr_path.open("xb") as stderr:
        result = subprocess.run(
            finalizer,
            env={**safe_environment(), **projected_environment},
            stdin=subprocess.DEVNULL,
            stdout=stdout,
            stderr=stderr,
            check=False,
            timeout=min(FINALIZER_INVOCATION_TIMEOUT_SECONDS, max(1, int(remaining))),
        )
    if result.returncode != 0:
        write_exclusive(
            invocation_log / "failure.json",
            {
                "schema_version": "0.1.0",
                "plan_id": PLAN_ID,
                "run_id": args.run_id,
                "failure_category": "downstream-finalizer-nonzero",
                "returncode": result.returncode,
                "raw_manifest_sha256": file_sha256(attempt_root / "raw-attempt-manifest.json"),
                "raw_receipt_sha256": file_sha256(attempt_root / "raw-attempt-complete.json"),
                "condition_retry_permitted": False,
                "campaign_may_continue_after_verified-raw": True,
            },
        )
        raise T09HostError("downstream finalizer failed; immutable raw attempt remains accepted")
    outcome, _evidence, semantic_projection, output_files = validate_finalized_attempt(
        repository=repository,
        finalized_root=finalized_root,
        run_id=args.run_id,
    )
    retained_raw_manifest, retained_raw_receipt = validate_raw_attempt_seal(
        attempt_root=attempt_root,
        raw_root=raw_root,
        run_id=args.run_id,
        package_commit=args.package_commit,
    )
    raw_manifest_sha256_after = file_sha256(attempt_root / "raw-attempt-manifest.json")
    raw_receipt_sha256_after = file_sha256(attempt_root / "raw-attempt-complete.json")
    if (
        retained_raw_manifest != raw_manifest
        or retained_raw_receipt != raw_receipt
        or raw_manifest_sha256_after != raw_manifest_sha256_before
        or raw_receipt_sha256_after != raw_receipt_sha256_before
    ):
        raise T09HostError("immutable raw attempt changed during finalization")
    completion_path = finalized_root / "finalization-complete.json"
    completion = projection_module.build_completion_projection(
        plan_id=PLAN_ID,
        host_run_id=HOST_RUN_ID,
        run_id=args.run_id,
        raw_manifest_sha256_before=raw_manifest_sha256_before,
        raw_manifest_sha256_after=raw_manifest_sha256_after,
        raw_receipt_sha256=raw_receipt_sha256_after,
        raw_manifest_payload_sha256=canonical_sha256(raw_manifest),
        raw_receipt_payload_sha256=canonical_sha256(raw_receipt),
        output_files=output_files,
        output_files_sha256=canonical_sha256(output_files),
        outcome_sha256=file_sha256(finalized_root / "attempt-outcome.json"),
        evidence_index_sha256=file_sha256(finalized_root / "evidence-index.json"),
        semantic_projection_file_sha256=file_sha256(finalized_root / "semantic-projection.json"),
        semantic_projection_sha256=canonical_sha256(semantic_projection),
        finalizer_closure=closure,
        finalizer_dependency_manifest_sha256=canonical_sha256(closure),
        network="socket-construction-denied" if local_mode else "none",
    )
    expected_completion = {
        "schema_version": "0.1.0",
        "plan_id": PLAN_ID,
        "host_run_id": HOST_RUN_ID,
        "run_id": args.run_id,
        "raw_manifest_sha256_before": raw_manifest_sha256_before,
        "raw_manifest_sha256_after": raw_manifest_sha256_after,
        "raw_receipt_sha256": raw_receipt_sha256_after,
        "raw_manifest_payload_sha256": canonical_sha256(raw_manifest),
        "raw_receipt_payload_sha256": canonical_sha256(raw_receipt),
        "output_files": output_files,
        "output_files_sha256": canonical_sha256(output_files),
        "outcome_sha256": file_sha256(finalized_root / "attempt-outcome.json"),
        "evidence_index_sha256": file_sha256(finalized_root / "evidence-index.json"),
        "semantic_projection_file_sha256": file_sha256(finalized_root / "semantic-projection.json"),
        "semantic_projection_sha256": canonical_sha256(semantic_projection),
        "finalizer_closure": closure,
        "finalizer_dependency_manifest_sha256": canonical_sha256(closure),
        "interpreter": closure["interpreter"],
        "interpreter_sha256": closure["interpreter_sha256"],
        "network": "socket-construction-denied" if local_mode else "none",
        "additional_model_calls": 0,
        "additional_browser_actions": 0,
        "raw_source_mutated": False,
        "output_schema_valid": True,
    }
    if completion != expected_completion:
        raise T09HostError("downstream completion projection exceeded its pure contract")
    write_exclusive(completion_path, completion)
    mark_attempt_completed(
        artifact_root / "pilot-v6/pilot-state.json",
        execution_contract_sha256=contract.sha256,
        run_id=args.run_id,
        finalizer_execution_mode=closure["finalizer_execution_mode"],
        finalizer_runtime_qualification_sha256=closure["finalizer_runtime_qualification_sha256"],
        finalizer_source_sha256=source_sha256,
        finalizer_projection_source_sha256=projection_source_sha256,
        finalizer_commit=args.finalizer_commit,
        finalizer_dependency_manifest_sha256=canonical_sha256(closure),
        evaluator_contract_sha256=contract.evaluator_contract_sha256,
        interpreter=closure["interpreter"],
        interpreter_sha256=closure["interpreter_sha256"],
        semantic_projection_sha256=canonical_sha256(semantic_projection),
        finalized_output_root=finalized_root.relative_to(artifact_root).as_posix(),
        finalization_complete_sha256=file_sha256(completion_path),
    )
    return {
        "run_id": args.run_id,
        "finalized_output_root": finalized_root.relative_to(artifact_root).as_posix(),
        "finalization_complete_sha256": file_sha256(completion_path),
        "valid_scored_attempt": outcome.get("valid_scored_attempt"),
        "evaluator_valid": outcome.get("evaluator_validity"),
        "evidence_index_sha256": file_sha256(finalized_root / "evidence-index.json"),
        "finalizer_closure_sha256": canonical_sha256(closure),
    }


def _severe_floor_or_ceiling(outcomes: list[dict[str, Any]]) -> bool:
    severe_floor = all(
        outcome.get("valid_scored_attempt") is True
        and outcome.get("task_completion") == "incomplete"
        and outcome.get("task_score") == 0.0
        for outcome in outcomes
    )
    severe_ceiling = all(
        outcome.get("valid_scored_attempt") is True
        and outcome.get("task_completion") == "completed"
        and outcome.get("task_score") == 1.0
        for outcome in outcomes
    )
    return severe_floor or severe_ceiling


def first_pair_checkpoint(args: argparse.Namespace) -> dict[str, object]:
    """Let only the frozen supervisor select evidence and open Task B."""

    repository = args.repository.resolve(strict=True)
    artifact_root = args.artifact_root.resolve(strict=True)
    verify_package(repository, args.package_commit)
    frozen_manifest, _frozen_manifest_sha256 = load_frozen_run_manifest(
        artifact_root,
        repository=repository,
        package_commit=args.package_commit,
    )
    paths = contract_paths(repository)
    contract = load_execution_contract(
        paths["execution"], expected_sha256=file_sha256(paths["execution"])
    )
    state_path = artifact_root / "pilot-v6/pilot-state.json"
    state = load_object(state_path, label="pilot state")
    validate_live_frozen_state_binding(state, frozen_manifest)
    checkpoint_path = artifact_root / "pilot-v6/first-pair-checkpoint.json"
    if checkpoint_path.exists():
        decision = load_object(checkpoint_path, label="first-pair checkpoint")
        checkpoint_binding = state.get("first_pair_checkpoint_binding")
        if (
            state.get("first_pair_decision_sha256") != canonical_sha256(decision)
            or not isinstance(checkpoint_binding, dict)
            or decision.get("first_pair_started_at_epoch")
            != checkpoint_binding.get("first_pair_started_at_epoch")
            or decision.get("second_pair_started_at_epoch")
            != checkpoint_binding.get("second_pair_started_at_epoch")
            or decision.get("decided_at_epoch") != checkpoint_binding.get("decided_at_epoch")
        ):
            raise T09HostError("retained first-pair checkpoint drifted from frozen state")
        return cast(dict[str, object], decision)
    if state.get("attempts_completed") != list(RUN_IDS[:2]):
        raise T09HostError("first-pair checkpoint requires both Task A finalizations")
    finalizations = state.get("attempt_finalizations")
    if not isinstance(finalizations, dict):
        raise T09HostError("first-pair finalization selections are unavailable")
    selected = [finalizations.get(run_id) for run_id in RUN_IDS[:2]]
    if not all(isinstance(item, dict) for item in selected):
        raise T09HostError("first-pair finalization selection is incomplete")
    closures = {
        canonical_sha256(
            {
                key: cast(dict[str, Any], item)[key]
                for key in (
                    "finalizer_execution_mode",
                    "finalizer_runtime_qualification_sha256",
                    "finalizer_source_sha256",
                    "finalizer_projection_source_sha256",
                    "finalizer_commit",
                    "finalizer_dependency_manifest_sha256",
                    "evaluator_contract_sha256",
                    "interpreter",
                    "interpreter_sha256",
                )
            }
        )
        for item in selected
    }
    if len(closures) != 1:
        raise T09HostError("Task A does not use one selected finalizer/interpreter closure")
    command_document = load_object(paths["commands"], label="command manifest set")
    pair_diffs = command_document.get("pair_diffs")
    pair_match_valid = (
        isinstance(pair_diffs, list)
        and len(pair_diffs) == 2
        and isinstance(pair_diffs[0], dict)
        and pair_diffs[0].get("valid") is True
    )
    evidence: list[dict[str, Any]] = []
    for run_id, selection in zip(RUN_IDS[:2], selected, strict=True):
        typed = cast(dict[str, Any], selection)
        _outcome, evidence_index = validate_selected_finalization(
            repository=repository,
            artifact_root=artifact_root,
            contract=contract,
            run_id=run_id,
            package_commit=args.package_commit,
            selection=typed,
        )
        evidence.append(evidence_index)
    require_prior_export_acknowledgements(
        artifact_root, next_attempt_index=2, package_commit=args.package_commit
    )
    outcomes = [cast(dict[str, Any], document["outcome"]) for document in evidence]
    usage = load_aggregate_usage(
        artifact_root / "pilot-v6/aggregate-budget.json", contract_sha256=contract.sha256
    )
    pair_started = state.get("first_pair_started_at_epoch")
    campaign_started = state.get("campaign_started_at_epoch", state.get("pilot_started_at_epoch"))
    owned_lambda_started = state.get("owned_lambda_started_at_epoch")
    prior_lambda_cost = state.get("prior_campaign_lambda_cost_usd")
    if not all(
        isinstance(value, (int, float)) and not isinstance(value, bool)
        for value in (pair_started, campaign_started, owned_lambda_started, prior_lambda_cost)
    ):
        raise T09HostError("first-pair timing origins are unavailable")
    assert isinstance(pair_started, (int, float))
    assert isinstance(campaign_started, (int, float))
    assert isinstance(owned_lambda_started, (int, float))
    assert isinstance(prior_lambda_cost, (int, float))
    now = time.time()
    pair_wall = now - float(pair_started)
    campaign_wall = now - float(campaign_started)
    owned_lambda_wall = now - float(owned_lambda_started)
    if min(pair_wall, campaign_wall, owned_lambda_wall) < 0:
        raise T09HostError("first-pair timing origin is in the future")
    lambda_cost = float(prior_lambda_cost) + (owned_lambda_wall * LAMBDA_HOURLY_PRICE_USD / 3600.0)
    actual_total = usage.cost_usd + lambda_cost
    decision = first_pair_decision(
        PairCheckpointInput(
            attempt_run_ids=(ATTEMPT_ORDER[0], ATTEMPT_ORDER[1]),
            valid_evidence=cast(
                tuple[bool, bool],
                tuple(outcome.get("valid_scored_attempt") is True for outcome in outcomes),
            ),
            evaluator_succeeded=cast(
                tuple[bool, bool],
                tuple(outcome.get("evaluator_validity") is True for outcome in outcomes),
            ),
            pair_match_valid=pair_match_valid,
            credential_issue=any(
                document.get("cleanup", {}).get("secret_removed") is not True
                for document in evidence
            ),
            cleanup_issue=any(
                document.get("cleanup", {}).get("browser_closed") is not True
                or document.get("cleanup", {}).get("container_removed") is not True
                for document in evidence
            ),
            severe_floor_or_ceiling_failure=_severe_floor_or_ceiling(outcomes),
            actual_usage=usage,
            actual_pair_wall_seconds=pair_wall,
            projected_aggregate_cost_usd=actual_total * 2.0,
            actual_lambda_cost_usd=lambda_cost,
            remaining_campaign_seconds=contract.campaign.remaining_seconds(
                billable_started_at=float(campaign_started), now=now
            ),
            next_attempt_hard_wall_seconds=contract.limits.max_condition_wall_seconds,
        )
    )
    decision = {
        **decision,
        "first_pair_started_at_epoch": float(pair_started),
        "second_pair_started_at_epoch": now
        if decision.get("decision") == "continue-to-task-b"
        else None,
        "decided_at_epoch": now,
    }
    write_exclusive(checkpoint_path, decision)
    record_first_pair_checkpoint(
        state_path,
        execution_contract_sha256=contract.sha256,
        decision=decision,
        decided_at_epoch=now,
    )
    return decision


def campaign_evidence_disposition(args: argparse.Namespace) -> dict[str, object]:
    """Seal the descriptive four-attempt result under one selected finalizer closure."""

    repository = args.repository.resolve(strict=True)
    artifact_root = args.artifact_root.resolve(strict=True)
    verify_package(repository, args.package_commit)
    frozen_manifest, frozen_manifest_sha256 = load_frozen_run_manifest(
        artifact_root,
        repository=repository,
        package_commit=args.package_commit,
        require_image=False,
    )
    paths = contract_paths(repository)
    contract = load_execution_contract(
        paths["execution"], expected_sha256=file_sha256(paths["execution"])
    )
    state = _runtime_budget_state(artifact_root)
    validate_live_frozen_state_binding(state, frozen_manifest)
    if (
        state.get("empirical_attempts_entered") != list(RUN_IDS)
        or state.get("raw_attempts_complete") != list(RUN_IDS)
        or state.get("attempts_completed") != list(RUN_IDS)
        or state.get("first_pair_decision") != "continue-to-task-b"
    ):
        raise T09HostError("campaign disposition requires the exact four-attempt prefix")
    require_prior_export_acknowledgements(
        artifact_root,
        next_attempt_index=len(RUN_IDS),
        package_commit=args.package_commit,
    )
    selected = state.get("attempt_finalizations")
    if not isinstance(selected, dict) or set(selected) != set(RUN_IDS):
        raise T09HostError("campaign disposition lacks four selected finalizations")
    closure_fields = (
        "finalizer_execution_mode",
        "finalizer_runtime_qualification_sha256",
        "finalizer_source_sha256",
        "finalizer_projection_source_sha256",
        "finalizer_commit",
        "finalizer_dependency_manifest_sha256",
        "evaluator_contract_sha256",
        "interpreter",
        "interpreter_sha256",
    )
    closures: dict[str, dict[str, object]] = {}
    attempts: list[dict[str, object]] = []
    for run_id in RUN_IDS:
        raw_selection = selected.get(run_id)
        if not isinstance(raw_selection, dict):
            raise T09HostError("campaign selected finalization is malformed")
        outcome, evidence = validate_selected_finalization(
            repository=repository,
            artifact_root=artifact_root,
            contract=contract,
            run_id=run_id,
            package_commit=args.package_commit,
            selection=raw_selection,
        )
        closure = {field: raw_selection.get(field) for field in closure_fields}
        closures[canonical_sha256(closure)] = closure
        identity = evidence.get("identity")
        timing = evidence.get("timing")
        attempt_binding = contract.attempt(run_id)
        provider = load_object(
            artifact_root / attempt_binding.raw_output_root / "provider-budget.json",
            label="campaign attempt provider budget",
        )
        if not isinstance(identity, dict) or not isinstance(timing, dict):
            raise T09HostError("campaign evidence identity or timing is malformed")
        attempts.append(
            {
                "run_id": run_id,
                "task_id": identity.get("task_id"),
                "pair_id": identity.get("pair_id"),
                "condition": identity.get("condition"),
                "task_completion": outcome.get("task_completion"),
                "answer_production": outcome.get("answer_production"),
                "evaluator_validity": outcome.get("evaluator_validity"),
                "valid_scored_attempt": outcome.get("valid_scored_attempt"),
                "task_score": outcome.get("task_score"),
                "invalid_infrastructure_attempt": outcome.get("invalid_infrastructure_attempt"),
                "condition_failure": outcome.get("condition_failure"),
                "timing": timing,
                "provider_usage": provider,
                "raw_manifest_sha256": file_sha256(
                    artifact_root / attempt_binding.output_root / "raw-attempt-manifest.json"
                ),
                "raw_receipt_sha256": file_sha256(
                    artifact_root / attempt_binding.output_root / "raw-attempt-complete.json"
                ),
                "finalization_complete_sha256": raw_selection.get("finalization_complete_sha256"),
            }
        )
    if len(closures) != 1:
        raise T09HostError("all four attempts must select one full finalizer closure")
    aggregate = load_aggregate_usage(
        artifact_root / "pilot-v6/aggregate-budget.json",
        contract_sha256=contract.sha256,
    )
    document: dict[str, object] = {
        "schema_version": "0.1.0",
        "record_id": "T09-PRAGMATIC-RETRY4-CAMPAIGN-EVIDENCE-0001",
        "plan_id": PLAN_ID,
        "host_run_id": HOST_RUN_ID,
        "experiment_id": "EXP-0001",
        "calibration_only": True,
        "scientific_result_claimed": False,
        "experiment_outcome_assigned": False,
        "frozen_run_manifest_sha256": frozen_manifest_sha256,
        "replacement_image_id": frozen_manifest["replacement_image_id"],
        "attempt_order": list(RUN_IDS),
        "attempts": attempts,
        "uniform_finalizer_closure": next(iter(closures.values())),
        "uniform_finalizer_closure_sha256": next(iter(closures)),
        "aggregate_provider_usage": {
            "cost_usd": aggregate.cost_usd,
            "input_tokens": aggregate.input_tokens,
            "cached_input_tokens": aggregate.cached_input_tokens,
            "output_tokens": aggregate.output_tokens,
            "total_tokens": aggregate.total_tokens,
            "model_call_attempts": aggregate.model_call_attempts,
            "browser_actions": aggregate.browser_actions,
        },
        "first_pair_decision": state.get("first_pair_decision"),
        "pair_matching": {"task_a": True, "task_b": True},
        "prior_v4_unpaired_attempt_excluded": True,
        "recorded_at": utc_now(),
    }
    destination = artifact_root / "pilot-v6/campaign-evidence-disposition.json"
    if destination.exists():
        retained = load_object(destination, label="campaign evidence disposition")
        retained.pop("recorded_at", None)
        expected = dict(document)
        expected.pop("recorded_at")
        if retained != expected:
            raise T09HostError("retained campaign disposition drifted")
    else:
        write_exclusive(destination, document)
    return document


def _attempt_export_archive_matches(
    archive: Path,
    *,
    export_manifest_path: Path,
    export_manifest: dict[str, object],
) -> bool:
    """Return whether a retained archive is the exact complete export."""

    if archive.is_symlink() or not archive.is_file():
        return False
    try:
        if not 0 < archive.stat().st_size <= MAX_ATTEMPT_EXPORT_BYTES:
            return False
        with tarfile.open(archive, "r:gz") as handle:
            members = handle.getmembers()
            if not 1 <= len(members) <= 2_048:
                return False
            by_name: dict[str, tarfile.TarInfo] = {}
            for member in members:
                relative = PurePosixPath(member.name)
                if (
                    not member.isfile()
                    or relative.is_absolute()
                    or ".." in relative.parts
                    or member.name in by_name
                    or member.size > MAX_ATTEMPT_OUTPUT_BYTES
                ):
                    return False
                by_name[member.name] = member
            expected = {"attempt-export-manifest.json"}
            manifest_member = by_name.get("attempt-export-manifest.json")
            if manifest_member is None or manifest_member.size > 2_097_152:
                return False
            manifest_stream = handle.extractfile(manifest_member)
            if (
                manifest_stream is None
                or manifest_stream.read() != export_manifest_path.read_bytes()
            ):
                return False
            files = export_manifest.get("files")
            if not isinstance(files, list):
                return False
            total = 0
            for raw in files:
                if not isinstance(raw, dict):
                    return False
                name = raw.get("path")
                size = raw.get("bytes")
                digest = raw.get("sha256")
                if (
                    not isinstance(name, str)
                    or type(size) is not int
                    or not isinstance(digest, str)
                    or _HEX64.fullmatch(digest) is None
                    or name not in by_name
                    or by_name[name].size != size
                ):
                    return False
                stream = handle.extractfile(by_name[name])
                if stream is None:
                    return False
                observed = hashlib.sha256()
                observed_size = 0
                while chunk := stream.read(1_048_576):
                    observed.update(chunk)
                    observed_size += len(chunk)
                    if observed_size > MAX_ATTEMPT_OUTPUT_BYTES:
                        return False
                if observed_size != size or observed.hexdigest() != digest:
                    return False
                expected.add(name)
                total += size
            return set(by_name) == expected and total == export_manifest.get("total_bytes")
    except (OSError, tarfile.TarError, EOFError):
        return False


def _quarantine_partial_attempt_export(archive: Path) -> Path:
    """Retain at most one bounded incomplete archive for this attempt."""

    quarantined = archive.with_name(f"{archive.name}.partial")
    if os.path.lexists(quarantined):
        raise T09HostError("attempt export already retains its one bounded partial archive")
    archive.rename(quarantined)
    descriptor = os.open(archive.parent, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    return quarantined


def _require_pilot_disk_headroom(artifact_root: Path, *, additional_bytes: int) -> int:
    """Reject a local write unless its full upper bound fits the hard disk cap."""

    if type(additional_bytes) is not int or additional_bytes < 0:
        raise T09HostError("attempt export disk reservation is invalid")
    current = tree_bytes(artifact_root)
    if current > MAX_PILOT_DISK_BYTES or additional_bytes > MAX_PILOT_DISK_BYTES - current:
        raise T09HostError("attempt export lacks aggregate pilot disk headroom")
    return current


class _BoundedArchiveWriter:
    """Write-through file adapter that cannot cross the archive byte ceiling."""

    def __init__(self, raw: BinaryIO) -> None:
        self.raw = raw

    def write(self, value: bytes) -> int:
        position = self.raw.tell()
        if position > MAX_ATTEMPT_EXPORT_BYTES or len(value) > MAX_ATTEMPT_EXPORT_BYTES - position:
            raise T09HostError("attempt export archive exceeded its write-time byte cap")
        if not value:
            return 0
        written = self.raw.write(value)
        if written is None or written <= 0:
            raise T09HostError("attempt export archive write made no progress")
        return written

    def tell(self) -> int:
        return self.raw.tell()

    def flush(self) -> None:
        self.raw.flush()


def _attempt_export_control_sources(
    artifact_root: Path,
    *,
    attempt_root: Path,
    run_id: str,
) -> dict[str, Path]:
    """Return the bounded control snapshot needed for offline finalization.

    The snapshot carries no condition-owned output into the control plane.  It
    retains the exact frozen runtime, source receipts, mutable state projection,
    prior off-host acknowledgements, and append-only selection/checkpoint records
    that existed when this raw attempt was exported.
    """

    snapshot_root = attempt_root / "attempt-export-control"
    snapshot_manifest_path = attempt_root / "attempt-export-control-manifest.json"
    if not snapshot_manifest_path.exists():
        if snapshot_root.exists() or snapshot_root.is_symlink():
            raise T09HostError("attempt export control snapshot is partial")
        relative_paths = list(ATTEMPT_EXPORT_REQUIRED_CONTROL_PATHS)
        frozen_for_export = load_object(
            artifact_root / "pilot-v6/frozen-run-manifest.json",
            label="attempt export frozen runtime",
        )
        transition_mode = frozen_for_export.get("preflight_transition_mode")
        if transition_mode == "replacement-launch":
            authority_root = artifact_root / "pilot-v6/slot2-authority"
            if authority_root.is_symlink() or not authority_root.is_dir():
                raise T09HostError("slot-2 attempt export lacks its authority root")
            relative_paths.extend(
                f"pilot-v6/slot2-authority/{relative}"
                for relative in _slot2_authority_relative_paths(authority_root)
            )
        elif transition_mode not in {None, "fresh"}:
            raise T09HostError("attempt export transition mode is unsupported")
        optional_roots = (
            artifact_root / "pilot-v6/received-export-acknowledgements",
            artifact_root / "pilot-v6/finalization-selections",
        )
        for root in optional_roots:
            if not root.exists():
                continue
            if root.is_symlink() or not root.is_dir():
                raise T09HostError("attempt export control root is unsafe")
            relative_paths.extend(
                path.relative_to(artifact_root).as_posix()
                for path in sorted(root.rglob("*"))
                if path.is_file()
            )
        checkpoint = artifact_root / "pilot-v6/first-pair-checkpoint.json"
        if checkpoint.exists():
            relative_paths.append(checkpoint.relative_to(artifact_root).as_posix())
        aggregate = artifact_root / "pilot-v6/aggregate-budget.json"
        if aggregate.exists():
            relative_paths.append(aggregate.relative_to(artifact_root).as_posix())
        snapshot_root.mkdir(mode=0o700, exist_ok=False)
        entries: list[dict[str, object]] = []
        for relative in sorted(set(relative_paths)):
            source = artifact_root / relative
            metadata = source.stat(follow_symlinks=False)
            if (
                source.is_symlink()
                or not stat.S_ISREG(metadata.st_mode)
                or metadata.st_nlink != 1
                or metadata.st_size > MAX_PRIVACY_JSON_BYTES
            ):
                raise T09HostError("attempt export control file is unsafe or oversized")
            try:
                source.resolve(strict=True).relative_to(artifact_root)
            except ValueError:
                raise T09HostError(
                    "attempt export control file escaped the artifact root"
                ) from None
            destination = snapshot_root / relative
            destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            with source.open("rb") as incoming, destination.open("xb") as outgoing:
                shutil.copyfileobj(incoming, outgoing, length=1_048_576)
                outgoing.flush()
                os.fsync(outgoing.fileno())
            os.chmod(destination, 0o600)
            entries.append(
                {
                    "path": f"control/{relative}",
                    "bytes": destination.stat().st_size,
                    "sha256": file_sha256(destination),
                }
            )
        write_exclusive(
            snapshot_manifest_path,
            {
                "schema_version": "0.1.0",
                "plan_id": PLAN_ID,
                "host_run_id": HOST_RUN_ID,
                "run_id": run_id,
                "files": entries,
                "files_sha256": canonical_sha256(entries),
            },
        )
    snapshot_manifest = load_object(
        snapshot_manifest_path,
        label="attempt export control snapshot manifest",
    )
    raw_entries = snapshot_manifest.get("files")
    if (
        snapshot_manifest.get("schema_version") != "0.1.0"
        or snapshot_manifest.get("plan_id") != PLAN_ID
        or snapshot_manifest.get("host_run_id") != HOST_RUN_ID
        or snapshot_manifest.get("run_id") != run_id
        or not isinstance(raw_entries, list)
        or snapshot_manifest.get("files_sha256") != canonical_sha256(raw_entries)
    ):
        raise T09HostError("attempt export control snapshot manifest drifted")
    snapshot_entries = cast(list[object], raw_entries)
    result: dict[str, Path] = {}
    for raw in snapshot_entries:
        if not isinstance(raw, dict):
            raise T09HostError("attempt export control snapshot record is malformed")
        archive_name = raw.get("path")
        size = raw.get("bytes")
        digest = raw.get("sha256")
        if not isinstance(archive_name, str) or not archive_name.startswith("control/"):
            raise T09HostError("attempt export control snapshot path is malformed")
        relative = archive_name.removeprefix("control/")
        source = snapshot_root / relative
        metadata = source.stat(follow_symlinks=False)
        if (
            source.is_symlink()
            or not stat.S_ISREG(metadata.st_mode)
            or metadata.st_nlink != 1
            or metadata.st_size != size
            or not isinstance(digest, str)
            or file_sha256(source) != digest
        ):
            raise T09HostError("attempt export control snapshot bytes drifted")
        result[archive_name] = source
    state = load_object(
        snapshot_root / "pilot-v6/pilot-state.json",
        label="export pilot-state snapshot",
    )
    raw_complete = state.get("raw_attempts_complete")
    expected_index = RUN_IDS.index(run_id)
    if not isinstance(raw_complete, list) or raw_complete[: expected_index + 1] != list(
        RUN_IDS[: expected_index + 1]
    ):
        raise T09HostError("attempt export control state lacks its exact raw prefix")
    result["attempt-export-control-manifest.json"] = snapshot_manifest_path
    return result


def export_attempt(args: argparse.Namespace, destination: BinaryIO) -> dict[str, object]:
    """Stream the authoritative immutable raw attempt before downstream finalization."""

    repository = args.repository.resolve(strict=True)
    artifact_root = args.artifact_root.resolve(strict=True)
    _require_pilot_disk_headroom(artifact_root, additional_bytes=0)
    command_document = load_object(
        contract_paths(repository)["commands"], label="command manifest set"
    )
    frozen_manifest, frozen_manifest_sha256 = load_frozen_run_manifest(
        artifact_root,
        repository=repository,
        package_commit=args.package_commit,
    )
    manifest = manifest_for_run(command_document, args.run_id)
    attempt_root = (artifact_root / manifest_output_root(manifest)).resolve(strict=True)
    try:
        attempt_root.relative_to(artifact_root)
    except ValueError:
        raise T09HostError("attempt export root escaped the pilot artifact root") from None
    owned = manifest.get("permitted_condition_owned")
    if not isinstance(owned, dict) or not isinstance(owned.get("raw_output_root"), str):
        raise T09HostError("attempt export lacks its exact raw root")
    raw_root = (artifact_root / cast(str, owned["raw_output_root"])).resolve(strict=True)
    if raw_root.parent != attempt_root:
        raise T09HostError("attempt raw export root drifted from the owned attempt")
    raw_manifest, raw_receipt = validate_raw_attempt_seal(
        attempt_root=attempt_root,
        raw_root=raw_root,
        run_id=args.run_id,
        package_commit=args.package_commit,
    )
    wall = load_object(raw_root / "attempt-wall.json", label="attempt wall")
    evidence_deadline_epoch = wall.get("evidence_handoff_deadline_epoch")
    if not isinstance(evidence_deadline_epoch, (int, float)) or isinstance(
        evidence_deadline_epoch, bool
    ):
        raise T09HostError("attempt export lacks its evidence handoff deadline")
    files: list[dict[str, object]] = []
    sources: dict[str, Path] = {}
    total = 0
    raw_files = raw_manifest.get("files")
    if not isinstance(raw_files, list):
        raise T09HostError("raw attempt manifest file set is malformed")
    for raw in cast(list[dict[str, object]], raw_files):
        relative = cast(str, raw["path"])
        size = cast(int, raw["bytes"])
        total += size
        archive_name = f"raw/{relative}"
        sources[archive_name] = raw_root / relative
        files.append({"path": archive_name, "bytes": size, "sha256": raw["sha256"]})
    for name in ("raw-attempt-manifest.json", "raw-attempt-complete.json"):
        path = attempt_root / name
        size = path.stat().st_size
        total += size
        sources[name] = path
        files.append({"path": name, "bytes": size, "sha256": file_sha256(path)})
    control_sources = _attempt_export_control_sources(
        artifact_root,
        attempt_root=attempt_root,
        run_id=args.run_id,
    )
    credential = validate_secret(args.secret_file.resolve(strict=True))
    control_secret_hits = secret_hits(attempt_root / "attempt-export-control", credential)
    credential = b""
    if control_secret_hits:
        raise T09HostError("attempt export control snapshot retained the exact credential")
    for archive_name, path in control_sources.items():
        size = path.stat().st_size
        total += size
        sources[archive_name] = path
        files.append({"path": archive_name, "bytes": size, "sha256": file_sha256(path)})
    if total > MAX_ATTEMPT_EXPORT_BYTES:
        raise T09HostError("attempt export exceeds its raw byte cap")
    export_manifest_path = attempt_root / "attempt-export-manifest.json"
    export_manifest: dict[str, object] = {
        "schema_version": "0.1.0",
        "plan_id": PLAN_ID,
        "host_run_id": HOST_RUN_ID,
        "run_id": args.run_id,
        "package_commit": args.package_commit,
        "frozen_run_manifest_id": frozen_manifest["manifest_id"],
        "frozen_run_manifest_sha256": frozen_manifest_sha256,
        "replacement_image_id": frozen_manifest["replacement_image_id"],
        "private_access_controlled": True,
        "public_release": "blocked-pending-review",
        "evidence_authority": "immutable-raw-attempt",
        "downstream_finalization_required_for_analysis": True,
        "files": files,
        "total_bytes": total,
        "actual_credential_scan_passed": True,
        "actual_credential_exposure_detected": raw_receipt.get(
            "actual_credential_exposure_detected"
        ),
        "credential_cleanup_integrity_failure": raw_receipt.get(
            "credential_cleanup_integrity_failure"
        ),
        "campaign_continuation_permitted": raw_receipt.get("credential_cleanup_clean") is True,
        "structural_privacy_scan_passed": raw_receipt.get("public_release_clearance") is True,
        "structural_privacy_findings": raw_receipt.get("structural_privacy_findings"),
        "exported_before_provider_termination": True,
    }
    if export_manifest_path.exists():
        if load_object(export_manifest_path, label="attempt export manifest") != export_manifest:
            raise T09HostError("retained attempt export manifest drifted")
    else:
        manifest_bytes = len(
            (json.dumps(export_manifest, allow_nan=False, indent=2, sort_keys=True) + "\n").encode()
        )
        _require_pilot_disk_headroom(artifact_root, additional_bytes=manifest_bytes)
        write_exclusive(export_manifest_path, export_manifest)
    remaining_attempt = float(evidence_deadline_epoch) - time.time()
    remaining_campaign_to_cutoff = (
        PROVIDER_TERMINATION_CUTOFF_SECONDS
        - (time.time() - float(_runtime_budget_state(artifact_root)["lambda_started_at_epoch"]))
        - PROVIDER_TERMINATION_HANDOFF_SECONDS
    )
    timeout = min(remaining_attempt, remaining_campaign_to_cutoff)
    if timeout <= 1:
        raise T09HostError("attempt evidence cannot export before provider termination cutoff")
    exports = artifact_root / "pilot-v6/attempt-exports"
    exports.mkdir(mode=0o700, exist_ok=True)
    archive = exports / f"{args.run_id}.tar.gz"
    with hard_deadline(timeout, message="attempt evidence export deadline exceeded"):
        if os.path.lexists(archive) and not _attempt_export_archive_matches(
            archive,
            export_manifest_path=export_manifest_path,
            export_manifest=export_manifest,
        ):
            # A rename adds no bytes, but a replacement is useful only when its
            # complete upper bound already fits.  Check before changing state.
            _require_pilot_disk_headroom(
                artifact_root,
                additional_bytes=MAX_ATTEMPT_EXPORT_BYTES,
            )
            _quarantine_partial_attempt_export(archive)
        if not archive.exists():
            _require_pilot_disk_headroom(
                artifact_root,
                additional_bytes=MAX_ATTEMPT_EXPORT_BYTES,
            )
            with archive.open("xb") as raw_archive:
                bounded_archive = _BoundedArchiveWriter(raw_archive)
                with tarfile.open(
                    fileobj=cast(BinaryIO, bounded_archive),
                    mode="w:gz",
                ) as handle:
                    for entry in files:
                        relative = str(entry["path"])
                        handle.add(sources[relative], arcname=relative, recursive=False)
                    handle.add(
                        export_manifest_path,
                        arcname="attempt-export-manifest.json",
                        recursive=False,
                    )
                bounded_archive.flush()
                os.fsync(raw_archive.fileno())
        _require_pilot_disk_headroom(artifact_root, additional_bytes=0)
        if not _attempt_export_archive_matches(
            archive,
            export_manifest_path=export_manifest_path,
            export_manifest=export_manifest,
        ):
            raise T09HostError("attempt export archive is incomplete after materialization")
        with archive.open("rb") as source:
            while chunk := source.read(1_048_576):
                offset = 0
                while offset < len(chunk):
                    written = destination.write(chunk[offset:])
                    if written is None or written <= 0:
                        raise T09HostError("attempt evidence export stream made no progress")
                    offset += written
        destination.flush()
    return {
        "run_id": args.run_id,
        "bytes": archive.stat().st_size,
        "sha256": file_sha256(archive),
        "manifest_sha256": file_sha256(export_manifest_path),
    }


def verify_attempt_export(args: argparse.Namespace) -> None:
    """Verify one directly streamed attempt archive before provider termination."""

    inbound = args.inbound_root.resolve(strict=True)
    archive = args.attempt_export.resolve(strict=True)
    expected_name = f"{args.run_id}.tar.gz"
    if archive.parent != inbound or archive.name != expected_name:
        raise T09HostError("attempt export is not at its exact inbound path")
    if archive.stat().st_size > MAX_ATTEMPT_EXPORT_BYTES:
        raise T09HostError("inbound attempt export exceeds its byte cap")
    with tarfile.open(archive, "r:gz") as handle:
        members = handle.getmembers()
        if not 1 <= len(members) <= 2_048:
            raise T09HostError("attempt export member count is invalid")
        by_name: dict[str, tarfile.TarInfo] = {}
        for member in members:
            relative = PurePosixPath(member.name)
            if (
                not member.isfile()
                or relative.is_absolute()
                or ".." in relative.parts
                or member.name in by_name
                or member.size > MAX_ATTEMPT_OUTPUT_BYTES
            ):
                raise T09HostError("attempt export contains an unsafe member")
            by_name[member.name] = member
        manifest_member = by_name.get("attempt-export-manifest.json")
        if manifest_member is None:
            raise T09HostError("attempt export manifest is absent")
        manifest_stream = handle.extractfile(manifest_member)
        if manifest_stream is None or manifest_member.size > 2_097_152:
            raise T09HostError("attempt export manifest is unreadable")
        try:
            manifest: object = json.loads(manifest_stream.read())
        except json.JSONDecodeError as exc:
            raise T09HostError("attempt export manifest is malformed") from exc
        if not isinstance(manifest, dict):
            raise T09HostError("attempt export manifest is not an object")
        files = manifest.get("files")
        if (
            manifest.get("schema_version") != "0.1.0"
            or manifest.get("plan_id") != PLAN_ID
            or manifest.get("host_run_id") != HOST_RUN_ID
            or manifest.get("run_id") != args.run_id
            or manifest.get("package_commit") != args.package_commit
            or manifest.get("frozen_run_manifest_id") != "RUN-MANIFEST-EXP0001-PILOT-V6-0004"
            or not isinstance(manifest.get("frozen_run_manifest_sha256"), str)
            or _HEX64.fullmatch(cast(str, manifest["frozen_run_manifest_sha256"])) is None
            or not isinstance(manifest.get("replacement_image_id"), str)
            or re.fullmatch(r"sha256:[a-f0-9]{64}", cast(str, manifest["replacement_image_id"]))
            is None
            or manifest.get("private_access_controlled") is not True
            or manifest.get("public_release") != "blocked-pending-review"
            or manifest.get("actual_credential_scan_passed") is not True
            or not isinstance(manifest.get("actual_credential_exposure_detected"), bool)
            or not isinstance(manifest.get("credential_cleanup_integrity_failure"), bool)
            or not isinstance(manifest.get("campaign_continuation_permitted"), bool)
            or not isinstance(manifest.get("structural_privacy_scan_passed"), bool)
            or not isinstance(manifest.get("structural_privacy_findings"), list)
            or manifest.get("exported_before_provider_termination") is not True
            or not isinstance(files, list)
        ):
            raise T09HostError("attempt export manifest contract drifted")
        expected_members = {"attempt-export-manifest.json"}
        total = 0
        for raw in files:
            if not isinstance(raw, dict):
                raise T09HostError("attempt export file record is malformed")
            name = raw.get("path")
            size = raw.get("bytes")
            digest = raw.get("sha256")
            if (
                not isinstance(name, str)
                or type(size) is not int
                or not isinstance(digest, str)
                or _HEX64.fullmatch(digest) is None
                or name not in by_name
                or by_name[name].size != size
            ):
                raise T09HostError("attempt export file identity drifted")
            stream = handle.extractfile(by_name[name])
            if stream is None:
                raise T09HostError("attempt export file is unreadable")
            observed = hashlib.sha256()
            observed_size = 0
            while chunk := stream.read(1_048_576):
                observed.update(chunk)
                observed_size += len(chunk)
                if observed_size > MAX_ATTEMPT_OUTPUT_BYTES:
                    raise T09HostError("attempt export expanded beyond its cap")
            if observed_size != size or observed.hexdigest() != digest:
                raise T09HostError("attempt export member hash mismatch")
            expected_members.add(name)
            total += size
        if set(by_name) != expected_members or total != manifest.get("total_bytes"):
            raise T09HostError("attempt export member set or aggregate bytes drifted")
        control_names = {name for name in by_name if name.startswith("control/")}
        control_snapshot_member = by_name.get("attempt-export-control-manifest.json")
        required_control_names = {
            f"control/{relative}" for relative in ATTEMPT_EXPORT_REQUIRED_CONTROL_PATHS
        }

        def archive_json(name: str, *, label: str) -> dict[str, Any]:
            member = by_name.get(name)
            stream = handle.extractfile(member) if member is not None else None
            if stream is None or member is None or member.size > MAX_PRIVACY_JSON_BYTES:
                raise T09HostError(f"attempt export {label} is unavailable")
            try:
                value: object = json.loads(stream.read())
            except json.JSONDecodeError as exc:
                raise T09HostError(f"attempt export {label} is malformed") from exc
            if not isinstance(value, dict):
                raise T09HostError(f"attempt export {label} is not an object")
            return value

        frozen_control_member = by_name.get("control/pilot-v6/frozen-run-manifest.json")
        frozen_control_stream = (
            handle.extractfile(frozen_control_member) if frozen_control_member is not None else None
        )
        if frozen_control_stream is None or frozen_control_member is None:
            raise T09HostError("attempt export frozen control is unavailable")
        try:
            frozen_transition_probe: object = json.loads(frozen_control_stream.read())
        except json.JSONDecodeError as exc:
            raise T09HostError("attempt export frozen control is malformed") from exc
        if not isinstance(frozen_transition_probe, dict):
            raise T09HostError("attempt export frozen control is not an object")
        transition_mode = frozen_transition_probe.get("preflight_transition_mode")
        if transition_mode == "replacement-launch":
            source_manifest_name = (
                "control/pilot-v6/slot2-authority/slot2-eligibility-source/source-manifest.json"
            )
            authority_manifest = archive_json(
                source_manifest_name,
                label="slot-2 authority source manifest",
            )
            raw_authority_files = authority_manifest.get("files")
            if (
                authority_manifest.get("schema_version") != "0.1.0"
                or authority_manifest.get("plan_id") != PLAN_ID
                or authority_manifest.get("host_run_id") != HOST_RUN_ID
                or not isinstance(raw_authority_files, list)
                or authority_manifest.get("file_count") != len(raw_authority_files)
                or authority_manifest.get("files_sha256")
                != hashlib.sha256(
                    (
                        json.dumps(
                            raw_authority_files,
                            allow_nan=False,
                            ensure_ascii=False,
                            separators=(",", ":"),
                            sort_keys=True,
                        )
                        + "\n"
                    ).encode()
                ).hexdigest()
            ):
                raise T09HostError("attempt export slot-2 authority manifest drifted")
            slot2_required = {
                "control/pilot-v6/slot2-authority/replacement-launch-eligibility.json",
                source_manifest_name,
            }
            authority_total = 0
            control_records_by_path = {
                cast(str, item["path"]): item
                for item in cast(list[dict[str, object]], files)
                if isinstance(item.get("path"), str)
                and cast(str, item["path"]).startswith("control/")
            }
            for raw in raw_authority_files:
                if not isinstance(raw, dict) or not isinstance(raw.get("path"), str):
                    raise T09HostError("attempt export slot-2 authority record is malformed")
                relative = PurePosixPath(cast(str, raw["path"]))
                if relative.is_absolute() or not relative.parts or ".." in relative.parts:
                    raise T09HostError("attempt export slot-2 authority path escaped")
                archive_name = (
                    "control/pilot-v6/slot2-authority/slot2-eligibility-source/"
                    + relative.as_posix()
                )
                record = control_records_by_path.get(archive_name)
                if (
                    record is None
                    or record.get("bytes") != raw.get("bytes")
                    or record.get("sha256") != raw.get("sha256")
                ):
                    raise T09HostError("attempt export slot-2 authority bytes drifted")
                slot2_required.add(archive_name)
                size = raw.get("bytes")
                if type(size) is not int:
                    raise T09HostError("attempt export slot-2 authority size is malformed")
                authority_total += size
            if authority_manifest.get("total_bytes") != authority_total:
                raise T09HostError("attempt export slot-2 authority total drifted")
            required_control_names.update(slot2_required)
        elif transition_mode not in {None, "fresh"}:
            raise T09HostError("attempt export transition mode is unsupported")
        optional_control_names = {
            "control/pilot-v6/first-pair-checkpoint.json",
            "control/pilot-v6/aggregate-budget.json",
        }
        if (
            control_snapshot_member is None
            or not required_control_names.issubset(control_names)
            or any(
                name not in required_control_names
                and name not in optional_control_names
                and not name.startswith("control/pilot-v6/received-export-acknowledgements/")
                and not name.startswith("control/pilot-v6/finalization-selections/")
                for name in control_names
            )
        ):
            raise T09HostError("attempt export control snapshot is incomplete or overbroad")

        frozen_control_name = "control/pilot-v6/frozen-run-manifest.json"
        provider_control_name = "control/pilot-v6/provider-entry.json"
        local_qualification_name = "control/pilot-v6/local-finalizer-qualification.json"
        frozen_control = archive_json(frozen_control_name, label="frozen run manifest")
        provider_control = archive_json(provider_control_name, label="provider entry")
        local_qualification = archive_json(
            local_qualification_name,
            label="local finalizer qualification",
        )
        control_snapshot = archive_json(
            "attempt-export-control-manifest.json",
            label="control snapshot manifest",
        )
        control_records = [
            item
            for item in cast(list[dict[str, object]], files)
            if isinstance(item.get("path"), str) and cast(str, item["path"]).startswith("control/")
        ]
        if (
            control_snapshot.get("schema_version") != "0.1.0"
            or control_snapshot.get("plan_id") != PLAN_ID
            or control_snapshot.get("host_run_id") != HOST_RUN_ID
            or control_snapshot.get("run_id") != args.run_id
            or control_snapshot.get("files") != control_records
            or control_snapshot.get("files_sha256") != canonical_sha256(control_records)
            or by_name[frozen_control_name].size
            != next(
                cast(int, item["bytes"])
                for item in cast(list[dict[str, object]], files)
                if item.get("path") == frozen_control_name
            )
            or cast(dict[str, object], manifest).get("frozen_run_manifest_sha256")
            != next(
                cast(str, item["sha256"])
                for item in cast(list[dict[str, object]], files)
                if item.get("path") == frozen_control_name
            )
            or frozen_control.get("manifest_id") != FROZEN_RUN_MANIFEST_ID
            or frozen_control.get("plan_id") != PLAN_ID
            or frozen_control.get("clean_package_commit") != args.package_commit
            or frozen_control.get("replacement_image_id") != manifest.get("replacement_image_id")
            or local_qualification.get("qualification_id")
            != "QUAL-T09-PILOT-V6-LOCAL-FINALIZER-0001"
            or local_qualification.get("package_commit") != args.package_commit
            or frozen_control.get("local_finalizer_qualification_sha256")
            != next(
                cast(str, item["sha256"])
                for item in cast(list[dict[str, object]], files)
                if item.get("path") == local_qualification_name
            )
        ):
            raise T09HostError("attempt export frozen/local control binding drifted")
        raw_receipt_member = by_name.get("raw-attempt-complete.json")
        raw_receipt_stream = (
            handle.extractfile(raw_receipt_member) if raw_receipt_member is not None else None
        )
        try:
            raw_receipt: object = (
                json.loads(raw_receipt_stream.read()) if raw_receipt_stream is not None else None
            )
        except json.JSONDecodeError as exc:
            raise T09HostError("attempt export raw receipt is malformed") from exc
        if (
            not isinstance(raw_receipt, dict)
            or raw_receipt.get("structural_privacy_findings")
            != manifest.get("structural_privacy_findings")
            or (raw_receipt.get("public_release_clearance") is True)
            != manifest.get("structural_privacy_scan_passed")
            or raw_receipt.get("actual_credential_exposure_detected")
            != manifest.get("actual_credential_exposure_detected")
            or raw_receipt.get("credential_cleanup_integrity_failure")
            != manifest.get("credential_cleanup_integrity_failure")
            or (raw_receipt.get("credential_cleanup_clean") is True)
            != manifest.get("campaign_continuation_permitted")
        ):
            raise T09HostError("attempt export privacy adjudication is not source-bound")
    entry = load_object(args.provider_entry_receipt.resolve(strict=True), label="provider entry")
    owned_hash = entry.get("owned_instance_identity_sha256")
    lambda_started = entry.get("lambda_started_at_epoch")
    if (
        not isinstance(owned_hash, str)
        or _HEX64.fullmatch(owned_hash) is None
        or not isinstance(lambda_started, (int, float))
        or isinstance(lambda_started, bool)
    ):
        raise T09HostError("attempt export lacks the source-bound provider entry identity")
    if (
        provider_control.get("receipt_sha256")
        != file_sha256(args.provider_entry_receipt.resolve(strict=True))
        or provider_control.get("owned_instance_identity_sha256") != owned_hash
        or provider_control.get("lambda_started_at_epoch") != float(lambda_started)
    ):
        raise T09HostError("attempt export provider control is not source-bound")
    verification: dict[str, object] = {
        "schema_version": "0.1.0",
        "plan_id": PLAN_ID,
        "host_run_id": HOST_RUN_ID,
        "run_id": args.run_id,
        "package_commit": args.package_commit,
        "archive_path": archive.name,
        "archive_bytes": archive.stat().st_size,
        "archive_sha256": file_sha256(archive),
        "frozen_run_manifest_sha256": manifest["frozen_run_manifest_sha256"],
        "replacement_image_id": manifest["replacement_image_id"],
        "provider_entry_receipt_sha256": file_sha256(
            args.provider_entry_receipt.resolve(strict=True)
        ),
        "owned_instance_identity_sha256": owned_hash,
        "lambda_started_at_epoch": float(lambda_started),
        "verified_before_provider_termination": True,
    }
    verification_path = inbound / f"{args.run_id}-export-verification.json"
    write_exclusive(verification_path, verification)
    restore_artifact_root = getattr(args, "restore_artifact_root", None)
    if restore_artifact_root is not None:
        restore_verified_attempt_export(
            repository=args.repository.resolve(strict=True),
            package_commit=args.package_commit,
            current_commit=args.restoration_commit,
            archive=archive,
            verification_path=verification_path,
            restoration_root=restore_artifact_root.resolve(strict=False),
            run_id=args.run_id,
        )


def _write_stream_exclusive_or_compare(
    *,
    stream: IO[bytes],
    destination: Path,
    expected_bytes: int,
    expected_sha256: str,
) -> None:
    """Materialize one verified archive member without overwrite authority."""

    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if destination.exists() or destination.is_symlink():
        if (
            destination.is_symlink()
            or not destination.is_file()
            or destination.stat().st_size != expected_bytes
            or file_sha256(destination) != expected_sha256
        ):
            raise T09HostError("offline restoration would overwrite different bytes")
        return
    observed = hashlib.sha256()
    observed_bytes = 0
    with destination.open("xb") as output:
        while chunk := stream.read(1_048_576):
            observed.update(chunk)
            observed_bytes += len(chunk)
            if observed_bytes > expected_bytes:
                raise T09HostError("offline restoration member exceeded its bound")
            output.write(chunk)
        output.flush()
        os.fsync(output.fileno())
    os.chmod(destination, 0o600)
    if observed_bytes != expected_bytes or observed.hexdigest() != expected_sha256:
        destination.unlink(missing_ok=True)
        raise T09HostError("offline restoration member hash mismatch")


def _replace_restored_state(path: Path, document: dict[str, Any]) -> None:
    """Atomically project one source-retained state snapshot into the local workspace."""

    temporary = path.with_suffix(f".{os.getpid()}.restore.tmp")
    encoded = (json.dumps(document, allow_nan=False, indent=2, sort_keys=True) + "\n").encode()
    descriptor = os.open(
        temporary,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        offset = 0
        while offset < len(encoded):
            written = os.write(descriptor, encoded[offset:])
            if written <= 0:
                raise T09HostError("offline state restoration write made no progress")
            offset += written
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    os.replace(temporary, path)
    directory = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def restore_verified_attempt_export(
    *,
    repository: Path,
    package_commit: str,
    current_commit: str | None,
    archive: Path,
    verification_path: Path,
    restoration_root: Path,
    run_id: str,
) -> None:
    """Restore a verified raw export for qualified post-termination finalization."""

    verify_package(repository, package_commit, current_commit=current_commit)
    contract_path = contract_paths(repository)["execution"]
    contract = load_execution_contract(
        contract_path,
        expected_sha256=file_sha256(contract_path),
    )
    attempt = contract.attempt(run_id)
    attempt_root = restoration_root / attempt.output_root
    raw_root = restoration_root / attempt.raw_output_root
    restoration_root.mkdir(mode=0o700, parents=True, exist_ok=True)
    if restoration_root.is_symlink() or not restoration_root.is_dir():
        raise T09HostError("offline restoration root is unsafe")
    snapshot_state: dict[str, Any] | None = None
    with tarfile.open(archive, "r:gz") as handle:
        member_list = handle.getmembers()
        if not 1 <= len(member_list) <= 2_048:
            raise T09HostError("offline restoration archive member count is invalid")
        members: dict[str, tarfile.TarInfo] = {}
        for member in member_list:
            relative = PurePosixPath(member.name)
            if (
                not member.isfile()
                or relative.is_absolute()
                or ".." in relative.parts
                or member.name in members
                or member.size < 0
                or member.size > MAX_ATTEMPT_OUTPUT_BYTES
            ):
                raise T09HostError("offline restoration archive member is unsafe")
            members[member.name] = member
        manifest_member = members.get("attempt-export-manifest.json")
        manifest_stream = (
            handle.extractfile(manifest_member) if manifest_member is not None else None
        )
        if manifest_stream is None:
            raise T09HostError("offline restoration lacks its export manifest")
        try:
            export_manifest: object = json.loads(manifest_stream.read())
        except json.JSONDecodeError as exc:
            raise T09HostError("offline restoration export manifest is malformed") from exc
        if not isinstance(export_manifest, dict) or export_manifest.get("run_id") != run_id:
            raise T09HostError("offline restoration export identity drifted")
        file_records = export_manifest.get("files")
        if not isinstance(file_records, list):
            raise T09HostError("offline restoration export file set is malformed")
        for record in file_records:
            if not isinstance(record, dict):
                raise T09HostError("offline restoration export record is malformed")
            name = record.get("path")
            size = record.get("bytes")
            digest = record.get("sha256")
            export_member = members.get(name) if isinstance(name, str) else None
            if (
                not isinstance(name, str)
                or type(size) is not int
                or not isinstance(digest, str)
                or _HEX64.fullmatch(digest) is None
                or export_member is None
                or export_member.size != size
            ):
                raise T09HostError("offline restoration member identity drifted")
            stream = handle.extractfile(export_member)
            if stream is None:
                raise T09HostError("offline restoration member is unreadable")
            if name.startswith("raw/"):
                destination = raw_root / name.removeprefix("raw/")
            elif name.startswith("control/"):
                control_relative = name.removeprefix("control/")
                if control_relative == "pilot-v6/pilot-state.json":
                    destination = (
                        restoration_root
                        / "pilot-v6/restored-control-snapshots"
                        / run_id
                        / "pilot-state.json"
                    )
                elif control_relative == "pilot-v6/aggregate-budget.json":
                    destination = (
                        restoration_root
                        / "pilot-v6/restored-control-snapshots"
                        / run_id
                        / "aggregate-budget.json"
                    )
                else:
                    destination = restoration_root / control_relative
            else:
                destination = attempt_root / name
            resolved_parent = destination.parent.resolve(strict=False)
            try:
                resolved_parent.relative_to(restoration_root)
            except ValueError:
                raise T09HostError("offline restoration path escaped its root") from None
            if destination.parent != resolved_parent:
                raise T09HostError("offline restoration path traversed a symlink")
            _write_stream_exclusive_or_compare(
                stream=stream,
                destination=destination,
                expected_bytes=size,
                expected_sha256=digest,
            )
            if name == "control/pilot-v6/pilot-state.json":
                snapshot_state = load_object(destination, label="restored pilot-state snapshot")
        manifest_record = next(
            (
                record
                for record in cast(list[dict[str, object]], file_records)
                if record.get("path") == "attempt-export-control-manifest.json"
            ),
            None,
        )
        if manifest_record is None:
            raise T09HostError("offline restoration lacks its control-snapshot manifest")
        assert manifest_member is not None
        manifest_again = handle.extractfile(manifest_member)
        if manifest_again is None:
            raise T09HostError("offline restoration export manifest became unreadable")
        _write_stream_exclusive_or_compare(
            stream=manifest_again,
            destination=attempt_root / "attempt-export-manifest.json",
            expected_bytes=manifest_member.size,
            expected_sha256=hashlib.sha256(
                (
                    json.dumps(export_manifest, allow_nan=False, indent=2, sort_keys=True) + "\n"
                ).encode()
            ).hexdigest(),
        )
    if snapshot_state is None:
        raise T09HostError("offline restoration lacks its exact pilot-state snapshot")
    expected_index = RUN_IDS.index(run_id)
    entered = snapshot_state.get("empirical_attempts_entered")
    raw_complete = snapshot_state.get("raw_attempts_complete")
    if (
        entered != list(RUN_IDS[: expected_index + 1])
        or raw_complete != list(RUN_IDS[: expected_index + 1])
        or snapshot_state.get("execution_contract_sha256") != contract.sha256
    ):
        raise T09HostError("offline restoration state is not the exact consumed raw prefix")
    state_path = restoration_root / "pilot-v6/pilot-state.json"
    if state_path.exists():
        retained = load_object(state_path, label="existing restored pilot state")
        retained_raw = retained.get("raw_attempts_complete")
        retained_raw_tuple = tuple(retained_raw) if isinstance(retained_raw, list) else None
        if retained_raw_tuple not in {
            tuple(RUN_IDS[:expected_index]),
            tuple(RUN_IDS[: expected_index + 1]),
        }:
            raise T09HostError("offline restoration archives were not applied in order")
        if (
            retained_raw_tuple == tuple(RUN_IDS[: expected_index + 1])
            and retained != snapshot_state
        ):
            raise T09HostError("repeated offline restoration state snapshot drifted")
    _replace_restored_state(state_path, snapshot_state)
    aggregate_snapshot_path = (
        restoration_root / "pilot-v6/restored-control-snapshots" / run_id / "aggregate-budget.json"
    )
    if aggregate_snapshot_path.exists():
        aggregate_snapshot = load_object(
            aggregate_snapshot_path,
            label="restored aggregate-budget snapshot",
        )
        if aggregate_snapshot.get("execution_contract_sha256") != contract.sha256:
            raise T09HostError("offline restoration aggregate budget binding drifted")
        _replace_restored_state(
            restoration_root / "pilot-v6/aggregate-budget.json",
            aggregate_snapshot,
        )
    export_destination = restoration_root / "pilot-v6/attempt-exports" / archive.name
    with archive.open("rb") as source:
        _write_stream_exclusive_or_compare(
            stream=source,
            destination=export_destination,
            expected_bytes=archive.stat().st_size,
            expected_sha256=file_sha256(archive),
        )
    verification = load_object(verification_path, label="attempt export verification")
    acknowledgement = _received_export_ack_path(restoration_root, run_id)
    if acknowledgement.exists():
        if load_object(acknowledgement, label="restored export acknowledgement") != verification:
            raise T09HostError("repeated offline export acknowledgement drifted")
    else:
        write_exclusive(acknowledgement, verification)
    load_frozen_run_manifest(
        restoration_root,
        repository=repository,
        package_commit=package_commit,
        require_image=False,
    )
    validate_raw_attempt_seal(
        attempt_root=attempt_root,
        raw_root=raw_root,
        run_id=run_id,
        package_commit=package_commit,
    )
    mark_raw_attempt_complete(
        state_path,
        execution_contract_sha256=contract.sha256,
        run_id=run_id,
        raw_manifest_sha256=file_sha256(attempt_root / "raw-attempt-manifest.json"),
        raw_receipt_sha256=file_sha256(attempt_root / "raw-attempt-complete.json"),
    )
    require_attempt_export_acknowledgement(
        restoration_root,
        run_id=run_id,
        package_commit=package_commit,
    )
    restore_receipt = {
        "schema_version": "0.1.0",
        "plan_id": PLAN_ID,
        "host_run_id": HOST_RUN_ID,
        "run_id": run_id,
        "package_commit": package_commit,
        "archive_sha256": file_sha256(archive),
        "verification_sha256": file_sha256(verification_path),
        "frozen_run_manifest_sha256": verification["frozen_run_manifest_sha256"],
        "raw_source_mutated": False,
        "qualified_local_finalization_ready": True,
    }
    restore_receipt_path = attempt_root / "offhost-restore-complete.json"
    if restore_receipt_path.exists():
        if load_object(restore_receipt_path, label="offhost restore receipt") != restore_receipt:
            raise T09HostError("repeated offline restore receipt drifted")
    else:
        write_exclusive(restore_receipt_path, restore_receipt)


def acknowledge_attempt_export(args: argparse.Namespace) -> None:
    """Register the off-host verifier receipt before any later empirical entry."""

    root = args.artifact_root.resolve(strict=True)
    incoming = args.acknowledgement_file.resolve(strict=True)
    acknowledgement = load_object(incoming, label="off-host export acknowledgement")
    state = _runtime_budget_state(root)
    raw_complete = state.get("raw_attempts_complete")
    if not isinstance(raw_complete, list) or args.run_id not in raw_complete:
        raise T09HostError("cannot acknowledge an attempt whose raw seal is incomplete")
    expected_index = RUN_IDS.index(args.run_id)
    if raw_complete[: expected_index + 1] != list(RUN_IDS[: expected_index + 1]):
        raise T09HostError("export acknowledgement violates frozen attempt order")
    destination = _received_export_ack_path(root, args.run_id)
    destination.parent.mkdir(mode=0o700, exist_ok=True)
    write_exclusive(destination, acknowledgement)
    try:
        require_prior_export_acknowledgements(
            root,
            next_attempt_index=expected_index + 1,
            package_commit=args.package_commit,
        )
    except BaseException:
        destination.unlink(missing_ok=True)
        raise
    if incoming != destination:
        incoming.unlink()


def _reconstructable_disposition(root: Path) -> dict[str, Any]:
    """Accept every zero-retry prefix that can be preserved for adjudication."""

    state = _runtime_budget_state(root)
    entered = state.get("empirical_attempts_entered")
    raw_complete = state.get("raw_attempts_complete")
    completed = state.get("attempts_completed")
    raw_bindings = state.get("raw_attempt_bindings")
    finalizations = state.get("attempt_finalizations")
    checkpoint = state.get("first_pair_decision")
    if (
        not isinstance(entered, list)
        or not isinstance(raw_complete, list)
        or not isinstance(completed, list)
        or not isinstance(raw_bindings, dict)
        or not isinstance(finalizations, dict)
        or entered != list(RUN_IDS[: len(entered)])
        or raw_complete != entered[: len(raw_complete)]
        or completed != [run_id for run_id in RUN_IDS if run_id in completed]
        or not set(completed).issubset(set(raw_complete))
        or set(raw_bindings) != set(raw_complete)
        or set(finalizations) != set(completed)
        or len(entered) > len(RUN_IDS)
        or len(entered) - len(raw_complete) > 1
        or checkpoint not in {None, "continue-to-task-b", "stop-before-task-b"}
        or (len(entered) > 2 and checkpoint != "continue-to-task-b")
    ):
        raise T09HostError("pilot attempt disposition is not a valid zero-retry prefix")
    return state


def _evidence_file_manifest(root: Path) -> tuple[list[dict[str, object]], int]:
    files: list[dict[str, object]] = []
    total = 0
    for path in sorted(root.rglob("*")):
        if (
            not path.is_file()
            or path.is_symlink()
            or path.name.endswith(".tar.gz")
            or path.name in {"evidence-stage-manifest.json", "evidence-stage-identity.json"}
        ):
            continue
        size = path.stat().st_size
        total += size
        if total > MAX_STAGED_EVIDENCE_BYTES:
            raise T09HostError("staged evidence exceeds its exact transfer cap")
        files.append(
            {
                "path": path.relative_to(root).as_posix(),
                "bytes": size,
                "sha256": file_sha256(path),
            }
        )
    return files, total


def staged_archive_headroom_ok(*, maximum_attempts: int = 4) -> bool:
    """Prove the raw-evidence envelope leaves room for one staged archive."""

    maximum_raw = maximum_attempts * MAX_ATTEMPT_OUTPUT_BYTES
    conservative_archive = maximum_raw + 64 * 1_048_576
    return (
        maximum_raw + conservative_archive <= MAX_PILOT_DISK_BYTES
        and conservative_archive <= MAX_STAGED_EVIDENCE_BYTES
    )


def export_image(args: argparse.Namespace) -> None:
    """Best-effort exact-image preservation that never consumes cleanup reserve."""

    root = args.artifact_root.resolve(strict=True)
    repository = args.repository.resolve(strict=True)
    verify_package(repository, args.package_commit)
    frozen, frozen_sha256 = load_frozen_run_manifest(
        root,
        repository=repository,
        package_commit=args.package_commit,
    )
    image_id = cast(str, frozen["replacement_image_id"])
    destination = args.image_archive.resolve(strict=False)
    if destination != IMAGE_ARCHIVE_PATH or destination.exists():
        raise T09HostError("replacement image archive path is not fresh and exact")
    remaining = provider_seconds_remaining(root)
    required_next_attempt = (
        MAX_CONDITION_WALL_SECONDS
        + ATTEMPT_EVIDENCE_EXPORT_RESERVE_SECONDS
        + PROVIDER_TERMINATION_HANDOFF_SECONDS
        + PROVIDER_CLOSEOUT_RESERVE_SECONDS
    )
    receipt_path = root / "pilot-v6/replacement-image-export.json"
    if remaining < required_next_attempt + MAX_IMAGE_EXPORT_SECONDS:
        write_exclusive(
            receipt_path,
            {
                "schema_version": "0.1.0",
                "replacement_image_id": image_id,
                "frozen_run_manifest_sha256": frozen_sha256,
                "preserved": False,
                "limitation": "deferred-to-protect-next-attempt-and-cleanup-reserve",
                "provider_seconds_remaining": remaining,
            },
        )
        return

    def limit_archive_size() -> None:
        resource.setrlimit(
            resource.RLIMIT_FSIZE,
            (MAX_IMAGE_ARCHIVE_BYTES, MAX_IMAGE_ARCHIVE_BYTES),
        )

    prefix = docker_prefix()
    started = time.monotonic()
    result: subprocess.CompletedProcess[bytes] | None = None
    limitation: str | None = None
    try:
        result = subprocess.run(
            [*prefix, "image", "save", "--output", str(destination), image_id],
            env=safe_environment(),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=MAX_IMAGE_EXPORT_SECONDS,
            preexec_fn=limit_archive_size,
        )
        if result.returncode != 0:
            limitation = f"docker-image-save-returncode-{result.returncode}"
    except subprocess.TimeoutExpired:
        limitation = "docker-image-save-timeout"
    if (
        limitation is None
        and destination.is_file()
        and not destination.is_symlink()
        and 0 < destination.stat().st_size <= MAX_IMAGE_ARCHIVE_BYTES
    ):
        write_exclusive(
            receipt_path,
            {
                "schema_version": "0.1.0",
                "replacement_image_id": image_id,
                "frozen_run_manifest_sha256": frozen_sha256,
                "preserved": True,
                "archive_path": str(destination),
                "archive_bytes": destination.stat().st_size,
                "archive_sha256": file_sha256(destination),
                "wall_seconds": time.monotonic() - started,
                "provider_cleanup_still_required": True,
            },
        )
        return
    with contextlib.suppress(OSError):
        destination.unlink()
    write_exclusive(
        receipt_path,
        {
            "schema_version": "0.1.0",
            "replacement_image_id": image_id,
            "frozen_run_manifest_sha256": frozen_sha256,
            "preserved": False,
            "limitation": limitation or "image-archive-invalid-or-oversize",
            "wall_seconds": time.monotonic() - started,
            "provider_cleanup_still_required": True,
        },
    )


def stage(args: argparse.Namespace) -> None:
    """Seal one remote evidence archive for the T07-style user download checkpoint."""

    root = args.artifact_root.resolve(strict=True)
    if not staged_archive_headroom_ok():
        raise T09HostError("frozen evidence caps do not reserve staged-archive headroom")
    cleanup_receipt = load_object(root / "pilot-v6/host-cleanup.json", label="cleanup")
    if (
        cleanup_receipt.get("global_secret_scan_passed") is not True
        or cleanup_receipt.get("remote_secret_removed") is not True
    ):
        raise T09HostError("global credential cleanup is incomplete")
    state = _reconstructable_disposition(root)
    frozen_manifest_path = root / "pilot-v6/frozen-run-manifest.json"
    frozen_manifest = load_object(frozen_manifest_path, label="frozen run manifest")
    frozen_manifest_sha256 = file_sha256(frozen_manifest_path)
    runtime_state = _runtime_budget_state(root)
    empirical_started_for_stage = runtime_state.get("campaign_started_at_epoch")
    if not isinstance(empirical_started_for_stage, (int, float)) or isinstance(
        empirical_started_for_stage, bool
    ):
        raise T09HostError("evidence stage lacks the empirical time origin")
    seconds_to_termination_cutoff = PROVIDER_TERMINATION_CUTOFF_SECONDS - (
        time.time() - float(empirical_started_for_stage)
    )
    if seconds_to_termination_cutoff <= 1:
        raise T09HostError(
            "provider termination is due; use the direct attempt exports and terminate now"
        )
    stage_timeout = min(MAX_STAGE_SECONDS, seconds_to_termination_cutoff)
    privacy_hits = privacy_violations(root)
    files, total = _evidence_file_manifest(root)
    manifest_path = root / "pilot-v6/evidence-stage-manifest.json"
    write_exclusive(
        manifest_path,
        {
            "schema_version": "0.1.0",
            "stage_id": STAGE_ID,
            "archive_id": ARCHIVE_ID,
            "private_access_controlled": True,
            "public_release": "blocked-pending-review",
            "frozen_run_manifest_id": frozen_manifest.get("manifest_id"),
            "frozen_run_manifest_sha256": frozen_manifest_sha256,
            "replacement_image_id": frozen_manifest.get("replacement_image_id"),
            "files": files,
            "total_bytes": total,
            "secret_scan_passed": True,
            "structural_privacy_scan_passed": not privacy_hits,
            "structural_privacy_findings": privacy_hits,
            "provider_closeout_pending": True,
        },
    )
    archive = root / "pilot-v6/t09-pilot-private-evidence-stage.tar.gz"
    with (
        hard_deadline(stage_timeout, message="aggregate evidence stage deadline exceeded"),
        tarfile.open(archive, "x:gz") as handle,
    ):
        for entry in files:
            handle.add(
                root / str(entry["path"]),
                arcname=str(entry["path"]),
                recursive=False,
            )
        handle.add(
            manifest_path,
            arcname=manifest_path.relative_to(root).as_posix(),
            recursive=False,
        )
    if archive.stat().st_size > MAX_STAGED_EVIDENCE_BYTES:
        raise T09HostError("compressed evidence stage exceeds its transfer cap")
    lambda_started = state.get("lambda_started_at_epoch")
    if not isinstance(lambda_started, (int, float)) or isinstance(lambda_started, bool):
        raise T09HostError("Lambda start time is unavailable at staging")
    provider_entry_path = root / "pilot-v6/provider-entry.json"
    dynamic_summary = load_object(provider_entry_path, label="provider entry summary")
    owned_hash = dynamic_summary.get("owned_instance_identity_sha256")
    if not isinstance(owned_hash, str) or _HEX64.fullmatch(owned_hash) is None:
        raise T09HostError("preflight lacks the owned provider identity hash")
    identity = {
        "schema_version": "0.1.0",
        "stage_id": STAGE_ID,
        "archive_id": ARCHIVE_ID,
        "bytes": archive.stat().st_size,
        "sha256": file_sha256(archive),
        "manifest_sha256": file_sha256(manifest_path),
        "frozen_run_manifest_sha256": frozen_manifest_sha256,
        "replacement_image_id": frozen_manifest.get("replacement_image_id"),
        "lambda_started_at_epoch": lambda_started,
        "owned_instance_identity_sha256": owned_hash,
        "provider_entry_receipt_sha256": dynamic_summary.get("receipt_sha256"),
        "provider_closeout_pending": True,
        "download_then_verify_before_termination": True,
    }
    write_exclusive(root / "pilot-v6/evidence-stage-identity.json", identity)
    write_exclusive(
        root / "pilot-v6/TERMINATE_REQUIRED.json",
        {
            "schema_version": "0.1.0",
            "stage_id": STAGE_ID,
            "archive_sha256": identity["sha256"],
            "owned_instance_identity_sha256": owned_hash,
            "action": (
                "download-stage-archive-identity-and-marker; verify-inbound; "
                "terminate-exact-bound-instance"
            ),
            "provider_closeout_required": True,
        },
    )


def verify_inbound(args: argparse.Namespace) -> None:
    """Verify the three manually downloaded T07-style handoff files locally."""

    inbound = args.inbound_root.resolve(strict=True)
    archive = inbound / "t09-pilot-private-evidence-stage.tar.gz"
    identity_path = inbound / "evidence-stage-identity.json"
    marker_path = inbound / "TERMINATE_REQUIRED.json"
    identity = load_object(identity_path, label="inbound stage identity")
    marker = load_object(marker_path, label="inbound termination marker")
    if (
        identity.get("stage_id") != STAGE_ID
        or identity.get("archive_id") != ARCHIVE_ID
        or identity.get("sha256") != file_sha256(archive)
        or identity.get("bytes") != archive.stat().st_size
        or marker.get("stage_id") != STAGE_ID
        or marker.get("archive_sha256") != identity.get("sha256")
        or marker.get("provider_closeout_required") is not True
        or not isinstance(identity.get("frozen_run_manifest_sha256"), str)
        or _HEX64.fullmatch(cast(str, identity["frozen_run_manifest_sha256"])) is None
        or not isinstance(identity.get("replacement_image_id"), str)
        or re.fullmatch(r"sha256:[a-f0-9]{64}", cast(str, identity["replacement_image_id"])) is None
        or archive.stat().st_size > MAX_STAGED_EVIDENCE_BYTES
    ):
        raise T09HostError("inbound evidence-stage identity drifted")
    write_exclusive(
        inbound / "inbound-verification.json",
        {
            "schema_version": "0.1.0",
            "stage_id": STAGE_ID,
            "archive_sha256": identity["sha256"],
            "archive_bytes": identity["bytes"],
            "owned_instance_identity_sha256": identity["owned_instance_identity_sha256"],
            "verified_before_provider_termination": True,
            "provider_closeout_still_required": True,
        },
    )


def package(args: argparse.Namespace) -> None:
    """Complete the private archive from aggregate or direct-prefix handoff evidence."""

    inbound = args.inbound_root.resolve(strict=True)
    entry_receipt_path = args.provider_entry_receipt.resolve(strict=True)
    entry = load_object(entry_receipt_path, label="provider entry receipt")
    lambda_started = entry.get("lambda_started_at_epoch")
    owned_hash = entry.get("owned_instance_identity_sha256")
    entry_sha256 = file_sha256(entry_receipt_path)
    provider_package_commit = entry.get("package_commit")
    if (
        not isinstance(lambda_started, (int, float))
        or isinstance(lambda_started, bool)
        or not isinstance(owned_hash, str)
        or _HEX64.fullmatch(owned_hash) is None
        or not isinstance(provider_package_commit, str)
        or re.fullmatch(r"[a-f0-9]{40}", provider_package_commit) is None
    ):
        raise T09HostError("source-bound provider entry identity is unavailable")
    if provider_package_commit != args.package_commit:
        transition = retry4_active_slot2_entry_transition(
            args.repository.resolve(strict=True), args.package_commit
        )
        if (
            provider_package_commit != RETRY4_ACTIVE_SLOT2_ENTRY_PACKAGE_COMMIT
            or transition.get("from_package_commit") != provider_package_commit
            or transition.get("to_package_commit") != args.package_commit
        ):
            raise T09HostError("provider closeout package transition drifted")
    source_archives: list[Path] = []
    frozen_manifest_sha256s: set[str] = set()
    replacement_image_ids: set[str] = set()
    aggregate_verification_path = inbound / "inbound-verification.json"
    if aggregate_verification_path.is_file():
        verification = load_object(
            aggregate_verification_path,
            label="inbound verification",
        )
        stage_archive = inbound / "t09-pilot-private-evidence-stage.tar.gz"
        stage_identity = load_object(
            inbound / "evidence-stage-identity.json", label="stage identity"
        )
        if (
            verification.get("verified_before_provider_termination") is not True
            or verification.get("archive_sha256") != file_sha256(stage_archive)
            or stage_identity.get("lambda_started_at_epoch") != lambda_started
            or stage_identity.get("owned_instance_identity_sha256") != owned_hash
            or stage_identity.get("provider_entry_receipt_sha256") != entry_sha256
        ):
            raise T09HostError("verified aggregate evidence stage drifted")
        frozen_sha = stage_identity.get("frozen_run_manifest_sha256")
        replacement_image = stage_identity.get("replacement_image_id")
        if (
            not isinstance(frozen_sha, str)
            or _HEX64.fullmatch(frozen_sha) is None
            or not isinstance(replacement_image, str)
            or re.fullmatch(r"sha256:[a-f0-9]{64}", replacement_image) is None
        ):
            raise T09HostError("aggregate evidence lacks the frozen runtime identity")
        frozen_manifest_sha256s.add(frozen_sha)
        replacement_image_ids.add(replacement_image)
        source_archives.append(stage_archive)
    else:
        prefix_open = True
        for run_id in RUN_IDS:
            verification_path = inbound / f"{run_id}-export-verification.json"
            if not verification_path.is_file():
                prefix_open = False
                continue
            if not prefix_open:
                raise T09HostError("direct attempt exports are not a frozen-order prefix")
            verification = load_object(
                verification_path,
                label="attempt export verification",
            )
            archive = inbound / f"{run_id}.tar.gz"
            if (
                verification.get("run_id") != run_id
                or verification.get("verified_before_provider_termination") is not True
                or verification.get("archive_sha256") != file_sha256(archive)
                or verification.get("archive_bytes") != archive.stat().st_size
                or verification.get("provider_entry_receipt_sha256") != entry_sha256
                or verification.get("owned_instance_identity_sha256") != owned_hash
                or verification.get("lambda_started_at_epoch") != lambda_started
            ):
                raise T09HostError("direct attempt export verification drifted")
            frozen_sha = verification.get("frozen_run_manifest_sha256")
            replacement_image = verification.get("replacement_image_id")
            if (
                not isinstance(frozen_sha, str)
                or _HEX64.fullmatch(frozen_sha) is None
                or not isinstance(replacement_image, str)
                or re.fullmatch(r"sha256:[a-f0-9]{64}", replacement_image) is None
            ):
                raise T09HostError("direct attempt export lacks the frozen runtime identity")
            frozen_manifest_sha256s.add(frozen_sha)
            replacement_image_ids.add(replacement_image)
            source_archives.append(archive)
    if len(frozen_manifest_sha256s) != 1 or len(replacement_image_ids) != 1:
        raise T09HostError("evidence payloads do not bind one frozen replacement runtime")
    closeout = validate_provider_closeout_receipt(
        args.provider_closeout_receipt.resolve(strict=True),
        expected_lambda_started_at_epoch=float(lambda_started),
        expected_owned_instance_identity_sha256=owned_hash,
        expected_entry_receipt_sha256=entry_sha256,
        expected_package_commit=provider_package_commit,
        repository_root=args.repository.resolve(strict=True),
        source_root=args.provider_closeout_source_root.resolve(strict=True),
        entry_receipt_path=entry_receipt_path,
        entry_source_root=args.provider_entry_source_root.resolve(strict=True),
    )
    output_root = args.final_archive_root.resolve(strict=True)
    if output_root != APPROVED_FINAL_ARCHIVE_ROOT:
        raise T09HostError("final archive root is not the approved T07-style APFS path")
    output_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    final_root = output_root / ARCHIVE_ID
    final_root.mkdir(mode=0o700)
    copied: list[dict[str, object]] = []
    for source_archive in source_archives:
        source_copy = final_root / source_archive.name
        with source_archive.open("rb") as source, source_copy.open("xb") as destination:
            shutil.copyfileobj(source, destination, length=1_048_576)
            destination.flush()
            os.fsync(destination.fileno())
        if file_sha256(source_copy) != file_sha256(source_archive):
            raise T09HostError("one-way evidence archive copy verification failed")
        copied.append(
            {
                "path": source_copy.name,
                "bytes": source_copy.stat().st_size,
                "sha256": file_sha256(source_copy),
            }
        )
    closeout_summary = final_root / "provider-closeout-summary.json"
    write_exclusive(closeout_summary, closeout)
    manifest_path = final_root / "evidence-archive-manifest.json"
    write_exclusive(
        manifest_path,
        {
            "schema_version": "0.1.0",
            "archive_id": ARCHIVE_ID,
            "private_access_controlled": True,
            "public_release": "blocked-pending-review",
            "payload_archives": copied,
            "frozen_run_manifest_sha256": next(iter(frozen_manifest_sha256s)),
            "replacement_image_id": next(iter(replacement_image_ids)),
            "payload_mode": (
                "aggregate-stage" if aggregate_verification_path.is_file() else "direct-prefix"
            ),
            "provider_closeout_receipt_sha256": closeout["receipt_sha256"],
            "provider_termination_confirmed": True,
            "zero_owned_instances_confirmed": True,
            "source_retained": True,
            "destination_reread_verified": True,
        },
    )
    write_exclusive(
        final_root / "archive-identity.json",
        {
            "schema_version": "0.1.0",
            "archive_id": ARCHIVE_ID,
            "manifest_sha256": file_sha256(manifest_path),
            "payload_archive_count": len(copied),
            "payload_archives_sha256": canonical_sha256(copied),
        },
    )


def cleanup(args: argparse.Namespace) -> None:
    root = args.artifact_root.resolve(strict=True)
    prefix = docker_prefix()
    removed = [name for name in owned_containers(prefix) if remove_container(prefix, name)]
    residue = owned_containers(prefix)
    image_removed = False
    materialization_path = root / "pilot-v6/replacement-image-qualification/receipt.json"
    if materialization_path.is_file():
        materialization = load_object(materialization_path, label="image materialization")
        image_id = materialization.get("image_id")
        if isinstance(image_id, str) and image_id_if_present(prefix, image_id) == image_id:
            removal = subprocess.run(
                [*prefix, "image", "rm", "--force", image_id],
                env=safe_environment(),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                timeout=60,
            )
            image_removed = removal.returncode == 0
    secret_path = args.secret_file.resolve(strict=True)
    credential_bytes = validate_secret(secret_path)
    hits = secret_hits(root, credential_bytes)
    removed_secret_artifacts: list[str] = []
    for relative in hits:
        target = root / relative
        if target.is_file() and not target.is_symlink():
            target.unlink()
            removed_secret_artifacts.append(relative)
    remaining_hits = secret_hits(root, credential_bytes)
    credential_bytes = b""
    state_path = root / "pilot-v6/pilot-state.json"
    credential_state_updated = False
    retained_actual_exposure = False
    retained_safety_stop = False
    try:
        retained_state = load_object(state_path, label="cleanup pilot state")
        execution_sha256 = retained_state.get("execution_contract_sha256")
        if not isinstance(execution_sha256, str):
            raise T09HostError("cleanup state lacks its execution contract")
        retained_actual_exposure = retained_state.get("actual_credential_exposure_detected") is True
        retained_safety_stop = retained_state.get("credential_safety_stop_detected") is True
        if hits:
            mark_actual_credential_exposure(
                state_path,
                execution_contract_sha256=execution_sha256,
            )
            retained_actual_exposure = True
            retained_safety_stop = True
        credential_state_updated = True
    except (OSError, T09HostError, T09PilotError):
        credential_state_updated = False
        retained_safety_stop = True
    actual_credential_exposure_detected = retained_actual_exposure or bool(hits)
    credential_safety_stop_detected = retained_safety_stop or bool(hits)
    secret_removed = destroy_secret(secret_path)
    image_archive_removed = False
    if IMAGE_ARCHIVE_PATH.exists() and not IMAGE_ARCHIVE_PATH.is_symlink():
        IMAGE_ARCHIVE_PATH.unlink()
        image_archive_removed = True
    regression_archive_removed = False
    if (
        PRIVATE_REGRESSION_ARCHIVE_PATH.exists()
        and not PRIVATE_REGRESSION_ARCHIVE_PATH.is_symlink()
    ):
        PRIVATE_REGRESSION_ARCHIVE_PATH.unlink()
        regression_archive_removed = True
    privacy_hits = privacy_violations(root)
    try:
        remaining_runtime = provider_seconds_remaining(root)
    except T09HostError:
        remaining_runtime = 0.0
    write_exclusive(
        root / "pilot-v6/host-cleanup.json",
        {
            "schema_version": "0.1.0",
            "completed_at": utc_now(),
            "owned_containers_removed": removed,
            "owned_container_residue": residue,
            "global_secret_scan_passed": not remaining_hits,
            "global_secret_bearing_artifacts_removed": removed_secret_artifacts,
            "global_secret_matching_paths": remaining_hits,
            "actual_credential_exposure_detected": actual_credential_exposure_detected,
            "credential_safety_stop_detected": credential_safety_stop_detected,
            "new_exact_credential_matches_detected_during_cleanup": bool(hits),
            "credential_exposure_state_updated": credential_state_updated,
            "campaign_continuation_permitted": not credential_safety_stop_detected,
            "remote_secret_removed": secret_removed,
            "replacement_image_archive_removed_after_copy_or_deferral": (
                image_archive_removed or not IMAGE_ARCHIVE_PATH.exists()
            ),
            "qualified_runtime_image_removed": image_removed
            or image_id_if_present(prefix, REPLACEMENT_IMAGE_TAG) is None,
            "private_regression_archive_removed": (
                regression_archive_removed or not PRIVATE_REGRESSION_ARCHIVE_PATH.exists()
            ),
            "structural_privacy_scan_passed": not privacy_hits,
            "structural_privacy_violations": privacy_hits,
            "gpu_pretermination_accounting": gpu_snapshot(),
            "evidence_stage_required_before_provider_termination": False,
            "aggregate_stage_optional_after_verified_direct_exports": True,
            "lambda_seconds_remaining_for_provider_closeout": remaining_runtime,
        },
    )
    if (
        residue
        or remaining_hits
        or not secret_removed
        or credential_safety_stop_detected
        or not credential_state_updated
    ):
        raise T09HostError(
            "owned runtime cleanup completed with credential residue or an actual exposure"
        )


def preempirical_replacement_disposition(args: argparse.Namespace) -> dict[str, object]:
    """Seal the narrow host proof that can authorize launch slot 2."""

    repository = args.repository.resolve(strict=True)
    root = args.artifact_root.resolve(strict=True)
    verify_package(repository, args.package_commit)
    state_path = root / "pilot-v6/pilot-state.json"
    cleanup_path = root / "pilot-v6/host-cleanup.json"
    provider_entry_path = root / "pilot-v6/provider-entry.json"
    failure_path = root / "pilot-v6/preflight-failure.json"
    state = load_object(state_path, label="pre-empirical pilot state")
    cleanup_receipt = load_object(cleanup_path, label="pre-empirical host cleanup")
    provider_entry = load_object(provider_entry_path, label="provider entry summary")
    failure = load_object(failure_path, label="preflight failure")
    qualification_root = root / "pilot-v6/replacement-image-qualification"
    materialization_receipt = qualification_root / "receipt.json"
    prefix = docker_prefix()
    if (
        state.get("empirical_attempts_entered") != []
        or state.get("raw_attempts_complete") != []
        or state.get("attempts_completed") != []
        or cleanup_receipt.get("owned_container_residue") != []
        or cleanup_receipt.get("global_secret_scan_passed") is not True
        or cleanup_receipt.get("remote_secret_removed") is not True
        or image_id_if_present(prefix, REPLACEMENT_IMAGE_TAG) is not None
        or failure.get("empirical_attempts_entered") != 0
        or failure.get("termination_dispatch_required") is not True
        or not isinstance(failure.get("failed_at_epoch"), (int, float))
        or failure.get("termination_dispatch_deadline_epoch")
        != cast(float, failure.get("failed_at_epoch"))
        + FAILED_PREFLIGHT_TERMINATION_DISPATCH_SECONDS
    ):
        raise T09HostError("launch slot 1 is not a zero-use replacement candidate")
    if materialization_receipt.is_file():
        materialization = load_object(
            materialization_receipt,
            label="pre-empirical image materialization",
        )
        if (
            materialization.get("method") != "exact-retained-image-archive-import"
            or materialization.get("image_id") != RETAINED_IMAGE_ID
            or materialization.get("build_count") != 0
            or materialization.get("image_import_count") != 1
            or materialization.get("retained_image_archive_sha256") != RETAINED_IMAGE_ARCHIVE_SHA256
        ):
            raise T09HostError(
                "only the exact retained-image zero-build prefix can authorize slot 2"
            )
        image_import_count = 1
        replacement_image_id: str | None = RETAINED_IMAGE_ID
        replacement_archive_sha256: str | None = RETAINED_IMAGE_ARCHIVE_SHA256
    else:
        image_import_count = 0
        replacement_image_id = None
        replacement_archive_sha256 = None
    entry_sha256 = provider_entry.get("receipt_sha256")
    if not isinstance(entry_sha256, str) or _HEX64.fullmatch(entry_sha256) is None:
        raise T09HostError("provider entry summary lacks its source receipt hash")
    source = root / "pilot-v6/preempirical-replacement-source"
    source.mkdir(mode=0o700, exist_ok=False)
    write_exclusive(source / "pilot-state.json", state)
    write_exclusive(source / "host-cleanup.json", cleanup_receipt)
    write_exclusive(source / "preflight-failure.json", failure)
    receipt: dict[str, object] = {
        "schema_version": "0.1.0",
        "plan_id": PLAN_ID,
        "host_run_id": HOST_RUN_ID,
        "package_commit": args.package_commit,
        "provider_entry_receipt_sha256": entry_sha256,
        "pilot_state_sha256": file_sha256(source / "pilot-state.json"),
        "host_cleanup_sha256": file_sha256(source / "host-cleanup.json"),
        "preflight_failure_sha256": file_sha256(source / "preflight-failure.json"),
        "preflight_failed_at_epoch": failure["failed_at_epoch"],
        "termination_dispatch_deadline_epoch": failure["termination_dispatch_deadline_epoch"],
        "empirical_attempts_entered": 0,
        "model_task_requests": 0,
        "task_browser_actions": 0,
        "replacement_image_build_count": 0,
        "replacement_image_import_count": image_import_count,
        "replacement_image_id": replacement_image_id,
        "replacement_image_archive_sha256": replacement_archive_sha256,
        "credentials_removed": True,
        "owned_containers_absent": True,
        "replacement_launch_evidence_only": True,
    }
    write_exclusive(source / "preempirical-disposition.json", receipt)
    files = [
        {
            "path": path.name,
            "bytes": path.stat().st_size,
            "sha256": file_sha256(path),
        }
        for path in sorted(source.iterdir())
    ]
    write_exclusive(
        source / "source-manifest.json",
        {
            "schema_version": "0.1.0",
            "plan_id": PLAN_ID,
            "host_run_id": HOST_RUN_ID,
            "files": files,
            "total_bytes": sum(cast(int, item["bytes"]) for item in files),
        },
    )
    return {
        "source_root": source.as_posix(),
        "receipt_sha256": file_sha256(source / "preempirical-disposition.json"),
        "source_manifest_sha256": file_sha256(source / "source-manifest.json"),
    }


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser()
    result.add_argument("--repository", type=Path, required=True)
    result.add_argument("--artifact-root", type=Path, required=True)
    result.add_argument("--secret-file", type=Path, required=True)
    result.add_argument("--evaluator-overlay", type=Path, required=True)
    result.add_argument("--package-commit", required=True)
    operations = result.add_subparsers(dest="operation", required=True)
    preflight_parser = operations.add_parser("preflight")
    preflight_parser.add_argument("--dynamic-receipt", type=Path, required=True)
    preflight_parser.add_argument("--dynamic-source-root", type=Path, required=True)
    preflight_parser.add_argument("--real-evidence-archive", type=Path, required=True)
    preflight_parser.add_argument("--local-finalizer-qualification", type=Path, required=True)
    preflight_parser.add_argument("--replacement-image-archive", type=Path, required=True)
    preflight_parser.add_argument("--slot2-authority-root", type=Path)
    condition_export = operations.add_parser("condition-export")
    condition_export.add_argument("--run-id", choices=RUN_IDS, required=True)
    finalize_parser = operations.add_parser("finalize-attempt")
    finalize_parser.add_argument("--run-id", choices=RUN_IDS, required=True)
    finalize_parser.add_argument("--finalizer-source", type=Path, required=True)
    finalize_parser.add_argument("--finalizer-projection-source", type=Path, required=True)
    finalize_parser.add_argument("--finalizer-commit", required=True)
    finalize_parser.add_argument(
        "--finalizer-execution-mode",
        choices=("qualified-image", "qualified-local"),
        default="qualified-image",
    )
    finalize_parser.add_argument("--local-finalizer-qualification", type=Path)
    finalize_parser.add_argument("--local-evaluator-root", type=Path)
    finalize_parser.add_argument("--local-dataset", type=Path)
    operations.add_parser("first-pair-checkpoint")
    operations.add_parser("campaign-disposition")
    export_only = operations.add_parser("export-only")
    export_only.add_argument("--run-id", choices=RUN_IDS, required=True)
    acknowledgement = operations.add_parser("acknowledge-attempt-export")
    acknowledgement.add_argument("--run-id", choices=RUN_IDS, required=True)
    acknowledgement.add_argument("--acknowledgement-file", type=Path, required=True)
    image_export = operations.add_parser("export-image")
    image_export.add_argument(
        "--image-archive",
        type=Path,
        default=IMAGE_ARCHIVE_PATH,
    )
    operations.add_parser("stage")
    inbound_parser = operations.add_parser("verify-inbound")
    inbound_parser.add_argument("--inbound-root", type=Path, required=True)
    attempt_export = operations.add_parser("verify-attempt-export")
    attempt_export.add_argument("--run-id", choices=RUN_IDS, required=True)
    attempt_export.add_argument("--inbound-root", type=Path, required=True)
    attempt_export.add_argument("--attempt-export", type=Path, required=True)
    attempt_export.add_argument("--provider-entry-receipt", type=Path, required=True)
    attempt_export.add_argument("--restore-artifact-root", type=Path)
    attempt_export.add_argument("--restoration-commit")
    package_parser = operations.add_parser("package")
    package_parser.add_argument("--inbound-root", type=Path, required=True)
    package_parser.add_argument("--provider-closeout-receipt", type=Path, required=True)
    package_parser.add_argument("--provider-closeout-source-root", type=Path, required=True)
    package_parser.add_argument("--provider-entry-receipt", type=Path, required=True)
    package_parser.add_argument("--provider-entry-source-root", type=Path, required=True)
    package_parser.add_argument("--final-archive-root", type=Path, required=True)
    operations.add_parser("cleanup")
    operations.add_parser("preempirical-replacement-disposition")
    return result


def main() -> int:
    args = parser().parse_args()
    if args.operation == "preflight":
        preflight_with_deadline(args)
        return 0
    if args.operation == "condition-export":
        execute_condition(args)
        export_attempt(args, sys.stdout.buffer)
        return 0
    if args.operation == "finalize-attempt":
        print(json.dumps(finalize_attempt(args), sort_keys=True))
        return 0
    if args.operation == "first-pair-checkpoint":
        print(json.dumps(first_pair_checkpoint(args), sort_keys=True))
        return 0
    if args.operation == "campaign-disposition":
        print(json.dumps(campaign_evidence_disposition(args), sort_keys=True))
        return 0
    if args.operation == "export-only":
        export_attempt(args, sys.stdout.buffer)
        return 0
    if args.operation == "acknowledge-attempt-export":
        acknowledge_attempt_export(args)
        return 0
    if args.operation == "export-image":
        export_image(args)
        return 0
    if args.operation == "stage":
        stage(args)
        return 0
    if args.operation == "verify-inbound":
        verify_inbound(args)
        return 0
    if args.operation == "verify-attempt-export":
        verify_attempt_export(args)
        return 0
    if args.operation == "package":
        package(args)
        return 0
    if args.operation == "cleanup":
        cleanup(args)
        return 0
    if args.operation == "preempirical-replacement-disposition":
        print(json.dumps(preempirical_replacement_disposition(args), sort_keys=True))
        return 0
    raise T09HostError("unknown operation")


if __name__ == "__main__":
    raise SystemExit(main())
