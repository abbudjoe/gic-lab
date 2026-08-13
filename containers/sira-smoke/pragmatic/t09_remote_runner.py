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
from typing import Any, BinaryIO, Final, cast

from giclab.harness.t09_pragmatic_provider import (
    T09ProviderError,
    load_campaign_lifecycle,
    validate_entry_receipt_source_bound,
)
from giclab.harness.t09_pragmatic_provider import (
    validate_closeout_receipt as validate_source_bound_closeout,
)
from giclab.harness.t09_sira_pilot import RuntimeQualification, T09PilotError

PLAN_ID: Final = "PLAN-EXP0001-PILOT-V4"
HOST_RUN_ID: Final = "RUN-T09-PILOT-HOST-0002"
ARCHIVE_ID: Final = "ARCHIVE-EXP0001-PILOT-V4-0002"
STAGE_ID: Final = "STAGE-EXP0001-PILOT-V4-0002"
QUALIFICATION_ID: Final = "QUAL-T09-PILOT-V4-IMAGE-0004"
CONTEXT_FAILURE_QUALIFICATION_ID: Final = "QUAL-T09-PILOT-V4-IMAGE-0002"
FAILED_CANDIDATE_QUALIFICATION_ID: Final = "QUAL-T09-PILOT-V4-IMAGE-0003"
MODEL: Final = "gpt-4o-2024-11-20"
SERVICE_TIER: Final = "default"
HISTORICAL_IMAGE_ID: Final = (
    "sha256:035edf61718e84a8156f4f0f7817b134b0ce31488d3f0b50bbfba2b4a30cc61c"
)
T07_EXECUTION_COMMIT: Final = "5698f04dfd08bc85a66d2355b0a4bd7d3ce24a23"
SIRA_COMMIT: Final = "93fb8d72de71f9a4a13419670adeb34d93cf7acd"
SIRA_TREE: Final = "6a6d9068b94d7632d3533a3d6f013d4de6ff76e8"
REPLACEMENT_IMAGE_TAG: Final = f"giclab/t09-pilot-v4:{SIRA_COMMIT[:12]}-0003"
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
        "pilot-v4-task-0000-reactive.yaml",
        "experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/conditions/"
        "pilot-v4-task-0000-simulative.yaml",
        "experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/conditions/"
        "pilot-v4-task-0001-reactive.yaml",
        "experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/conditions/"
        "pilot-v4-task-0001-simulative.yaml",
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
    "RUN-T09-TASK-A-REACTIVE-0002",
    "RUN-T09-TASK-A-SIMULATIVE-0002",
    "RUN-T09-TASK-B-SIMULATIVE-0002",
    "RUN-T09-TASK-B-REACTIVE-0002",
)
CONTAINER_PREFIX: Final = "giclab-t09-pilot-v4-"
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
MAX_LAMBDA_DURATION_SECONDS: Final = 14_400
MAX_LAMBDA_COST_USD: Final = 5.16
LAMBDA_HOURLY_PRICE_USD: Final = 1.29
FINALIZATION_RESERVE_SECONDS: Final = 60
ATTEMPT_EVIDENCE_EXPORT_RESERVE_SECONDS: Final = 600
PROVIDER_CLOSEOUT_RESERVE_SECONDS: Final = 900
PROVIDER_TERMINATION_CUTOFF_SECONDS: Final = 13_500
PROVIDER_TERMINATION_HANDOFF_SECONDS: Final = 60
MAX_LAMBDA_INSTANCES: Final = 1
MAX_LAMBDA_LAUNCHES: Final = 1
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
IMAGE_ARCHIVE_PATH: Final = Path("/home/ubuntu/t09-pilot-v4-replacement-image-0002.tar")


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
        "schema_version": "0.1.0",
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


def retain_prior_qualification_failures(
    *,
    artifact_root: Path,
    prior_artifact_root: Path,
    failed_candidate_root: Path,
    previous_transition_receipt: Path,
    package_transition_receipt: Path,
) -> dict[str, object]:
    destination = artifact_root / "pilot-v4/prior-qualification-failures"
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
    source = failed_candidate_root / "pilot-v4/replacement-image-qualification"
    destination = artifact_root / "pilot-v4/replacement-image-qualification"
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
    failed_candidate_root: Path | None = None,
) -> dict[str, object]:
    if failed_candidate_root is not None:
        return carry_forward_replacement_image(
            artifact_root=artifact_root,
            failed_candidate_root=failed_candidate_root.resolve(strict=True),
            prefix=prefix,
        )
    if image_id_if_present(prefix, REPLACEMENT_IMAGE_TAG) is not None:
        raise T09HostError("replacement image tag already exists; exactly one build is allowed")

    materialization = artifact_root / "pilot-v4/replacement-image-qualification"
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
    }


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
    if root.name != "t09-pilot-v4-output-0002":
        raise T09HostError("prior qualification root identity drifted")
    state_path = root / "pilot-v4/pilot-state.json"
    state = load_object(state_path, label="prior qualification state")
    env_example = (
        root / "pilot-v4/replacement-image-qualification/work/build-context/upstream/.env.example"
    )
    if (
        state.get("plan_id") != PLAN_ID
        or state.get("empirical_attempts_entered") != []
        or state.get("attempts_completed") != []
        or not env_example.is_file()
        or env_example.stat(follow_symlinks=False).st_size != PINNED_ENV_EXAMPLE_BYTES
        or file_sha256(env_example) != PINNED_ENV_EXAMPLE_SHA256
        or (root / "pilot-v4/frozen-run-manifest.json").exists()
        or (root / "pilot-v4/replacement-image-qualification/build-context-manifest.json").exists()
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
    if root.name != "t09-pilot-v4-output-0003":
        raise T09HostError("failed candidate root identity drifted")
    state = load_object(root / "pilot-v4/pilot-state.json", label="failed candidate state")
    qualification_root = root / "pilot-v4/replacement-image-qualification"
    receipt_path = qualification_root / "receipt.json"
    receipt = load_object(receipt_path, label="failed candidate materialization receipt")
    stderr_path = root / "pilot-v4/offline-runtime-preflight/offline-preflight.stderr"
    provider_entry = load_object(
        root / "pilot-v4/provider-entry.json", label="prior provider entry"
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
        or (root / "pilot-v4/frozen-run-manifest.json").exists()
        or (root / "pilot-v4/preflight.json").exists()
        or (root / "pilot-v4/model-metadata-preflight").exists()
        or (root / "pilot-v4/browser-preflight").exists()
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
    package_transition_receipt: Path | None = None,
    prior_artifact_root: Path | None = None,
    failed_candidate_root: Path | None = None,
    previous_transition_receipt: Path | None = None,
) -> dict[str, object]:
    """Reconstruct the receipt from retained allowlisted provider projections."""

    if repository_root is None or source_root is None:
        raise T09HostError("provider entry source bundle is required")
    repository = repository_root.resolve(strict=True)
    source = source_root.resolve(strict=True)
    plan = contract_paths(repository)["plan"]
    entry_package_commit = expected_package_commit
    transition: dict[str, object] | None = None
    if expected_package_commit != PACKAGE_TRANSITION_FROM_COMMIT:
        if any(
            item is None
            for item in (
                package_transition_receipt,
                prior_artifact_root,
                failed_candidate_root,
                previous_transition_receipt,
            )
        ):
            raise T09HostError("a source-bound preentry package transition is required")
        assert package_transition_receipt is not None
        assert prior_artifact_root is not None
        assert failed_candidate_root is not None
        assert previous_transition_receipt is not None
        transition = validate_package_transition_receipt(
            package_transition_receipt,
            repository=repository,
            package_commit=expected_package_commit,
            entry_receipt=path,
            entry_source_root=source,
            prior_artifact_root=prior_artifact_root,
            failed_candidate_root=failed_candidate_root,
            previous_transition_receipt=previous_transition_receipt,
            require_fresh=True,
            require_candidate_present=True,
        )
        entry_package_commit = PACKAGE_TRANSITION_FROM_COMMIT
    try:
        value = validate_entry_receipt_source_bound(
            path.resolve(strict=True),
            source,
            package_commit=entry_package_commit,
            plan_sha256=file_sha256(plan),
        )
    except T09ProviderError as exc:
        raise T09HostError("provider entry receipt is not source-bound") from exc
    captured = value.get("captured_at_epoch")
    if (
        not isinstance(captured, (int, float))
        or isinstance(captured, bool)
        or not 0
        <= time.time() - float(captured)
        <= (MAX_TOTAL_WALL_SECONDS if transition is not None else 1_800)
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
    result["receipt_sha256"] = file_sha256(path)
    if transition is not None:
        result["entry_package_commit"] = entry_package_commit
        result["active_package_commit"] = expected_package_commit
        result["package_transition_receipt_sha256"] = transition["receipt_sha256"]
        result["previous_package_transition_receipt_sha256"] = transition[
            "previous_package_transition_receipt_sha256"
        ]
        result["package_transition_created_at_epoch"] = transition["created_at_epoch"]
        result["context_failure_qualification_id"] = CONTEXT_FAILURE_QUALIFICATION_ID
        result["prior_qualification_id"] = FAILED_CANDIDATE_QUALIFICATION_ID
        result["qualification_id"] = QUALIFICATION_ID
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
    return load_object(root / "pilot-v4/pilot-state.json", label="pilot state")


def _received_export_ack_path(root: Path, run_id: str) -> Path:
    if run_id not in RUN_IDS:
        raise T09HostError("export acknowledgement run identity is unknown")
    return root / "pilot-v4/received-export-acknowledgements" / f"{run_id}.json"


def require_prior_export_acknowledgements(
    root: Path,
    *,
    next_attempt_index: int,
    package_commit: str,
) -> None:
    """Block empirical progression until every prior archive was verified off-host."""

    entry = load_object(root / "pilot-v4/provider-entry.json", label="provider entry")
    frozen_manifest_path = root / "pilot-v4/frozen-run-manifest.json"
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
        archive = root / "pilot-v4/attempt-exports" / f"{run_id}.tar.gz"
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


def provider_seconds_remaining(root: Path, *, reserve_seconds: float = 0.0) -> float:
    """Return provider time left while preserving an explicit cleanup reserve."""

    state = _runtime_budget_state(root)
    now = time.time()
    lambda_started = state.get("lambda_started_at_epoch")
    if not isinstance(lambda_started, (int, float)) or isinstance(lambda_started, bool):
        raise T09HostError("Lambda time origin is unavailable")
    lambda_elapsed = now - float(lambda_started)
    lambda_limit_from_cost = MAX_LAMBDA_COST_USD * 3600.0 / LAMBDA_HOURLY_PRICE_USD
    remaining = min(
        MAX_TOTAL_WALL_SECONDS - lambda_elapsed,
        MAX_LAMBDA_DURATION_SECONDS - lambda_elapsed,
        lambda_limit_from_cost - lambda_elapsed,
    )
    if remaining < reserve_seconds:
        raise T09HostError("provider duration or cost ceiling has no required reserve")
    return remaining - reserve_seconds


def scientific_seconds_remaining(root: Path, *, reserve_seconds: float = 0.0) -> float:
    """Return actual campaign time without reserving theoretical future attempts."""

    return provider_seconds_remaining(root, reserve_seconds=reserve_seconds)


def admit_next_attempt(root: Path) -> float:
    """Reserve one full condition, its evidence handoff, and provider cleanup."""

    usable = provider_seconds_remaining(
        root,
        reserve_seconds=(
            PROVIDER_CLOSEOUT_RESERVE_SECONDS
            + ATTEMPT_EVIDENCE_EXPORT_RESERVE_SECONDS
            + PROVIDER_TERMINATION_HANDOFF_SECONDS
        ),
    )
    if usable < MAX_CONDITION_WALL_SECONDS:
        raise T09HostError(
            "remaining campaign time cannot cover the next attempt hard wall, evidence handoff, "
            "termination dispatch, and cleanup reserve"
        )
    return usable


def provider_termination_due(root: Path) -> bool:
    """Return whether normal provider termination must already have begun."""

    state = _runtime_budget_state(root)
    started = state.get("lambda_started_at_epoch")
    if not isinstance(started, (int, float)) or isinstance(started, bool):
        raise T09HostError("Lambda time origin is unavailable")
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


def verify_package(repository: Path, package_commit: str) -> dict[str, Any]:
    if output(["git", "-C", str(repository), "rev-parse", "HEAD"]) != package_commit:
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
        != "single-qualified-replacement-preentry-frozen-run-manifest-v1"
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
            or file_sha256(repository / relative) != expected_sha256
        ):
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
    manifest_path = artifact_root / "pilot-v4/evaluator-overlay-manifest.json"
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
    manifest_path = artifact_root / "pilot-v4/evaluator-overlay-manifest.json"
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
    attempt = artifact_root / "pilot-v4/browser-preflight"
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
    attempt = artifact_root / "pilot-v4/secret-channel-preflight"
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
    attempt = artifact_root / "pilot-v4/offline-runtime-preflight"
    attempt.mkdir(parents=True, mode=0o700)
    source = repository / "containers/sira-smoke/pragmatic/t09_preflight.py"
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
        "/opt/giclab-artifacts/pilot-v4/offline-runtime-preflight",
        "--aggregate-ledger",
        "/opt/giclab-artifacts/pilot-v4/aggregate-budget.json",
        "--pilot-state",
        "/opt/giclab-artifacts/pilot-v4/pilot-state.json",
        "--evaluator-root",
        "/opt/sira/evaluation/fanout",
        "--dataset",
        "/opt/sira/data/fanout-final-dev.json",
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
        or receipt.get("provider_or_task_request") is not False
        or receipt.get("browser_action") is not False
    ):
        raise T09HostError("offline runtime or evaluator fixture preflight drifted")
    return receipt


def final_image_runtime_preflight(
    *,
    artifact_root: Path,
    prefix: list[str],
    image_id: str,
    command_document: dict[str, Any],
) -> dict[str, Any]:
    attempt = artifact_root / "pilot-v4/final-image-runtime-preflight"
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
    evidence = artifact_root / "pilot-v4/final-image-file-hashes"
    paths = {
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
            *paths,
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
    if observed != paths:
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
    attempt = artifact_root / "pilot-v4/model-metadata-preflight"
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
        artifact_root / "pilot-v4/replacement-image-qualification/replacement-image-inspect.stdout"
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
    write_exclusive(artifact_root / "pilot-v4/image-equivalence-adjudication.json", adjudication)
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
    adjudication: dict[str, object],
) -> tuple[Path, dict[str, object]]:
    paths = contract_paths(repository)
    image_id = image_materialization.get("image_id")
    if not isinstance(image_id, str) or re.fullmatch(r"sha256:[a-f0-9]{64}", image_id) is None:
        raise T09HostError("qualified replacement image ID is unavailable")
    if image_id_if_present(docker_prefix(), image_id) != image_id:
        raise T09HostError("qualified replacement image is no longer loaded by exact ID")
    empirical = _runtime_budget_state(artifact_root).get("empirical_attempts_entered")
    if empirical != []:
        raise T09HostError("runtime cannot freeze after empirical entry")
    qualification_root = artifact_root / "pilot-v4/replacement-image-qualification"
    manifest: dict[str, object] = {
        "schema_version": "0.1.0",
        "manifest_id": "RUN-MANIFEST-EXP0001-PILOT-V4-0002",
        "plan_id": PLAN_ID,
        "host_run_id": HOST_RUN_ID,
        "qualification_id": QUALIFICATION_ID,
        "qualification_count": 1,
        "build_count": image_materialization.get("build_count"),
        "source_contract_sha256": (
            "3852fe8dabb9ee6b10e40cbc6dc1ab964ea6fce11f71f81f0966e927cadddeb9"
        ),
        "clean_package_commit": package_commit,
        "plan_sha256": file_sha256(paths["plan"]),
        "execution_contract_sha256": file_sha256(paths["execution"]),
        "runtime_contract_sha256": file_sha256(paths["runtime"]),
        "command_manifests_sha256": file_sha256(paths["commands"]),
        "provider_entry_receipt_sha256": dynamic.get("receipt_sha256"),
        "package_transition_receipt_sha256": dynamic.get("package_transition_receipt_sha256"),
        "previous_package_transition_receipt_sha256": dynamic.get(
            "previous_package_transition_receipt_sha256"
        ),
        "owned_instance_identity_sha256": dynamic.get("owned_instance_identity_sha256"),
        "lambda_started_at_epoch": dynamic.get("lambda_started_at_epoch"),
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
        "model_metadata_request_count": 1,
        "model_task_request_count": 0,
        "task_browser_action_count": 0,
        "image_adjudication_sha256": canonical_sha256(adjudication),
        "command_argv_sha256s": [item["argv_sha256"] for item in manifests(command_document)],
        "pair_diffs": command_document.get("pair_diffs"),
        "attempt_order": list(RUN_IDS),
        "empirical_entry_crossed": False,
        "post_entry_code_science_image_freeze": True,
        "source_receipts": {
            "materialization": file_sha256(qualification_root / "receipt.json"),
            "build_context": file_sha256(qualification_root / "build-context-manifest.json"),
            "build_context_exclusions": file_sha256(
                qualification_root / "build-context-exclusions.json"
            ),
            "image_inspect": file_sha256(qualification_root / "replacement-image-inspect.stdout"),
            "evaluator_overlay": file_sha256(
                artifact_root / "pilot-v4/evaluator-overlay-manifest.json"
            ),
            "prior_qualification_failures": file_sha256(
                artifact_root / "pilot-v4/prior-qualification-failures/retention-receipt.json"
            ),
        },
    }
    if (
        manifest["build_count"] != 1
        or not isinstance(manifest["package_transition_receipt_sha256"], str)
        or _HEX64.fullmatch(manifest["package_transition_receipt_sha256"]) is None
        or not isinstance(manifest["pair_diffs"], list)
        or any(
            not isinstance(item, dict) or item.get("valid") is not True
            for item in cast(list[object], manifest["pair_diffs"])
        )
    ):
        raise T09HostError("replacement runtime cannot be frozen")
    path = artifact_root / "pilot-v4/frozen-run-manifest.json"
    write_exclusive(path, manifest)
    return path, manifest


def load_frozen_run_manifest(
    artifact_root: Path,
    *,
    repository: Path,
    package_commit: str,
) -> tuple[dict[str, Any], str]:
    path = artifact_root / "pilot-v4/frozen-run-manifest.json"
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
        artifact_root / "pilot-v4/provider-entry.json",
        label="provider entry summary",
    )
    expected = {
        "plan_id": PLAN_ID,
        "host_run_id": HOST_RUN_ID,
        "qualification_id": QUALIFICATION_ID,
        "qualification_count": 1,
        "build_count": 1,
        "source_contract_sha256": (
            "3852fe8dabb9ee6b10e40cbc6dc1ab964ea6fce11f71f81f0966e927cadddeb9"
        ),
        "clean_package_commit": package_commit,
        "plan_sha256": file_sha256(paths["plan"]),
        "execution_contract_sha256": file_sha256(paths["execution"]),
        "runtime_contract_sha256": file_sha256(paths["runtime"]),
        "command_manifests_sha256": file_sha256(paths["commands"]),
        "package_transition_receipt_sha256": provider_entry.get(
            "package_transition_receipt_sha256"
        ),
        "previous_package_transition_receipt_sha256": provider_entry.get(
            "previous_package_transition_receipt_sha256"
        ),
        "package_manifest_sha256": EXPECTED_PACKAGE_MANIFEST_SHA256,
        "chromium_executable_sha256": EXPECTED_CHROMIUM_SHA256,
        "patched_upstream_runner_sha256": EXPECTED_UPSTREAM_RUNNER_SHA256,
        "evaluator_overlay_manifest_sha256": manifest.get("evaluator_overlay_manifest_sha256"),
        "evaluator_overlay_entries_sha256": manifest.get("evaluator_overlay_entries_sha256"),
        "evaluator_overlay_packages_sha256": manifest.get("evaluator_overlay_packages_sha256"),
        "model_metadata_request_count": 1,
        "model_task_request_count": 0,
        "task_browser_action_count": 0,
        "attempt_order": list(RUN_IDS),
        "empirical_entry_crossed": False,
        "post_entry_code_science_image_freeze": True,
    }
    if any(manifest.get(key) != value for key, value in expected.items()):
        raise T09HostError("frozen run manifest binding drifted")
    exclusion_path = (
        artifact_root / "pilot-v4/replacement-image-qualification/build-context-exclusions.json"
    )
    if manifest.get("build_context_exclusions_sha256") != file_sha256(exclusion_path):
        raise T09HostError("frozen build-context exclusion receipt drifted")
    image_id = typed_qualification.replacement_image_id
    if (
        not isinstance(image_id, str)
        or re.fullmatch(r"sha256:[a-f0-9]{64}", image_id) is None
        or image_id_if_present(docker_prefix(), image_id) != image_id
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


def initialize_state(root: Path, execution_sha256: str, *, lambda_started_at_epoch: float) -> None:
    state = {
        "schema_version": "0.1.0",
        "plan_id": PLAN_ID,
        "execution_contract_sha256": execution_sha256,
        "pilot_started_at_epoch": lambda_started_at_epoch,
        "lambda_started_at_epoch": lambda_started_at_epoch,
        "first_pair_started_at_epoch": None,
        "second_pair_started_at_epoch": None,
        "empirical_attempts_entered": [],
        "attempts_completed": [],
        "first_pair_decision": None,
    }
    write_exclusive(root / "pilot-v4/pilot-state.json", state)


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
        package_transition_receipt=args.package_transition_receipt.resolve(strict=True),
        prior_artifact_root=args.prior_artifact_root.resolve(strict=True),
        failed_candidate_root=args.failed_candidate_root.resolve(strict=True),
        previous_transition_receipt=args.previous_package_transition_receipt.resolve(strict=True),
    )
    command_document = verify_package(repository, args.package_commit)
    paths = contract_paths(repository)
    prefix = docker_prefix()
    if owned_containers(prefix):
        raise T09HostError("owned pilot containers already exist")
    artifact_root.mkdir(mode=0o700, parents=True)
    lambda_started_raw = dynamic["lambda_started_at_epoch"]
    if not isinstance(lambda_started_raw, (int, float)) or isinstance(lambda_started_raw, bool):
        raise T09HostError("provider entry receipt lacks the billable time origin")
    lambda_started = float(lambda_started_raw)
    execution_sha256 = file_sha256(paths["execution"])
    initialize_state(
        artifact_root,
        execution_sha256,
        lambda_started_at_epoch=lambda_started,
    )
    write_exclusive(
        artifact_root / "pilot-v4/provider-entry.json",
        sanitized_dynamic_receipt(args.dynamic_receipt, dynamic),
    )
    retain_prior_qualification_failures(
        artifact_root=artifact_root,
        prior_artifact_root=args.prior_artifact_root.resolve(strict=True),
        failed_candidate_root=args.failed_candidate_root.resolve(strict=True),
        previous_transition_receipt=args.previous_package_transition_receipt.resolve(strict=True),
        package_transition_receipt=args.package_transition_receipt.resolve(strict=True),
    )
    image_materialization = materialize_replacement_image(
        repository=repository,
        artifact_root=artifact_root,
        prefix=prefix,
        failed_candidate_root=args.failed_candidate_root.resolve(strict=True),
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
    lambda_elapsed = time.time() - lambda_started
    if (
        lambda_elapsed >= MAX_LAMBDA_DURATION_SECONDS
        or lambda_elapsed * LAMBDA_HOURLY_PRICE_USD / 3600.0 >= MAX_LAMBDA_COST_USD
    ):
        raise T09HostError("preflight consumed the Lambda duration or cost ceiling")
    # This is the one authorized provider metadata GET and is intentionally the last
    # fallible functional gate before the immutable run manifest is written.
    model_metadata = model_metadata_preflight(
        artifact_root=artifact_root,
        secret_file=args.secret_file.resolve(strict=True),
        prefix=prefix,
        image_id=image_id,
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
        adjudication=adjudication,
    )
    state_path = artifact_root / "pilot-v4/pilot-state.json"
    state = load_object(state_path, label="pilot state")
    state["first_pair_started_at_epoch"] = time.time()
    write_atomic(state_path, state)
    admitted_seconds = admit_next_attempt(artifact_root)
    write_exclusive(
        artifact_root / "pilot-v4/preflight.json",
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
            "package_transition_receipt_sha256": file_sha256(args.package_transition_receipt),
            "dynamic_receipt": sanitized_dynamic_receipt(args.dynamic_receipt, dynamic),
            "image_materialization": image_materialization,
            "replacement_image_id": image_id,
            "frozen_run_manifest_sha256": file_sha256(frozen_manifest_path),
            "frozen_run_manifest_id": frozen_manifest["manifest_id"],
            "image_equivalence_adjudication": adjudication,
            "final_image_file_hashes": image_files,
            "final_image_runtime_preflight": final_runtime,
            "runtime_imports": "passed-by-network-none-offline-runtime-preflight",
            "evidence_write_fsync_readback": "passed-by-network-none-offline-runtime-preflight",
            "budget_ledger": "passed-zero-state-by-network-none-offline-runtime-preflight",
            "command_rendering": "passed-four-exact-by-network-none-offline-runtime-preflight",
            "browser_startup_screenshot_cleanup": browser,
            "evaluator_loading": "passed-exact-network-none-with-approved-fixtures",
            "evaluator_overlay_revalidation": evaluator_overlay_verified,
            "task_loading": "passed-two-exact-rows-network-none",
            "model_metadata": model_metadata,
            "model_metadata_request_count": 1,
            "model_task_request_count": 0,
            "credential_channel": credential_channel,
            "zero_prior_lambda_instances": True,
            "gpu_accounting": gpu,
            "empirical_entry_crossed": False,
            "actual_campaign_seconds_consumed_by_setup": time.time() - lambda_started,
            "seconds_available_after_cleanup_reserve": admitted_seconds,
        },
    )


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
    lambda_started_at_epoch: float,
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
            lambda_elapsed = now_wall - lambda_started_at_epoch
            if elapsed > MAX_CONDITION_WALL_SECONDS:
                stop_reason = "condition_wall_budget_stop"
            elif (
                now_wall - pair_started_at_epoch
                > MAX_PAIR_WALL_SECONDS - FINALIZATION_RESERVE_SECONDS
            ):
                stop_reason = "pair_wall_budget_stop"
            elif (
                now_wall - pilot_started_at_epoch
                > MAX_TOTAL_WALL_SECONDS - FINALIZATION_RESERVE_SECONDS
            ):
                stop_reason = "campaign_total_wall_budget_stop"
            elif lambda_elapsed > MAX_LAMBDA_DURATION_SECONDS - PROVIDER_CLOSEOUT_RESERVE_SECONDS:
                stop_reason = "lambda_duration_budget_stop"
            elif lambda_elapsed > (
                PROVIDER_TERMINATION_CUTOFF_SECONDS
                - ATTEMPT_EVIDENCE_EXPORT_RESERVE_SECONDS
                - PROVIDER_TERMINATION_HANDOFF_SECONDS
            ):
                stop_reason = "provider_termination_handoff_budget_stop"
            elif (
                lambda_elapsed + PROVIDER_CLOSEOUT_RESERVE_SECONDS
            ) * LAMBDA_HOURLY_PRICE_USD / 3600.0 > MAX_LAMBDA_COST_USD:
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
) -> list[str]:
    repository = args.repository.resolve(strict=True)
    paths = contract_paths(repository)
    artifact_root = args.artifact_root.resolve(strict=True)
    finalizer_source = repository / "containers/sira-smoke/pragmatic/t09_evaluate_attempt.py"
    return [
        *docker_prefix(),
        "run",
        "--rm",
        "--network",
        "none",
        "--read-only",
        "--user",
        "1000:1000",
        "--env",
        "PYTHONPATH=/opt/giclab-src",
        "--mount",
        f"type=bind,src={artifact_root},dst=/opt/giclab-artifacts",
        "--mount",
        f"type=bind,src={repository / 'src/giclab'},dst=/opt/giclab-src/giclab,readonly",
        "--mount",
        f"type=bind,src={finalizer_source},dst=/opt/giclab/t09_evaluate_attempt.py,readonly",
        "--mount",
        f"type=bind,src={args.evaluator_overlay.resolve(strict=True)},dst=/opt/evaluator,readonly",
        "--mount",
        f"type=bind,src={paths['execution']},dst=/opt/giclab-contracts/execution.json,readonly",
        "--mount",
        f"type=bind,src={paths['commands']},dst=/opt/giclab-contracts/T09_PILOT_COMMAND_MANIFESTS.json,readonly",
        "--mount",
        f"type=bind,src={paths['conditions']},dst=/opt/giclab-contracts/conditions,readonly",
        "--mount",
        f"type=bind,src={repository / 'schemas'},dst=/opt/giclab-schemas,readonly",
        "--entrypoint",
        "/opt/evaluator/.venv/bin/python",
        image_id,
        "/opt/giclab/t09_evaluate_attempt.py",
        "--execution-contract",
        "/opt/giclab-contracts/execution.json",
        "--execution-contract-sha256",
        file_sha256(paths["execution"]),
        "--command-manifests",
        "/opt/giclab-contracts/T09_PILOT_COMMAND_MANIFESTS.json",
        "--command-manifests-sha256",
        file_sha256(paths["commands"]),
        "--condition-plan",
        f"/opt/giclab-contracts/conditions/{Path(manifest['condition_plan_path']).name}",
        "--attempt-root",
        f"/opt/giclab-artifacts/{manifest['output_root']}",
        "--run-id",
        manifest["run_id"],
        "--package-commit",
        args.package_commit,
        "--frozen-run-manifest",
        "/opt/giclab-artifacts/pilot-v4/frozen-run-manifest.json",
        "--frozen-run-manifest-sha256",
        frozen_run_manifest_sha256,
        "--replacement-image-id",
        image_id,
        "--aggregate-ledger",
        "/opt/giclab-artifacts/pilot-v4/aggregate-budget.json",
        "--pilot-state",
        "/opt/giclab-artifacts/pilot-v4/pilot-state.json",
        "--host-cleanup-receipt",
        f"/opt/giclab-artifacts/{cleanup_receipt.relative_to(artifact_root).as_posix()}",
        "--evaluator-root",
        "/opt/sira/evaluation/fanout",
        "--dataset",
        "/opt/sira/data/fanout-final-dev.json",
        "--score-schema",
        "/opt/giclab-schemas/t09-sira-pilot-score.schema.json",
        "--evidence-schema",
        "/opt/giclab-schemas/t09-sira-pilot-evidence.schema.json",
    ]


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
) -> Path:
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
            or retained.get("structural_privacy_violations") != []
            or retained.get("retry_same_frozen_condition_permitted") is not True
            or retained.get("failure_prefix_entries") != observed_prefix
            or retained.get("failure_prefix_entries_sha256") != canonical_sha256(observed_prefix)
            or privacy_violations(attempt_root)
        ):
            raise T09HostError("existing attempt root is not a repairable pre-entry prefix")
        repair_root = artifact_root / "pilot-v4/preentry-condition-repairs" / run_id
        repair_root.mkdir(mode=0o700, parents=True, exist_ok=True)
        existing = sorted(path for path in repair_root.iterdir() if path.is_dir())
        if len(existing) >= MAX_PREENTRY_REPAIRS_PER_RUN:
            raise T09HostError("pre-entry condition repair limit reached")
        destination = repair_root / f"repair-{len(existing) + 1:02d}"
        if destination.exists() or destination.is_symlink():
            raise T09HostError("pre-entry repair identity is not fresh")
        os.replace(attempt_root, destination)
    attempt_root.mkdir(parents=True, mode=0o700, exist_ok=False)
    return attempt_root


def record_preentry_condition_failure(
    *,
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
            "remaining_exact_secret_matches": remaining,
            "structural_privacy_violations": privacy,
            "failure_prefix_entries": failure_prefix_entries,
            "failure_prefix_entries_sha256": canonical_sha256(failure_prefix_entries),
            "retry_same_frozen_condition_permitted": not residue and not remaining and not privacy,
            "recorded_at": utc_now(),
        },
    )
    if residue or remaining or privacy:
        raise T09HostError("pre-entry failure cleanup did not preserve a repairable prefix")


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
    preflight_path = artifact_root / "pilot-v4/preflight.json"
    if not preflight_path.is_file():
        raise T09HostError("exact preflight did not complete")
    preflight_receipt = load_object(preflight_path, label="exact preflight")
    if (
        preflight_receipt.get("frozen_run_manifest_sha256") != frozen_manifest_sha256
        or preflight_receipt.get("replacement_image_id") != image_id
        or preflight_receipt.get("empirical_entry_crossed") is not False
    ):
        raise T09HostError("preflight and frozen runtime manifest drifted")
    state = load_object(artifact_root / "pilot-v4/pilot-state.json", label="pilot state")
    entered = state.get("empirical_attempts_entered")
    completed = state.get("attempts_completed")
    if not isinstance(entered, list) or not isinstance(completed, list):
        raise T09HostError("pilot attempt state is malformed")
    expected_index = len(entered)
    if expected_index >= len(RUN_IDS) or RUN_IDS[expected_index] != args.run_id:
        raise T09HostError("condition would violate frozen order or zero retry")
    if len(entered) == 2 and state.get("first_pair_decision") != "continue-to-task-b":
        raise T09HostError("Task B is blocked by the first-pair checkpoint")
    require_prior_export_acknowledgements(
        artifact_root,
        next_attempt_index=expected_index,
        package_commit=args.package_commit,
    )
    started_epoch = state.get("pilot_started_at_epoch")
    lambda_started_epoch = state.get("lambda_started_at_epoch")
    pair_field = (
        "first_pair_started_at_epoch" if expected_index < 2 else "second_pair_started_at_epoch"
    )
    pair_started_epoch = state.get(pair_field)
    if not all(
        isinstance(value, (int, float)) and not isinstance(value, bool)
        for value in (started_epoch, pair_started_epoch, lambda_started_epoch)
    ):
        raise T09HostError("pilot, pair, or Lambda wall origin is unavailable")
    assert isinstance(started_epoch, (int, float))
    assert isinstance(pair_started_epoch, (int, float))
    assert isinstance(lambda_started_epoch, (int, float))
    total_elapsed = time.time() - float(started_epoch)
    if total_elapsed >= MAX_TOTAL_WALL_SECONDS:
        raise T09HostError("total pilot wall cap reached")
    pair_elapsed = time.time() - float(pair_started_epoch)
    lambda_elapsed = time.time() - float(lambda_started_epoch)
    if pair_elapsed >= MAX_PAIR_WALL_SECONDS:
        raise T09HostError("pair wall cap reached")
    if lambda_elapsed >= MAX_LAMBDA_DURATION_SECONDS:
        raise T09HostError("Lambda duration cap reached")
    if lambda_elapsed * LAMBDA_HOURLY_PRICE_USD / 3600.0 >= MAX_LAMBDA_COST_USD:
        raise T09HostError("Lambda cost cap reached")

    attempt_root = prepare_condition_attempt_root(
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
        attempt_root=attempt_root,
        container_name=name,
        image_id=image_id,
    )
    write_exclusive(
        attempt_root / "container-command.json",
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
        attempt_root / "attempt-wall.json",
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
                attempt_root=attempt_root,
                pilot_root=artifact_root,
                attempt_started=attempt_started,
                pair_started_at_epoch=float(pair_started_epoch),
                pilot_started_at_epoch=float(started_epoch),
                lambda_started_at_epoch=float(lambda_started_epoch),
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
        write_exclusive(attempt_root / "container-state.json", container_state)
        container_removed = remove_container(prefix, name)
    gpu_after = gpu_snapshot()
    write_exclusive(
        attempt_root / "gpu-accounting.json",
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
    hits = secret_hits(attempt_root, credential_bytes)
    removed_secret_artifacts: list[str] = []
    for relative in hits:
        target = attempt_root / relative
        if target.is_file() and not target.is_symlink():
            target.unlink()
            removed_secret_artifacts.append(relative)
    remaining_hits = secret_hits(attempt_root, credential_bytes)
    credential_bytes = b""
    residue = owned_containers(prefix)
    cleanup_receipt = attempt_root / "host-cleanup-receipt.json"
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
            "secret_matching_paths": remaining_hits,
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
    state_after_condition = load_object(
        artifact_root / "pilot-v4/pilot-state.json", label="post-condition pilot state"
    )
    entered_after_condition = state_after_condition.get("empirical_attempts_entered")
    if not isinstance(entered_after_condition, list):
        raise T09HostError("post-condition empirical state is malformed")
    if args.run_id not in entered_after_condition:
        record_preentry_condition_failure(
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
        )
        if runner_exception is not None:
            raise T09HostError(
                "condition host runner failed before empirical entry"
            ) from runner_exception
        raise T09HostError("condition ended before empirical entry; frozen retry remains permitted")
    finalizer = evaluator_argv(
        args=args,
        manifest=manifest,
        attempt_root=attempt_root,
        cleanup_receipt=cleanup_receipt,
        image_id=image_id,
        frozen_run_manifest_sha256=frozen_manifest_sha256,
    )
    evaluator_overlay_revalidation = validate_evaluator_overlay_binding(
        artifact_root=artifact_root,
        repository=repository,
        overlay=args.evaluator_overlay.resolve(strict=True),
        prefix=prefix,
        image_id=image_id,
        frozen_manifest=frozen_manifest,
        verify_packages=True,
    )
    write_exclusive(
        attempt_root / "evaluator-overlay-revalidation.json",
        evaluator_overlay_revalidation,
    )
    remaining_evidence_seconds = (
        MAX_CONDITION_WALL_SECONDS
        + ATTEMPT_EVIDENCE_EXPORT_RESERVE_SECONDS
        - (time.monotonic() - attempt_started)
    )
    remaining_pair_seconds = MAX_PAIR_WALL_SECONDS - (time.time() - float(pair_started_epoch))
    remaining_runtime_seconds = scientific_seconds_remaining(
        artifact_root,
        reserve_seconds=PROVIDER_CLOSEOUT_RESERVE_SECONDS,
    )
    finalizer_seconds = min(
        remaining_evidence_seconds,
        remaining_pair_seconds,
        remaining_runtime_seconds,
    )
    if finalizer_seconds <= 1:
        raise T09HostError("post-condition evidence handoff left no time for the evaluator")
    with (
        (attempt_root / "evaluator-finalizer.stdout").open("xb") as stdout,
        (attempt_root / "evaluator-finalizer.stderr").open("xb") as stderr,
    ):
        result = subprocess.run(
            finalizer,
            env=safe_environment(),
            stdin=subprocess.DEVNULL,
            stdout=stdout,
            stderr=stderr,
            check=False,
            timeout=min(FINALIZATION_RESERVE_SECONDS, max(1, int(finalizer_seconds))),
        )
    if result.returncode != 0:
        raise T09HostError("offline attempt evaluator/finalizer failed")
    if tree_bytes(attempt_root) > MAX_ATTEMPT_OUTPUT_BYTES:
        raise T09HostError("attempt output cap exceeded during finalization")
    if tree_bytes(artifact_root) > MAX_PILOT_DISK_BYTES:
        raise T09HostError("pilot disk cap exceeded during finalization")
    if time.time() - float(pair_started_epoch) > MAX_PAIR_WALL_SECONDS:
        raise T09HostError("pair wall cap exceeded during finalization")
    scientific_seconds_remaining(
        artifact_root,
        reserve_seconds=PROVIDER_CLOSEOUT_RESERVE_SECONDS,
    )
    return returncode


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


def export_attempt(args: argparse.Namespace, destination: BinaryIO) -> dict[str, object]:
    """Stream one finalized attempt to the operator inside its 3,600-second wall."""

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
    wall = load_object(attempt_root / "attempt-wall.json", label="attempt wall")
    evidence_deadline_epoch = wall.get("evidence_handoff_deadline_epoch")
    if not isinstance(evidence_deadline_epoch, (int, float)) or isinstance(
        evidence_deadline_epoch, bool
    ):
        raise T09HostError("attempt export lacks its evidence handoff deadline")
    required = {
        "attempt-outcome.json",
        "evidence-index.json",
        "host-cleanup-receipt.json",
        "normalized-events.jsonl",
    }
    if any(not (attempt_root / name).is_file() for name in required):
        raise T09HostError("attempt export lacks reconstructable finalized evidence")
    privacy_hits = privacy_violations(attempt_root)
    if privacy_hits:
        raise T09HostError("attempt export failed structural privacy validation")
    files: list[dict[str, object]] = []
    total = 0
    for path in sorted(attempt_root.rglob("*")):
        if not path.is_file() or path.is_symlink() or path.name == "attempt-export-manifest.json":
            continue
        size = path.stat().st_size
        total += size
        if total > MAX_ATTEMPT_OUTPUT_BYTES:
            raise T09HostError("attempt export exceeds its raw byte cap")
        files.append(
            {
                "path": path.relative_to(attempt_root).as_posix(),
                "bytes": size,
                "sha256": file_sha256(path),
            }
        )
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
        "files": files,
        "total_bytes": total,
        "structural_privacy_scan_passed": True,
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
    exports = artifact_root / "pilot-v4/attempt-exports"
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
                        handle.add(attempt_root / relative, arcname=relative, recursive=False)
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
            or manifest.get("frozen_run_manifest_id") != "RUN-MANIFEST-EXP0001-PILOT-V4-0002"
            or not isinstance(manifest.get("frozen_run_manifest_sha256"), str)
            or _HEX64.fullmatch(cast(str, manifest["frozen_run_manifest_sha256"])) is None
            or not isinstance(manifest.get("replacement_image_id"), str)
            or re.fullmatch(r"sha256:[a-f0-9]{64}", cast(str, manifest["replacement_image_id"]))
            is None
            or manifest.get("private_access_controlled") is not True
            or manifest.get("public_release") != "blocked-pending-review"
            or manifest.get("structural_privacy_scan_passed") is not True
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
    write_exclusive(
        inbound / f"{args.run_id}-export-verification.json",
        {
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
        },
    )


def acknowledge_attempt_export(args: argparse.Namespace) -> None:
    """Register the off-host verifier receipt before any later empirical entry."""

    root = args.artifact_root.resolve(strict=True)
    incoming = args.acknowledgement_file.resolve(strict=True)
    acknowledgement = load_object(incoming, label="off-host export acknowledgement")
    state = _runtime_budget_state(root)
    completed = state.get("attempts_completed")
    if not isinstance(completed, list) or args.run_id not in completed:
        raise T09HostError("cannot acknowledge an attempt that is not finalized")
    expected_index = RUN_IDS.index(args.run_id)
    if completed[: expected_index + 1] != list(RUN_IDS[: expected_index + 1]):
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
    completed = state.get("attempts_completed")
    checkpoint = state.get("first_pair_decision")
    if (
        not isinstance(entered, list)
        or not isinstance(completed, list)
        or entered != list(RUN_IDS[: len(entered)])
        or completed != entered[: len(completed)]
        or len(entered) > len(RUN_IDS)
        or len(entered) - len(completed) > 1
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
    receipt_path = root / "pilot-v4/replacement-image-export.json"
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
    cleanup_receipt = load_object(root / "pilot-v4/host-cleanup.json", label="cleanup")
    if (
        cleanup_receipt.get("global_secret_scan_passed") is not True
        or cleanup_receipt.get("remote_secret_removed") is not True
        or cleanup_receipt.get("structural_privacy_scan_passed") is not True
    ):
        raise T09HostError("global credential cleanup is incomplete")
    state = _reconstructable_disposition(root)
    frozen_manifest_path = root / "pilot-v4/frozen-run-manifest.json"
    frozen_manifest = load_object(frozen_manifest_path, label="frozen run manifest")
    frozen_manifest_sha256 = file_sha256(frozen_manifest_path)
    runtime_state = _runtime_budget_state(root)
    lambda_started_for_stage = runtime_state.get("lambda_started_at_epoch")
    if not isinstance(lambda_started_for_stage, (int, float)) or isinstance(
        lambda_started_for_stage, bool
    ):
        raise T09HostError("evidence stage lacks the provider time origin")
    seconds_to_termination_cutoff = PROVIDER_TERMINATION_CUTOFF_SECONDS - (
        time.time() - float(lambda_started_for_stage)
    )
    if seconds_to_termination_cutoff <= 1:
        raise T09HostError(
            "provider termination is due; use the direct attempt exports and terminate now"
        )
    stage_timeout = min(MAX_STAGE_SECONDS, seconds_to_termination_cutoff)
    privacy_hits = privacy_violations(root)
    if privacy_hits:
        raise T09HostError(
            "structural privacy scan failed before staging: " + ", ".join(privacy_hits)
        )
    files, total = _evidence_file_manifest(root)
    manifest_path = root / "pilot-v4/evidence-stage-manifest.json"
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
            "structural_privacy_scan_passed": True,
            "provider_closeout_pending": True,
        },
    )
    archive = root / "pilot-v4/t09-pilot-private-evidence-stage.tar.gz"
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
    provider_entry_path = root / "pilot-v4/provider-entry.json"
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
    write_exclusive(root / "pilot-v4/evidence-stage-identity.json", identity)
    write_exclusive(
        root / "pilot-v4/TERMINATE_REQUIRED.json",
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
    transition = validate_package_transition_receipt(
        args.package_transition_receipt.resolve(strict=True),
        repository=args.repository.resolve(strict=True),
        package_commit=args.package_commit,
        entry_receipt=entry_receipt_path,
        entry_source_root=args.provider_entry_source_root.resolve(strict=True),
        prior_artifact_root=args.prior_artifact_root.resolve(strict=True),
        failed_candidate_root=args.failed_candidate_root.resolve(strict=True),
        previous_transition_receipt=args.previous_package_transition_receipt.resolve(strict=True),
        require_fresh=False,
        require_candidate_present=False,
    )
    if (
        not isinstance(lambda_started, (int, float))
        or isinstance(lambda_started, bool)
        or not isinstance(owned_hash, str)
        or _HEX64.fullmatch(owned_hash) is None
    ):
        raise T09HostError("source-bound provider entry identity is unavailable")
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
        expected_package_commit=PACKAGE_TRANSITION_FROM_COMMIT,
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
    transition_summary = final_root / "package-transition-summary.json"
    write_exclusive(transition_summary, transition)
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
            "package_transition_receipt_sha256": transition["receipt_sha256"],
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
    secret_removed = destroy_secret(secret_path)
    image_archive_removed = False
    if IMAGE_ARCHIVE_PATH.exists() and not IMAGE_ARCHIVE_PATH.is_symlink():
        IMAGE_ARCHIVE_PATH.unlink()
        image_archive_removed = True
    privacy_hits = privacy_violations(root)
    try:
        remaining_runtime = provider_seconds_remaining(root)
    except T09HostError:
        remaining_runtime = 0.0
    write_exclusive(
        root / "pilot-v4/host-cleanup.json",
        {
            "schema_version": "0.1.0",
            "completed_at": utc_now(),
            "owned_containers_removed": removed,
            "owned_container_residue": residue,
            "global_secret_scan_passed": not remaining_hits,
            "global_secret_bearing_artifacts_removed": removed_secret_artifacts,
            "global_secret_matching_paths": remaining_hits,
            "remote_secret_removed": secret_removed,
            "replacement_image_archive_removed_after_copy_or_deferral": (
                image_archive_removed or not IMAGE_ARCHIVE_PATH.exists()
            ),
            "structural_privacy_scan_passed": not privacy_hits,
            "structural_privacy_violations": privacy_hits,
            "gpu_pretermination_accounting": gpu_snapshot(),
            "evidence_stage_required_before_provider_termination": False,
            "aggregate_stage_optional_after_verified_direct_exports": True,
            "lambda_seconds_remaining_for_provider_closeout": remaining_runtime,
        },
    )
    if residue or remaining_hits or not secret_removed or privacy_hits:
        raise T09HostError("owned runtime or credential cleanup is incomplete")


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser()
    result.add_argument("--repository", type=Path, required=True)
    result.add_argument("--artifact-root", type=Path, required=True)
    result.add_argument("--secret-file", type=Path, required=True)
    result.add_argument("--evaluator-overlay", type=Path, required=True)
    result.add_argument("--package-commit", required=True)
    operations = result.add_subparsers(dest="operation", required=True)
    transition_parser = operations.add_parser("bind-package-transition")
    transition_parser.add_argument("--dynamic-receipt", type=Path, required=True)
    transition_parser.add_argument("--dynamic-source-root", type=Path, required=True)
    transition_parser.add_argument("--prior-artifact-root", type=Path, required=True)
    transition_parser.add_argument("--failed-candidate-root", type=Path, required=True)
    transition_parser.add_argument(
        "--previous-package-transition-receipt", type=Path, required=True
    )
    transition_parser.add_argument("--output", type=Path, required=True)
    preflight_parser = operations.add_parser("preflight")
    preflight_parser.add_argument("--dynamic-receipt", type=Path, required=True)
    preflight_parser.add_argument("--dynamic-source-root", type=Path, required=True)
    preflight_parser.add_argument("--package-transition-receipt", type=Path, required=True)
    preflight_parser.add_argument("--prior-artifact-root", type=Path, required=True)
    preflight_parser.add_argument("--failed-candidate-root", type=Path, required=True)
    preflight_parser.add_argument("--previous-package-transition-receipt", type=Path, required=True)
    condition_export = operations.add_parser("condition-export")
    condition_export.add_argument("--run-id", choices=RUN_IDS, required=True)
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
    package_parser = operations.add_parser("package")
    package_parser.add_argument("--inbound-root", type=Path, required=True)
    package_parser.add_argument("--provider-closeout-receipt", type=Path, required=True)
    package_parser.add_argument("--provider-closeout-source-root", type=Path, required=True)
    package_parser.add_argument("--provider-entry-receipt", type=Path, required=True)
    package_parser.add_argument("--provider-entry-source-root", type=Path, required=True)
    package_parser.add_argument("--package-transition-receipt", type=Path, required=True)
    package_parser.add_argument("--prior-artifact-root", type=Path, required=True)
    package_parser.add_argument("--failed-candidate-root", type=Path, required=True)
    package_parser.add_argument("--previous-package-transition-receipt", type=Path, required=True)
    package_parser.add_argument("--final-archive-root", type=Path, required=True)
    operations.add_parser("cleanup")
    return result


def main() -> int:
    args = parser().parse_args()
    if args.operation == "bind-package-transition":
        write_package_transition_receipt(args)
        return 0
    if args.operation == "preflight":
        preflight(args)
        return 0
    if args.operation == "condition-export":
        execute_condition(args)
        export_attempt(args, sys.stdout.buffer)
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
    raise T09HostError("unknown operation")


if __name__ == "__main__":
    raise SystemExit(main())
