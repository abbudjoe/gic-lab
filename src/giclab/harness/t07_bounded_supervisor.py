"""Executable local supervisor for the manually operated T07 bounded smoke.

Import is inert.  A future, separately authorized invocation may materialize the
external authorization overlay, perform the fixed GET-only Lambda observations, or
copy already-sealed evidence to the approved external APFS volume.  Cloud mutations
remain user-console actions and are never implemented here.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import contextlib
import hashlib
import http.client
import io
import ipaddress
import json
import math
import os
import re
import socket
import ssl
import stat
import subprocess
import sys
import tarfile
import time
import zipfile
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path, PurePosixPath
from types import ModuleType
from typing import Any, Final, Literal, Protocol, cast

import yaml
from jsonschema import Draft202012Validator, FormatChecker

SCHEMA_VERSION: Final = "0.1.0"
PLAN_ID: Final = "PLAN-T07-BOUNDED-SIRA-SMOKE-V1"
HOST_RUN_ID: Final = "RUN-T07-BOUNDED-HOST-0001"
BRANCH: Final = "phase-1/sira-smoke-bounded"
RUN_ROOT_RELATIVE: Final = Path("artifacts/t07/bounded") / HOST_RUN_ID
INBOUND_RELATIVE: Final = RUN_ROOT_RELATIVE / "inbound"
AUTHORIZATION_RELATIVE: Final = RUN_ROOT_RELATIVE / "authorization.json"
PRIVATE_BINDING_RELATIVE: Final = RUN_ROOT_RELATIVE / "private-binding.json"
STATE_RELATIVE: Final = RUN_ROOT_RELATIVE / "observer-state.json"
LEDGER_RELATIVE: Final = RUN_ROOT_RELATIVE / "request-ledger.jsonl"
MATERIALIZATION_SUMMARY_RELATIVE: Final = RUN_ROOT_RELATIVE / "MATERIALIZATION_SUMMARY.json"
BOOTSTRAP_RELEASE_RELATIVE: Final = RUN_ROOT_RELATIVE / "BOOTSTRAP_RELEASE.json"
BOOTSTRAP_RELEASE_STATE_RELATIVE: Final = RUN_ROOT_RELATIVE / "BOOTSTRAP_RELEASE_STATE.json"
INBOUND_VERIFICATION_RELATIVE: Final = RUN_ROOT_RELATIVE / "INBOUND_VERIFICATION.json"
COMPUTE_CLOSEOUT_RELATIVE: Final = RUN_ROOT_RELATIVE / "COMPUTE_USE_CLOSEOUT.json"
OBSERVER_VERIFICATION_RELATIVE: Final = RUN_ROOT_RELATIVE / "OBSERVER_EVIDENCE_VERIFICATION.json"
RESPONSES_RELATIVE: Final = RUN_ROOT_RELATIVE / "responses"
UPLOAD_ROOT_RELATIVE: Final = Path("artifacts/t07/bounded-upload") / HOST_RUN_ID
UPLOAD_IDENTITY_RELATIVE: Final = RUN_ROOT_RELATIVE / "UPLOAD_BUNDLE_IDENTITY.json"
UPLOAD_ARCHIVE_NAME: Final = "t07-bounded-repository.tar"
UPLOAD_BOOTSTRAP_NAME: Final = "t07-bounded-bootstrap.py"
UPLOAD_MANIFEST_NAME: Final = "BUNDLE_MANIFEST.json"
BOUNDED_PLAN_RELATIVE: Final = Path("containers/sira-smoke/bounded/bounded-smoke-plan-v1.json")
REMOTE_BOOTSTRAP_RELATIVE: Final = Path("containers/sira-smoke/bounded/bootstrap.py")

SOURCE_PARAMETERS_RELATIVE: Final = Path(
    "artifacts/t07/lambda/gate-l2m/"
    "RUN-T07-L2M-MANUAL-CONSOLE-HOST-QUALIFICATION-0003/"
    "materialization-v1/private-parameters.json"
)
SOURCE_PARAMETERS_SHA256: Final = "a9b210594ed3b4c962f414b8a2d9509d14a2d7deb097050e92321e6da4d5d096"
RESTORATION_RELATIVE: Final = Path(
    "artifacts/t07/lambda/gate-l2m/"
    "T07-HIGH-ASSURANCE-FIREWALL-CLOSEOUT-0001/restoration-payload.json"
)
RESTORATION_SHA256: Final = "50ca7febe9f160ada862371376485ea2ece11b373d25179ccd578d9c7acd42b8"
BASELINE_SEMANTIC_SHA256: Final = "b0ef711158113cdbdbb1707cb43f21a635271bb2e93bfc0e898ce7118589f764"

AUTHORIZATION_SCHEMA_RELATIVE: Final = Path("schemas/t07-bounded-smoke-authorization.schema.json")
PRIVATE_BINDING_SCHEMA_RELATIVE: Final = Path(
    "schemas/t07-bounded-smoke-private-binding.schema.json"
)
LEDGER_SCHEMA_RELATIVE: Final = Path("schemas/t07-bounded-smoke-observer-ledger.schema.json")
EVIDENCE_SCHEMA_RELATIVE: Final = Path("schemas/t07-bounded-smoke-evidence.schema.json")
ENDPOINT_SCHEMA_ROOT: Final = Path("containers/sira-smoke/lambda/endpoint-schemas-v3")
ENDPOINT_SCHEMAS: Final[Mapping[str, str]] = {
    "/api/v1/instance-types": "instance-types.schema.json",
    "/api/v1/images": "images.schema.json",
    "/api/v1/regions": "regions.schema.json",
    "/api/v1/ssh-keys": "ssh-keys.schema.json",
    "/api/v1/firewall-rulesets": "firewall-rulesets.schema.json",
    "/api/v1/firewall-rulesets/global": "global-firewall-ruleset.schema.json",
    "/api/v1/instances": "instances.schema.json",
}
PHASE_REQUESTS: Final[Mapping[str, tuple[str, ...]]] = {
    "prelaunch": (
        "/api/v1/instance-types",
        "/api/v1/images",
        "/api/v1/regions",
        "/api/v1/ssh-keys",
        "/api/v1/firewall-rulesets",
        "/api/v1/firewall-rulesets/global",
        "/api/v1/instances",
    ),
    "security": (
        "/api/v1/firewall-rulesets",
        "/api/v1/firewall-rulesets/global",
    ),
    "post_launch": ("/api/v1/instances",),
    "termination": ("/api/v1/instances",),
    "terminal": (
        "/api/v1/firewall-rulesets",
        "/api/v1/firewall-rulesets/global",
    ),
}
PHASE_ORDER: Final = tuple(PHASE_REQUESTS)
PHASE_START_ORDINAL: Final = {
    "prelaunch": 1,
    "security": 8,
    "post_launch": 10,
    "termination": 11,
    "terminal": 12,
}
CLEANUP_NEXT_PHASE: Final[Mapping[str, str | None]] = {
    "prelaunch": "terminal",
    "security": "terminal",
    "post_launch": "termination",
    "termination": "terminal",
    "terminal": None,
}
MAX_REQUESTS: Final = 13
MAX_RESPONSE_BYTES: Final = 1_048_576
MAX_RESPONSE_BYTES_AGGREGATE: Final = 13_631_488
MAX_REQUEST_SECONDS: Final = 60
MAX_OBSERVER_WALL_SECONDS: Final = 3_600
MIN_REQUEST_SPACING_NS: Final = 1_000_000_000
MAX_LEDGER_BYTES: Final = 262_144
MAX_LEDGER_EVENTS: Final = 96
MAX_LEDGER_EVENT_BYTES: Final = 4_096
MAX_PRIVATE_FILE_BYTES: Final = 1_048_576
MAX_AUTHORIZATION_BYTES: Final = 65_536
MAX_PLAN_BYTES: Final = 1_048_576
MAX_UPLOAD_BUNDLE_BYTES: Final = 8_388_608
MAX_UPLOAD_BUNDLE_FILES: Final = 36
MAX_ARCHIVE_BYTES: Final = 301_989_888
MAX_ARCHIVE_FILES: Final = 128
MAX_ARCHIVE_PAYLOAD_FILES: Final = MAX_ARCHIVE_FILES - 3
MAX_REMOTE_EVIDENCE_BYTES: Final = 268_435_456
MAX_REMOTE_EVIDENCE_FILES: Final = 4_096
ARCHIVE_WALL_SECONDS: Final = 600
MAC_PREWRITE_FLOOR_BYTES: Final = 8_891_924_480
MAC_RETAINED_FLOOR_BYTES: Final = 8_589_934_592
EXTERNAL_RETAINED_FLOOR_BYTES: Final = 200_048_192_717
EXTERNAL_PREWRITE_FLOOR_BYTES: Final = 200_350_182_605
EXTERNAL_MOUNT: Final = Path("/Volumes/Macintosh HD - Data")
EXTERNAL_PARENT: Final = EXTERNAL_MOUNT / "GIC-Lab/t07/sealed-artifacts"
EXTERNAL_FINAL: Final = EXTERNAL_PARENT / HOST_RUN_ID

_HEX40 = re.compile(r"^[a-f0-9]{40}$")
_HEX64 = re.compile(r"^[a-f0-9]{64}$")
_AUTHORIZATION = re.compile(r"^AUTH-T07-BOUNDED-SIRA-SMOKE-V1-[A-Z0-9._-]{3,80}$")
_OWNED_RULESET = re.compile(r"^giclab-t07-bounded-[a-f0-9]{12}$")
_SECRET_SHAPES = (
    re.compile(rb"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(
        rb"(?im)^[ \t]*[A-Z0-9_]*(?:API_"
        rb"KEY|TO"
        rb"KEN|SE"
        rb"CRET)[ \t]*=[^\r\n]+$"
    ),
)
_SECRET_PREFIX_SHAPES = (
    re.compile(rb"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(rb"(?im)^[ \t]*[A-Z0-9_]*(?:API_KEY|TOKEN|SECRET)[ \t]*="),
    re.compile(
        rb"""(?ix)["']?(?:(?:api|access|private)[ _-]?key|"""
        rb"""token|secret|password|cookie|credential)"""
        rb"""["']?\s*[:=]\s*["']?[a-z0-9._~+/=-]{8,}"""
    ),
    re.compile(
        rb"""(?isx)["']?(?:key|label|name|type)["']?\s*:\s*"""
        rb"""["']?(?:(?:api|access|private)[ _-]?key|token|secret|password|cookie|"""
        rb"""credential|authorization)"""
        rb"""["']?[\s\S]{0,256}?["']?value["']?\s*:\s*"""
        rb"""["']?[a-z0-9._~+/=-]{8,}"""
    ),
    re.compile(
        rb"""(?isx)["']?value["']?\s*:\s*["']?"""
        rb"""[a-z0-9._~+/=-]{8,}["']?[\s\S]{0,256}?"""
        rb"""["']?(?:key|label|name|type)["']?\s*:\s*"""
        rb"""["']?(?:(?:api|access|private)[ _-]?key|token|secret|password|cookie|"""
        rb"""credential|authorization)"""
    ),
    re.compile(
        rb"""(?ix)["']?authorization["']?[ \t]*[:=][ \t]*["']?"""
        rb"""(?:bearer|basic)[ \t]+[a-z0-9._~+/=-]{8,}"""
    ),
)


def _artifact_sensitive_key(name: str) -> bool:
    normalized = re.sub(r"[^a-z0-9]+", "_", name.casefold()).strip("_")
    if normalized in {
        "api_key",
        "access_key",
        "private_key",
        "token",
        "password",
        "cookie",
        "credential",
        "secret",
        "authorization",
    }:
        return True
    return any(
        normalized.endswith("_" + suffix)
        for suffix in (
            "api_key",
            "access_key",
            "private_key",
            "token",
            "password",
            "cookie",
            "credential",
            "secret",
            "authorization",
        )
    )


def _json_contains_artifact_secret(value: object) -> bool:
    if isinstance(value, Mapping):
        discriminator_sensitive = any(
            isinstance(key, str)
            and key.casefold() in _SENSITIVE_PROVIDER_DISCRIMINATORS
            and isinstance(child, str)
            and _artifact_sensitive_key(child)
            for key, child in value.items()
        )
        candidate = value.get("value")
        if (
            discriminator_sensitive
            and isinstance(candidate, str)
            and len(candidate) >= 8
            and _AUTHORIZATION.fullmatch(candidate) is None
        ):
            return True
        for key, child in value.items():
            if (
                isinstance(key, str)
                and _artifact_sensitive_key(key)
                and isinstance(child, str)
                and len(child) >= 8
                and not (
                    key.casefold().endswith("authorization")
                    and _AUTHORIZATION.fullmatch(child) is not None
                )
            ):
                return True
            if _json_contains_artifact_secret(child):
                return True
        return False
    if isinstance(value, list):
        return any(_json_contains_artifact_secret(item) for item in value)
    return False


def _contains_artifact_secret(encoded: bytes) -> bool:
    if any(pattern.search(encoded) for pattern in _SECRET_PREFIX_SHAPES):
        return True
    if len(encoded) > 16_777_216:
        return False
    try:
        document = json.loads(encoded)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return False
    return _json_contains_artifact_secret(document)


_SENSITIVE_PROVIDER_KEYS: Final = frozenset(
    {
        "authorization",
        "cookie",
        "credential",
        "jupyter_token",
        "jupyter_url",
        "password",
        "secret",
        "token",
    }
)
_SENSITIVE_PROVIDER_DISCRIMINATORS: Final = frozenset({"key", "label", "name", "type"})
_DROP_PROVIDER_VALUE: Final = object()

_LIFECYCLE_EVIDENCE_NAMES: Final = (
    "container-id.txt",
    "container-create.json",
    "container-inspect-before-stop-command.json",
    "container-inspect-before-stop.json",
    "container-top-before-stop-command.json",
    "container-processes-before-stop.txt",
    "container-copy-out-prestop.json",
    "container-copy-out-prestop-budget.json",
    "container-payload-capture.json",
    "container-start.json",
    "stdout.log",
    "stderr.log",
    "container-stop.json",
    "container-kill.json",
    "container-terminal-inspect-command.json",
    "container-terminal-inspect.json",
    "container-remove.json",
    "container-removal-proof.json",
    "container-residue-containers.json",
    "container-residue-networks.json",
    "container-residue-volumes.json",
    "container-cleanup.json",
)
_LIFECYCLE_EVIDENCE_ROOTS: Final[Mapping[str, str]] = {
    "browser-preflight": "BROWSER-PREFLIGHT",
    "model-preflight": "MODEL-PREFLIGHT",
    "reactive": "SIRA-REACTIVE",
    "simulative": "SIRA-SIMULATIVE",
}
CONDITION_PLAN_SHA256: Final[Mapping[str, str]] = {
    "SIRA-REACTIVE": "7ca19470e550e48978090c9b7014e047c56d80962e40275b846f589b08bfb018",
    "SIRA-SIMULATIVE": "68f5f4a4a123620bab039ba7bc6844243cad229ed992df6562bf0d8562874436",
}


class BoundedSupervisorError(RuntimeError):
    """The bounded local control plane failed closed."""


class VolumeObservation(Protocol):
    """Stdlib-only structural copy used before any verified repository dependency import."""

    mount_path: Path
    filesystem: str
    writable: bool
    volume_uuid: str | None
    physical_store_uuid: str | None
    total_bytes: int
    free_bytes: int
    internal: bool
    owners_enabled: bool
    encrypted: bool
    unlocked: bool
    device_identifier: str
    bus_protocol: str
    device_tree_path: str


@dataclass(frozen=True, slots=True)
class HttpResponse:
    status: int
    content_type: str
    body: bytes = field(repr=False)
    elapsed_ms: int


@dataclass(frozen=True, slots=True)
class TransportFailure(Exception):
    stage: str
    classification: str
    bytes_received: int = 0
    elapsed_ms: int = 0


@dataclass(frozen=True, slots=True)
class ArchiveSource:
    """One exact archive source with an explicit privacy-validation class."""

    relative: str
    path: Path
    byte_count: int
    sha256: str
    content_class: Literal["runtime_evidence", "reviewed_repository_upload"]


class ReadOnlyTransport(Protocol):
    def fetch(
        self,
        path: str,
        *,
        credential: str,
        timeout_seconds: float,
        max_response_bytes: int,
    ) -> HttpResponse: ...


def canonical_json_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
        + b"\n"
    )


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _strict_json(encoded: bytes, *, context: str) -> dict[str, object]:
    def pairs(items: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in items:
            if key in result:
                raise BoundedSupervisorError(f"{context} contains a duplicate key")
            result[key] = value
        return result

    def reject_constant(_: str) -> object:
        raise BoundedSupervisorError(f"{context} contains a non-finite number")

    try:
        value = json.loads(encoded, object_pairs_hook=pairs, parse_constant=reject_constant)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise BoundedSupervisorError(f"{context} is not strict JSON") from None
    if not isinstance(value, dict):
        raise BoundedSupervisorError(f"{context} must be an object")
    return value


def _read_regular(path: Path, *, max_bytes: int) -> bytes:
    try:
        linked = path.lstat()
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except OSError:
        raise BoundedSupervisorError("required input is unavailable") from None
    try:
        opened = os.fstat(descriptor)
        if (
            not stat.S_ISREG(linked.st_mode)
            or stat.S_ISLNK(linked.st_mode)
            or linked.st_nlink != 1
            or (linked.st_dev, linked.st_ino) != (opened.st_dev, opened.st_ino)
            or opened.st_size > max_bytes
        ):
            raise BoundedSupervisorError("required input identity is unsafe")
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(descriptor, min(65_536, max_bytes + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > max_bytes:
                raise BoundedSupervisorError("required input exceeds its cap")
        if total != opened.st_size:
            raise BoundedSupervisorError("required input changed while held")
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def _write_exclusive(path: Path, encoded: bytes, *, mode: int = 0o600) -> None:
    descriptor = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        mode,
    )
    try:
        offset = 0
        while offset < len(encoded):
            written = os.write(descriptor, encoded[offset:])
            if written < 1:
                raise BoundedSupervisorError("evidence write made no progress")
            offset += written
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _atomic_write(path: Path, encoded: bytes) -> None:
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    _write_exclusive(temporary, encoded)
    try:
        os.replace(temporary, path)
        parent = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(parent)
        finally:
            os.close(parent)
    except Exception:
        with contextlib.suppress(OSError):
            temporary.unlink()
        raise


def _load_schema(root: Path, relative: Path) -> tuple[dict[str, object], str]:
    encoded = _read_regular(root / relative, max_bytes=1_048_576)
    return _strict_json(encoded, context=relative.name), sha256_bytes(encoded)


def _validate_schema(document: object, schema: Mapping[str, object], *, context: str) -> None:
    error = next(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(document),
        None,
    )
    if error is not None:
        raise BoundedSupervisorError(f"{context} failed its bound schema")


def _parse_utc(value: object, *, context: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise BoundedSupervisorError(f"{context} is not an exact UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        raise BoundedSupervisorError(f"{context} is malformed") from None
    if parsed.tzinfo != UTC:
        raise BoundedSupervisorError(f"{context} is not UTC")
    return parsed


def _utc_text(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _mapping(value: object, *, context: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or any(not isinstance(key, str) for key in value):
        raise BoundedSupervisorError(f"{context} must be an object")
    return value


def _sequence(value: object, *, context: str) -> Sequence[object]:
    if not isinstance(value, list):
        raise BoundedSupervisorError(f"{context} must be an array")
    return value


def _nonnegative_integer(value: object, *, context: str) -> int:
    if type(value) is not int or value < 0:
        raise BoundedSupervisorError(f"{context} must be a nonnegative integer")
    return value


def _text(value: object, *, context: str) -> str:
    if not isinstance(value, str) or not value:
        raise BoundedSupervisorError(f"{context} must be nonempty text")
    return value


def _git(root: Path, *args: str) -> str:
    environment = {
        "HOME": str(root),
        "LANG": "C",
        "LC_ALL": "C",
        "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
    }
    try:
        result = subprocess.run(
            ("/usr/bin/git", *args),
            cwd=root,
            env=environment,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        raise BoundedSupervisorError("read-only Git identity check failed") from None
    if result.returncode != 0 or len(result.stdout) + len(result.stderr) > 1_048_576:
        raise BoundedSupervisorError("read-only Git identity check failed")
    return result.stdout.decode("utf-8", "strict").strip()


def verify_repository_identity(root: Path, expected_commit: str) -> None:
    resolved = root.resolve(strict=True)
    if resolved != root.absolute() or not _HEX40.fullmatch(expected_commit):
        raise BoundedSupervisorError("repository identity input is invalid")
    if (
        _git(root, "branch", "--show-current") != BRANCH
        or _git(root, "rev-parse", "HEAD") != expected_commit
        or _git(root, "status", "--short")
    ):
        raise BoundedSupervisorError("bounded supervisor requires the exact clean branch/commit")


def load_and_validate_plan(
    root: Path,
    *,
    plan_path: Path,
    plan_sha256: str,
    contract: ModuleType,
) -> dict[str, object]:
    encoded = _read_regular(plan_path, max_bytes=MAX_PLAN_BYTES)
    if not _HEX64.fullmatch(plan_sha256) or sha256_bytes(encoded) != plan_sha256:
        raise BoundedSupervisorError("bounded plan hash drifted")
    plan = _strict_json(encoded, context="bounded plan")
    contract.validate_plan(plan, repository_root=root)
    return plan


def _validate_base_authority(root: Path, plan: Mapping[str, object]) -> None:
    try:
        state = yaml.safe_load(_read_regular(root / "docs/PROJECT_STATE.yaml", max_bytes=65_536))
        compute = yaml.safe_load(_read_regular(root / "manifests/compute.yaml", max_bytes=65_536))
    except yaml.YAMLError:
        raise BoundedSupervisorError("base authorization YAML is invalid") from None
    state_map = _mapping(state, context="project state")
    for permission in (
        "paid_compute_allowed",
        "prototype_execution_allowed",
        "benchmark_execution_allowed",
        "training_allowed",
        "cloud_mutation_allowed",
    ):
        if state_map.get(permission) is not False:
            raise BoundedSupervisorError("base project permissions must remain false")
    substrate = _mapping(state_map.get("planned_execution_substrate"), context="substrate")
    if substrate.get("decision_state") != "bounded-smoke-v1-ready-unauthorized":
        raise BoundedSupervisorError("bounded planned substrate is unavailable")
    entries = _sequence(
        _mapping(compute, context="compute ledger").get("entries"), context="compute"
    )
    expected = {
        "id": "CMP-0001",
        "experiment_id": "EXP-0001",
        "provider": "Lambda On-Demand Cloud",
        "hardware": "gpu_1x_a10",
        "region": "us-east-1",
        "started_at": None,
        "ended_at": None,
        "wall_clock_hours": 0.0,
        "accelerator_hours": 0.0,
        "cost_usd": 0.0,
        "authorization_reference": "AUTH-T07-BOUNDED-SIRA-SMOKE-V1-PENDING",
        "status": "planned",
    }
    if (
        list(entries) != [expected]
        or _mapping(plan.get("identity"), context="plan identity").get("authorized") is not False
    ):
        raise BoundedSupervisorError("planned compute/base plan authorization drifted")


def _normalize_rule(value: object) -> dict[str, object]:
    rule = _mapping(value, context="firewall rule")
    required = {"protocol", "source_network", "description"}
    allowed = required | {"port_range"}
    if not required.issubset(rule) or set(rule) - allowed:
        raise BoundedSupervisorError("firewall rule shape drifted")
    protocol = _text(rule.get("protocol"), context="firewall protocol")
    if protocol not in {"tcp", "udp", "icmp", "all"}:
        raise BoundedSupervisorError("firewall protocol drifted")
    source = _text(rule.get("source_network"), context="firewall source")
    try:
        network = ipaddress.ip_network(source, strict=True)
    except ValueError:
        raise BoundedSupervisorError("firewall source is not a canonical network") from None
    if network.version != 4:
        raise BoundedSupervisorError("firewall source is not IPv4")
    description = rule.get("description")
    if not isinstance(description, str) or len(description) > 512:
        raise BoundedSupervisorError("firewall description drifted")
    output: dict[str, object] = {
        "protocol": protocol,
        "source_network": str(network),
        "description": description,
    }
    ports = rule.get("port_range")
    if protocol == "icmp":
        if "port_range" in rule and ports is not None:
            raise BoundedSupervisorError("ICMP firewall rule has ports")
    else:
        values = _sequence(ports, context="firewall ports")
        if (
            len(values) != 2
            or type(values[0]) is not int
            or type(values[1]) is not int
            or not 1 <= values[0] <= values[1] <= 65_535
        ):
            raise BoundedSupervisorError("firewall port range drifted")
        output["port_range"] = [values[0], values[1]]
    return output


def _firewall_semantic_sha256(rules: object) -> str:
    canonical = sorted(
        (_normalize_rule(item) for item in _sequence(rules, context="firewall rules")),
        key=canonical_json_bytes,
    )
    return sha256_bytes(
        canonical_json_bytes(
            {"canonicalization_version": "t07-firewall-canonical-v1", "rules": canonical}
        )
    )


def _fingerprint(public_key: str) -> str:
    parts = public_key.strip().split()
    if len(parts) < 2:
        raise BoundedSupervisorError("provider public key shape drifted")
    try:
        raw = base64.b64decode(parts[1], validate=True)
    except (ValueError, binascii.Error):
        raise BoundedSupervisorError("provider public key encoding drifted") from None
    encoded = base64.b64encode(hashlib.sha256(raw).digest()).decode().rstrip("=")
    return "SHA256:" + encoded


def _validate_private_binding(
    root: Path,
    document: Mapping[str, object],
    *,
    authorization_reference: str,
) -> None:
    schema, _ = _load_schema(root, PRIVATE_BINDING_SCHEMA_RELATIVE)
    _validate_schema(document, schema, context="private binding")
    if document.get("authorization_reference") != authorization_reference:
        raise BoundedSupervisorError("private binding authorization reference drifted")
    cidr = _text(document.get("source_ipv4_cidr"), context="source IPv4 CIDR")
    try:
        network = ipaddress.ip_network(cidr, strict=True)
    except ValueError:
        raise BoundedSupervisorError("private source is not a canonical CIDR") from None
    if network.version != 4 or network.prefixlen != 32:
        raise BoundedSupervisorError("private source must be one IPv4 /32")
    strict = _normalize_rule(document.get("strict_firewall_rule"))
    owned = _normalize_rule(document.get("owned_ruleset_rule"))
    if (
        strict["protocol"] != "tcp"
        or strict.get("port_range") != [22, 22]
        or strict["source_network"] != cidr
        or owned["protocol"] != "tcp"
        or owned.get("port_range") != [22, 22]
        or owned["source_network"] != cidr
        or not _OWNED_RULESET.fullmatch(str(document.get("owned_ruleset_name")))
        or _firewall_semantic_sha256(document.get("restoration_rules")) != BASELINE_SEMANTIC_SHA256
    ):
        raise BoundedSupervisorError("private security binding drifted")


def materialize_authority(
    root: Path,
    *,
    plan: Mapping[str, object],
    plan_sha256: str,
    expected_commit: str,
    authorization_reference: str,
    source_parameters_path: Path,
    source_parameters_sha256: str,
    restoration_path: Path,
    restoration_sha256: str,
    volume_observer: Callable[[], tuple[VolumeObservation, VolumeObservation]] | None = None,
    utc_now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> dict[str, object]:
    verify_repository_identity(root, expected_commit)
    _validate_base_authority(root, plan)
    if volume_observer is None:
        from giclab.harness.lambda_archive import DiskutilVolumeObserver

        observer: Callable[[], tuple[VolumeObservation, VolumeObservation]] = cast(
            Callable[[], tuple[VolumeObservation, VolumeObservation]],
            DiskutilVolumeObserver(),
        )
    else:
        observer = volume_observer
    from giclab.harness.lambda_archive import _validate_external, _validate_system

    external_pre, system_pre = observer()
    external_floor = _validate_external(
        cast(Any, external_pre), incremental_bytes=MAX_ARCHIVE_BYTES
    )
    _validate_system(cast(Any, system_pre), floor_bytes=MAC_PREWRITE_FLOOR_BYTES)
    if external_floor != EXTERNAL_RETAINED_FLOOR_BYTES:
        raise BoundedSupervisorError("bounded storage floor drifted")
    if (
        _AUTHORIZATION.fullmatch(authorization_reference) is None
        or authorization_reference.endswith("-PENDING")
        or source_parameters_path != root / SOURCE_PARAMETERS_RELATIVE
        or source_parameters_sha256 != SOURCE_PARAMETERS_SHA256
        or restoration_path != root / RESTORATION_RELATIVE
        or restoration_sha256 != RESTORATION_SHA256
    ):
        raise BoundedSupervisorError("authorization materialization input drifted")
    source_encoded = _read_regular(source_parameters_path, max_bytes=1_048_576)
    restoration_encoded = _read_regular(restoration_path, max_bytes=1_048_576)
    if (
        sha256_bytes(source_encoded) != source_parameters_sha256
        or sha256_bytes(restoration_encoded) != restoration_sha256
    ):
        raise BoundedSupervisorError("private source identity drifted")
    source = _strict_json(source_encoded, context="private source parameters")
    restoration = _strict_json(restoration_encoded, context="restoration payload")
    selected = _mapping(source.get("selected_resource"), context="selected private resource")
    cidr = _text(source.get("source_ipv4_cidr"), context="source IPv4 CIDR")
    marker = hashlib.sha256(f"{HOST_RUN_ID}\0{authorization_reference}".encode()).hexdigest()[:12]
    ruleset_name = f"giclab-t07-bounded-{marker}"
    description = f"T07 bounded smoke {marker}"
    strict_source = _normalize_rule(source.get("strict_firewall_rule"))
    owned_source = _normalize_rule(
        _sequence(
            _mapping(source.get("owned_regional_ruleset"), context="owned ruleset").get("rules"),
            context="owned ruleset rules",
        )[0]
    )
    strict_rule = {**strict_source, "description": description}
    owned_rule = {**owned_source, "description": description}
    private_binding: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "plan_id": PLAN_ID,
        "host_run_id": HOST_RUN_ID,
        "authorization_reference": authorization_reference,
        "source_parameter_sha256": source_parameters_sha256,
        "restoration_payload_sha256": restoration_sha256,
        "source_ipv4_cidr": cidr,
        "owned_ruleset_name": ruleset_name,
        "owned_ruleset_description": description,
        "strict_firewall_rule": strict_rule,
        "owned_ruleset_rule": owned_rule,
        "restoration_rules": list(_sequence(restoration.get("rules"), context="restoration rules")),
        "selected_resource": {
            "instance_type": selected.get("instance_type"),
            "region": selected.get("region"),
            "architecture": selected.get("architecture"),
            "image_alias": selected.get("image_alias"),
            "image_family": selected.get("image_family"),
            "image_version": selected.get("image_version"),
            "raw_image_id": selected.get("raw_image_id"),
            "ssh_key_name": selected.get("ssh_key_name"),
            "raw_ssh_key_id": selected.get("raw_ssh_key_id"),
            "ssh_key_fingerprint": selected.get("local_public_key_fingerprint"),
            "price_cents_per_hour": selected.get("price_cents_per_hour"),
        },
    }
    _validate_private_binding(
        root, private_binding, authorization_reference=authorization_reference
    )
    private_encoded = canonical_json_bytes(private_binding)
    private_sha256 = sha256_bytes(private_encoded)
    limits = _mapping(plan.get("limits"), context="plan limits")
    started = utc_now().astimezone(UTC)
    if started.microsecond == 0:
        started = started.replace(microsecond=1)
    expires = started + timedelta(seconds=3_600)
    authorization: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "authorized": True,
        "authorization_reference": authorization_reference,
        "execution_commit": expected_commit,
        "branch": BRANCH,
        "plan_id": PLAN_ID,
        "plan_sha256": plan_sha256,
        "host_run_id": HOST_RUN_ID,
        "condition_run_ids": [
            "RUN-T07-BOUNDED-SIRA-REACTIVE-0001",
            "RUN-T07-BOUNDED-SIRA-SIMULATIVE-0001",
        ],
        "supervised_wall_started_at_utc": _utc_text(started),
        "expires_at_utc": _utc_text(expires),
        "private_binding_sha256": private_sha256,
        "limits_sha256": sha256_bytes(canonical_json_bytes(dict(limits))),
        "pricing": {
            "model": "gpt-4o-2024-11-20",
            "service_tier": "standard",
            "input_usd_per_million": 2.5,
            "cached_input_usd_per_million": 1.25,
            "output_usd_per_million": 10.0,
            "lambda_cents_per_hour": 129,
        },
        "permissions": {
            "lambda_read_only_gets": 13,
            "user_cloud_mutations": True,
            "paid_compute": True,
            "prototype_execution": True,
            "scientific_interpretation": False,
            "training": False,
            "pilot": False,
            "ssh": False,
        },
        "user_present": True,
        "manual_termination_path_confirmed": True,
    }
    authorization_schema, _ = _load_schema(root, AUTHORIZATION_SCHEMA_RELATIVE)
    _validate_schema(authorization, authorization_schema, context="authorization overlay")
    run_root = root / RUN_ROOT_RELATIVE
    if run_root.exists() or run_root.is_symlink():
        raise BoundedSupervisorError("bounded run identity is not fresh")
    run_root.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    run_root.mkdir(mode=0o700, exist_ok=False)
    (run_root / "responses").mkdir(mode=0o700)
    authorization_encoded = canonical_json_bytes(authorization)
    _write_exclusive(run_root / "private-binding.json", private_encoded)
    _write_exclusive(run_root / "authorization.json", authorization_encoded)
    state: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "plan_id": PLAN_ID,
        "run_id": HOST_RUN_ID,
        "authorization_reference": authorization_reference,
        "authorization_sha256": sha256_bytes(authorization_encoded),
        "private_binding_sha256": private_sha256,
        "status": "materialized",
        "next_phase": "prelaunch",
        "request_count": 0,
        "attempted_request_ordinals": [],
        "response_bytes": 0,
        "event_count": 0,
        "last_request_monotonic_ns": None,
        "selected_image_id": None,
        "owned_ruleset_id": None,
        "bound_instance_id": None,
        "cleanup_origin_phase": None,
        "termination_verified": False,
    }
    _write_exclusive(run_root / "observer-state.json", canonical_json_bytes(state))
    ledger_schema, _ = _load_schema(root, LEDGER_SCHEMA_RELATIVE)
    ledger = FsyncLedger(
        run_root / "request-ledger.jsonl",
        schema=ledger_schema,
        authorization_reference=authorization_reference,
        create=True,
    )
    ledger.append("run_materialized", phase="materialize")
    state["event_count"] = ledger.event_count
    _atomic_write(run_root / "observer-state.json", canonical_json_bytes(state))
    summary = {
        "schema_version": SCHEMA_VERSION,
        "plan_id": PLAN_ID,
        "run_id": HOST_RUN_ID,
        "authorization_reference": authorization_reference,
        "authorization_path": str(AUTHORIZATION_RELATIVE),
        "authorization_bytes": len(authorization_encoded),
        "authorization_sha256": sha256_bytes(authorization_encoded),
        "private_binding_path": str(PRIVATE_BINDING_RELATIVE),
        "private_binding_bytes": len(private_encoded),
        "private_binding_sha256": private_sha256,
        "ledger_path": str(LEDGER_RELATIVE),
        "ledger_capacity_reserved_bytes": MAX_LEDGER_BYTES,
        "external_volume_uuid": external_pre.volume_uuid,
        "external_physical_store_uuid": external_pre.physical_store_uuid,
        "external_prewrite_free_bytes": external_pre.free_bytes,
        "mac_prewrite_free_bytes": system_pre.free_bytes,
        "secret_values_retained": False,
    }
    _write_exclusive(
        run_root / "MATERIALIZATION_SUMMARY.json", canonical_json_bytes(summary), mode=0o644
    )
    return summary


class FsyncLedger:
    def __init__(
        self,
        path: Path,
        *,
        schema: Mapping[str, object],
        authorization_reference: str,
        create: bool = False,
    ) -> None:
        self.path = path
        self.schema = schema
        self.authorization_reference = authorization_reference
        if create:
            descriptor = os.open(
                path,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
                0o600,
            )
            os.close(descriptor)
        self.event_count = 0
        self.events: list[dict[str, object]] = []
        self.sent_ordinals: set[int] = set()
        self._load()

    def _load(self) -> None:
        encoded = _read_regular(self.path, max_bytes=MAX_LEDGER_BYTES)
        if not encoded:
            self.event_count = 0
            self.events = []
            self.sent_ordinals = set()
            return
        lines = encoded.splitlines(keepends=True)
        if not all(line.endswith(b"\n") for line in lines):
            raise BoundedSupervisorError("observer ledger has an incomplete event")
        for expected, line in enumerate(lines, start=1):
            event = _strict_json(line, context="observer ledger event")
            _validate_schema(event, self.schema, context="observer ledger event")
            if (
                event.get("event_sequence") != expected
                or event.get("authorization_reference") != self.authorization_reference
            ):
                raise BoundedSupervisorError("observer ledger sequence or binding drifted")
            if event.get("event_type") == "request_send_started":
                ordinal = event.get("request_ordinal")
                if type(ordinal) is not int or ordinal in self.sent_ordinals:
                    raise BoundedSupervisorError("observer ledger replays a request ordinal")
                self.sent_ordinals.add(ordinal)
            self.events.append(event)
        self.event_count = len(lines)

    def append(
        self,
        event_type: str,
        *,
        phase: str,
        request_ordinal: int | None = None,
        path: str | None = None,
        bytes_received: int = 0,
        http_status: int | None = None,
        content_type: str | None = None,
        elapsed_ms: int | None = None,
        failure_stage: str | None = None,
        failure_class: str | None = None,
        monotonic_ns: int | None = None,
        utc_now: datetime | None = None,
    ) -> None:
        if self.event_count >= MAX_LEDGER_EVENTS:
            raise BoundedSupervisorError("observer ledger event cap exhausted")
        if event_type == "request_send_started" and (
            request_ordinal is None or request_ordinal in self.sent_ordinals
        ):
            raise BoundedSupervisorError("observer request ordinal was already sent")
        event = {
            "schema_version": SCHEMA_VERSION,
            "run_id": HOST_RUN_ID,
            "plan_id": PLAN_ID,
            "authorization_reference": self.authorization_reference,
            "event_sequence": self.event_count + 1,
            "event_type": event_type,
            "phase": phase,
            "monotonic_timestamp_ns": time.monotonic_ns() if monotonic_ns is None else monotonic_ns,
            "wall_timestamp_utc": _utc_text(datetime.now(UTC) if utc_now is None else utc_now),
            "request_ordinal": request_ordinal,
            "method": "GET" if request_ordinal is not None else None,
            "scheme": "https" if request_ordinal is not None else None,
            "host": "cloud.lambda.ai" if request_ordinal is not None else None,
            "path": path,
            "bytes_received": bytes_received,
            "http_status": http_status,
            "content_type": content_type,
            "elapsed_ms": elapsed_ms,
            "failure_stage": failure_stage,
            "failure_class": failure_class,
            "retry_count": 0,
            "pagination_request": False,
        }
        _validate_schema(event, self.schema, context="observer ledger event")
        encoded = canonical_json_bytes(event)
        if len(encoded) > MAX_LEDGER_EVENT_BYTES or self.path.stat().st_size + len(encoded) > (
            MAX_LEDGER_BYTES
        ):
            raise BoundedSupervisorError("observer ledger byte cap exhausted")
        descriptor = os.open(
            self.path,
            os.O_WRONLY | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0),
        )
        try:
            written = os.write(descriptor, encoded)
            if written != len(encoded):
                raise BoundedSupervisorError("observer ledger append was incomplete")
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        self.event_count += 1
        self.events.append(event)
        if event_type == "request_send_started" and request_ordinal is not None:
            self.sent_ordinals.add(request_ordinal)


class LambdaHttpsBoundedTransport:
    """One exact-host, non-redirecting, no-retry in-process HTTPS GET."""

    def __init__(
        self,
        *,
        context: ssl.SSLContext | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.context = context or ssl.create_default_context()
        self.clock = clock

    def fetch(
        self,
        path: str,
        *,
        credential: str,
        timeout_seconds: float,
        max_response_bytes: int,
    ) -> HttpResponse:
        if path not in ENDPOINT_SCHEMAS:
            raise TransportFailure("request_write", "path_not_allowlisted")
        if (
            not credential
            or len(credential) > 4_096
            or any(marker in credential for marker in ("\r", "\n", "\x00"))
        ):
            raise TransportFailure("secret_source", "secret_malformed")
        if not 0 < timeout_seconds <= MAX_REQUEST_SECONDS:
            raise TransportFailure("unknown", "request_deadline_invalid")
        started = self.clock()
        body = bytearray()
        connection = http.client.HTTPSConnection(
            "cloud.lambda.ai", 443, timeout=timeout_seconds, context=self.context
        )
        try:
            try:
                connection.connect()
            except socket.gaierror:
                raise TransportFailure("dns", "dns_failure") from None
            except ssl.SSLError:
                raise TransportFailure("tls_handshake", "tls_failure") from None
            except OSError:
                raise TransportFailure("tcp_connect", "tcp_connect_failure") from None
            try:
                connection.request(
                    "GET",
                    path,
                    body=None,
                    headers={
                        "Accept": "application/json",
                        "Authorization": f"Bearer {credential}",
                        "User-Agent": "giclab-t07-bounded-observer-v1/1",
                    },
                )
                response = connection.getresponse()
            except (OSError, ssl.SSLError, http.client.HTTPException):
                raise TransportFailure("request_write", "request_or_headers_failure") from None
            content_type = (
                response.getheader("Content-Type", "").split(";", 1)[0].strip().casefold()
            )
            while True:
                try:
                    chunk = response.read(min(65_536, max_response_bytes + 1 - len(body)))
                except (OSError, ssl.SSLError, http.client.HTTPException):
                    raise TransportFailure(
                        "response_body",
                        "response_body_failure",
                        len(body),
                        min(int((self.clock() - started) * 1_000), 60_000),
                    ) from None
                if not chunk:
                    break
                body.extend(chunk)
                if len(body) > max_response_bytes:
                    raise TransportFailure(
                        "response_size",
                        "response_too_large",
                        len(body),
                        min(int((self.clock() - started) * 1_000), 60_000),
                    )
            return HttpResponse(
                response.status,
                content_type,
                bytes(body),
                min(int((self.clock() - started) * 1_000), 60_000),
            )
        finally:
            connection.close()


def _load_state(root: Path) -> dict[str, object]:
    return _strict_json(
        _read_regular(root / STATE_RELATIVE, max_bytes=65_536), context="observer state"
    )


def _validate_authority_inputs(
    root: Path,
    *,
    plan: Mapping[str, object],
    plan_sha256: str,
    authorization_path: Path,
    authorization_sha256: str,
    private_binding_path: Path,
    private_binding_sha256: str,
    utc_now: Callable[[], datetime],
    require_live: bool = True,
) -> tuple[dict[str, object], dict[str, object]]:
    if (
        authorization_path != root / AUTHORIZATION_RELATIVE
        or private_binding_path != root / PRIVATE_BINDING_RELATIVE
        or not _HEX64.fullmatch(authorization_sha256)
        or not _HEX64.fullmatch(private_binding_sha256)
        or stat.S_IMODE(authorization_path.lstat().st_mode) != 0o600
        or stat.S_IMODE(private_binding_path.lstat().st_mode) != 0o600
    ):
        raise BoundedSupervisorError("authority path or hash input drifted")
    authorization_encoded = _read_regular(authorization_path, max_bytes=MAX_AUTHORIZATION_BYTES)
    private_encoded = _read_regular(private_binding_path, max_bytes=MAX_PRIVATE_FILE_BYTES)
    if (
        sha256_bytes(authorization_encoded) != authorization_sha256
        or sha256_bytes(private_encoded) != private_binding_sha256
    ):
        raise BoundedSupervisorError("authority artifact hash drifted")
    authorization = _strict_json(authorization_encoded, context="authorization overlay")
    private = _strict_json(private_encoded, context="private binding")
    auth_schema, _ = _load_schema(root, AUTHORIZATION_SCHEMA_RELATIVE)
    _validate_schema(authorization, auth_schema, context="authorization overlay")
    if (
        authorization.get("plan_sha256") != plan_sha256
        or authorization.get("private_binding_sha256") != private_binding_sha256
        or authorization.get("limits_sha256")
        != sha256_bytes(canonical_json_bytes(dict(_mapping(plan.get("limits"), context="limits"))))
    ):
        raise BoundedSupervisorError("authorization overlay binding drifted")
    started = _parse_utc(
        authorization.get("supervised_wall_started_at_utc"), context="supervised wall start"
    )
    expires = _parse_utc(authorization.get("expires_at_utc"), context="authorization expiry")
    now = utc_now().astimezone(UTC)
    if (
        expires - started != timedelta(seconds=3_600)
        or now < started
        or (require_live and now >= expires)
    ):
        raise BoundedSupervisorError("bounded authorization wall is unavailable")
    _validate_private_binding(
        root,
        private,
        authorization_reference=_text(
            authorization.get("authorization_reference"), context="authorization reference"
        ),
    )
    _validate_base_authority(root, plan)
    return authorization, private


def _pagination_present(envelope: Mapping[str, object]) -> bool:
    for name in ("page_token", "next_page_token", "continuation_token", "next"):
        if name in envelope and envelope[name] not in (None, "", False):
            return True
    return False


def _endpoint_document(root: Path, path: str, encoded: bytes) -> dict[str, object]:
    document = _strict_json(encoded, context="provider response")
    if _pagination_present(document):
        raise BoundedSupervisorError("provider response contains pagination")
    schema, _ = _load_schema(root, ENDPOINT_SCHEMA_ROOT / ENDPOINT_SCHEMAS[path])
    _validate_schema(document, schema, context="provider response")
    return document


def _schema_reference(root_schema: Mapping[str, object], reference: object) -> Mapping[str, object]:
    if not isinstance(reference, str) or not reference.startswith("#/"):
        raise BoundedSupervisorError("provider projection schema reference is unsupported")
    current: object = root_schema
    for component in reference[2:].split("/"):
        if not isinstance(current, Mapping) or component not in current:
            raise BoundedSupervisorError("provider projection schema reference is invalid")
        current = current[component]
    return _mapping(current, context="provider projection schema")


def _sensitive_provider_key(name: str) -> bool:
    normalized = re.sub(r"[^a-z0-9]+", "_", name.casefold()).strip("_")
    return (
        normalized in _SENSITIVE_PROVIDER_KEYS
        or any(
            marker in normalized
            for marker in ("authorization", "cookie", "credential", "password", "secret", "token")
        )
        or re.search(r"(?:^|_)(?:api|access|private)_?key(?:_|$)", normalized) is not None
    )


def _mapping_uses_sensitive_discriminator(value: Mapping[object, object]) -> bool:
    """Reject generic key/value records that semantically name a secret field."""

    return any(
        isinstance(key, str)
        and key.casefold() in _SENSITIVE_PROVIDER_DISCRIMINATORS
        and isinstance(child, str)
        and _sensitive_provider_key(child)
        for key, child in value.items()
    )


def _project_to_declared_schema(
    value: object,
    schema: Mapping[str, object],
    *,
    root_schema: Mapping[str, object],
) -> object:
    if "$ref" in schema:
        schema = _schema_reference(root_schema, schema["$ref"])
    if isinstance(value, Mapping):
        if _mapping_uses_sensitive_discriminator(value):
            return _DROP_PROVIDER_VALUE
        properties_raw = schema.get("properties", {})
        properties = properties_raw if isinstance(properties_raw, Mapping) else {}
        additional = schema.get("additionalProperties")
        output: dict[str, object] = {}
        for key, child in value.items():
            if not isinstance(key, str) or _sensitive_provider_key(key):
                continue
            child_schema = properties.get(key)
            if child_schema is None and isinstance(additional, Mapping):
                child_schema = additional
            if not isinstance(child_schema, Mapping):
                continue
            projected_value = _project_to_declared_schema(
                child, child_schema, root_schema=root_schema
            )
            if projected_value is not _DROP_PROVIDER_VALUE:
                output[key] = projected_value
        return output
    if isinstance(value, list):
        items = schema.get("items")
        prefix = schema.get("prefixItems")
        projected_items: list[object] = []
        for index, child in enumerate(value):
            item_schema: object = items
            if (
                isinstance(prefix, Sequence)
                and not isinstance(prefix, (str, bytes))
                and index < len(prefix)
            ):
                item_schema = prefix[index]
            if not isinstance(item_schema, Mapping):
                continue
            projected_child = _project_to_declared_schema(
                child, item_schema, root_schema=root_schema
            )
            if projected_child is not _DROP_PROVIDER_VALUE:
                projected_items.append(projected_child)
        return projected_items
    return value


def _sanitized_provider_receipt(
    root: Path,
    *,
    path: str,
    document: Mapping[str, object],
    received_bytes: int,
    credential: str,
) -> bytes:
    schema, _ = _load_schema(root, ENDPOINT_SCHEMA_ROOT / ENDPOINT_SCHEMAS[path])
    projection = _project_to_declared_schema(document, schema, root_schema=schema)
    if projection is _DROP_PROVIDER_VALUE:
        raise BoundedSupervisorError("provider response root is semantically sensitive")
    encoded = canonical_json_bytes(
        {
            "schema_version": SCHEMA_VERSION,
            "path": path,
            "received_bytes": received_bytes,
            "projection": projection,
            "unknown_additive_fields_retained": False,
            "credential_fields_retained": False,
        }
    )
    if credential.encode("utf-8") in encoded or _contains_artifact_secret(encoded):
        raise BoundedSupervisorError("sanitized provider receipt contains secret-shaped data")
    return encoded


def _region_name(value: object) -> str:
    return _text(_mapping(value, context="region").get("name"), context="region name")


def _nonterminal_instances(rows: Sequence[object]) -> list[Mapping[str, object]]:
    terminal = {"terminated", "preempted"}
    return [
        _mapping(row, context="instance")
        for row in rows
        if _mapping(row, context="instance").get("status") not in terminal
    ]


def _validate_prelaunch(
    responses: Mapping[str, Mapping[str, object]],
    private: Mapping[str, object],
    state: dict[str, object],
) -> dict[str, object]:
    selected = _mapping(private.get("selected_resource"), context="selected resource")
    types = _mapping(responses["/api/v1/instance-types"].get("data"), context="types")
    row = _mapping(types.get("gpu_1x_a10"), context="selected type")
    type_detail = _mapping(row.get("instance_type"), context="selected type detail")
    capacity = {
        _region_name(item)
        for item in _sequence(row.get("regions_with_capacity_available"), context="capacity")
    }
    if (
        type_detail.get("name") != "gpu_1x_a10"
        or type_detail.get("architecture") != "x86_64"
        or type_detail.get("price_cents_per_hour") != 129
        or "us-east-1" not in capacity
    ):
        raise BoundedSupervisorError("selected instance type/capacity/price drifted")
    regions = {
        _region_name(item)
        for item in _sequence(responses["/api/v1/regions"].get("data"), context="regions")
    }
    if "us-east-1" not in regions:
        raise BoundedSupervisorError("selected region is unavailable")
    images = [
        _mapping(item, context="image")
        for item in _sequence(responses["/api/v1/images"].get("data"), context="images")
    ]
    matching_images = [
        item
        for item in images
        if item.get("id") == selected.get("raw_image_id")
        and item.get("family") == "lambda-stack-22-04"
        and item.get("version") == "22.4.5-2141"
        and item.get("architecture") == "x86_64"
        and _region_name(item.get("region")) == "us-east-1"
    ]
    if len(matching_images) != 1:
        raise BoundedSupervisorError("selected image identity is unavailable")
    keys = [
        _mapping(item, context="SSH key")
        for item in _sequence(responses["/api/v1/ssh-keys"].get("data"), context="SSH keys")
    ]
    matching_keys = [
        item
        for item in keys
        if item.get("id") == selected.get("raw_ssh_key_id")
        and item.get("name") == "fractal-lambda-codex"
        and _fingerprint(_text(item.get("public_key"), context="public key"))
        == selected.get("ssh_key_fingerprint")
    ]
    if len(matching_keys) != 1:
        raise BoundedSupervisorError("selected SSH key fingerprint is unavailable")
    rulesets = [
        _mapping(item, context="ruleset")
        for item in _sequence(
            responses["/api/v1/firewall-rulesets"].get("data"), context="rulesets"
        )
    ]
    if any(item.get("name") == private.get("owned_ruleset_name") for item in rulesets):
        raise BoundedSupervisorError("owned ruleset identity is not fresh")
    global_data = _mapping(
        responses["/api/v1/firewall-rulesets/global"].get("data"), context="global firewall"
    )
    if _firewall_semantic_sha256(global_data.get("rules")) != BASELINE_SEMANTIC_SHA256:
        raise BoundedSupervisorError("global firewall differs from the sealed baseline")
    instances = _sequence(responses["/api/v1/instances"].get("data"), context="instances")
    if _nonterminal_instances(instances):
        raise BoundedSupervisorError("a prior nonterminal instance is unresolved")
    state["selected_image_id"] = selected.get("raw_image_id")
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": "prelaunch",
        "selected_resource_available": True,
        "capacity_available": True,
        "price_cents_per_hour": 129,
        "prior_nonterminal_instance_count": 0,
        "global_firewall_baseline_sha256": BASELINE_SEMANTIC_SHA256,
        "selected_image_id_sha256": sha256_bytes(
            _text(selected.get("raw_image_id"), context="raw image ID").encode()
        ),
        "selected_ssh_key_identity_sha256": sha256_bytes(
            (
                _text(selected.get("raw_ssh_key_id"), context="raw SSH key ID")
                + "\0"
                + _text(selected.get("ssh_key_fingerprint"), context="SSH fingerprint")
            ).encode()
        ),
    }


def _validate_security(
    responses: Mapping[str, Mapping[str, object]],
    private: Mapping[str, object],
    state: dict[str, object],
) -> dict[str, object]:
    rows = [
        _mapping(item, context="ruleset")
        for item in _sequence(
            responses["/api/v1/firewall-rulesets"].get("data"), context="rulesets"
        )
    ]
    matches = [item for item in rows if item.get("name") == private.get("owned_ruleset_name")]
    if len(matches) != 1:
        raise BoundedSupervisorError("exactly one owned ruleset was not observed")
    match = matches[0]
    rules = _sequence(match.get("rules"), context="owned ruleset rules")
    if (
        _region_name(match.get("region")) != "us-east-1"
        or len(rules) != 1
        or _normalize_rule(rules[0]) != _normalize_rule(private.get("owned_ruleset_rule"))
        or list(_sequence(match.get("instance_ids"), context="ruleset instances"))
    ):
        raise BoundedSupervisorError("owned ruleset security contract drifted")
    ruleset_id = _text(match.get("id"), context="ruleset ID")
    global_data = _mapping(
        responses["/api/v1/firewall-rulesets/global"].get("data"), context="global firewall"
    )
    global_rules = _sequence(global_data.get("rules"), context="global firewall rules")
    if len(global_rules) != 1 or _normalize_rule(global_rules[0]) != _normalize_rule(
        private.get("strict_firewall_rule")
    ):
        raise BoundedSupervisorError("temporary global firewall is not exact")
    state["owned_ruleset_id"] = ruleset_id
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": "security",
        "owned_ruleset_bound_before_launch": True,
        "owned_ruleset_id_sha256": sha256_bytes(ruleset_id.encode()),
        "global_firewall_restricted": True,
    }


def _validate_post_launch(
    responses: Mapping[str, Mapping[str, object]],
    private: Mapping[str, object],
    state: dict[str, object],
) -> dict[str, object]:
    ruleset_id = _text(state.get("owned_ruleset_id"), context="bound ruleset ID")
    rows = _nonterminal_instances(
        _sequence(responses["/api/v1/instances"].get("data"), context="instances")
    )
    if len(rows) != 1:
        raise BoundedSupervisorError(
            "post-launch observation requires exactly one total nonterminal instance"
        )
    matches: list[Mapping[str, object]] = []
    for item in rows:
        attached = {
            _text(_mapping(value, context="attached ruleset").get("id"), context="ruleset ID")
            for value in _sequence(item.get("firewall_rulesets"), context="attached rulesets")
        }
        instance_type = _mapping(item.get("instance_type"), context="instance type")
        terminate = _mapping(
            _mapping(item.get("actions"), context="instance actions").get("terminate"),
            context="terminate action",
        )
        if (
            item.get("status") == "active"
            and instance_type.get("name") == "gpu_1x_a10"
            and instance_type.get("architecture") == "x86_64"
            and _region_name(item.get("region")) == "us-east-1"
            and list(_sequence(item.get("ssh_key_names"), context="instance SSH keys"))
            == ["fractal-lambda-codex"]
            and not list(_sequence(item.get("file_system_names"), context="file systems"))
            and item.get("file_system_mounts") in (None, [])
            and attached == {ruleset_id}
            and terminate.get("available") is True
        ):
            matches.append(item)
    if len(matches) != 1 or state.get("bound_instance_id") is not None:
        raise BoundedSupervisorError("exactly one owned active instance was not observed")
    instance_id = _text(matches[0].get("id"), context="instance ID")
    state["bound_instance_id"] = instance_id
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": "post_launch",
        "owned_instance_match_count": 1,
        "bound_instance_id_sha256": sha256_bytes(instance_id.encode()),
        "termination_action_available": True,
        "persistent_filesystem_count": 0,
    }


def _validate_termination(
    responses: Mapping[str, Mapping[str, object]],
    private: Mapping[str, object],
    state: dict[str, object],
) -> dict[str, object]:
    del private
    instances = [
        _mapping(item, context="instance")
        for item in _sequence(responses["/api/v1/instances"].get("data"), context="instances")
    ]
    bound_value = state.get("bound_instance_id")
    instance_id: str | None
    if isinstance(bound_value, str) and bound_value:
        instance_id = bound_value
        if _nonterminal_instances(instances):
            raise BoundedSupervisorError(
                "a nonterminal instance remains after the termination step"
            )
        bound_rows = [item for item in instances if item.get("id") == instance_id]
        if len(bound_rows) > 1 or (
            bound_rows and bound_rows[0].get("status") not in {"terminated", "preempted"}
        ):
            raise BoundedSupervisorError("bound instance is not terminal or absent")
    else:
        if _nonterminal_instances(instances):
            raise BoundedSupervisorError(
                "an unbound nonterminal instance remains after the launch step"
            )
        ruleset_id = _text(state.get("owned_ruleset_id"), context="bound ruleset ID")
        candidates: list[Mapping[str, object]] = []
        for item in instances:
            attached = {
                _text(_mapping(value, context="attached ruleset").get("id"), context="ruleset ID")
                for value in _sequence(item.get("firewall_rulesets"), context="attached rulesets")
            }
            instance_type = _mapping(item.get("instance_type"), context="instance type")
            if (
                instance_type.get("name") == "gpu_1x_a10"
                and instance_type.get("architecture") == "x86_64"
                and _region_name(item.get("region")) == "us-east-1"
                and list(_sequence(item.get("ssh_key_names"), context="instance SSH keys"))
                == ["fractal-lambda-codex"]
                and not list(_sequence(item.get("file_system_names"), context="file systems"))
                and item.get("file_system_mounts") in (None, [])
                and attached == {ruleset_id}
            ):
                candidates.append(item)
        if len(candidates) > 1:
            raise BoundedSupervisorError("multiple possible owned instances were observed")
        instance_id = _text(candidates[0].get("id"), context="instance ID") if candidates else None
        state["bound_instance_id"] = instance_id
    state["termination_verified"] = True
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": "termination",
        "provider_terminal_or_absent": True,
        "billing_stopped": True,
        "bound_instance_id_sha256": (
            sha256_bytes(instance_id.encode()) if instance_id is not None else None
        ),
        "identity_recovered_during_cleanup": bound_value is None and instance_id is not None,
    }


def _validate_terminal(
    responses: Mapping[str, Mapping[str, object]],
    private: Mapping[str, object],
    state: dict[str, object],
) -> dict[str, object]:
    instance_id = state.get("bound_instance_id")
    ruleset_id = state.get("owned_ruleset_id")
    rulesets = [
        _mapping(item, context="ruleset")
        for item in _sequence(
            responses["/api/v1/firewall-rulesets"].get("data"), context="rulesets"
        )
    ]
    if any(
        (isinstance(ruleset_id, str) and item.get("id") == ruleset_id)
        or item.get("name") == private.get("owned_ruleset_name")
        for item in rulesets
    ):
        raise BoundedSupervisorError("owned ruleset remains present")
    global_data = _mapping(
        responses["/api/v1/firewall-rulesets/global"].get("data"), context="global firewall"
    )
    if _firewall_semantic_sha256(global_data.get("rules")) != BASELINE_SEMANTIC_SHA256:
        raise BoundedSupervisorError("global firewall baseline was not restored")
    no_launch_cleanup = state.get("cleanup_origin_phase") in {"prelaunch", "security"}
    termination_verified = state.get("termination_verified") is True or no_launch_cleanup
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": "terminal",
        "provider_termination_previously_verified": termination_verified,
        "owned_regional_ruleset_match_count": 0,
        "global_firewall_baseline_sha256": BASELINE_SEMANTIC_SHA256,
        "bound_instance_id_sha256": (
            sha256_bytes(instance_id.encode()) if isinstance(instance_id, str) else None
        ),
        "owned_ruleset_id_sha256": (
            sha256_bytes(ruleset_id.encode()) if isinstance(ruleset_id, str) else None
        ),
    }


_PHASE_VALIDATORS: Final = {
    "prelaunch": _validate_prelaunch,
    "security": _validate_security,
    "post_launch": _validate_post_launch,
    "termination": _validate_termination,
    "terminal": _validate_terminal,
}


def _enter_cleanup_only(state: dict[str, object], *, failed_phase: str) -> None:
    if state.get("cleanup_origin_phase") is None:
        state["cleanup_origin_phase"] = failed_phase
    state["status"] = (
        "cleanup_required" if CLEANUP_NEXT_PHASE[failed_phase] else "cleanup_incomplete"
    )
    state["next_phase"] = CLEANUP_NEXT_PHASE[failed_phase]


def execute_observer_phase(
    root: Path,
    *,
    plan: Mapping[str, object],
    plan_sha256: str,
    expected_commit: str,
    phase: str,
    authorization_path: Path,
    authorization_sha256: str,
    private_binding_path: Path,
    private_binding_sha256: str,
    transport: ReadOnlyTransport,
    credential_provider: Callable[[], str | None],
    monotonic_ns: Callable[[], int] = time.monotonic_ns,
    utc_now: Callable[[], datetime] = lambda: datetime.now(UTC),
    sleeper: Callable[[float], None] = time.sleep,
) -> dict[str, object]:
    if phase not in PHASE_REQUESTS:
        raise BoundedSupervisorError("observer phase is not allowlisted")
    verify_repository_identity(root, expected_commit)
    authorization, private = _validate_authority_inputs(
        root,
        plan=plan,
        plan_sha256=plan_sha256,
        authorization_path=authorization_path,
        authorization_sha256=authorization_sha256,
        private_binding_path=private_binding_path,
        private_binding_sha256=private_binding_sha256,
        utc_now=utc_now,
        require_live=phase not in {"termination", "terminal"},
    )
    state = _load_state(root)
    if (
        state.get("next_phase") != phase
        or state.get("status") in {"complete", "cleanup_complete", "cleanup_incomplete"}
        or state.get("authorization_sha256") != authorization_sha256
        or state.get("private_binding_sha256") != private_binding_sha256
    ):
        raise BoundedSupervisorError("observer phase/state identity drifted")
    ledger_schema, _ = _load_schema(root, LEDGER_SCHEMA_RELATIVE)
    ledger = FsyncLedger(
        root / LEDGER_RELATIVE,
        schema=ledger_schema,
        authorization_reference=_text(
            authorization.get("authorization_reference"), context="authorization reference"
        ),
    )
    attempted_raw = state.get("attempted_request_ordinals")
    if (
        not isinstance(attempted_raw, list)
        or any(type(value) is not int for value in attempted_raw)
        or len(set(attempted_raw)) != len(attempted_raw)
        or set(attempted_raw) != ledger.sent_ordinals
        or state.get("request_count") != len(attempted_raw)
        or len(attempted_raw) > MAX_REQUESTS
        or any(
            ordinal in ledger.sent_ordinals
            for ordinal in range(
                PHASE_START_ORDINAL[phase],
                PHASE_START_ORDINAL[phase] + len(PHASE_REQUESTS[phase]),
            )
        )
    ):
        raise BoundedSupervisorError("observer request history drifted or would replay")
    if state.get("event_count") != ledger.event_count:
        raise BoundedSupervisorError("observer state/ledger event count drifted")
    cleanup_mode = state.get("status") == "cleanup_required"
    if cleanup_mode and phase not in {"termination", "terminal"}:
        raise BoundedSupervisorError("cleanup-only continuation cannot resume execution phases")
    ledger.append("phase_started", phase=phase, monotonic_ns=monotonic_ns(), utc_now=utc_now())
    state["status"] = f"{phase}_running"
    state["event_count"] = ledger.event_count
    _atomic_write(root / STATE_RELATIVE, canonical_json_bytes(state))
    try:
        credential = credential_provider()
    except BaseException:
        ledger.append(
            "phase_failed",
            phase=phase,
            failure_stage="secret_source",
            failure_class="secret_channel_failure",
            monotonic_ns=monotonic_ns(),
            utc_now=utc_now(),
        )
        _enter_cleanup_only(state, failed_phase=phase)
        state["event_count"] = ledger.event_count
        _atomic_write(root / STATE_RELATIVE, canonical_json_bytes(state))
        raise BoundedSupervisorError("Lambda observer credential channel failed") from None
    if (
        not isinstance(credential, str)
        or not credential
        or len(credential) > 4_096
        or any(marker in credential for marker in ("\r", "\n", "\x00"))
    ):
        ledger.append(
            "phase_failed",
            phase=phase,
            failure_stage="secret_source",
            failure_class="secret_unavailable_or_malformed",
            monotonic_ns=monotonic_ns(),
            utc_now=utc_now(),
        )
        _enter_cleanup_only(state, failed_phase=phase)
        state["event_count"] = ledger.event_count
        _atomic_write(root / STATE_RELATIVE, canonical_json_bytes(state))
        raise BoundedSupervisorError("Lambda observer credential is unavailable")
    phase_responses: dict[str, Mapping[str, object]] = {}
    active_ordinal: int | None = None
    active_path: str | None = None
    active_terminal_recorded = True
    response_completed_at: datetime | None = None
    try:
        for offset, path in enumerate(PHASE_REQUESTS[phase]):
            ordinal = PHASE_START_ORDINAL[phase] + offset
            active_ordinal = ordinal
            active_path = path
            active_terminal_recorded = True
            last_ns = state.get("last_request_monotonic_ns")
            now_ns = monotonic_ns()
            if type(last_ns) is int:
                wait_ns = MIN_REQUEST_SPACING_NS - (now_ns - last_ns)
                if wait_ns > 0:
                    sleeper(wait_ns / 1_000_000_000)
                    now_ns = monotonic_ns()
            ledger.append(
                "request_intent_committed",
                phase=phase,
                request_ordinal=ordinal,
                path=path,
                monotonic_ns=now_ns,
                utc_now=utc_now(),
            )
            ledger.append(
                "request_send_started",
                phase=phase,
                request_ordinal=ordinal,
                path=path,
                monotonic_ns=monotonic_ns(),
                utc_now=utc_now(),
            )
            active_terminal_recorded = False
            attempted = list(attempted_raw)
            attempted.append(ordinal)
            attempted_raw = attempted
            state["attempted_request_ordinals"] = attempted
            state["request_count"] = len(attempted)
            state["event_count"] = ledger.event_count
            _atomic_write(root / STATE_RELATIVE, canonical_json_bytes(state))
            try:
                response = transport.fetch(
                    path,
                    credential=credential,
                    timeout_seconds=MAX_REQUEST_SECONDS,
                    max_response_bytes=MAX_RESPONSE_BYTES,
                )
            except TransportFailure as failure:
                event_type = (
                    "request_failed"
                    if failure.stage in {"secret_source", "dns", "tcp_connect", "tls_handshake"}
                    else "request_outcome_unknown_after_send"
                )
                ledger.append(
                    event_type,
                    phase=phase,
                    request_ordinal=ordinal,
                    path=path,
                    bytes_received=min(failure.bytes_received, MAX_RESPONSE_BYTES),
                    elapsed_ms=min(failure.elapsed_ms, 60_000),
                    failure_stage=failure.stage,
                    failure_class=failure.classification,
                    monotonic_ns=monotonic_ns(),
                    utc_now=utc_now(),
                )
                active_terminal_recorded = True
                raise BoundedSupervisorError("bounded observer transport failed") from None
            normalized = response.content_type.split(";", 1)[0].strip().casefold()
            failure_stage: str | None = None
            failure_class: str | None = None
            if 300 <= response.status <= 399:
                failure_stage, failure_class = "redirect", "http_redirect"
            elif response.status == 429:
                failure_stage, failure_class = "rate_limit", "http_rate_limited"
            elif response.status != 200:
                failure_stage, failure_class = "http_status", "http_status_failure"
            elif normalized != "application/json":
                failure_stage, failure_class = "content_type", "unexpected_content_type"
            elif not 0 < len(response.body) <= MAX_RESPONSE_BYTES:
                failure_stage, failure_class = "response_size", "response_size_failure"
            if failure_stage is not None:
                ledger.append(
                    "request_failed",
                    phase=phase,
                    request_ordinal=ordinal,
                    path=path,
                    bytes_received=min(len(response.body), MAX_RESPONSE_BYTES),
                    http_status=response.status,
                    content_type=normalized[:128],
                    elapsed_ms=min(response.elapsed_ms, 60_000),
                    failure_stage=failure_stage,
                    failure_class=failure_class,
                    monotonic_ns=monotonic_ns(),
                    utc_now=utc_now(),
                )
                active_terminal_recorded = True
                raise BoundedSupervisorError("bounded observer HTTP response failed")
            try:
                document = _endpoint_document(root, path, response.body)
            except BoundedSupervisorError as error:
                text = str(error)
                stage = "pagination" if "pagination" in text else "schema_validation"
                ledger.append(
                    "request_failed",
                    phase=phase,
                    request_ordinal=ordinal,
                    path=path,
                    bytes_received=len(response.body),
                    http_status=response.status,
                    content_type=normalized,
                    elapsed_ms=min(response.elapsed_ms, 60_000),
                    failure_stage=stage,
                    failure_class="response_contract_failure",
                    monotonic_ns=monotonic_ns(),
                    utc_now=utc_now(),
                )
                active_terminal_recorded = True
                raise
            response_path = root / RESPONSES_RELATIVE / f"{ordinal:03d}.json"
            _write_exclusive(
                response_path,
                _sanitized_provider_receipt(
                    root,
                    path=path,
                    document=document,
                    received_bytes=len(response.body),
                    credential=credential,
                ),
            )
            response_completed_at = utc_now()
            ledger.append(
                "response_completed",
                phase=phase,
                request_ordinal=ordinal,
                path=path,
                bytes_received=len(response.body),
                http_status=response.status,
                content_type=normalized,
                elapsed_ms=min(response.elapsed_ms, 60_000),
                monotonic_ns=monotonic_ns(),
                utc_now=response_completed_at,
            )
            active_terminal_recorded = True
            state["response_bytes"] = _nonnegative_integer(
                state.get("response_bytes"), context="observer response bytes"
            ) + len(response.body)
            state["last_request_monotonic_ns"] = monotonic_ns()
            state["event_count"] = ledger.event_count
            if (
                _nonnegative_integer(state.get("response_bytes"), context="observer response bytes")
                > MAX_RESPONSE_BYTES_AGGREGATE
            ):
                raise BoundedSupervisorError("observer aggregate response cap exceeded")
            _atomic_write(root / STATE_RELATIVE, canonical_json_bytes(state))
            phase_responses[path] = document
        report = _PHASE_VALIDATORS[phase](phase_responses, private, state)
        if response_completed_at is None:
            raise BoundedSupervisorError("observer phase completed without a response timestamp")
        if phase == "post_launch":
            observed_at = _utc_text(response_completed_at)
            state["provider_active_observed_at_utc"] = observed_at
            report["provider_active_observed_at_utc"] = observed_at
        elif phase == "termination":
            observed_at = _utc_text(response_completed_at)
            state["provider_terminal_observed_at_utc"] = observed_at
            report["provider_terminal_observed_at_utc"] = observed_at
        ordinals = list(
            range(
                PHASE_START_ORDINAL[phase],
                PHASE_START_ORDINAL[phase] + len(PHASE_REQUESTS[phase]),
            )
        )
        report["request_ordinals"] = ordinals
        report["sanitized_response_sha256s"] = [
            sha256_bytes(
                _read_regular(
                    root / RESPONSES_RELATIVE / f"{ordinal:03d}.json",
                    max_bytes=MAX_RESPONSE_BYTES,
                )
            )
            for ordinal in ordinals
        ]
        _write_exclusive(
            root / RUN_ROOT_RELATIVE / f"{phase}-report.json", canonical_json_bytes(report)
        )
        if cleanup_mode:
            state["next_phase"] = "terminal" if phase == "termination" else None
            if phase == "terminal":
                state["status"] = (
                    "cleanup_complete"
                    if report.get("provider_termination_previously_verified") is True
                    else "cleanup_incomplete"
                )
            else:
                state["status"] = "cleanup_required"
        else:
            next_index = PHASE_ORDER.index(phase) + 1
            state["next_phase"] = PHASE_ORDER[next_index] if next_index < len(PHASE_ORDER) else None
            state["status"] = "complete" if phase == "terminal" else f"{phase}_passed"
        ledger.append("phase_passed", phase=phase, monotonic_ns=monotonic_ns(), utc_now=utc_now())
        if phase == "terminal":
            ledger.append(
                "run_stopped", phase=phase, monotonic_ns=monotonic_ns(), utc_now=utc_now()
            )
        state["event_count"] = ledger.event_count
        _atomic_write(root / STATE_RELATIVE, canonical_json_bytes(state))
        return report
    except BaseException:
        if state.get("status") not in {"cleanup_required", "cleanup_incomplete"}:
            if (
                active_ordinal is not None
                and active_path is not None
                and not active_terminal_recorded
            ):
                with contextlib.suppress(BoundedSupervisorError):
                    ledger.append(
                        "request_outcome_unknown_after_send",
                        phase=phase,
                        request_ordinal=active_ordinal,
                        path=active_path,
                        failure_stage="unknown",
                        failure_class="supervisor_failure_after_send",
                        monotonic_ns=monotonic_ns(),
                        utc_now=utc_now(),
                    )
            with contextlib.suppress(BoundedSupervisorError):
                ledger.append(
                    "phase_failed",
                    phase=phase,
                    failure_stage="state_validation",
                    failure_class="phase_contract_failure",
                    monotonic_ns=monotonic_ns(),
                    utc_now=utc_now(),
                )
            _enter_cleanup_only(state, failed_phase=phase)
            state["event_count"] = ledger.event_count
            with contextlib.suppress(OSError, BoundedSupervisorError):
                _atomic_write(root / STATE_RELATIVE, canonical_json_bytes(state))
        raise


def _plan_upload_rows(
    root: Path,
    *,
    plan: Mapping[str, object],
    plan_sha256: str,
    expected_commit: str,
) -> tuple[list[tuple[str, bytes]], bytes]:
    implementation = _mapping(plan.get("implementation"), context="plan implementation")
    raw_artifacts = _sequence(implementation.get("artifacts"), context="implementation artifacts")
    plan_path = root / BOUNDED_PLAN_RELATIVE
    plan_encoded = _read_regular(plan_path, max_bytes=MAX_PLAN_BYTES)
    if sha256_bytes(plan_encoded) != plan_sha256:
        raise BoundedSupervisorError("upload bundle plan hash drifted")
    rows: list[tuple[str, bytes]] = [(BOUNDED_PLAN_RELATIVE.as_posix(), plan_encoded)]
    expected_metadata: dict[str, tuple[int, str]] = {}
    for raw in raw_artifacts:
        artifact = _mapping(raw, context="implementation artifact")
        relative = _text(artifact.get("path"), context="implementation artifact path")
        pure = PurePosixPath(relative)
        if (
            pure.is_absolute()
            or ".." in pure.parts
            or any(part in {".git", ".env", "artifacts", ".secrets"} for part in pure.parts)
            or relative in expected_metadata
        ):
            raise BoundedSupervisorError("upload bundle member path is unsafe")
        expected_metadata[relative] = (
            _nonnegative_integer(artifact.get("bytes"), context="artifact bytes"),
            _text(artifact.get("sha256"), context="artifact SHA-256"),
        )
    tracked = set(
        filter(
            None,
            _git(
                root,
                "ls-files",
                "--",
                BOUNDED_PLAN_RELATIVE.as_posix(),
                *sorted(expected_metadata),
            ).splitlines(),
        )
    )
    required_tracked = {BOUNDED_PLAN_RELATIVE.as_posix(), *expected_metadata}
    if tracked != required_tracked:
        raise BoundedSupervisorError("upload bundle contains a nontracked input")
    for relative in sorted(expected_metadata):
        expected_bytes, expected_sha256 = expected_metadata[relative]
        encoded = _read_regular(root / relative, max_bytes=MAX_UPLOAD_BUNDLE_BYTES)
        if len(encoded) != expected_bytes or sha256_bytes(encoded) != expected_sha256:
            raise BoundedSupervisorError("upload bundle artifact binding drifted")
        rows.append((relative, encoded))
    if len(rows) + 1 != MAX_UPLOAD_BUNDLE_FILES:
        raise BoundedSupervisorError("upload bundle file count drifted")
    payload_bytes = sum(len(encoded) for _, encoded in rows)
    if payload_bytes > MAX_UPLOAD_BUNDLE_BYTES:
        raise BoundedSupervisorError("upload bundle payload exceeds its cap")
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "plan_id": PLAN_ID,
        "host_run_id": HOST_RUN_ID,
        "execution_commit": expected_commit,
        "plan_sha256": plan_sha256,
        "files": [
            {"path": relative, "bytes": len(encoded), "sha256": sha256_bytes(encoded)}
            for relative, encoded in rows
        ],
        "file_count": len(rows),
        "archive_member_count": len(rows) + 1,
        "payload_bytes": payload_bytes,
        "tracked_files_only": True,
        "forbidden_untracked_inputs_absent": True,
    }
    return rows, canonical_json_bytes(manifest)


def prepare_upload_bundle(
    root: Path,
    *,
    plan: Mapping[str, object],
    plan_sha256: str,
    expected_commit: str,
    authorization_path: Path,
    authorization_sha256: str,
    private_binding_path: Path,
    private_binding_sha256: str,
    utc_now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> dict[str, object]:
    """Create the only repository payload permitted for manual cloud upload."""

    verify_repository_identity(root, expected_commit)
    authorization, _ = _validate_authority_inputs(
        root,
        plan=plan,
        plan_sha256=plan_sha256,
        authorization_path=authorization_path,
        authorization_sha256=authorization_sha256,
        private_binding_path=private_binding_path,
        private_binding_sha256=private_binding_sha256,
        utc_now=utc_now,
        require_live=True,
    )
    state = _load_state(root)
    if state.get("status") != "materialized" or state.get("next_phase") != "prelaunch":
        raise BoundedSupervisorError("upload bundle must be prepared before provider preflight")
    upload_root = root / UPLOAD_ROOT_RELATIVE
    identity_path = root / UPLOAD_IDENTITY_RELATIVE
    if upload_root.exists() or upload_root.is_symlink() or identity_path.exists():
        raise BoundedSupervisorError("upload bundle identity is not fresh")
    rows, manifest_encoded = _plan_upload_rows(
        root,
        plan=plan,
        plan_sha256=plan_sha256,
        expected_commit=expected_commit,
    )
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w", format=tarfile.USTAR_FORMAT) as archive:
        members = [(UPLOAD_MANIFEST_NAME, manifest_encoded), *rows]
        for relative, encoded in members:
            info = tarfile.TarInfo(relative)
            info.size = len(encoded)
            info.mode = 0o444
            info.mtime = 0
            info.uid = 0
            info.gid = 0
            info.uname = ""
            info.gname = ""
            archive.addfile(info, io.BytesIO(encoded))
    archive_encoded = stream.getvalue()
    if len(archive_encoded) > MAX_UPLOAD_BUNDLE_BYTES:
        raise BoundedSupervisorError("upload bundle archive exceeds its cap")
    bootstrap_row = next(
        (encoded for relative, encoded in rows if relative == REMOTE_BOOTSTRAP_RELATIVE.as_posix()),
        None,
    )
    if bootstrap_row is None:
        raise BoundedSupervisorError("upload bundle has no reviewed remote bootstrap")
    upload_root.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    upload_root.mkdir(mode=0o700, exist_ok=False)
    archive_path = upload_root / UPLOAD_ARCHIVE_NAME
    bootstrap_path = upload_root / UPLOAD_BOOTSTRAP_NAME
    _write_exclusive(archive_path, archive_encoded)
    _write_exclusive(bootstrap_path, bootstrap_row)
    identity = {
        "schema_version": SCHEMA_VERSION,
        "plan_id": PLAN_ID,
        "host_run_id": HOST_RUN_ID,
        "authorization_reference": authorization.get("authorization_reference"),
        "authorization_sha256": authorization_sha256,
        "private_binding_sha256": private_binding_sha256,
        "execution_commit": expected_commit,
        "plan_sha256": plan_sha256,
        "archive_path": (UPLOAD_ROOT_RELATIVE / UPLOAD_ARCHIVE_NAME).as_posix(),
        "archive_bytes": len(archive_encoded),
        "archive_sha256": sha256_bytes(archive_encoded),
        "bundle_manifest_sha256": sha256_bytes(manifest_encoded),
        "archive_member_count": len(rows) + 1,
        "bootstrap_path": (UPLOAD_ROOT_RELATIVE / UPLOAD_BOOTSTRAP_NAME).as_posix(),
        "bootstrap_bytes": len(bootstrap_row),
        "bootstrap_sha256": sha256_bytes(bootstrap_row),
        "tracked_files_only": True,
        "forbidden_untracked_inputs_absent": True,
        "source_retained": True,
    }
    identity_encoded = canonical_json_bytes(identity)
    _write_exclusive(identity_path, identity_encoded, mode=0o644)
    return {
        "schema_version": SCHEMA_VERSION,
        "plan_id": PLAN_ID,
        "run_id": HOST_RUN_ID,
        "upload_bundle_identity_path": str(UPLOAD_IDENTITY_RELATIVE),
        "upload_bundle_identity_sha256": sha256_bytes(identity_encoded),
        "archive_path": identity["archive_path"],
        "archive_bytes": identity["archive_bytes"],
        "archive_sha256": identity["archive_sha256"],
        "bundle_manifest_sha256": identity["bundle_manifest_sha256"],
        "bootstrap_path": identity["bootstrap_path"],
        "bootstrap_sha256": identity["bootstrap_sha256"],
    }


def _load_upload_bundle_identity(
    root: Path,
    *,
    plan: Mapping[str, object],
    plan_sha256: str,
    expected_commit: str,
    authorization_reference: object,
    authorization_sha256: str,
    private_binding_sha256: str,
) -> dict[str, object]:
    encoded = _read_regular(root / UPLOAD_IDENTITY_RELATIVE, max_bytes=MAX_RESPONSE_BYTES)
    identity = _strict_json(encoded, context="upload bundle identity")
    archive = _read_regular(
        root / UPLOAD_ROOT_RELATIVE / UPLOAD_ARCHIVE_NAME,
        max_bytes=MAX_UPLOAD_BUNDLE_BYTES,
    )
    bootstrap = _read_regular(
        root / UPLOAD_ROOT_RELATIVE / UPLOAD_BOOTSTRAP_NAME,
        max_bytes=MAX_UPLOAD_BUNDLE_BYTES,
    )
    rows, manifest_encoded = _plan_upload_rows(
        root,
        plan=plan,
        plan_sha256=plan_sha256,
        expected_commit=expected_commit,
    )
    try:
        with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as opened:
            members = opened.getmembers()
            captured: dict[str, bytes] = {}
            for member in members:
                reader = opened.extractfile(member) if member.isfile() else None
                if (
                    reader is None
                    or member.name in captured
                    or member.mode != 0o444
                    or member.mtime != 0
                    or member.uid != 0
                    or member.gid != 0
                    or member.pax_headers
                ):
                    raise BoundedSupervisorError("upload bundle archive metadata drifted")
                captured[member.name] = reader.read(MAX_UPLOAD_BUNDLE_BYTES + 1)
    except (tarfile.TarError, OSError):
        raise BoundedSupervisorError("upload bundle archive is invalid") from None
    expected_members = {UPLOAD_MANIFEST_NAME: manifest_encoded, **dict(rows)}
    if captured != expected_members:
        raise BoundedSupervisorError("upload bundle archive differs from its exact source set")
    artifacts = _sequence(
        _mapping(plan.get("implementation"), context="plan implementation").get("artifacts"),
        context="implementation artifacts",
    )
    expected_bootstrap = next(
        (
            _mapping(item, context="implementation artifact")
            for item in artifacts
            if _mapping(item, context="implementation artifact").get("path")
            == REMOTE_BOOTSTRAP_RELATIVE.as_posix()
        ),
        None,
    )
    expected = {
        "schema_version": SCHEMA_VERSION,
        "plan_id": PLAN_ID,
        "host_run_id": HOST_RUN_ID,
        "authorization_reference": authorization_reference,
        "authorization_sha256": authorization_sha256,
        "private_binding_sha256": private_binding_sha256,
        "execution_commit": expected_commit,
        "plan_sha256": plan_sha256,
        "archive_path": (UPLOAD_ROOT_RELATIVE / UPLOAD_ARCHIVE_NAME).as_posix(),
        "archive_bytes": len(archive),
        "archive_sha256": sha256_bytes(archive),
        "bundle_manifest_sha256": sha256_bytes(manifest_encoded),
        "archive_member_count": MAX_UPLOAD_BUNDLE_FILES,
        "bootstrap_path": (UPLOAD_ROOT_RELATIVE / UPLOAD_BOOTSTRAP_NAME).as_posix(),
        "bootstrap_bytes": len(bootstrap),
        "bootstrap_sha256": sha256_bytes(bootstrap),
        "tracked_files_only": True,
        "forbidden_untracked_inputs_absent": True,
        "source_retained": True,
    }
    if (
        identity != expected
        or expected_bootstrap is None
        or expected_bootstrap.get("bytes") != len(bootstrap)
        or expected_bootstrap.get("sha256") != sha256_bytes(bootstrap)
        or not isinstance(identity.get("bundle_manifest_sha256"), str)
        or _HEX64.fullmatch(str(identity["bundle_manifest_sha256"])) is None
    ):
        raise BoundedSupervisorError("upload bundle identity drifted")
    return identity


def issue_bootstrap_release(
    root: Path,
    *,
    plan: Mapping[str, object],
    plan_sha256: str,
    expected_commit: str,
    authorization_path: Path,
    authorization_sha256: str,
    private_binding_path: Path,
    private_binding_sha256: str,
    provider_image_attestation: str,
    utc_now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> dict[str, object]:
    """Durably authorize the one fresh remote bootstrap after launch identity is bound."""

    verify_repository_identity(root, expected_commit)
    authorization, private = _validate_authority_inputs(
        root,
        plan=plan,
        plan_sha256=plan_sha256,
        authorization_path=authorization_path,
        authorization_sha256=authorization_sha256,
        private_binding_path=private_binding_path,
        private_binding_sha256=private_binding_sha256,
        utc_now=utc_now,
        require_live=True,
    )
    replay = _verify_observer_evidence(
        root,
        authorization=authorization,
        private=private,
        authorization_sha256=authorization_sha256,
        private_binding_sha256=private_binding_sha256,
        disposition="post_launch",
        write_receipt=False,
    )
    state = _load_state(root)
    selected = _mapping(private.get("selected_resource"), context="selected resource")
    if provider_image_attestation != "confirmed-in-provider-console":
        raise BoundedSupervisorError("provider image requires an explicit console attestation")
    active_at = state.get("provider_active_observed_at_utc")
    if (
        state.get("status") != "post_launch_passed"
        or state.get("next_phase") != "termination"
        or not isinstance(state.get("bound_instance_id"), str)
        or not state.get("bound_instance_id")
        or not isinstance(active_at, str)
        or (root / INBOUND_RELATIVE).exists()
    ):
        raise BoundedSupervisorError("bootstrap release requires a bound active instance")
    state_encoded = _read_regular(root / STATE_RELATIVE, max_bytes=MAX_RESPONSE_BYTES)
    report_encoded = _read_regular(
        root / RUN_ROOT_RELATIVE / "post_launch-report.json", max_bytes=MAX_RESPONSE_BYTES
    )
    report = _strict_json(report_encoded, context="post-launch report")
    if (
        report.get("phase") != "post_launch"
        or report.get("provider_active_observed_at_utc") != active_at
        or report.get("bound_instance_id_sha256")
        != sha256_bytes(_text(state.get("bound_instance_id"), context="instance ID").encode())
        or replay.get("observer_state_sha256") != sha256_bytes(state_encoded)
        or _mapping(replay.get("phase_report_sha256s"), context="release phase hashes").get(
            "post_launch"
        )
        != sha256_bytes(report_encoded)
        or replay.get("provider_active_observed_at_utc") != active_at
    ):
        raise BoundedSupervisorError("post-launch evidence cannot authorize bootstrap")
    upload = _load_upload_bundle_identity(
        root,
        plan=plan,
        plan_sha256=plan_sha256,
        expected_commit=expected_commit,
        authorization_reference=authorization.get("authorization_reference"),
        authorization_sha256=authorization_sha256,
        private_binding_sha256=private_binding_sha256,
    )
    release = {
        "schema_version": SCHEMA_VERSION,
        "plan_id": PLAN_ID,
        "host_run_id": HOST_RUN_ID,
        "authorization_reference": authorization.get("authorization_reference"),
        "execution_commit": expected_commit,
        "plan_sha256": plan_sha256,
        "authorization_sha256": authorization_sha256,
        "private_binding_sha256": private_binding_sha256,
        "observer_state_sha256": sha256_bytes(state_encoded),
        "post_launch_report_sha256": sha256_bytes(report_encoded),
        "provider_active_observed_at_utc": active_at,
        "selected_provider_image": {
            "alias": selected.get("image_alias"),
            "family": selected.get("image_family"),
            "version": selected.get("image_version"),
            "attestation": provider_image_attestation,
            "binding_basis": "prelaunch-offered-plus-user-console-attestation",
            "post_launch_api_image_observation_available": False,
        },
        "bundle_archive_sha256": upload["archive_sha256"],
        "bundle_manifest_sha256": upload["bundle_manifest_sha256"],
        "bootstrap_file_sha256": upload["bootstrap_sha256"],
        "issued_at_utc": _utc_text(utc_now()),
        "bootstrap_release": True,
        "single_use_output_root": "/home/ubuntu/t07-bounded-output-0001",
    }
    encoded = canonical_json_bytes(release)
    path = root / BOOTSTRAP_RELEASE_RELATIVE
    _write_exclusive(root / BOOTSTRAP_RELEASE_STATE_RELATIVE, state_encoded, mode=0o644)
    _write_exclusive(path, encoded, mode=0o644)
    return {
        "schema_version": SCHEMA_VERSION,
        "plan_id": PLAN_ID,
        "run_id": HOST_RUN_ID,
        "bootstrap_release_path": str(path),
        "bootstrap_release_bytes": len(encoded),
        "bootstrap_release_sha256": sha256_bytes(encoded),
        "bootstrap_release_state_sha256": sha256_bytes(state_encoded),
        "single_use": True,
    }


def _validate_local_bootstrap_release(
    root: Path,
    *,
    plan: Mapping[str, object],
    plan_sha256: str,
    expected_commit: str,
    authorization: Mapping[str, object],
    authorization_sha256: str,
    private: Mapping[str, object],
    private_binding_sha256: str,
    replay: Mapping[str, object] | None,
) -> tuple[dict[str, object], bytes]:
    release_encoded = _read_regular(
        root / BOOTSTRAP_RELEASE_RELATIVE, max_bytes=MAX_AUTHORIZATION_BYTES
    )
    release = _strict_json(release_encoded, context="bootstrap release")
    snapshot_encoded = _read_regular(
        root / BOOTSTRAP_RELEASE_STATE_RELATIVE, max_bytes=MAX_RESPONSE_BYTES
    )
    snapshot = _strict_json(snapshot_encoded, context="bootstrap release state")
    report_encoded = _read_regular(
        root / RUN_ROOT_RELATIVE / "post_launch-report.json", max_bytes=MAX_RESPONSE_BYTES
    )
    report = _strict_json(report_encoded, context="post-launch report")
    selected = _mapping(private.get("selected_resource"), context="selected resource")
    upload = _load_upload_bundle_identity(
        root,
        plan=plan,
        plan_sha256=plan_sha256,
        expected_commit=expected_commit,
        authorization_reference=authorization.get("authorization_reference"),
        authorization_sha256=authorization_sha256,
        private_binding_sha256=private_binding_sha256,
    )
    active = _text(
        snapshot.get("provider_active_observed_at_utc"), context="provider active observation"
    )
    issued = _parse_utc(release.get("issued_at_utc"), context="bootstrap release time")
    active_at = _parse_utc(active, context="provider active observation")
    expires = _parse_utc(authorization.get("expires_at_utc"), context="authorization expiry")
    expected = {
        "schema_version": SCHEMA_VERSION,
        "plan_id": PLAN_ID,
        "host_run_id": HOST_RUN_ID,
        "authorization_reference": authorization.get("authorization_reference"),
        "execution_commit": expected_commit,
        "plan_sha256": plan_sha256,
        "authorization_sha256": authorization_sha256,
        "private_binding_sha256": private_binding_sha256,
        "observer_state_sha256": sha256_bytes(snapshot_encoded),
        "post_launch_report_sha256": sha256_bytes(report_encoded),
        "provider_active_observed_at_utc": active,
        "selected_provider_image": {
            "alias": selected.get("image_alias"),
            "family": selected.get("image_family"),
            "version": selected.get("image_version"),
            "attestation": "confirmed-in-provider-console",
            "binding_basis": "prelaunch-offered-plus-user-console-attestation",
            "post_launch_api_image_observation_available": False,
        },
        "bundle_archive_sha256": upload["archive_sha256"],
        "bundle_manifest_sha256": upload["bundle_manifest_sha256"],
        "bootstrap_file_sha256": upload["bootstrap_sha256"],
        "issued_at_utc": release.get("issued_at_utc"),
        "bootstrap_release": True,
        "single_use_output_root": "/home/ubuntu/t07-bounded-output-0001",
    }
    if (
        release != expected
        or authorization.get("execution_commit") != expected_commit
        or snapshot.get("status") != "post_launch_passed"
        or snapshot.get("next_phase") != "termination"
        or snapshot.get("authorization_reference") != authorization.get("authorization_reference")
        or snapshot.get("authorization_sha256") != authorization_sha256
        or snapshot.get("private_binding_sha256") != private_binding_sha256
        or not isinstance(snapshot.get("bound_instance_id"), str)
        or not snapshot.get("bound_instance_id")
        or report.get("phase") != "post_launch"
        or report.get("provider_active_observed_at_utc") != active
        or report.get("bound_instance_id_sha256")
        != sha256_bytes(_text(snapshot.get("bound_instance_id"), context="instance ID").encode())
        or not active_at <= issued < expires
    ):
        raise BoundedSupervisorError("bootstrap release local authority binding drifted")
    selected_plan = _mapping(plan.get("lambda"), context="Lambda plan")
    if (
        selected_plan.get("image_alias") != selected.get("image_alias")
        or selected_plan.get("image_family") != selected.get("image_family")
        or selected_plan.get("image_version") != selected.get("image_version")
    ):
        raise BoundedSupervisorError("bootstrap release provider image binding drifted")
    if replay is not None:
        phase_hashes = _mapping(replay.get("phase_report_sha256s"), context="release replay hashes")
        if (
            replay.get("observer_state_sha256") != sha256_bytes(snapshot_encoded)
            or phase_hashes.get("post_launch") != sha256_bytes(report_encoded)
            or replay.get("provider_active_observed_at_utc") != active
        ):
            raise BoundedSupervisorError("bootstrap release differs from observer replay")
    return dict(release), release_encoded


def _safe_zip_member_name(name: str) -> str:
    encoded = name.encode("utf-8", "strict")
    if (
        not name
        or "\\" in name
        or name.endswith("/")
        or any(pattern.search(encoded) for pattern in _SECRET_PREFIX_SHAPES)
    ):
        raise BoundedSupervisorError("inbound archive contains an unsafe member name")
    path = PurePosixPath(name)
    if (
        path.is_absolute()
        or path.as_posix() != name
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise BoundedSupervisorError("inbound archive member escapes its root")
    return name


def _read_verified_zip_member(
    opened: zipfile.ZipFile,
    info: zipfile.ZipInfo,
    *,
    capture: bool,
) -> tuple[int, str, bytes | None]:
    if (
        info.flag_bits & 0x1
        or info.compress_type != zipfile.ZIP_STORED
        or info.compress_size != info.file_size
        or info.file_size > MAX_REMOTE_EVIDENCE_BYTES
        or stat.S_ISLNK((info.external_attr >> 16) & 0xFFFF)
    ):
        raise BoundedSupervisorError("inbound archive member contract is unsafe")
    digest = hashlib.sha256()
    retained = bytearray() if capture else None
    semantic_scan = bytearray() if info.file_size <= 16_777_216 else None
    total = 0
    tail = b""
    try:
        with opened.open(info, "r") as member:
            while chunk := member.read(65_536):
                total += len(chunk)
                if total > info.file_size or total > MAX_REMOTE_EVIDENCE_BYTES:
                    raise BoundedSupervisorError("inbound archive member exceeds its cap")
                probe = tail + chunk
                if any(pattern.search(probe) for pattern in _SECRET_PREFIX_SHAPES):
                    raise BoundedSupervisorError(
                        "decoded inbound archive contains credential-shaped material"
                    )
                tail = probe[-512:]
                digest.update(chunk)
                if retained is not None:
                    retained.extend(chunk)
                if semantic_scan is not None:
                    semantic_scan.extend(chunk)
    except BoundedSupervisorError:
        raise
    except (OSError, RuntimeError, zipfile.BadZipFile):
        raise BoundedSupervisorError("inbound archive member could not be verified") from None
    if total != info.file_size:
        raise BoundedSupervisorError("inbound archive member length drifted")
    if semantic_scan is not None and _contains_artifact_secret(bytes(semantic_scan)):
        raise BoundedSupervisorError("decoded inbound archive contains credential-shaped material")
    return total, digest.hexdigest(), bytes(retained) if retained is not None else None


def _finite_number(value: object, *, context: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise BoundedSupervisorError(f"{context} must be numeric")
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise BoundedSupervisorError(f"{context} is invalid")
    return number


def _success_fixed_members() -> set[str]:
    required = {
        "bootstrap-authority.json",
        "image-inspect.json",
        "image-provenance.json",
        "host-environment.json",
        "bootstrap-execution.json",
        "command-meter.jsonl",
        "secret-cleanup.json",
        "pair-budget.json",
        "pair-equivalence.json",
        "normalized-events.jsonl",
        "browser-preflight/payload/browser-preflight.json",
        "browser-preflight/payload/browser-preflight.png",
        "browser-preflight/payload/installed-packages.txt",
        "model-preflight/payload/model-availability.json",
        "reactive/payload/provider-budget.json",
        "reactive/payload/runtime-environment.json",
        "reactive/payload/runtime-cleanup.json",
        "reactive/regulation-decision.json",
        "reactive/resolved-command.json",
        "reactive/condition-completion.json",
        "simulative/payload/provider-budget.json",
        "simulative/payload/runtime-environment.json",
        "simulative/payload/runtime-cleanup.json",
        "simulative/regulation-decision.json",
        "simulative/resolved-command.json",
        "simulative/condition-completion.json",
    }
    for root in _LIFECYCLE_EVIDENCE_ROOTS:
        required.update(f"{root}/{name}" for name in _LIFECYCLE_EVIDENCE_NAMES)
        required.add(f"{root}/container-readiness.json")
        if root != "browser-preflight":
            required.update(
                {
                    f"{root}/container-release.json",
                    f"{root}/container-wait.json",
                    f"{root}/container-logs.json",
                    f"{root}/container-workload-result.json",
                }
            )
    return required


def _is_condition_session_member(name: str) -> bool:
    parts = PurePosixPath(name).parts
    return (
        len(parts) == 4
        and parts[0] in {"reactive", "simulative"}
        and parts[1:3] == ("payload", "sira-output")
        and parts[3].endswith(".json")
    )


def _strict_json_array(encoded: bytes, *, context: str) -> list[object]:
    wrapped = _strict_json(b'{"value":' + encoded + b"}", context=context)
    return list(_sequence(wrapped.get("value"), context=context))


def _command_receipt(
    captured: Mapping[str, bytes],
    name: str,
    *,
    expected_argv_sha256: str,
) -> Mapping[str, object]:
    record = _strict_json(captured[name], context=name)
    stdout_bytes = record.get("stdout_bytes")
    stderr_bytes = record.get("stderr_bytes")
    if (
        set(record)
        != {
            "argv_sha256",
            "returncode",
            "stdout_bytes",
            "stdout_sha256",
            "stderr_bytes",
            "stderr_sha256",
            "elapsed_seconds",
        }
        or record.get("argv_sha256") != expected_argv_sha256
        or type(record.get("returncode")) is not int
        or type(stdout_bytes) is not int
        or stdout_bytes < 0
        or not isinstance(record.get("stdout_sha256"), str)
        or _HEX64.fullmatch(str(record["stdout_sha256"])) is None
        or type(stderr_bytes) is not int
        or stderr_bytes < 0
        or not isinstance(record.get("stderr_sha256"), str)
        or _HEX64.fullmatch(str(record["stderr_sha256"])) is None
        or _finite_number(record.get("elapsed_seconds"), context=f"{name} elapsed") < 0
    ):
        raise BoundedSupervisorError(f"{name} command receipt drifted")
    return record


def _render_lifecycle_argv(
    plan: Mapping[str, object], action: str, substitutions: Mapping[str, str]
) -> list[str]:
    lifecycle = _mapping(plan.get("container_lifecycle"), context="container lifecycle")
    template = [
        _text(item, context=f"{action} argument")
        for item in _sequence(lifecycle.get(action), context=f"{action} template")
    ]
    rendered: list[str] = []
    for item in template:
        value = item
        for placeholder, replacement in substitutions.items():
            value = value.replace(placeholder, replacement)
        if "${" in value:
            raise BoundedSupervisorError("lifecycle evidence retains an unresolved placeholder")
        rendered.append(value)
    return rendered


def _argv_sha256(argv: Sequence[str]) -> str:
    return sha256_bytes(json.dumps(list(argv), separators=(",", ":")).encode())


def _argv_option(argv: Sequence[str], name: str) -> str:
    indexes = [index for index, value in enumerate(argv) if value == name]
    if len(indexes) != 1 or indexes[0] + 1 >= len(argv):
        raise BoundedSupervisorError(f"container create option {name} drifted")
    return argv[indexes[0] + 1]


def _argv_options(argv: Sequence[str], name: str) -> list[str]:
    indexes = [index for index, value in enumerate(argv) if value == name]
    if any(index + 1 >= len(argv) for index in indexes):
        raise BoundedSupervisorError(f"container create option {name} drifted")
    return [argv[index + 1] for index in indexes]


def _render_create_argv(
    plan: Mapping[str, object],
    *,
    root_name: str,
    condition: str,
    substitutions: Mapping[str, str],
) -> list[str]:
    if root_name in {"browser-preflight", "model-preflight"}:
        preflights = _mapping(plan.get("preflights"), context="preflights")
        key = "browser" if root_name == "browser-preflight" else "model"
        bound = _mapping(preflights.get(key), context=f"{key} preflight")
    else:
        conditions = [
            _mapping(item, context="plan condition")
            for item in _sequence(plan.get("conditions"), context="plan conditions")
        ]
        matches = [item for item in conditions if item.get("condition") == condition]
        if len(matches) != 1:
            raise BoundedSupervisorError("container condition plan identity drifted")
        bound = matches[0]
    template = [
        _text(item, context="container create argument")
        for item in _sequence(
            bound.get("container_create_argv_template"), context="container create template"
        )
    ]
    rendered: list[str] = []
    for item in template:
        value = item
        for placeholder, replacement in substitutions.items():
            value = value.replace(placeholder, replacement)
        if "${" in value:
            raise BoundedSupervisorError("container create evidence retains a placeholder")
        rendered.append(value)
    return rendered


def _mount_list(value: object, *, context: str) -> list[Mapping[str, object]]:
    if value is None:
        return []
    return [_mapping(item, context=context) for item in _sequence(value, context=context)]


def _tmpfs_option_set(value: object, *, context: str) -> frozenset[str]:
    encoded = _text(value, context=context)
    options = encoded.split(",")
    if not options or any(not option for option in options) or len(set(options)) != len(options):
        raise BoundedSupervisorError(f"{context} is malformed")
    return frozenset(options)


def _verify_container_inspect_policy(
    inspected: Mapping[str, object],
    *,
    container_id: str,
    create_argv: Sequence[str],
    image_id: str,
) -> None:
    config = _mapping(inspected.get("Config"), context="container inspect config")
    host = _mapping(inspected.get("HostConfig"), context="container inspect host config")
    state = _mapping(inspected.get("State"), context="container inspect state")
    expected_name = _argv_option(create_argv, "--name")
    expected_network = _argv_option(create_argv, "--network")
    expected_labels = dict(
        _text(value, context="container label").split("=", 1)
        for value in _argv_options(create_argv, "--label")
    )
    labels = _mapping(config.get("Labels"), context="container inspect labels")
    observed_owned_labels = {
        key: value for key, value in labels.items() if str(key).startswith("org.giclab.t07.")
    }
    image_index = [index for index, value in enumerate(create_argv) if value == image_id]
    if len(image_index) != 1:
        raise BoundedSupervisorError("container create image identity drifted")
    command_index = image_index[0]
    expected_command = list(create_argv[command_index + 1 :])
    expected_tmpfs = {
        value.split(":", 1)[0]: _tmpfs_option_set(
            value.split(":", 1)[1], context="planned tmpfs options"
        )
        for value in _argv_options(create_argv, "--tmpfs")
        if ":" in value
    }
    observed_tmpfs_raw = _mapping(host.get("Tmpfs"), context="container inspect tmpfs")
    observed_tmpfs = {
        str(key): _tmpfs_option_set(value, context="observed tmpfs options")
        for key, value in observed_tmpfs_raw.items()
    }
    expected_mount_values = _argv_options(create_argv, "--mount")
    expected_mounts: list[dict[str, str]] = []
    for value in expected_mount_values:
        fields = dict(part.split("=", 1) for part in value.split(",") if "=" in part)
        if value.endswith(",readonly"):
            fields["readonly"] = "true"
        expected_mounts.append(fields)
    host_mounts = _mount_list(host.get("Mounts"), context="container inspect host mount")
    realized_mounts = _mount_list(
        inspected.get("Mounts"), context="container inspect realized mount"
    )
    mount_policy_ok = len(host_mounts) == len(expected_mounts) == len(realized_mounts)
    for expected, configured, realized in zip(
        expected_mounts, host_mounts, realized_mounts, strict=True
    ):
        mount_policy_ok = mount_policy_ok and (
            configured.get("Type") == expected.get("type") == "bind"
            and configured.get("Source") == expected.get("src")
            and configured.get("Target") == expected.get("dst")
            and configured.get("ReadOnly") is True
            and realized.get("Type") == "bind"
            and realized.get("Source") == expected.get("src")
            and realized.get("Destination") == expected.get("dst")
            and realized.get("RW") is False
        )
    cap_drop = host.get("CapDrop")
    security_options = host.get("SecurityOpt")
    restart = _mapping(host.get("RestartPolicy"), context="container restart policy")
    log_config = _mapping(host.get("LogConfig"), context="container log config")
    log_options = _mapping(log_config.get("Config"), context="container log options")
    environment = config.get("Env")
    if environment is None:
        environment_names: set[str] = set()
    else:
        environment_names = {
            _text(value, context="container environment entry").split("=", 1)[0].upper()
            for value in _sequence(environment, context="container environment")
        }
    inspect_bytes = canonical_json_bytes(inspected).lower()
    if (
        inspected.get("Id") != container_id
        or inspected.get("Name") != f"/{expected_name}"
        or inspected.get("Image") != image_id
        or config.get("Image") != image_id
        or config.get("User") != _argv_option(create_argv, "--user")
        or config.get("Entrypoint") != [_argv_option(create_argv, "--entrypoint")]
        or config.get("Cmd") != expected_command
        or observed_owned_labels != expected_labels
        or state.get("Running") is not True
        or host.get("Privileged") is not False
        or host.get("PidMode") not in {"", "private"}
        or host.get("NetworkMode") != expected_network
        or host.get("IpcMode") != _argv_option(create_argv, "--ipc")
        or host.get("CgroupnsMode") != _argv_option(create_argv, "--cgroupns")
        or host.get("UTSMode") not in {None, "", "private"}
        or host.get("CapAdd") not in (None, [])
        or cap_drop != ["ALL"]
        or security_options
        not in (
            ["no-new-privileges=true"],
            ["no-new-privileges"],
        )
        or host.get("ReadonlyRootfs") is not True
        or host.get("Init") is not True
        or host.get("AutoRemove") is not False
        or restart.get("Name") != "no"
        or restart.get("MaximumRetryCount") != 0
        or host.get("NanoCpus") != int(float(_argv_option(create_argv, "--cpus")) * 1_000_000_000)
        or host.get("Memory") != int(_argv_option(create_argv, "--memory"))
        or host.get("MemorySwap") != int(_argv_option(create_argv, "--memory-swap"))
        or host.get("PidsLimit") != int(_argv_option(create_argv, "--pids-limit"))
        or host.get("ShmSize") != int(_argv_option(create_argv, "--shm-size"))
        or observed_tmpfs != expected_tmpfs
        or host.get("Binds") not in (None, [])
        or host.get("VolumesFrom") not in (None, [])
        or not mount_policy_ok
        or log_config.get("Type") != _argv_option(create_argv, "--log-driver")
        or log_options
        != dict(value.split("=", 1) for value in _argv_options(create_argv, "--log-opt"))
        or any(
            "API_KEY" in name or "TOKEN" in name or "SECRET" in name for name in environment_names
        )
        or b"docker.sock" in inspect_bytes
        or b"podman.sock" in inspect_bytes
    ):
        raise BoundedSupervisorError("container inspect policy drifted")


def _verify_lifecycle_surface(
    captured: Mapping[str, bytes],
    *,
    plan: Mapping[str, object],
    root_name: str,
    condition: str,
    run_id: str,
    bootstrap_release: Mapping[str, object],
) -> str:
    prefix = f"{root_name}/"
    container_id_encoded = captured[prefix + "container-id.txt"]
    try:
        container_id = container_id_encoded.decode("ascii").strip()
    except UnicodeDecodeError:
        raise BoundedSupervisorError("container identity evidence is not ASCII") from None
    if re.fullmatch(r"[a-f0-9]{64}", container_id) is None:
        raise BoundedSupervisorError("container identity evidence is not immutable")
    provenance = _strict_json(captured["image-provenance.json"], context="image provenance")
    image_id = _text(provenance.get("image_id"), context="image identity")
    create_argv = _render_create_argv(
        plan,
        root_name=root_name,
        condition=condition,
        substitutions={
            "${SIRA_SECRET_FILE}": "/home/ubuntu/.config/giclab/sira_api_key",
            "${EXECUTION_COMMIT}": _text(
                bootstrap_release.get("execution_commit"), context="execution commit"
            ),
            "${AUTHORIZATION_REFERENCE}": _text(
                bootstrap_release.get("authorization_reference"),
                context="authorization reference",
            ),
            "${IMAGE_ID}": image_id,
        },
    )
    create_receipt = _command_receipt(
        captured,
        prefix + "container-create.json",
        expected_argv_sha256=_argv_sha256(create_argv),
    )
    expected_create_stdout = (container_id + "\n").encode()
    if (
        create_receipt.get("returncode") != 0
        or create_receipt.get("stdout_bytes") != len(expected_create_stdout)
        or create_receipt.get("stdout_sha256") != sha256_bytes(expected_create_stdout)
        or create_receipt.get("stderr_bytes") != 0
        or create_receipt.get("stderr_sha256") != sha256_bytes(b"")
    ):
        raise BoundedSupervisorError("container create receipt drifted")
    common = {"${CONTAINER_ID}": container_id, "${RUN_ID}": run_id}
    storage = _mapping(plan.get("storage"), context="storage")
    host_root = (
        _text(storage.get("remote_active_root"), context="remote active root")
        + f"/evidence/{root_name}/payload-prestop"
    )
    readiness_path = (
        "/giclab/attempt/browser-preflight.json"
        if root_name == "browser-preflight"
        else "/giclab/attempt/.giclab-entrypoint-ready"
    )
    action_records = {
        "container-start.json": ("start_detached", common),
        "container-inspect-before-stop-command.json": ("inspect", common),
        "container-top-before-stop-command.json": ("top", common),
        "container-readiness.json": (
            "readiness",
            {**common, "${READINESS_PATH}": readiness_path},
        ),
        "container-copy-out-prestop.json": (
            "copy_out",
            {**common, "${HOST_ATTEMPT_ROOT}": host_root},
        ),
        "container-stop.json": ("stop", common),
        "container-kill.json": ("kill", common),
        "container-terminal-inspect-command.json": ("inspect", common),
        "container-remove.json": ("remove", common),
        "container-removal-proof.json": ("inspect", common),
        "container-residue-containers.json": ("container_residue", common),
        "container-residue-networks.json": ("network_residue", common),
        "container-residue-volumes.json": ("volume_residue", common),
    }
    if root_name != "browser-preflight":
        action_records.update(
            {
                "container-release.json": ("release", common),
                "container-wait.json": ("wait", common),
                "container-logs.json": ("logs", common),
                "container-workload-result.json": ("wait", common),
            }
        )
    receipts: dict[str, Mapping[str, object]] = {}
    for filename, (action, substitutions) in action_records.items():
        receipts[filename] = _command_receipt(
            captured,
            prefix + filename,
            expected_argv_sha256=_argv_sha256(_render_lifecycle_argv(plan, action, substitutions)),
        )
    if (
        receipts["container-start.json"].get("returncode") != 0
        or receipts["container-readiness.json"].get("returncode") != 0
        or receipts["container-copy-out-prestop.json"].get("returncode") != 0
        or receipts["container-remove.json"].get("returncode") != 0
        or receipts["container-removal-proof.json"].get("returncode") == 0
        or (
            receipts["container-stop.json"].get("returncode") != 0
            and receipts["container-kill.json"].get("returncode") != 0
        )
        or any(
            receipts[name].get("returncode") != 0
            for name in (
                "container-release.json",
                "container-wait.json",
                "container-logs.json",
                "container-workload-result.json",
            )
            if name in receipts
        )
    ):
        raise BoundedSupervisorError("container lifecycle command outcome is incomplete")
    for name in (
        "container-residue-containers.json",
        "container-residue-networks.json",
        "container-residue-volumes.json",
    ):
        receipt = receipts[name]
        if (
            receipt.get("returncode") != 0
            or receipt.get("stdout_bytes") != 0
            or receipt.get("stdout_sha256") != sha256_bytes(b"")
            or receipt.get("stderr_bytes") != 0
            or receipt.get("stderr_sha256") != sha256_bytes(b"")
        ):
            raise BoundedSupervisorError("container residue receipt is not empty")
    copy_budget = _strict_json(
        captured[prefix + "container-copy-out-prestop-budget.json"],
        context="copy-out budget",
    )
    copied_payload_bytes = copy_budget.get("payload_bytes")
    if (
        set(copy_budget)
        != {
            "phase",
            "payload_bytes",
            "payload_cap_bytes",
            "within_cap",
            "copy_complete",
        }
        or copy_budget.get("phase") != "prestop"
        or type(copied_payload_bytes) is not int
        or not 0 <= copied_payload_bytes <= 67_108_864
        or copy_budget.get("payload_cap_bytes") != 67_108_864
        or copy_budget.get("within_cap") is not True
        or copy_budget.get("copy_complete") is not True
    ):
        raise BoundedSupervisorError("container copy-out budget drifted")
    payload_capture = _strict_json(
        captured[prefix + "container-payload-capture.json"], context="payload capture"
    )
    if (
        set(payload_capture)
        != {
            "schema_version",
            "condition",
            "copy_complete",
            "selected_phase",
            "payload_root",
            "payload_bytes",
            "payload_cap_bytes",
            "captured_before_removal",
        }
        or payload_capture.get("schema_version") != SCHEMA_VERSION
        or payload_capture.get("condition") != condition
        or payload_capture.get("copy_complete") is not True
        or payload_capture.get("selected_phase") != "prestop"
        or payload_capture.get("payload_root") != "payload"
        or payload_capture.get("payload_bytes") != copy_budget.get("payload_bytes")
        or payload_capture.get("payload_cap_bytes") != 67_108_864
        or payload_capture.get("captured_before_removal") is not True
    ):
        raise BoundedSupervisorError("container payload capture evidence drifted")
    running = _strict_json_array(
        captured[prefix + "container-inspect-before-stop.json"],
        context="pre-stop container inspect",
    )
    terminal = _strict_json_array(
        captured[prefix + "container-terminal-inspect.json"],
        context="terminal container inspect",
    )
    if (
        len(running) != 1
        or not isinstance(running[0], Mapping)
        or not isinstance(running[0].get("State"), Mapping)
        or running[0]["State"].get("Running") is not True
        or len(terminal) != 1
        or not isinstance(terminal[0], Mapping)
        or terminal[0].get("Id") != container_id
        or not isinstance(terminal[0].get("State"), Mapping)
        or terminal[0]["State"].get("Running") is not False
        or terminal[0]["State"].get("Status") not in {"created", "exited", "dead"}
    ):
        raise BoundedSupervisorError("container inspect lifecycle evidence drifted")
    for receipt_name, raw_name in (
        ("container-inspect-before-stop-command.json", "container-inspect-before-stop.json"),
        ("container-top-before-stop-command.json", "container-processes-before-stop.txt"),
        ("container-terminal-inspect-command.json", "container-terminal-inspect.json"),
    ):
        receipt = receipts[receipt_name]
        raw = captured[prefix + raw_name]
        if (
            receipt.get("returncode") != 0
            or receipt.get("stdout_bytes") != len(raw)
            or receipt.get("stdout_sha256") != sha256_bytes(raw)
            or receipt.get("stderr_bytes") != 0
            or receipt.get("stderr_sha256") != sha256_bytes(b"")
        ):
            raise BoundedSupervisorError("container inspection receipt drifted")
    _verify_container_inspect_policy(
        _mapping(running[0], context="pre-stop container inspect"),
        container_id=container_id,
        create_argv=create_argv,
        image_id=image_id,
    )
    process_lines = [
        line
        for line in captured[prefix + "container-processes-before-stop.txt"].splitlines()
        if line.strip()
    ]
    if len(process_lines) < 2:
        raise BoundedSupervisorError("pre-stop process evidence is empty")
    cleanup = _strict_json(captured[prefix + "container-cleanup.json"], context="cleanup")
    pre_stop_process_count = cleanup.get("pre_stop_process_count")
    if (
        set(cleanup)
        != {
            "schema_version",
            "condition",
            "container_id_sha256",
            "terminal_state_observed",
            "removed",
            "owned_container_residue_count",
            "owned_network_residue_count",
            "owned_volume_residue_count",
            "browser_process_residue_count",
            "process_evidence_captured_before_removal",
            "payload_capture_complete_before_removal",
            "payload_capture_phase",
            "payload_bytes",
            "pre_stop_running_state_observed",
            "pre_stop_process_capture_succeeded",
            "pre_stop_process_count",
        }
        or cleanup.get("schema_version") != SCHEMA_VERSION
        or cleanup.get("condition") != condition
        or cleanup.get("container_id_sha256") != sha256_bytes(container_id.encode())
        or cleanup.get("terminal_state_observed") is not True
        or cleanup.get("removed") is not True
        or cleanup.get("process_evidence_captured_before_removal") is not True
        or cleanup.get("payload_capture_complete_before_removal") is not True
        or cleanup.get("payload_capture_phase") != "prestop"
        or cleanup.get("payload_bytes") != copy_budget.get("payload_bytes")
        or cleanup.get("pre_stop_running_state_observed") is not True
        or cleanup.get("pre_stop_process_capture_succeeded") is not True
        or type(pre_stop_process_count) is not int
        or pre_stop_process_count < 1
        or any(
            cleanup.get(field) != 0
            for field in (
                "owned_container_residue_count",
                "owned_network_residue_count",
                "owned_volume_residue_count",
                "browser_process_residue_count",
            )
        )
    ):
        raise BoundedSupervisorError("container cleanup evidence is incomplete")
    stdout = captured[prefix + "stdout.log"]
    stderr = captured[prefix + "stderr.log"]
    bound_receipts = (
        [receipts["container-start.json"]]
        if root_name == "browser-preflight"
        else [
            receipts["container-logs.json"],
            receipts["container-workload-result.json"],
        ]
    )
    if any(
        receipt.get("stdout_bytes") != len(stdout)
        or receipt.get("stdout_sha256") != sha256_bytes(stdout)
        or receipt.get("stderr_bytes") != len(stderr)
        or receipt.get("stderr_sha256") != sha256_bytes(stderr)
        for receipt in bound_receipts
    ):
        raise BoundedSupervisorError("container raw logs differ from their command receipts")
    return container_id


def _verify_host_environment_surface(
    captured: Mapping[str, bytes], *, plan: Mapping[str, object]
) -> None:
    record = _strict_json(captured["host-environment.json"], context="host environment")
    selected = _mapping(plan.get("lambda"), context="Lambda plan")
    expected_image = {
        "alias": selected.get("image_alias"),
        "family": selected.get("image_family"),
        "version": selected.get("image_version"),
        "attestation": "confirmed-in-provider-console",
        "binding_basis": "prelaunch-offered-plus-user-console-attestation",
        "post_launch_api_image_observation_available": False,
    }
    os_release = _mapping(record.get("os_release"), context="host OS release")
    kernel = _mapping(record.get("kernel"), context="host kernel")
    python = _mapping(record.get("bootstrap_python"), context="bootstrap Python")
    docker = _mapping(record.get("docker"), context="host Docker")
    gpus = [
        _mapping(value, context="host GPU")
        for value in _sequence(record.get("gpus"), context="host GPUs")
    ]
    info_format = (
        '{"driver":{{json .Driver}},"root":{{json .DockerRootDir}},'
        '"operating_system":{{json .OperatingSystem}},"os_type":{{json .OSType}},'
        '"architecture":{{json .Architecture}},"cgroup_driver":{{json .CgroupDriver}},'
        '"cgroup_version":{{json .CgroupVersion}},'
        '"security_options":{{json .SecurityOptions}}}'
    )
    expected_commands = [
        ["/usr/bin/docker", "version", "--format", "{{json .}}"],
        ["/usr/bin/docker", "info", "--format", info_format],
        [
            "/usr/bin/nvidia-smi",
            "--query-gpu=name,uuid,driver_version",
            "--format=csv,noheader,nounits",
        ],
    ]
    commands = [
        _mapping(value, context="host command observation")
        for value in _sequence(record.get("commands"), context="host commands")
    ]
    if len(commands) != len(expected_commands):
        raise BoundedSupervisorError("host command evidence is incomplete")
    for command, argv in zip(commands, expected_commands, strict=True):
        stdout_bytes = command.get("stdout_bytes")
        stderr_bytes = command.get("stderr_bytes")
        if (
            set(command)
            != {
                "argv",
                "argv_sha256",
                "returncode",
                "stdout_bytes",
                "stderr_bytes",
                "elapsed_seconds",
            }
            or command.get("argv") != argv
            or command.get("argv_sha256") != _argv_sha256(argv)
            or command.get("returncode") != 0
            or type(stdout_bytes) is not int
            or stdout_bytes <= 0
            or type(stderr_bytes) is not int
            or stderr_bytes < 0
            or _finite_number(command.get("elapsed_seconds"), context="host command elapsed") > 30
        ):
            raise BoundedSupervisorError("host command observation drifted")
    if (
        set(record)
        != {
            "schema_version",
            "captured_before_image_build",
            "provider_image",
            "provider_image_identity_basis",
            "os_release",
            "kernel",
            "bootstrap_python",
            "docker",
            "gpus",
            "commands",
            "secret_values_retained",
        }
        or record.get("schema_version") != SCHEMA_VERSION
        or record.get("captured_before_image_build") is not True
        or record.get("provider_image") != expected_image
        or record.get("provider_image_identity_basis")
        != "user-attested-not-postlaunch-api-observed"
        or os_release.get("id") != "ubuntu"
        or os_release.get("version_id") != "22.04"
        or not isinstance(os_release.get("pretty_name"), str)
        or kernel.get("system") != "Linux"
        or kernel.get("machine") not in {"x86_64", "amd64"}
        or not isinstance(kernel.get("release"), str)
        or python.get("executable") != "/usr/bin/python3"
        or not isinstance(python.get("version"), str)
        or docker.get("client_os") != "linux"
        or docker.get("client_arch") not in {"amd64", "x86_64"}
        or docker.get("server_os") != "linux"
        or docker.get("server_arch") not in {"amd64", "x86_64"}
        or docker.get("os_type") != "linux"
        or docker.get("architecture") not in {"amd64", "x86_64"}
        or any(
            not isinstance(docker.get(field), str) or not docker.get(field)
            for field in (
                "client_version",
                "server_version",
                "storage_driver",
                "operating_system",
                "cgroup_driver",
                "cgroup_version",
            )
        )
        or not isinstance(docker.get("root_dir_sha256"), str)
        or _HEX64.fullmatch(str(docker["root_dir_sha256"])) is None
        or not isinstance(docker.get("security_options"), list)
        or len(gpus) != 1
        or "A10" not in _text(gpus[0].get("name"), context="GPU name")
        or not isinstance(gpus[0].get("uuid_sha256"), str)
        or _HEX64.fullmatch(str(gpus[0]["uuid_sha256"])) is None
        or not isinstance(gpus[0].get("driver_version"), str)
        or not gpus[0].get("driver_version")
        or record.get("secret_values_retained") is not False
    ):
        raise BoundedSupervisorError("host environment identity drifted")


def _verify_preflight_and_image_surface(
    captured: Mapping[str, bytes], *, plan: Mapping[str, object]
) -> None:
    _verify_host_environment_surface(captured, plan=plan)
    runtime = _mapping(plan.get("source_and_runtime"), context="source and runtime")
    browser = _strict_json(
        captured["browser-preflight/payload/browser-preflight.json"],
        context="browser preflight",
    )
    screenshot = captured["browser-preflight/payload/browser-preflight.png"]
    installed = captured["browser-preflight/payload/installed-packages.txt"]
    if (
        set(browser)
        != {
            "schema_version",
            "source",
            "network_mode",
            "browser_actions",
            "screenshot_captures",
            "title",
            "screenshot",
            "browser_running_before_container_stop",
            "browser_closed_by_fixture",
            "runtime_uid",
            "runtime_gid",
            "playwright_version",
            "chromium_revision",
            "chromium_browser_version",
            "chromium_executable_sha256",
            "installed_package_manifest_sha256",
        }
        or browser.get("schema_version") != SCHEMA_VERSION
        or browser.get("source") != "local-static-file"
        or browser.get("network_mode") != "none"
        or browser.get("browser_actions") != 1
        or browser.get("screenshot_captures") != 1
        or browser.get("title") != "GIC Lab T07 local browser preflight"
        or browser.get("screenshot") != "browser-preflight.png"
        or browser.get("browser_running_before_container_stop") is not True
        or browser.get("browser_closed_by_fixture") is not False
        or type(browser.get("runtime_uid")) is not int
        or type(browser.get("runtime_gid")) is not int
        or browser.get("playwright_version") != runtime.get("playwright")
        or browser.get("chromium_revision") != runtime.get("chromium_revision")
        or browser.get("chromium_browser_version") != runtime.get("chromium_version")
        or not isinstance(browser.get("chromium_executable_sha256"), str)
        or _HEX64.fullmatch(str(browser["chromium_executable_sha256"])) is None
        or browser.get("installed_package_manifest_sha256") != sha256_bytes(installed)
        or not screenshot.startswith(b"\x89PNG\r\n\x1a\n")
    ):
        raise BoundedSupervisorError("browser preflight evidence drifted")
    model = _strict_json(
        captured["model-preflight/payload/model-availability.json"],
        context="model preflight",
    )
    model_response_bytes = model.get("response_bytes")
    if (
        model
        != {
            "schema_version": SCHEMA_VERSION,
            "method": "GET",
            "scheme": "https",
            "host": "api.openai.com",
            "path": "/v1/models/gpt-4o-2024-11-20",
            "http_status": 200,
            "response_bytes": model.get("response_bytes"),
            "model": "gpt-4o-2024-11-20",
            "available": True,
            "retry_count": 0,
            "redirect_follow_count": 0,
        }
        or type(model_response_bytes) is not int
        or model_response_bytes <= 0
    ):
        raise BoundedSupervisorError("model preflight evidence drifted")
    provenance = _strict_json(captured["image-provenance.json"], context="image provenance")
    expected_provenance = {
        "schema_version": SCHEMA_VERSION,
        "base_image": runtime.get("base_image"),
        "base_image_index_digest": runtime.get("base_image_index_digest"),
        "base_image_amd64_manifest": runtime.get("base_image_amd64_manifest"),
        "base_image_amd64_config": runtime.get("base_image_amd64_config"),
        "source_commit": runtime.get("upstream_commit"),
        "source_tree": runtime.get("upstream_tree"),
        "uv_lock_sha256": runtime.get("uv_lock_sha256"),
        "routing_patch_sha256": runtime.get("routing_patch_sha256"),
        "runtime_adaptation_sha256": runtime.get("runtime_adaptation_sha256"),
        "playwright_version": runtime.get("playwright"),
        "chromium_revision": runtime.get("chromium_revision"),
        "chromium_version": runtime.get("chromium_version"),
        "chromium_executable_sha256": browser.get("chromium_executable_sha256"),
        "installed_package_manifest_sha256": sha256_bytes(installed),
        "image_id": provenance.get("image_id"),
        "platform": runtime.get("platform"),
    }
    image_id = provenance.get("image_id")
    inspected = _strict_json_array(captured["image-inspect.json"], context="image inspect")
    if (
        provenance != expected_provenance
        or not isinstance(image_id, str)
        or re.fullmatch(r"sha256:[a-f0-9]{64}", image_id) is None
        or len(inspected) != 1
        or not isinstance(inspected[0], Mapping)
        or inspected[0].get("Id") != image_id
    ):
        raise BoundedSupervisorError("image provenance evidence drifted")


def _implementation_artifact_sha256(plan: Mapping[str, object], path: str) -> str:
    implementation = _mapping(plan.get("implementation"), context="plan implementation")
    rows = [
        _mapping(item, context="implementation artifact")
        for item in _sequence(implementation.get("artifacts"), context="implementation artifacts")
    ]
    matches = [row for row in rows if row.get("path") == path]
    if len(matches) != 1:
        raise BoundedSupervisorError("implementation artifact binding is unavailable")
    digest = _text(matches[0].get("sha256"), context="implementation artifact SHA-256")
    if _HEX64.fullmatch(digest) is None:
        raise BoundedSupervisorError("implementation artifact SHA-256 is invalid")
    return digest


def _verify_bootstrap_authority_surface(
    captured: Mapping[str, bytes],
    *,
    plan: Mapping[str, object],
    bootstrap_release: Mapping[str, object],
    bootstrap_release_sha256: str,
) -> None:
    record = _strict_json(captured["bootstrap-authority.json"], context="bootstrap authority")
    expected = {
        "schema_version": SCHEMA_VERSION,
        "plan_id": PLAN_ID,
        "host_run_id": HOST_RUN_ID,
        "authorization_reference": bootstrap_release.get("authorization_reference"),
        "execution_commit": bootstrap_release.get("execution_commit"),
        "plan_sha256": bootstrap_release.get("plan_sha256"),
        "contract_sha256": _implementation_artifact_sha256(
            plan, "src/giclab/harness/t07_bounded_smoke.py"
        ),
        "authorization_sha256": bootstrap_release.get("authorization_sha256"),
        "private_binding_sha256": bootstrap_release.get("private_binding_sha256"),
        "bootstrap_release_sha256": bootstrap_release_sha256,
        "bundle_archive_sha256": bootstrap_release.get("bundle_archive_sha256"),
        "bundle_manifest_sha256": bootstrap_release.get("bundle_manifest_sha256"),
        "bootstrap_file_sha256": bootstrap_release.get("bootstrap_file_sha256"),
        "observer_state_sha256": bootstrap_release.get("observer_state_sha256"),
        "post_launch_report_sha256": bootstrap_release.get("post_launch_report_sha256"),
        "provider_active_observed_at_utc": bootstrap_release.get("provider_active_observed_at_utc"),
        "selected_provider_image": bootstrap_release.get("selected_provider_image"),
        "authority_validation_complete": True,
        "secret_value_or_hash_retained": False,
    }
    if record != expected:
        raise BoundedSupervisorError("remote bootstrap authority binding drifted")


def _verify_condition_surface(
    captured: Mapping[str, bytes],
    rows: Mapping[str, tuple[int, str]],
    *,
    plan: Mapping[str, object],
    mode: str,
) -> None:
    runtime_plan = _mapping(plan.get("source_and_runtime"), context="source and runtime")
    runtime = _strict_json(captured[f"{mode}/payload/runtime-environment.json"], context="runtime")
    if (
        set(runtime)
        != {
            "schema_version",
            "python_executable",
            "python_version",
            "os",
            "architecture",
            "upstream_runner",
            "runtime_adaptation_sha256",
            "routing_sha256",
            "environment_variable_names",
            "secret_variable_names",
        }
        or runtime.get("schema_version") != SCHEMA_VERSION
        or runtime.get("python_executable") != "/opt/sira/.venv/bin/python"
        or not isinstance(runtime.get("python_version"), str)
        or not str(runtime["python_version"]).startswith("3.10.")
        or runtime.get("os") != "Linux"
        or runtime.get("architecture") != "x86_64"
        or runtime.get("upstream_runner") != "/opt/sira/scripts/run_web_agent.py"
        or runtime.get("runtime_adaptation_sha256") != runtime_plan.get("runtime_adaptation_sha256")
        or runtime.get("routing_sha256") != runtime_plan.get("routing_sha256")
        or runtime.get("secret_variable_names") != ["SIRA_API_KEY"]
        or "OPENAI_API_KEY"
        in _sequence(runtime.get("environment_variable_names"), context="environment names")
    ):
        raise BoundedSupervisorError("condition runtime identity drifted")
    cleanup = _strict_json(
        captured[f"{mode}/payload/runtime-cleanup.json"], context="runtime cleanup"
    )
    tracked_environments = cleanup.get("tracked_browser_environments")
    if (
        set(cleanup)
        != {
            "schema_version",
            "tracked_browser_environments",
            "close_error_types",
            "all_environment_closes_succeeded",
        }
        or cleanup.get("schema_version") != SCHEMA_VERSION
        or type(tracked_environments) is not int
        or tracked_environments < 1
        or cleanup.get("close_error_types") != []
        or cleanup.get("all_environment_closes_succeeded") is not True
    ):
        raise BoundedSupervisorError("condition browser cleanup evidence drifted")
    sessions = sorted(
        name
        for name in rows
        if name.startswith(f"{mode}/payload/sira-output/") and _is_condition_session_member(name)
    )
    if len(sessions) != 1 or sessions[0] not in captured:
        raise BoundedSupervisorError("condition raw session evidence is missing or ambiguous")
    session = _strict_json(captured[sessions[0]], context=f"{mode} raw session")
    history = _sequence(session.get("history"), context=f"{mode} session history")
    screenshots = 0
    for raw_step in history:
        step = _sequence(raw_step, context=f"{mode} session step")
        if not step or not isinstance(step[0], Mapping):
            continue
        encoded = step[0].get("screenshot")
        if not isinstance(encoded, str) or not encoded:
            continue
        try:
            decoded = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError):
            raise BoundedSupervisorError("condition screenshot evidence is malformed") from None
        if not decoded or len(decoded) > 16_777_216:
            raise BoundedSupervisorError("condition screenshot evidence is empty or oversized")
        screenshots += 1
    source_logs = sorted(
        (name, size)
        for name, (size, _) in rows.items()
        if name.startswith(f"{mode}/payload/source-logs/") and name.endswith(".log")
    )
    if not source_logs or not any(size > 0 for _, size in source_logs):
        raise BoundedSupervisorError("condition source text logs are missing")
    condition = "SIRA-REACTIVE" if mode == "reactive" else "SIRA-SIMULATIVE"
    plan_conditions = [
        _mapping(item, context="plan condition")
        for item in _sequence(plan.get("conditions"), context="plan conditions")
    ]
    bound = next(item for item in plan_conditions if item.get("condition") == condition)
    expected_browser_actions = _nonnegative_integer(
        bound.get("browser_actions"), context="condition browser-action cap"
    )
    if len(history) != expected_browser_actions or screenshots != expected_browser_actions:
        raise BoundedSupervisorError("condition browser-step evidence drifted")
    resolved = _strict_json(captured[f"{mode}/resolved-command.json"], context="resolved command")
    create_argv = [
        _text(item, context="resolved create argument")
        for item in _sequence(resolved.get("container_create_argv"), context="resolved create")
    ]
    template = [
        _text(item, context="planned create argument")
        for item in _sequence(bound.get("container_create_argv_template"), context="planned create")
    ]
    if len(create_argv) != len(template):
        raise BoundedSupervisorError("resolved condition command length drifted")
    for planned, actual in zip(template, create_argv, strict=True):
        if "${" not in planned and planned != actual:
            raise BoundedSupervisorError("resolved condition command drifted")
        if "${SIRA_SECRET_FILE}" in planned and actual != planned.replace(
            "${SIRA_SECRET_FILE}", "/home/ubuntu/.config/giclab/sira_api_key"
        ):
            raise BoundedSupervisorError("resolved secret-file path drifted")
        for placeholder, pattern, context in (
            ("${EXECUTION_COMMIT}", r"[a-f0-9]{40}", "execution commit"),
            (
                "${AUTHORIZATION_REFERENCE}",
                _AUTHORIZATION.pattern,
                "authorization reference",
            ),
            ("${IMAGE_ID}", r"sha256:[a-f0-9]{64}", "image identity"),
        ):
            if placeholder not in planned:
                continue
            before, after = planned.split(placeholder, 1)
            if (
                not actual.startswith(before)
                or not actual.endswith(after)
                or re.fullmatch(
                    pattern,
                    actual[len(before) : len(actual) - len(after) if after else None],
                )
                is None
            ):
                raise BoundedSupervisorError(f"resolved {context} drifted")
    inner = [
        _text(item, context="resolved inner argument")
        for item in _sequence(resolved.get("inner_argv"), context="resolved inner command")
    ]
    configuration_refs = [
        "containers/sira-smoke/bounded/bounded-smoke-plan-v1.json",
        "experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/conditions/"
        + ("smoke-reactive.yaml" if mode == "reactive" else "smoke-simulative.yaml"),
        f"{mode}/resolved-command.json",
    ]
    if (
        set(resolved)
        != {
            "schema_version",
            "condition",
            "run_id",
            "container_create_argv",
            "container_create_argv_sha256",
            "inner_argv",
            "inner_argv_sha256",
            "configuration_refs",
        }
        or resolved.get("schema_version") != SCHEMA_VERSION
        or resolved.get("condition") != condition
        or resolved.get("run_id") != bound.get("run_id")
        or resolved.get("container_create_argv_sha256")
        != sha256_bytes(canonical_json_bytes(create_argv))
        or inner
        != [
            _text(item, context="planned inner argument")
            for item in _sequence(bound.get("inner_argv_template"), context="planned inner")
        ]
        or resolved.get("inner_argv_sha256") != sha256_bytes(canonical_json_bytes(inner))
        or resolved.get("configuration_refs") != configuration_refs
    ):
        raise BoundedSupervisorError("resolved condition command evidence drifted")
    completion = _strict_json(
        captured[f"{mode}/condition-completion.json"], context="condition completion"
    )
    raw_rows = [
        _mapping(item, context="condition raw artifact")
        for item in _sequence(completion.get("raw_artifacts"), context="condition raw artifacts")
    ]
    fixed_payloads = {
        f"{mode}/payload/provider-budget.json",
        f"{mode}/payload/runtime-environment.json",
        f"{mode}/payload/runtime-cleanup.json",
    }
    payload_members = {name for name in rows if name.startswith(f"{mode}/payload/")}
    allowed_payloads = fixed_payloads | set(sessions) | {name for name, _ in source_logs}
    if payload_members != allowed_payloads:
        raise BoundedSupervisorError("condition payload surface contains an unowned artifact")
    expected_raw_rows = [
        {"path": name, "bytes": rows[name][0], "sha256": rows[name][1]}
        for name in sorted(allowed_payloads)
    ]
    if raw_rows != expected_raw_rows:
        raise BoundedSupervisorError("condition raw artifact binding drifted")
    session_refs = [name for name in sessions]
    log_refs = [name for name, _ in source_logs]
    if (
        set(completion)
        != {
            "schema_version",
            "plan_id",
            "host_run_id",
            "run_id",
            "condition",
            "raw_artifacts",
            "raw_session_refs",
            "source_log_refs",
            "resolved_configuration_refs",
            "field_level_provenance",
            "interpretation_allowed",
        }
        or completion.get("schema_version") != SCHEMA_VERSION
        or completion.get("plan_id") != PLAN_ID
        or completion.get("host_run_id") != HOST_RUN_ID
        or completion.get("run_id") != bound.get("run_id")
        or completion.get("condition") != condition
        or completion.get("raw_session_refs") != session_refs
        or completion.get("source_log_refs") != log_refs
        or completion.get("resolved_configuration_refs") != configuration_refs
        or completion.get("field_level_provenance")
        != {
            "raw_artifacts": "observed_file_bytes",
            "runtime": "observed_container_output",
            "accounting": "observed_provider_budget_boundary",
            "cleanup": "observed_runtime_close_record",
        }
        or completion.get("interpretation_allowed") is not False
    ):
        raise BoundedSupervisorError("condition completion evidence drifted")


def _verify_success_surface(
    captured: Mapping[str, bytes],
    rows: Mapping[str, tuple[int, str]],
    *,
    plan: Mapping[str, object],
    bootstrap_release: Mapping[str, object],
    bootstrap_release_sha256: str,
) -> dict[str, float]:
    required = _success_fixed_members()
    if not required.issubset(rows) or not required.issubset(captured):
        raise BoundedSupervisorError("complete evidence lacks its required evidence surface")
    _verify_bootstrap_authority_surface(
        captured,
        plan=plan,
        bootstrap_release=bootstrap_release,
        bootstrap_release_sha256=bootstrap_release_sha256,
    )
    meter_events = [
        _strict_json(line + b"\n", context="command meter event")
        for line in captured["command-meter.jsonl"].splitlines()
        if line
    ]
    limits = _mapping(plan.get("limits"), context="plan limits")
    if not meter_events or len(meter_events) % 2 != 1:
        raise BoundedSupervisorError("command meter ledger is incomplete")
    open_command: tuple[str, str] | None = None
    counter_names = (
        "aggregate_call_count",
        "aggregate_output_bytes",
        "work_call_count",
        "work_output_bytes",
        "cleanup_call_count",
        "cleanup_output_bytes",
    )
    previous_counters: dict[str, int] | None = None
    call_cap = _nonnegative_integer(limits.get("docker_lifecycle_calls"), context="call cap")
    output_cap = _nonnegative_integer(
        limits.get("docker_control_output_bytes"), context="output cap"
    )
    cleanup_call_cap = _nonnegative_integer(
        limits.get("docker_cleanup_reserved_calls"), context="cleanup call cap"
    )
    cleanup_output_cap = _nonnegative_integer(
        limits.get("docker_cleanup_reserved_output_bytes"), context="cleanup output cap"
    )
    for index, event in enumerate(meter_events, start=1):
        if (
            set(event)
            != {
                "schema_version",
                "event_sequence",
                "event_type",
                "scope",
                "argv_sha256",
                "returncode",
                "stdout_bytes",
                "stderr_bytes",
                "elapsed_ms",
                "failure_code",
                "aggregate_call_count",
                "aggregate_output_bytes",
                "work_call_count",
                "work_output_bytes",
                "cleanup_call_count",
                "cleanup_output_bytes",
                "aggregate_call_cap",
                "aggregate_output_cap_bytes",
                "cleanup_reserved_calls",
                "cleanup_reserved_output_bytes",
            }
            or event.get("schema_version") != SCHEMA_VERSION
            or event.get("event_sequence") != index
            or event.get("aggregate_call_cap") != limits.get("docker_lifecycle_calls")
            or event.get("aggregate_output_cap_bytes") != limits.get("docker_control_output_bytes")
            or event.get("cleanup_reserved_calls") != limits.get("docker_cleanup_reserved_calls")
            or event.get("cleanup_reserved_output_bytes")
            != limits.get("docker_cleanup_reserved_output_bytes")
        ):
            raise BoundedSupervisorError("command meter event drifted")
        counters = {
            name: _nonnegative_integer(event.get(name), context=f"command meter {name}")
            for name in counter_names
        }
        if (
            counters["aggregate_call_count"]
            != counters["work_call_count"] + counters["cleanup_call_count"]
            or counters["aggregate_output_bytes"]
            != counters["work_output_bytes"] + counters["cleanup_output_bytes"]
            or counters["aggregate_call_count"] > call_cap
            or counters["work_call_count"] > call_cap - cleanup_call_cap
            or counters["cleanup_call_count"] > cleanup_call_cap
            or counters["aggregate_output_bytes"] > output_cap
            or counters["work_output_bytes"] > output_cap - cleanup_output_cap
            or counters["cleanup_output_bytes"] > cleanup_output_cap
        ):
            raise BoundedSupervisorError("command meter counter invariant drifted")
        event_type = event.get("event_type")
        if index == 1:
            if (
                event_type != "meter_started"
                or event.get("scope") is not None
                or event.get("argv_sha256") is not None
                or event.get("returncode") is not None
                or event.get("stdout_bytes") is not None
                or event.get("stderr_bytes") is not None
                or event.get("elapsed_ms") is not None
                or event.get("failure_code") is not None
                or any(counters.values())
            ):
                raise BoundedSupervisorError("command meter did not start empty")
            previous_counters = counters
            continue
        if previous_counters is None:
            raise BoundedSupervisorError("command meter has no prior counter state")
        if event_type == "command_started":
            if open_command is not None:
                raise BoundedSupervisorError("command meter events overlap")
            scope = _text(event.get("scope"), context="command scope")
            digest = _text(event.get("argv_sha256"), context="command hash")
            if scope not in {"work", "cleanup"}:
                raise BoundedSupervisorError("command meter start scope drifted")
            expected_calls = dict(previous_counters)
            expected_calls["aggregate_call_count"] += 1
            expected_calls[f"{scope}_call_count"] += 1
            if (
                _HEX64.fullmatch(digest) is None
                or event.get("returncode") is not None
                or event.get("stdout_bytes") is not None
                or event.get("stderr_bytes") is not None
                or event.get("elapsed_ms") is not None
                or event.get("failure_code") is not None
                or counters != expected_calls
            ):
                raise BoundedSupervisorError("command meter start counter event drifted")
            open_command = (scope, digest)
        elif event_type == "command_completed":
            scope = _text(event.get("scope"), context="command scope")
            stdout_bytes = _nonnegative_integer(
                event.get("stdout_bytes"), context="command stdout bytes"
            )
            stderr_bytes = _nonnegative_integer(
                event.get("stderr_bytes"), context="command stderr bytes"
            )
            _nonnegative_integer(event.get("elapsed_ms"), context="command elapsed ms")
            if scope not in {"work", "cleanup"}:
                raise BoundedSupervisorError("command meter completion scope drifted")
            if (
                open_command != (scope, event.get("argv_sha256"))
                or type(event.get("returncode")) is not int
                or event.get("failure_code") is not None
                or counters["aggregate_call_count"] != previous_counters["aggregate_call_count"]
                or counters["work_call_count"] != previous_counters["work_call_count"]
                or counters["cleanup_call_count"] != previous_counters["cleanup_call_count"]
                or counters["aggregate_output_bytes"] < previous_counters["aggregate_output_bytes"]
                or counters["work_output_bytes"] < previous_counters["work_output_bytes"]
                or counters["cleanup_output_bytes"] < previous_counters["cleanup_output_bytes"]
                or (
                    counters["aggregate_output_bytes"] - previous_counters["aggregate_output_bytes"]
                    != counters[f"{scope}_output_bytes"]
                    - previous_counters[f"{scope}_output_bytes"]
                    or stdout_bytes + stderr_bytes
                    != counters["aggregate_output_bytes"]
                    - previous_counters["aggregate_output_bytes"]
                )
                or counters[f"{'cleanup' if scope == 'work' else 'work'}_output_bytes"]
                != previous_counters[f"{'cleanup' if scope == 'work' else 'work'}_output_bytes"]
            ):
                raise BoundedSupervisorError("command meter completion drifted")
            open_command = None
        else:
            raise BoundedSupervisorError("successful command meter contains a failure")
        previous_counters = counters
    if open_command is not None:
        raise BoundedSupervisorError("command meter has an unterminated call")
    bootstrap = _strict_json(captured["bootstrap-execution.json"], context="bootstrap execution")
    started = _parse_utc(bootstrap.get("started_at_utc"), context="bootstrap start")
    ended = _parse_utc(bootstrap.get("ended_at_utc"), context="bootstrap end")
    if (
        set(bootstrap)
        != {
            "schema_version",
            "plan_id",
            "run_id",
            "record_kind",
            "started_at_utc",
            "ended_at_utc",
            "wall_clock_seconds",
            "status",
            "provider_allocation_accounting",
            "cost_accounting_authority",
        }
        or bootstrap.get("schema_version") != SCHEMA_VERSION
        or bootstrap.get("plan_id") != PLAN_ID
        or bootstrap.get("run_id") != HOST_RUN_ID
        or bootstrap.get("record_kind") != "remote_bootstrap_execution_interval"
        or bootstrap.get("status") != "completed"
        or bootstrap.get("provider_allocation_accounting") is not False
        or bootstrap.get("cost_accounting_authority") != "local-post-termination-compute-closeout"
        or abs(
            _finite_number(bootstrap.get("wall_clock_seconds"), context="bootstrap wall")
            - (ended - started).total_seconds()
        )
        > 0.000001
        or ended < started
    ):
        raise BoundedSupervisorError("bootstrap execution evidence drifted")
    secret_cleanup = _strict_json(captured["secret-cleanup.json"], context="secret cleanup")
    if secret_cleanup != {
        "schema_version": SCHEMA_VERSION,
        "secret_variable_name": "SIRA_API_KEY",
        "secret_file_basename": "sira_api_key",
        "held_identity_established_before_preflight": True,
        "truncated_before_unlink": True,
        "unlinked": True,
        "absence_verified": True,
        "path_identity_replaced": False,
        "value_or_hash_retained": False,
        "manual_fallback_deletion_required": False,
    }:
        raise BoundedSupervisorError("remote secret cleanup evidence drifted")
    identities = []
    run_ids = {
        "browser-preflight": "RUN-T07-BOUNDED-BROWSER-PREFLIGHT-0001",
        "model-preflight": "RUN-T07-BOUNDED-MODEL-PREFLIGHT-0001",
        "reactive": "RUN-T07-BOUNDED-SIRA-REACTIVE-0001",
        "simulative": "RUN-T07-BOUNDED-SIRA-SIMULATIVE-0001",
    }
    for root_name, condition in _LIFECYCLE_EVIDENCE_ROOTS.items():
        identities.append(
            _verify_lifecycle_surface(
                captured,
                plan=plan,
                root_name=root_name,
                condition=condition,
                run_id=run_ids[root_name],
                bootstrap_release=bootstrap_release,
            )
        )
    if len(set(identities)) != len(identities):
        raise BoundedSupervisorError("attempt container identities are not unique")
    if b"chrom" not in captured["browser-preflight/container-processes-before-stop.txt"].lower():
        raise BoundedSupervisorError("browser process evidence is missing")
    _verify_preflight_and_image_surface(captured, plan=plan)
    for mode in ("reactive", "simulative"):
        _verify_condition_surface(captured, rows, plan=plan, mode=mode)
    return _verify_pair_reconstruction(captured, plan=plan)


def _verify_pair_reconstruction(
    captured: Mapping[str, bytes],
    *,
    plan: Mapping[str, object],
) -> dict[str, float]:
    required = {
        "pair-budget.json",
        "pair-equivalence.json",
        "normalized-events.jsonl",
        "reactive/payload/provider-budget.json",
        "reactive/regulation-decision.json",
        "simulative/payload/provider-budget.json",
        "simulative/regulation-decision.json",
    }
    if not required.issubset(captured):
        raise BoundedSupervisorError("complete evidence lacks reconstruction records")
    plan_conditions = [
        _mapping(item, context="plan condition")
        for item in _sequence(plan.get("conditions"), context="plan conditions")
    ]
    if [item.get("condition") for item in plan_conditions] != [
        "SIRA-REACTIVE",
        "SIRA-SIMULATIVE",
    ]:
        raise BoundedSupervisorError("plan condition order drifted during reconstruction")
    pair = _strict_json(captured["pair-budget.json"], context="pair budget")
    pair_conditions = [
        _mapping(item, context="pair condition")
        for item in _sequence(pair.get("conditions"), context="pair conditions")
    ]
    if (
        set(pair)
        != {
            "schema_version",
            "plan_id",
            "host_run_id",
            "condition_order",
            "conditions",
            "within_all_caps",
        }
        or pair.get("schema_version") != SCHEMA_VERSION
        or pair.get("plan_id") != PLAN_ID
        or pair.get("host_run_id") != HOST_RUN_ID
        or pair.get("condition_order") != ["SIRA-REACTIVE", "SIRA-SIMULATIVE"]
        or pair.get("within_all_caps") is not True
        or len(pair_conditions) != 2
    ):
        raise BoundedSupervisorError("pair budget receipt is incomplete")
    totals: dict[str, float] = {
        "cost_usd": 0.0,
        "model_tokens": 0,
        "model_call_attempts": 0,
        "browser_actions": 0,
        "wall_seconds": 0.0,
        "output_bytes": 0,
    }
    for actual, bound in zip(pair_conditions, plan_conditions, strict=True):
        if (
            set(actual)
            != {
                "condition",
                "run_id",
                "cost_usd",
                "model_tokens",
                "model_call_attempts",
                "browser_actions",
                "wall_seconds",
                "output_bytes",
            }
            or actual.get("condition") != bound.get("condition")
            or actual.get("run_id") != bound.get("run_id")
        ):
            raise BoundedSupervisorError("pair condition identity drifted")
        cost = _finite_number(actual.get("cost_usd"), context="condition cost")
        wall = _finite_number(actual.get("wall_seconds"), context="condition wall")
        for metric in (
            "model_tokens",
            "model_call_attempts",
            "browser_actions",
            "output_bytes",
        ):
            observed = _nonnegative_integer(actual.get(metric), context=metric)
            limit_name = "model_call_attempts" if metric == "model_call_attempts" else metric
            if observed > _nonnegative_integer(bound.get(limit_name), context=f"{metric} cap"):
                raise BoundedSupervisorError("condition evidence exceeds its bound plan")
            totals[metric] += observed
        if cost > _finite_number(
            bound.get("api_cost_usd"), context="condition cost cap"
        ) or wall > _finite_number(bound.get("wall_seconds"), context="condition wall cap"):
            raise BoundedSupervisorError("condition evidence exceeds its bound plan")
        totals["cost_usd"] += cost
        totals["wall_seconds"] += wall
    limits = _mapping(plan.get("limits"), context="plan limits")
    aggregate_caps: dict[str, float] = {
        "cost_usd": _nonnegative_integer(
            limits.get("openai_api_cost_cents_aggregate"), context="API cent cap"
        )
        / 100,
        "model_tokens": _nonnegative_integer(
            limits.get("model_tokens_aggregate"), context="model token cap"
        ),
        "model_call_attempts": _nonnegative_integer(
            limits.get("model_call_attempts_aggregate"), context="model call cap"
        ),
        "browser_actions": _nonnegative_integer(
            limits.get("browser_actions_aggregate"), context="browser action cap"
        ),
        "wall_seconds": _nonnegative_integer(
            limits.get("condition_wall_seconds_aggregate"), context="condition wall cap"
        ),
        "output_bytes": _nonnegative_integer(
            limits.get("condition_output_bytes_aggregate"), context="output cap"
        ),
    }
    if any(totals[field] > cap for field, cap in aggregate_caps.items()):
        raise BoundedSupervisorError("pair evidence exceeds an aggregate cap")

    reactive_argv = [
        _text(item, context="reactive command argument")
        for item in _sequence(
            plan_conditions[0].get("container_create_argv_template"),
            context="reactive command",
        )
    ]
    simulative_argv = [
        _text(item, context="simulative command argument")
        for item in _sequence(
            plan_conditions[1].get("container_create_argv_template"),
            context="simulative command",
        )
    ]
    if len(reactive_argv) != len(simulative_argv):
        raise BoundedSupervisorError("condition command lengths drifted")
    expected_differences = [
        {"index": index, "reactive": left, "simulative": right}
        for index, (left, right) in enumerate(zip(reactive_argv, simulative_argv, strict=True))
        if left != right
    ]
    equivalence = _strict_json(captured["pair-equivalence.json"], context="pair equivalence")
    if (
        set(equivalence)
        != {
            "schema_version",
            "plan_id",
            "host_run_id",
            "condition_order",
            "reactive_command_sha256",
            "simulative_command_sha256",
            "difference_count",
            "differences",
            "canonical_condition_diff_only",
            "trace_instrumentation_changed_contrast",
            "interpretation_allowed",
        }
        or equivalence.get("schema_version") != SCHEMA_VERSION
        or equivalence.get("plan_id") != PLAN_ID
        or equivalence.get("host_run_id") != HOST_RUN_ID
        or equivalence.get("condition_order") != ["SIRA-REACTIVE", "SIRA-SIMULATIVE"]
        or equivalence.get("reactive_command_sha256")
        != sha256_bytes(canonical_json_bytes(reactive_argv))
        or equivalence.get("simulative_command_sha256")
        != sha256_bytes(canonical_json_bytes(simulative_argv))
        or equivalence.get("difference_count") != len(expected_differences)
        or equivalence.get("differences") != expected_differences
        or equivalence.get("canonical_condition_diff_only") is not True
        or equivalence.get("trace_instrumentation_changed_contrast") is not False
        or equivalence.get("interpretation_allowed") is not False
    ):
        raise BoundedSupervisorError("pair equivalence receipt drifted")

    for mode, condition in (("reactive", "SIRA-REACTIVE"), ("simulative", "SIRA-SIMULATIVE")):
        budget_encoded = captured[f"{mode}/payload/provider-budget.json"]
        budget = _strict_json(budget_encoded, context=f"{mode} provider budget")
        input_tokens = _nonnegative_integer(
            budget.get("input_tokens"), context="provider input tokens"
        )
        cached_tokens = _nonnegative_integer(
            budget.get("cached_input_tokens"), context="provider cached tokens"
        )
        output_tokens = _nonnegative_integer(
            budget.get("output_tokens"), context="provider output tokens"
        )
        provider_output_bytes = _nonnegative_integer(
            budget.get("output_bytes"), context="provider output bytes"
        )
        condition_record = pair_conditions[0 if condition == "SIRA-REACTIVE" else 1]
        if (
            set(budget)
            != {
                "schema_version",
                "model_revision",
                "cost_usd",
                "input_tokens",
                "cached_input_tokens",
                "output_tokens",
                "total_tokens",
                "model_call_attempts",
                "unreconciled_provider_attempts",
                "browser_actions",
                "output_bytes",
            }
            or budget.get("schema_version") != SCHEMA_VERSION
            or budget.get("model_revision") != "gpt-4o-2024-11-20"
            or cached_tokens > input_tokens
            or budget.get("total_tokens") != input_tokens + output_tokens
            or budget.get("unreconciled_provider_attempts") != 0
            or _finite_number(budget.get("cost_usd"), context="provider cost")
            != _finite_number(condition_record.get("cost_usd"), context="pair cost")
            or input_tokens + output_tokens != condition_record.get("model_tokens")
            or budget.get("model_call_attempts") != condition_record.get("model_call_attempts")
            or budget.get("browser_actions") != condition_record.get("browser_actions")
            or provider_output_bytes < 0
        ):
            raise BoundedSupervisorError("provider budget reconstruction drifted")
        decision = _strict_json(
            captured[f"{mode}/regulation-decision.json"],
            context=f"{mode} regulation decision",
        )
        configuration_refs = [
            "containers/sira-smoke/bounded/bounded-smoke-plan-v1.json",
            "experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/conditions/"
            + ("smoke-reactive.yaml" if mode == "reactive" else "smoke-simulative.yaml"),
            f"{mode}/resolved-command.json",
        ]
        decision_provenance = {
            "source_kind": "observed_from_locked_experiment_assignment",
            "selected_mode": "derived_from_locked_condition_plan",
            "assignment_policy_sha256": "observed_file_hash",
            "resolved_configuration_refs": "observed_repository_paths",
            "raw_artifact_refs": "observed_owned_output_paths",
            "confidence": "unavailable_from_pinned_source",
            "override": "unavailable_from_pinned_source",
            "fallback": "unavailable_from_pinned_source",
            "critic": "unavailable_from_pinned_source",
            "configurator": "unavailable_from_pinned_source",
            "per_step_planning": "unavailable_from_pinned_source",
        }
        if (
            set(decision)
            != {
                "schema_version",
                "plan_id",
                "host_run_id",
                "run_id",
                "condition",
                "source_kind",
                "selected_mode",
                "assignment_policy_sha256",
                "resolved_configuration_refs",
                "raw_artifact_roots",
                "field_level_provenance",
                "confidence",
                "override",
                "fallback",
                "critic",
                "configurator",
                "per_step_planning",
                "interpretation_allowed",
            }
            or decision.get("schema_version") != SCHEMA_VERSION
            or decision.get("plan_id") != PLAN_ID
            or decision.get("host_run_id") != HOST_RUN_ID
            or decision.get("run_id")
            != (
                "RUN-T07-BOUNDED-SIRA-REACTIVE-0001"
                if condition == "SIRA-REACTIVE"
                else "RUN-T07-BOUNDED-SIRA-SIMULATIVE-0001"
            )
            or decision.get("condition") != condition
            or decision.get("source_kind") != "experiment_assignment"
            or decision.get("selected_mode") != mode
            or decision.get("assignment_policy_sha256") != CONDITION_PLAN_SHA256[condition]
            or decision.get("resolved_configuration_refs") != configuration_refs
            or decision.get("raw_artifact_roots")
            != [f"{mode}/payload/sira-output", f"{mode}/payload/source-logs"]
            or decision.get("field_level_provenance") != decision_provenance
            or any(
                decision.get(field) is not None
                for field in (
                    "confidence",
                    "override",
                    "fallback",
                    "critic",
                    "configurator",
                    "per_step_planning",
                )
            )
            or decision.get("interpretation_allowed") is not False
        ):
            raise BoundedSupervisorError("regulation-decision receipt drifted")

    events = [
        _strict_json(line + b"\n", context="normalized event")
        for line in captured["normalized-events.jsonl"].splitlines()
        if line
    ]
    expected_events: list[dict[str, object]] = []
    for condition, run_id, mode in (
        ("SIRA-REACTIVE", "RUN-T07-BOUNDED-SIRA-REACTIVE-0001", "reactive"),
        ("SIRA-SIMULATIVE", "RUN-T07-BOUNDED-SIRA-SIMULATIVE-0001", "simulative"),
    ):
        decision = _strict_json(
            captured[f"{mode}/regulation-decision.json"], context="event decision"
        )
        completion = _strict_json(
            captured[f"{mode}/condition-completion.json"], context="event completion"
        )
        expected_events.extend(
            [
                {
                    "schema_version": SCHEMA_VERSION,
                    "plan_id": PLAN_ID,
                    "host_run_id": HOST_RUN_ID,
                    "run_id": run_id,
                    "event_sequence": len(expected_events) + 1,
                    "event_type": "condition_assignment_bound",
                    "condition": condition,
                    "source_kind": "experiment_assignment",
                    "evidence_reference": f"{mode}/regulation-decision.json",
                    "raw_artifact_refs": [],
                    "resolved_configuration_refs": decision.get("resolved_configuration_refs"),
                    "field_level_provenance": decision.get("field_level_provenance"),
                    "interpretation_allowed": False,
                },
                {
                    "schema_version": SCHEMA_VERSION,
                    "plan_id": PLAN_ID,
                    "host_run_id": HOST_RUN_ID,
                    "run_id": run_id,
                    "event_sequence": len(expected_events) + 2,
                    "event_type": "condition_execution_completed",
                    "condition": condition,
                    "source_kind": "experiment_assignment",
                    "evidence_reference": f"{mode}/condition-completion.json",
                    "raw_artifact_refs": [
                        row.get("path")
                        for row in _sequence(
                            completion.get("raw_artifacts"), context="completion artifacts"
                        )
                        if isinstance(row, Mapping)
                    ],
                    "resolved_configuration_refs": completion.get("resolved_configuration_refs"),
                    "field_level_provenance": completion.get("field_level_provenance"),
                    "interpretation_allowed": False,
                },
            ]
        )
    if len(events) != len(expected_events):
        raise BoundedSupervisorError("normalized reconstruction events drifted")
    previous_monotonic = 0
    for event, expected in zip(events, expected_events, strict=True):
        observed_monotonic = _nonnegative_integer(
            event.get("monotonic_timestamp_ns"), context="event monotonic timestamp"
        )
        _parse_utc(event.get("wall_timestamp_utc"), context="event wall timestamp")
        reduced = dict(event)
        reduced.pop("monotonic_timestamp_ns", None)
        reduced.pop("wall_timestamp_utc", None)
        if observed_monotonic <= previous_monotonic or reduced != expected:
            raise BoundedSupervisorError("normalized reconstruction events drifted")
        previous_monotonic = observed_monotonic
    return totals


def _verify_zip_payload(
    root: Path,
    archive: Path,
    *,
    plan: Mapping[str, object],
    manifest_name: str,
    failure: bool,
    early_failure: bool,
    termination_receipt_encoded: bytes,
    bootstrap_release: Mapping[str, object],
    bootstrap_release_sha256: str,
) -> dict[str, object]:
    capture_names = {manifest_name}
    if not failure:
        capture_names.update(_success_fixed_members())
    else:
        capture_names.add("TERMINATE_REQUIRED.json")
        if early_failure:
            capture_names.update(
                {
                    "evidence/early-failure-disposition.json",
                    "evidence/secret-cleanup.json",
                }
            )
        else:
            capture_names.add("bootstrap-authority.json")
    rows: dict[str, tuple[int, str]] = {}
    captured: dict[str, bytes] = {}
    total = 0
    try:
        with zipfile.ZipFile(archive, "r") as opened:
            if opened.comment:
                raise BoundedSupervisorError("inbound archive contains an unbound comment")
            infos = opened.infolist()
            if not infos or len(infos) > MAX_REMOTE_EVIDENCE_FILES + 1:
                raise BoundedSupervisorError("inbound archive file count is invalid")
            for info in infos:
                if info.comment or info.extra:
                    raise BoundedSupervisorError("inbound archive member contains unbound metadata")
                name = _safe_zip_member_name(info.filename)
                if name in rows:
                    raise BoundedSupervisorError("inbound archive repeats a member")
                size, digest, retained = _read_verified_zip_member(
                    opened,
                    info,
                    capture=name in capture_names
                    or (not failure and _is_condition_session_member(name)),
                )
                total += size
                if total > MAX_REMOTE_EVIDENCE_BYTES:
                    raise BoundedSupervisorError("decoded inbound archive exceeds its cap")
                rows[name] = (size, digest)
                if retained is not None:
                    captured[name] = retained
    except (OSError, zipfile.BadZipFile):
        raise BoundedSupervisorError("inbound evidence is not a valid archive") from None
    manifest_encoded = captured.get(manifest_name)
    if manifest_encoded is None or len(manifest_encoded) > 1_048_576:
        raise BoundedSupervisorError("inbound evidence manifest is missing or oversized")
    manifest = _strict_json(manifest_encoded, context="inbound evidence manifest")
    if failure:
        required_keys = {
            "schema_version",
            "plan_id",
            "host_run_id",
            "disposition",
            "files",
            "file_count",
            "payload_bytes",
            "skipped_secret_shaped_file_count",
            "skipped_cap_or_unsafe_file_count",
            "secret_values_retained",
            "source_retained",
        }
        if (
            set(manifest) != required_keys
            or manifest.get("schema_version") != SCHEMA_VERSION
            or manifest.get("plan_id") != PLAN_ID
            or manifest.get("host_run_id") != HOST_RUN_ID
            or manifest.get("disposition") != "bootstrap_failed"
            or manifest.get("secret_values_retained") is not False
            or manifest.get("source_retained") is not True
        ):
            raise BoundedSupervisorError("failure evidence manifest identity drifted")
    else:
        schema, _ = _load_schema(root, EVIDENCE_SCHEMA_RELATIVE)
        _validate_schema(manifest, schema, context="inbound evidence manifest")
    manifest_rows = _sequence(manifest.get("files"), context="inbound manifest files")
    expected: dict[str, tuple[int, str]] = {}
    payload_bytes = 0
    for raw in manifest_rows:
        row = _mapping(raw, context="inbound manifest row")
        if set(row) != {"path", "bytes", "sha256"}:
            raise BoundedSupervisorError("inbound manifest row shape drifted")
        name = _safe_zip_member_name(_text(row.get("path"), context="manifest path"))
        size = _nonnegative_integer(row.get("bytes"), context="manifest bytes")
        digest = _text(row.get("sha256"), context="manifest SHA-256")
        if name in expected or _HEX64.fullmatch(digest) is None:
            raise BoundedSupervisorError("inbound manifest row identity drifted")
        expected[name] = (size, digest)
        payload_bytes += size
    actual_payload = {name: value for name, value in rows.items() if name != manifest_name}
    if (
        actual_payload != expected
        or manifest.get("file_count") != len(expected)
        or manifest.get("payload_bytes", manifest.get("total_bytes")) != payload_bytes
    ):
        raise BoundedSupervisorError("inbound archive members do not match their manifest")
    if early_failure:
        incident = _strict_json(
            termination_receipt_encoded, context="early-failure termination receipt"
        )
        if (
            manifest.get("skipped_secret_shaped_file_count") != 0
            or manifest.get("skipped_cap_or_unsafe_file_count") != 0
        ):
            raise BoundedSupervisorError("early-failure archive omitted evidence")
        cleanup_verified = incident.get("secret_cleanup_verified") is True
        exact_members = {
            "evidence/early-failure-disposition.json",
            "TERMINATE_REQUIRED.json",
        }
        if cleanup_verified:
            exact_members.add("evidence/secret-cleanup.json")
        if set(actual_payload) != exact_members:
            raise BoundedSupervisorError("early-failure archive member set is incomplete")
        early_disposition = _strict_json(
            captured["evidence/early-failure-disposition.json"],
            context="early-failure disposition",
        )
        if (
            set(early_disposition)
            != {
                "schema_version",
                "plan_id",
                "host_run_id",
                "failure_stage",
                "failure_code",
                "message_retained",
                "secret_target_identity_established",
                "secret_cleanup_verified",
                "manual_secret_deletion_and_rotation_required",
                "secret_value_read",
                "value_or_hash_retained",
            }
            or early_disposition.get("schema_version") != SCHEMA_VERSION
            or early_disposition.get("plan_id") != PLAN_ID
            or early_disposition.get("host_run_id") != HOST_RUN_ID
            or early_disposition.get("failure_stage") != incident.get("failure_stage")
            or early_disposition.get("failure_code") != incident.get("failure_class")
            or early_disposition.get("message_retained") is not False
            or early_disposition.get("secret_target_identity_established")
            != incident.get("secret_target_validation_completed")
            or early_disposition.get("secret_cleanup_verified") != cleanup_verified
            or early_disposition.get("manual_secret_deletion_and_rotation_required")
            != (not cleanup_verified)
            or early_disposition.get("secret_value_read") != incident.get("secret_value_read")
            or early_disposition.get("value_or_hash_retained") is not False
            or incident.get("manual_credential_rotation_required")
            != (incident.get("failure_class") == "credential_material_detected")
        ):
            raise BoundedSupervisorError("early-failure disposition binding drifted")
        if cleanup_verified:
            cleanup = _strict_json(
                captured["evidence/secret-cleanup.json"],
                context="early-failure secret cleanup",
            )
            if cleanup != {
                "schema_version": SCHEMA_VERSION,
                "secret_variable_name": "SIRA_API_KEY",
                "secret_file_basename": "sira_api_key",
                "held_identity_established_before_preflight": True,
                "truncated_before_unlink": True,
                "unlinked": True,
                "absence_verified": True,
                "path_identity_replaced": False,
                "value_or_hash_retained": False,
                "manual_fallback_deletion_required": False,
            }:
                raise BoundedSupervisorError("early-failure secret cleanup drifted")
    elif failure:
        if "bootstrap-authority.json" not in captured:
            raise BoundedSupervisorError("failure evidence lacks bootstrap authority")
        _verify_bootstrap_authority_surface(
            captured,
            plan=plan,
            bootstrap_release=bootstrap_release,
            bootstrap_release_sha256=bootstrap_release_sha256,
        )
    reconstruction: dict[str, float] | None = None
    if not failure:
        reconstruction = _verify_success_surface(
            captured,
            rows,
            plan=plan,
            bootstrap_release=bootstrap_release,
            bootstrap_release_sha256=bootstrap_release_sha256,
        )
    elif captured.get("TERMINATE_REQUIRED.json") != termination_receipt_encoded:
        raise BoundedSupervisorError("failure archive termination receipt is not bound")
    result: dict[str, object] = {
        "archive_member_count": len(rows),
        "decoded_payload_bytes": total,
        "manifest_sha256": sha256_bytes(manifest_encoded),
        "all_member_hashes_verified": True,
        "decoded_secret_scan_passed": True,
    }
    if reconstruction is not None:
        result["reconstruction_usage"] = reconstruction
    return result


def _verify_inbound_evidence(
    root: Path,
    *,
    plan: Mapping[str, object],
    disposition: str,
) -> dict[str, object]:
    inbound = root / INBOUND_RELATIVE
    release_path = root / BOOTSTRAP_RELEASE_RELATIVE
    release_encoded: bytes | None = None
    if release_path.exists():
        release_encoded = _read_regular(release_path, max_bytes=MAX_AUTHORIZATION_BYTES)
        release = _strict_json(release_encoded, context="bootstrap release")
        selected = _mapping(plan.get("lambda"), context="Lambda plan")
        if (
            set(release)
            != {
                "schema_version",
                "plan_id",
                "host_run_id",
                "authorization_reference",
                "execution_commit",
                "plan_sha256",
                "authorization_sha256",
                "private_binding_sha256",
                "observer_state_sha256",
                "post_launch_report_sha256",
                "bundle_archive_sha256",
                "bundle_manifest_sha256",
                "bootstrap_file_sha256",
                "provider_active_observed_at_utc",
                "selected_provider_image",
                "issued_at_utc",
                "bootstrap_release",
                "single_use_output_root",
            }
            or release.get("schema_version") != SCHEMA_VERSION
            or release.get("plan_id") != PLAN_ID
            or release.get("host_run_id") != HOST_RUN_ID
            or not isinstance(release.get("authorization_reference"), str)
            or _AUTHORIZATION.fullmatch(str(release["authorization_reference"])) is None
            or not isinstance(release.get("execution_commit"), str)
            or _HEX40.fullmatch(str(release["execution_commit"])) is None
            or any(
                not isinstance(release.get(field), str)
                or _HEX64.fullmatch(str(release[field])) is None
                for field in (
                    "plan_sha256",
                    "authorization_sha256",
                    "private_binding_sha256",
                    "observer_state_sha256",
                    "post_launch_report_sha256",
                    "bundle_archive_sha256",
                    "bundle_manifest_sha256",
                    "bootstrap_file_sha256",
                )
            )
            or release.get("selected_provider_image")
            != {
                "alias": selected.get("image_alias"),
                "family": selected.get("image_family"),
                "version": selected.get("image_version"),
                "attestation": "confirmed-in-provider-console",
                "binding_basis": "prelaunch-offered-plus-user-console-attestation",
                "post_launch_api_image_observation_available": False,
            }
            or release.get("bootstrap_release") is not True
            or release.get("single_use_output_root") != "/home/ubuntu/t07-bounded-output-0001"
        ):
            raise BoundedSupervisorError("bootstrap release evidence drifted")
    success = {
        "t07-bounded-evidence.zip",
        "ARCHIVE_IDENTITY.json",
        "TERMINATE_REQUIRED.json",
    }
    failure = {
        "t07-bounded-failure-evidence.zip",
        "FAILURE_ARCHIVE_IDENTITY.json",
        "TERMINATE_REQUIRED.json",
    }
    early_failure = {
        "t07-bounded-early-failure-evidence.zip",
        "EARLY_FAILURE_ARCHIVE_IDENTITY.json",
        "TERMINATE_REQUIRED.json",
    }
    if not inbound.exists():
        if disposition == "complete" or release_encoded is not None:
            raise BoundedSupervisorError("released bootstrap evidence was not downloaded")
        return {
            "schema_version": SCHEMA_VERSION,
            "plan_id": PLAN_ID,
            "run_id": HOST_RUN_ID,
            "remote_archive_kind": "not-produced-before-bootstrap",
            "bootstrap_release_present": False,
            "remote_bootstrap_provably_not_authorized": True,
            "all_member_hashes_verified": False,
            "decoded_secret_scan_passed": True,
        }
    if release_encoded is None:
        raise BoundedSupervisorError("inbound evidence has no durable bootstrap release")
    if inbound.is_symlink() or not inbound.is_dir():
        raise BoundedSupervisorError("inbound evidence root is unsafe")
    observed = {path.name for path in inbound.iterdir()}
    if any(path.is_symlink() or not path.is_file() for path in inbound.iterdir()):
        raise BoundedSupervisorError("inbound evidence contains a non-regular entry")
    if observed == success:
        archive_name = "t07-bounded-evidence.zip"
        identity_name = "ARCHIVE_IDENTITY.json"
        manifest_name = "EVIDENCE_MANIFEST.json"
        failure_kind = False
    elif observed == failure and disposition == "failed":
        archive_name = "t07-bounded-failure-evidence.zip"
        identity_name = "FAILURE_ARCHIVE_IDENTITY.json"
        manifest_name = "FAILURE_EVIDENCE_MANIFEST.json"
        failure_kind = True
        remote_archive_kind = "failure"
    elif observed == early_failure and disposition == "failed":
        archive_name = "t07-bounded-early-failure-evidence.zip"
        identity_name = "EARLY_FAILURE_ARCHIVE_IDENTITY.json"
        manifest_name = "FAILURE_EVIDENCE_MANIFEST.json"
        failure_kind = True
        remote_archive_kind = "early_failure"
    else:
        raise BoundedSupervisorError("inbound evidence set is incomplete or ambiguous")
    if not failure_kind:
        remote_archive_kind = "complete"
    archive = inbound / archive_name
    archive_encoded = _read_regular(archive, max_bytes=MAX_REMOTE_EVIDENCE_BYTES)
    identity = _strict_json(
        _read_regular(inbound / identity_name, max_bytes=65_536), context="archive identity"
    )
    expected_identity_keys = (
        {"archive", "bytes", "sha256", "source_retained"}
        if not failure_kind
        else {
            "schema_version",
            "archive",
            "bytes",
            "sha256",
            "manifest_sha256",
            "secret_scan_passed",
            "source_retained",
        }
    )
    if (
        set(identity) != expected_identity_keys
        or identity.get("archive") != archive_name
        or identity.get("bytes") != len(archive_encoded)
        or identity.get("sha256") != sha256_bytes(archive_encoded)
        or identity.get("source_retained") is not True
        or (failure_kind and identity.get("secret_scan_passed") is not True)
    ):
        raise BoundedSupervisorError("downloaded archive identity verification failed")
    incident_encoded = _read_regular(inbound / "TERMINATE_REQUIRED.json", max_bytes=65_536)
    incident = _strict_json(incident_encoded, context="termination receipt")
    if (
        incident.get("provider_termination_required") is not True
        or incident.get("message_retained") is not False
        or (not failure_kind and incident.get("bootstrap_complete") is not True)
        or (failure_kind and not isinstance(incident.get("failure_class"), str))
        or (failure_kind and not isinstance(incident.get("failure_stage"), str))
        or not isinstance(incident.get("secret_cleanup_verified"), bool)
        or incident.get("manual_secret_deletion_required")
        != (not bool(incident.get("secret_cleanup_verified")))
        or not isinstance(incident.get("manual_credential_rotation_required"), bool)
        or (not failure_kind and incident.get("secret_cleanup_verified") is not True)
    ):
        raise BoundedSupervisorError("provider termination receipt drifted")
    result = _verify_zip_payload(
        root,
        archive,
        plan=plan,
        manifest_name=manifest_name,
        failure=failure_kind,
        early_failure=remote_archive_kind == "early_failure",
        termination_receipt_encoded=incident_encoded,
        bootstrap_release=release,
        bootstrap_release_sha256=sha256_bytes(release_encoded),
    )
    if failure_kind and identity.get("manifest_sha256") != result["manifest_sha256"]:
        raise BoundedSupervisorError("failure manifest identity verification failed")
    return {
        "schema_version": SCHEMA_VERSION,
        "plan_id": PLAN_ID,
        "run_id": HOST_RUN_ID,
        "remote_archive_kind": remote_archive_kind,
        "archive": archive_name,
        "archive_bytes": len(archive_encoded),
        "archive_sha256": sha256_bytes(archive_encoded),
        "archive_identity_sha256": sha256_bytes(
            _read_regular(inbound / identity_name, max_bytes=65_536)
        ),
        "termination_receipt_sha256": sha256_bytes(incident_encoded),
        "bootstrap_release_present": True,
        "bootstrap_release_sha256": sha256_bytes(release_encoded),
        "remote_bootstrap_provably_not_authorized": False,
        "secret_cleanup_verified": incident.get("secret_cleanup_verified"),
        "manual_secret_deletion_required": incident.get("manual_secret_deletion_required"),
        "manual_credential_rotation_required": incident.get("manual_credential_rotation_required"),
        **result,
    }


def verify_inbound_evidence(
    root: Path,
    *,
    plan: Mapping[str, object],
    plan_sha256: str,
    expected_commit: str,
    authorization_path: Path,
    authorization_sha256: str,
    private_binding_path: Path,
    private_binding_sha256: str,
    disposition: str,
    utc_now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> dict[str, object]:
    """Hash-first verification that must succeed before provider termination."""

    if disposition not in {"complete", "failed"}:
        raise BoundedSupervisorError("inbound verification disposition is invalid")
    verify_repository_identity(root, expected_commit)
    authorization, private = _validate_authority_inputs(
        root,
        plan=plan,
        plan_sha256=plan_sha256,
        authorization_path=authorization_path,
        authorization_sha256=authorization_sha256,
        private_binding_path=private_binding_path,
        private_binding_sha256=private_binding_sha256,
        utc_now=utc_now,
        require_live=False,
    )
    state = _load_state(root)
    if state.get("termination_verified") is True or state.get("status") in {
        "complete",
        "cleanup_complete",
        "cleanup_incomplete",
    }:
        raise BoundedSupervisorError("inbound verification must precede provider termination")
    if disposition == "complete" and (
        state.get("status") != "post_launch_passed" or state.get("next_phase") != "termination"
    ):
        raise BoundedSupervisorError("complete inbound verification requires the launch checkpoint")
    release_path = root / BOOTSTRAP_RELEASE_RELATIVE
    if release_path.exists():
        replay = _verify_observer_evidence(
            root,
            authorization=authorization,
            private=private,
            authorization_sha256=authorization_sha256,
            private_binding_sha256=private_binding_sha256,
            disposition="post_launch",
            write_receipt=False,
        )
        _validate_local_bootstrap_release(
            root,
            plan=plan,
            plan_sha256=plan_sha256,
            expected_commit=expected_commit,
            authorization=authorization,
            authorization_sha256=authorization_sha256,
            private=private,
            private_binding_sha256=private_binding_sha256,
            replay=replay,
        )
    verification = _verify_inbound_evidence(root, plan=plan, disposition=disposition)
    receipt = {
        "schema_version": SCHEMA_VERSION,
        "plan_id": PLAN_ID,
        "run_id": HOST_RUN_ID,
        "disposition": disposition,
        "plan_sha256": plan_sha256,
        "authorization_sha256": authorization_sha256,
        "private_binding_sha256": private_binding_sha256,
        "verified_at_utc": _utc_text(utc_now()),
        "verification": verification,
        "source_retained": True,
        "provider_termination_not_yet_verified": True,
    }
    encoded = canonical_json_bytes(receipt)
    _write_exclusive(root / INBOUND_VERIFICATION_RELATIVE, encoded, mode=0o644)
    cleanup_transition_applied = False
    if disposition == "failed" and state.get("status") != "cleanup_required":
        status = state.get("status")
        if status == "post_launch_passed":
            state["cleanup_origin_phase"] = "post_launch"
            state["status"] = "cleanup_required"
            state["next_phase"] = "termination"
        elif status == "security_passed":
            # A manual launch could have occurred after the last durable observer
            # checkpoint, so prove provider absence through the termination phase.
            state["cleanup_origin_phase"] = "security"
            state["status"] = "cleanup_required"
            state["next_phase"] = "termination"
        elif status in {"prelaunch_passed", "materialized"}:
            state["cleanup_origin_phase"] = "prelaunch"
            state["status"] = "cleanup_required"
            state["next_phase"] = "terminal"
        elif status not in {"cleanup_required", "cleanup_incomplete"}:
            raise BoundedSupervisorError(
                "failed inbound disposition cannot enter a typed cleanup path"
            )
        if state.get("status") == "cleanup_required":
            _atomic_write(root / STATE_RELATIVE, canonical_json_bytes(state))
            cleanup_transition_applied = True
    return {
        "schema_version": SCHEMA_VERSION,
        "plan_id": PLAN_ID,
        "run_id": HOST_RUN_ID,
        "disposition": disposition,
        "inbound_verification_path": str(root / INBOUND_VERIFICATION_RELATIVE),
        "inbound_verification_bytes": len(encoded),
        "inbound_verification_sha256": sha256_bytes(encoded),
        "all_member_hashes_verified": verification.get("all_member_hashes_verified"),
        "cleanup_transition_applied": cleanup_transition_applied,
        "source_retained": True,
    }


def _revalidate_inbound_receipt(
    root: Path,
    *,
    plan: Mapping[str, object],
    plan_sha256: str,
    expected_commit: str,
    authorization: Mapping[str, object],
    authorization_sha256: str,
    private: Mapping[str, object],
    private_binding_sha256: str,
    disposition: str,
) -> tuple[dict[str, object], str]:
    if (root / BOOTSTRAP_RELEASE_RELATIVE).exists():
        _validate_local_bootstrap_release(
            root,
            plan=plan,
            plan_sha256=plan_sha256,
            expected_commit=expected_commit,
            authorization=authorization,
            authorization_sha256=authorization_sha256,
            private=private,
            private_binding_sha256=private_binding_sha256,
            replay=None,
        )
    encoded = _read_regular(root / INBOUND_VERIFICATION_RELATIVE, max_bytes=MAX_RESPONSE_BYTES)
    receipt = _strict_json(encoded, context="inbound verification receipt")
    verification = _mapping(receipt.get("verification"), context="inbound verification")
    expected = _verify_inbound_evidence(root, plan=plan, disposition=disposition)
    if (
        set(receipt)
        != {
            "schema_version",
            "plan_id",
            "run_id",
            "disposition",
            "plan_sha256",
            "authorization_sha256",
            "private_binding_sha256",
            "verified_at_utc",
            "verification",
            "source_retained",
            "provider_termination_not_yet_verified",
        }
        or receipt.get("schema_version") != SCHEMA_VERSION
        or receipt.get("plan_id") != PLAN_ID
        or receipt.get("run_id") != HOST_RUN_ID
        or receipt.get("disposition") != disposition
        or receipt.get("plan_sha256") != plan_sha256
        or receipt.get("authorization_sha256") != authorization_sha256
        or receipt.get("private_binding_sha256") != private_binding_sha256
        or receipt.get("source_retained") is not True
        or receipt.get("provider_termination_not_yet_verified") is not True
        or verification != expected
    ):
        raise BoundedSupervisorError("inbound verification receipt drifted")
    _parse_utc(receipt.get("verified_at_utc"), context="inbound verification time")
    return dict(verification), sha256_bytes(encoded)


def _observer_request_contract() -> dict[int, tuple[str, str]]:
    contract: dict[int, tuple[str, str]] = {}
    for phase, paths in PHASE_REQUESTS.items():
        for offset, path in enumerate(paths):
            contract[PHASE_START_ORDINAL[phase] + offset] = (phase, path)
    if set(contract) != set(range(1, MAX_REQUESTS + 1)):
        raise BoundedSupervisorError("observer request ordinal contract is incomplete")
    return contract


def _verify_observer_evidence(
    root: Path,
    *,
    authorization: Mapping[str, object],
    private: Mapping[str, object],
    authorization_sha256: str,
    private_binding_sha256: str,
    disposition: str,
    write_receipt: bool = True,
) -> dict[str, object]:
    """Reconcile the final observer state, ledger, reports, and response receipts."""

    if disposition not in {"complete", "failed", "post_launch"}:
        raise BoundedSupervisorError("observer verification disposition is invalid")
    if disposition == "post_launch" and write_receipt:
        raise BoundedSupervisorError("post-launch replay must not consume the final receipt path")

    state = _load_state(root)
    authorization_reference = _text(
        authorization.get("authorization_reference"), context="authorization reference"
    )
    if (
        state.get("schema_version") != SCHEMA_VERSION
        or state.get("plan_id") != PLAN_ID
        or state.get("run_id") != HOST_RUN_ID
        or state.get("authorization_reference") != authorization_reference
        or state.get("authorization_sha256") != authorization_sha256
        or state.get("private_binding_sha256") != private_binding_sha256
    ):
        raise BoundedSupervisorError("observer state authority binding drifted")

    ledger_schema, ledger_schema_sha256 = _load_schema(root, LEDGER_SCHEMA_RELATIVE)
    ledger = FsyncLedger(
        root / LEDGER_RELATIVE,
        schema=ledger_schema,
        authorization_reference=authorization_reference,
    )
    attempted_raw = state.get("attempted_request_ordinals")
    if not isinstance(attempted_raw, list) or any(
        type(value) is not int for value in attempted_raw
    ):
        raise BoundedSupervisorError("observer attempted-request state is invalid")
    attempted = list(attempted_raw)
    sent = [
        cast(int, event["request_ordinal"])
        for event in ledger.events
        if event.get("event_type") == "request_send_started"
        and type(event.get("request_ordinal")) is int
    ]
    if (
        state.get("event_count") != ledger.event_count
        or state.get("request_count") != len(attempted)
        or attempted != sent
        or len(attempted) != len(set(attempted))
        or len(attempted) > MAX_REQUESTS
    ):
        raise BoundedSupervisorError("observer state and ledger counters drifted")

    ordinal_contract = _observer_request_contract()
    request_stage: dict[int, str] = {}
    terminal_events: dict[int, Mapping[str, object]] = {}
    started_phases: list[str] = []
    passed_phases: list[str] = []
    failed_phases: list[str] = []
    stopped_count = 0
    active_phase: str | None = None
    previous_monotonic = -1
    previous_send_monotonic: int | None = None
    for index, event in enumerate(ledger.events):
        event_type = _text(event.get("event_type"), context="observer event type")
        phase = _text(event.get("phase"), context="observer event phase")
        ordinal = event.get("request_ordinal")
        monotonic = _nonnegative_integer(
            event.get("monotonic_timestamp_ns"), context="observer monotonic timestamp"
        )
        if monotonic <= previous_monotonic:
            raise BoundedSupervisorError("observer ledger monotonic order drifted")
        previous_monotonic = monotonic
        if index == 0 and event_type != "run_materialized":
            raise BoundedSupervisorError("observer ledger does not begin with materialization")
        if event_type == "run_materialized":
            if index != 0 or phase != "materialize" or ordinal is not None:
                raise BoundedSupervisorError("observer materialization event drifted")
            continue
        if event_type == "phase_started":
            if ordinal is not None or phase in started_phases or active_phase is not None:
                raise BoundedSupervisorError("observer phase-start sequence drifted")
            started_phases.append(phase)
            active_phase = phase
            continue
        if event_type in {"phase_passed", "phase_failed"}:
            if ordinal is not None or phase != active_phase:
                raise BoundedSupervisorError("observer phase terminal event drifted")
            target = passed_phases if event_type == "phase_passed" else failed_phases
            if phase in passed_phases or phase in failed_phases:
                raise BoundedSupervisorError("observer phase has multiple terminal events")
            target.append(phase)
            active_phase = None
            continue
        if event_type == "run_stopped":
            if (
                ordinal is not None
                or phase != "terminal"
                or active_phase is not None
                or index != len(ledger.events) - 1
            ):
                raise BoundedSupervisorError("observer stop event is not final")
            stopped_count += 1
            continue
        if type(ordinal) is not int or ordinal not in ordinal_contract:
            raise BoundedSupervisorError("observer request event has an invalid ordinal")
        expected_phase, expected_path = ordinal_contract[ordinal]
        if (
            phase != expected_phase
            or phase != active_phase
            or event.get("method") != "GET"
            or event.get("scheme") != "https"
            or event.get("host") != "cloud.lambda.ai"
            or event.get("path") != expected_path
        ):
            raise BoundedSupervisorError("observer request event identity drifted")
        prior = request_stage.get(ordinal)
        if event_type == "request_intent_committed" and prior is None:
            request_stage[ordinal] = "intent"
        elif event_type == "request_send_started" and prior == "intent":
            if (
                previous_send_monotonic is not None
                and monotonic - previous_send_monotonic < MIN_REQUEST_SPACING_NS
            ):
                raise BoundedSupervisorError("observer request start spacing drifted")
            previous_send_monotonic = monotonic
            request_stage[ordinal] = "sent"
        elif (
            event_type
            in {
                "response_completed",
                "request_failed",
                "request_outcome_unknown_after_send",
            }
            and prior == "sent"
        ):
            request_stage[ordinal] = "terminal"
            terminal_events[ordinal] = event
        else:
            raise BoundedSupervisorError("observer per-request event order drifted")
    if (
        active_phase is not None
        or stopped_count > 1
        or attempted != sorted(attempted)
        or any(stage != "terminal" for stage in request_stage.values())
    ):
        raise BoundedSupervisorError("observer ledger contains an unterminated request")

    response_root = root / RESPONSES_RELATIVE
    if response_root.is_symlink() or not response_root.is_dir():
        raise BoundedSupervisorError("observer response root is unsafe")
    response_paths: dict[int, Path] = {}
    for path in response_root.iterdir():
        if (
            path.is_symlink()
            or not path.is_file()
            or re.fullmatch(r"[0-9]{3}\.json", path.name) is None
        ):
            raise BoundedSupervisorError("observer response root contains an unsafe entry")
        ordinal = int(path.stem)
        if ordinal in response_paths or ordinal not in ordinal_contract:
            raise BoundedSupervisorError("observer response receipt identity drifted")
        response_paths[ordinal] = path
    completed_ordinals = {
        ordinal
        for ordinal, event in terminal_events.items()
        if event.get("event_type") == "response_completed"
    }
    if set(response_paths) != completed_ordinals:
        raise BoundedSupervisorError("observer response receipts do not match completed requests")

    response_hashes: dict[int, str] = {}
    response_documents: dict[int, Mapping[str, object]] = {}
    response_bytes = 0
    for ordinal, path in response_paths.items():
        encoded = _read_regular(path, max_bytes=MAX_RESPONSE_BYTES)
        receipt = _strict_json(encoded, context="sanitized provider response receipt")
        terminal_event_record = terminal_events[ordinal]
        expected_path = ordinal_contract[ordinal][1]
        if (
            set(receipt)
            != {
                "schema_version",
                "path",
                "received_bytes",
                "projection",
                "unknown_additive_fields_retained",
                "credential_fields_retained",
            }
            or receipt.get("schema_version") != SCHEMA_VERSION
            or receipt.get("path") != expected_path
            or receipt.get("received_bytes") != terminal_event_record.get("bytes_received")
            or receipt.get("unknown_additive_fields_retained") is not False
            or receipt.get("credential_fields_retained") is not False
            or terminal_event_record.get("http_status") != 200
            or terminal_event_record.get("content_type") != "application/json"
        ):
            raise BoundedSupervisorError("sanitized provider response receipt drifted")
        response_bytes += _nonnegative_integer(
            terminal_event_record.get("bytes_received"),
            context="observer completed response bytes",
        )
        response_hashes[ordinal] = sha256_bytes(encoded)
        response_documents[ordinal] = _mapping(
            receipt.get("projection"), context="sanitized provider projection"
        )
    if (
        state.get("response_bytes") != response_bytes
        or response_bytes > MAX_RESPONSE_BYTES_AGGREGATE
    ):
        raise BoundedSupervisorError("observer response-byte accounting drifted")

    report_paths: dict[str, Path] = {}
    run_root = root / RUN_ROOT_RELATIVE
    for phase in PHASE_ORDER:
        path = run_root / f"{phase}-report.json"
        if path.exists() or path.is_symlink():
            if path.is_symlink() or not path.is_file():
                raise BoundedSupervisorError("observer phase report is unsafe")
            report_paths[phase] = path
    if set(report_paths) != set(passed_phases):
        raise BoundedSupervisorError("observer phase reports do not match passed phases")
    report_hashes: dict[str, str] = {}
    if disposition in {"complete", "post_launch"}:
        replayed_cleanup_origin: str | None = None
    elif failed_phases:
        replayed_cleanup_origin = failed_phases[0]
    elif "post_launch" in passed_phases:
        replayed_cleanup_origin = "post_launch"
    elif "security" in passed_phases:
        replayed_cleanup_origin = "security"
    else:
        replayed_cleanup_origin = "prelaunch"
    if state.get("cleanup_origin_phase") != replayed_cleanup_origin:
        raise BoundedSupervisorError("observer cleanup origin differs from replayed evidence")
    if disposition == "complete":
        expected_started_phases = list(PHASE_ORDER)
    elif disposition == "post_launch":
        expected_started_phases = list(PHASE_ORDER[:3])
    elif failed_phases:
        origin = failed_phases[0]
        expected_started_phases = list(PHASE_ORDER[: PHASE_ORDER.index(origin) + 1])
        cleanup_phase = CLEANUP_NEXT_PHASE[origin]
        while cleanup_phase is not None:
            expected_started_phases.append(cleanup_phase)
            cleanup_phase = CLEANUP_NEXT_PHASE[cleanup_phase]
    else:
        prefix_end = (
            PHASE_ORDER.index(replayed_cleanup_origin) + 1
            if replayed_cleanup_origin in PHASE_ORDER and replayed_cleanup_origin in passed_phases
            else 0
        )
        expected_started_phases = list(PHASE_ORDER[:prefix_end])
        if replayed_cleanup_origin == "security":
            cleanup_phase = "termination"
        elif replayed_cleanup_origin is None:
            cleanup_phase = None
        else:
            cleanup_phase = CLEANUP_NEXT_PHASE[replayed_cleanup_origin]
        while cleanup_phase is not None:
            expected_started_phases.append(cleanup_phase)
            cleanup_phase = CLEANUP_NEXT_PHASE[cleanup_phase]
    if started_phases != expected_started_phases:
        raise BoundedSupervisorError("observer phase path differs from its cleanup state machine")
    replayed_state: dict[str, object] = {
        "selected_image_id": None,
        "owned_ruleset_id": None,
        "bound_instance_id": None,
        "cleanup_origin_phase": replayed_cleanup_origin,
        "termination_verified": False,
    }
    ledger_active_observed_at: str | None = None
    ledger_terminal_observed_at: str | None = None
    for phase in passed_phases:
        path = report_paths[phase]
        encoded = _read_regular(path, max_bytes=MAX_RESPONSE_BYTES)
        report = _strict_json(encoded, context=f"{phase} observer report")
        ordinals = list(
            range(
                PHASE_START_ORDINAL[phase],
                PHASE_START_ORDINAL[phase] + len(PHASE_REQUESTS[phase]),
            )
        )
        hashes = [response_hashes.get(ordinal) for ordinal in ordinals]
        if any(value is None for value in hashes):
            raise BoundedSupervisorError("observer phase report lacks a completed response")
        phase_responses = {
            path_name: response_documents[ordinal]
            for ordinal, path_name in zip(ordinals, PHASE_REQUESTS[phase], strict=True)
        }
        expected_report = _PHASE_VALIDATORS[phase](phase_responses, private, replayed_state)
        if phase == "post_launch":
            terminal_event = terminal_events[ordinals[-1]]
            if terminal_event.get("event_type") != "response_completed":
                raise BoundedSupervisorError(
                    "provider active observation lacks a completed ledger response"
                )
            ledger_active_observed_at = _utc_text(
                _parse_utc(
                    terminal_event.get("wall_timestamp_utc"),
                    context="provider active ledger observation",
                )
            )
            if state.get("provider_active_observed_at_utc") != ledger_active_observed_at:
                raise BoundedSupervisorError(
                    "provider active state timestamp differs from the request ledger"
                )
            expected_report["provider_active_observed_at_utc"] = ledger_active_observed_at
        elif phase == "termination":
            terminal_event = terminal_events[ordinals[-1]]
            if terminal_event.get("event_type") != "response_completed":
                raise BoundedSupervisorError(
                    "provider terminal observation lacks a completed ledger response"
                )
            ledger_terminal_observed_at = _utc_text(
                _parse_utc(
                    terminal_event.get("wall_timestamp_utc"),
                    context="provider terminal ledger observation",
                )
            )
            if state.get("provider_terminal_observed_at_utc") != ledger_terminal_observed_at:
                raise BoundedSupervisorError(
                    "provider terminal state timestamp differs from the request ledger"
                )
            expected_report["provider_terminal_observed_at_utc"] = ledger_terminal_observed_at
        expected_report["request_ordinals"] = ordinals
        expected_report["sanitized_response_sha256s"] = hashes
        if report != expected_report:
            raise BoundedSupervisorError("observer phase report binding drifted")
        report_hashes[phase] = sha256_bytes(encoded)

    if any(
        state.get(field) != replayed_state.get(field)
        for field in (
            "selected_image_id",
            "owned_ruleset_id",
            "bound_instance_id",
            "termination_verified",
        )
    ):
        raise BoundedSupervisorError("observer final state differs from replayed evidence")

    if disposition == "complete":
        if (
            state.get("status") != "complete"
            or state.get("next_phase") is not None
            or state.get("termination_verified") is not True
            or attempted != list(range(1, MAX_REQUESTS + 1))
            or completed_ordinals != set(range(1, MAX_REQUESTS + 1))
            or passed_phases != list(PHASE_ORDER)
            or failed_phases
            or stopped_count != 1
        ):
            raise BoundedSupervisorError("complete observer evidence is not an exact closed run")
    elif disposition == "post_launch":
        expected_ordinals = list(range(1, PHASE_START_ORDINAL["termination"]))
        if (
            state.get("status") != "post_launch_passed"
            or state.get("next_phase") != "termination"
            or state.get("termination_verified") is not False
            or attempted != expected_ordinals
            or completed_ordinals != set(expected_ordinals)
            or passed_phases != list(PHASE_ORDER[:3])
            or failed_phases
            or stopped_count != 0
            or ledger_terminal_observed_at is not None
        ):
            raise BoundedSupervisorError("post-launch observer evidence is not an exact prefix")
    elif (
        state.get("status") not in {"cleanup_complete", "cleanup_incomplete"}
        or state.get("next_phase") is not None
        or (state.get("status") == "cleanup_complete" and stopped_count != 1)
        or (state.get("status") == "cleanup_incomplete" and stopped_count != 0)
    ):
        raise BoundedSupervisorError("failed observer evidence is not a terminal maximal prefix")

    record = {
        "schema_version": SCHEMA_VERSION,
        "plan_id": PLAN_ID,
        "run_id": HOST_RUN_ID,
        "disposition": disposition,
        "authorization_sha256": authorization_sha256,
        "private_binding_sha256": private_binding_sha256,
        "observer_state_sha256": sha256_bytes(
            _read_regular(root / STATE_RELATIVE, max_bytes=65_536)
        ),
        "request_ledger_sha256": sha256_bytes(
            _read_regular(root / LEDGER_RELATIVE, max_bytes=MAX_LEDGER_BYTES)
        ),
        "request_ledger_schema_sha256": ledger_schema_sha256,
        "event_count": ledger.event_count,
        "attempted_request_ordinals": attempted,
        "completed_response_ordinals": sorted(completed_ordinals),
        "response_bytes": response_bytes,
        "passed_phases": passed_phases,
        "failed_phases": failed_phases,
        "cleanup_origin_phase": replayed_cleanup_origin,
        "phase_report_sha256s": report_hashes,
        "provider_active_observed_at_utc": ledger_active_observed_at,
        "provider_terminal_observed_at_utc": ledger_terminal_observed_at,
        "terminal_status": state.get("status"),
        "maximal_typed_prefix_verified": True,
        "no_replay_verified": True,
    }
    if write_receipt:
        _write_exclusive(
            root / OBSERVER_VERIFICATION_RELATIVE, canonical_json_bytes(record), mode=0o644
        )
    return record


def _write_compute_closeout(
    root: Path,
    *,
    authorization: Mapping[str, object],
    state: Mapping[str, object],
    disposition: str,
    inbound_verification: Mapping[str, object],
    observer_verification: Mapping[str, object],
    inbound_verification_sha256: str,
) -> dict[str, object]:
    authorization_start = _parse_utc(
        authorization.get("supervised_wall_started_at_utc"), context="authorization start"
    )
    active_raw = observer_verification.get("provider_active_observed_at_utc")
    terminal_raw = observer_verification.get("provider_terminal_observed_at_utc")
    if (
        state.get("provider_active_observed_at_utc") != active_raw
        or state.get("provider_terminal_observed_at_utc") != terminal_raw
    ):
        raise BoundedSupervisorError(
            "provider lifecycle timestamps differ from ledger-verified evidence"
        )
    active = _parse_utc(active_raw, context="provider active observation") if active_raw else None
    terminal = (
        _parse_utc(terminal_raw, context="provider terminal observation") if terminal_raw else None
    )
    bound_instance = isinstance(state.get("bound_instance_id"), str) and bool(
        state.get("bound_instance_id")
    )
    cleanup_origin = state.get("cleanup_origin_phase")
    failed_phases = [
        _text(value, context="observer failed phase")
        for value in _sequence(
            observer_verification.get("failed_phases"), context="observer failed phases"
        )
    ]
    explicit_no_launch = (
        (cleanup_origin == "prelaunch" or "security" in failed_phases)
        and active is None
        and not bound_instance
        and not (root / BOOTSTRAP_RELEASE_RELATIVE).exists()
    )
    if active is not None and active < authorization_start:
        raise BoundedSupervisorError("provider active observation predates authorization")
    if terminal is not None and (
        terminal < authorization_start or (active is not None and terminal < active)
    ):
        raise BoundedSupervisorError("provider terminal observation interval is invalid")
    if disposition == "complete" and (
        not bound_instance
        or active is None
        or terminal is None
        or state.get("termination_verified") is not True
    ):
        raise BoundedSupervisorError("complete compute closeout lacks provider lifecycle evidence")
    if explicit_no_launch:
        basis = "prelaunch_stop_no_instance_observed"
        wall_seconds: float | None = 0.0
        accelerator_hours: float | None = 0.0
        provider_cost: float | None = 0.0
    elif terminal is not None:
        basis = "authorization_start_to_provider_terminal_observation_upper_bound"
        wall_seconds = (terminal - authorization_start).total_seconds()
        accelerator_hours = wall_seconds / 3_600
        provider_cost = math.ceil(wall_seconds / 60) * 129 / 6_000
    else:
        basis = "provider_terminal_not_observed_cost_unreconciled"
        wall_seconds = None
        accelerator_hours = None
        provider_cost = None
    usage_raw = inbound_verification.get("reconstruction_usage")
    usage = usage_raw if isinstance(usage_raw, Mapping) else None
    api_cost_raw = usage.get("cost_usd") if usage is not None else None
    api_cost = (
        _finite_number(api_cost_raw, context="reconstructed OpenAI cost")
        if api_cost_raw is not None
        else None
    )
    within = (
        wall_seconds is not None
        and provider_cost is not None
        and wall_seconds <= 3_600
        and provider_cost <= 2.0
        and (api_cost is None or api_cost <= 4.0)
    )
    if disposition == "complete" and (within is not True or api_cost is None):
        raise BoundedSupervisorError("complete compute closeout exceeds or lacks a cap")
    provider_lifecycle_reconciled = explicit_no_launch or (
        terminal is not None and state.get("termination_verified") is True
    )
    remote_kind = inbound_verification.get("remote_archive_kind")
    remote_secret_cleanup_verified = (
        remote_kind == "not-produced-before-bootstrap"
        and not (root / BOOTSTRAP_RELEASE_RELATIVE).exists()
    ) or (
        inbound_verification.get("secret_cleanup_verified") is True
        and inbound_verification.get("manual_secret_deletion_required") is False
        and inbound_verification.get("manual_credential_rotation_required") is False
    )
    provider_and_security_cleanup_complete = (
        provider_lifecycle_reconciled
        and remote_secret_cleanup_verified
        and state.get("status") in {"complete", "cleanup_complete"}
    )
    record = {
        "schema_version": SCHEMA_VERSION,
        "plan_id": PLAN_ID,
        "run_id": HOST_RUN_ID,
        "record_kind": "conservative_provider_allocation_upper_bound",
        "provider": "Lambda On-Demand Cloud",
        "hardware": "gpu_1x_a10",
        "region": "us-east-1",
        "disposition": disposition,
        "accounting_basis": basis,
        "authorization_window_started_at_utc": _utc_text(authorization_start),
        "provider_active_observed_at_utc": active_raw if active is not None else None,
        "provider_terminal_observed_at_utc": terminal_raw if terminal is not None else None,
        "wall_clock_upper_bound_seconds": wall_seconds,
        "accelerator_hours_upper_bound": accelerator_hours,
        "list_price_upper_bound_usd": provider_cost,
        "actual_provider_invoice_cost_usd": None,
        "observed_openai_api_cost_usd": api_cost,
        "openai_api_cost_reconciled": api_cost is not None,
        "billing_stop_verified": provider_lifecycle_reconciled,
        "remote_secret_cleanup_verified": remote_secret_cleanup_verified,
        "manual_secret_deletion_required": not remote_secret_cleanup_verified,
        "manual_credential_rotation_required": inbound_verification.get(
            "manual_credential_rotation_required"
        )
        is True,
        "observer_terminal_status": state.get("status"),
        "provider_and_security_cleanup_complete": provider_and_security_cleanup_complete,
        "unresolved_billing_or_security": not provider_and_security_cleanup_complete,
        "within_wall_and_cost_caps": within,
        "inbound_verification_sha256": inbound_verification_sha256,
        "repository_compute_record": "CMP-0001",
        "repository_reconciliation_required": True,
    }
    _write_exclusive(root / COMPUTE_CLOSEOUT_RELATIVE, canonical_json_bytes(record), mode=0o644)
    return record


def _safe_source_files(root: Path, *, disposition: str) -> list[ArchiveSource]:
    run_root = root / RUN_ROOT_RELATIVE
    required = {
        "authorization.json",
        "private-binding.json",
        "observer-state.json",
        "request-ledger.jsonl",
        "MATERIALIZATION_SUMMARY.json",
        "UPLOAD_BUNDLE_IDENTITY.json",
        "INBOUND_VERIFICATION.json",
        "OBSERVER_EVIDENCE_VERIFICATION.json",
        "COMPUTE_USE_CLOSEOUT.json",
    }
    observer = _strict_json(
        _read_regular(root / OBSERVER_VERIFICATION_RELATIVE, max_bytes=MAX_RESPONSE_BYTES),
        context="observer evidence verification",
    )
    completed = [
        _nonnegative_integer(value, context="completed observer response ordinal")
        for value in _sequence(
            observer.get("completed_response_ordinals"), context="completed response ordinals"
        )
    ]
    phase_hashes = _mapping(observer.get("phase_report_sha256s"), context="observer phase hashes")
    if any(ordinal not in range(1, MAX_REQUESTS + 1) for ordinal in completed) or any(
        phase not in PHASE_ORDER for phase in phase_hashes
    ):
        raise BoundedSupervisorError("observer archive member identity drifted")
    inbound_receipt = _strict_json(
        _read_regular(root / INBOUND_VERIFICATION_RELATIVE, max_bytes=MAX_RESPONSE_BYTES),
        context="inbound verification receipt",
    )
    inbound = _mapping(inbound_receipt.get("verification"), context="inbound verification")
    remote_kind = inbound.get("remote_archive_kind")
    inbound_members: set[str]
    if remote_kind == "complete":
        inbound_members = {
            "inbound/t07-bounded-evidence.zip",
            "inbound/ARCHIVE_IDENTITY.json",
            "inbound/TERMINATE_REQUIRED.json",
        }
    elif remote_kind == "failure":
        inbound_members = {
            "inbound/t07-bounded-failure-evidence.zip",
            "inbound/FAILURE_ARCHIVE_IDENTITY.json",
            "inbound/TERMINATE_REQUIRED.json",
        }
    elif remote_kind == "early_failure":
        inbound_members = {
            "inbound/t07-bounded-early-failure-evidence.zip",
            "inbound/EARLY_FAILURE_ARCHIVE_IDENTITY.json",
            "inbound/TERMINATE_REQUIRED.json",
        }
    elif remote_kind == "not-produced-before-bootstrap":
        inbound_members = set()
    else:
        raise BoundedSupervisorError("inbound archive kind is not admissible")
    expected = {
        *required,
        *(f"responses/{ordinal:03d}.json" for ordinal in completed),
        *(f"{phase}-report.json" for phase in phase_hashes),
        *inbound_members,
    }
    if inbound.get("bootstrap_release_present") is True:
        expected.add("BOOTSTRAP_RELEASE.json")
        expected.add("BOOTSTRAP_RELEASE_STATE.json")
    elif (root / BOOTSTRAP_RELEASE_RELATIVE).exists() or (
        root / BOOTSTRAP_RELEASE_STATE_RELATIVE
    ).exists():
        raise BoundedSupervisorError("unverified bootstrap release is present")
    paths: list[tuple[str, Path]] = []
    for path in sorted(run_root.rglob("*")):
        if path.is_symlink() or not path.is_file():
            if path.is_symlink():
                raise BoundedSupervisorError("archive source contains a symlink")
            continue
        relative = path.relative_to(run_root).as_posix()
        paths.append((relative, path))
    names = {name for name, _ in paths}
    if names != expected or (disposition == "complete") != (remote_kind == "complete"):
        raise BoundedSupervisorError("archive source differs from its exact verified member set")
    if len(paths) > MAX_ARCHIVE_PAYLOAD_FILES:
        raise BoundedSupervisorError("archive payload file count exceeds its exact cap")
    files: list[ArchiveSource] = []
    total = 0
    for relative, path in paths:
        encoded = _read_regular(path, max_bytes=MAX_ARCHIVE_BYTES - total)
        total += len(encoded)
        if total > MAX_ARCHIVE_BYTES:
            raise BoundedSupervisorError("archive source exceeds its aggregate cap")
        files.append(
            ArchiveSource(
                relative=relative,
                path=path,
                byte_count=len(encoded),
                sha256=sha256_bytes(encoded),
                content_class="runtime_evidence",
            )
        )

    upload_identity = _strict_json(
        _read_regular(root / UPLOAD_IDENTITY_RELATIVE, max_bytes=MAX_RESPONSE_BYTES),
        context="upload bundle identity",
    )
    upload_sources = (
        (
            "upload-bundle/t07-bounded-repository.tar",
            UPLOAD_ROOT_RELATIVE / UPLOAD_ARCHIVE_NAME,
            "archive_path",
            "archive_bytes",
            "archive_sha256",
        ),
        (
            "upload-bundle/t07-bounded-bootstrap.py",
            UPLOAD_ROOT_RELATIVE / UPLOAD_BOOTSTRAP_NAME,
            "bootstrap_path",
            "bootstrap_bytes",
            "bootstrap_sha256",
        ),
    )
    for archive_relative, source_relative, path_key, bytes_key, hash_key in upload_sources:
        if upload_identity.get(path_key) != source_relative.as_posix():
            raise BoundedSupervisorError("upload artifact path identity drifted before archive")
        source = root / source_relative
        encoded = _read_regular(source, max_bytes=MAX_ARCHIVE_BYTES - total)
        byte_count = _nonnegative_integer(
            upload_identity.get(bytes_key), context="upload artifact bytes"
        )
        digest = _text(upload_identity.get(hash_key), context="upload artifact SHA-256")
        if (
            len(encoded) != byte_count
            or sha256_bytes(encoded) != digest
            or _HEX64.fullmatch(digest) is None
        ):
            raise BoundedSupervisorError("upload artifact changed before external archive")
        total += len(encoded)
        if total > MAX_ARCHIVE_BYTES:
            raise BoundedSupervisorError("archive source exceeds its aggregate cap")
        files.append(
            ArchiveSource(
                relative=archive_relative,
                path=source,
                byte_count=byte_count,
                sha256=digest,
                content_class="reviewed_repository_upload",
            )
        )
    if len(files) > MAX_ARCHIVE_PAYLOAD_FILES:
        raise BoundedSupervisorError("archive payload file count exceeds its exact cap")
    return files


def _copy_archive_tree(
    root: Path,
    *,
    files: Sequence[ArchiveSource],
    disposition: str,
    volume_observer: Callable[[], tuple[VolumeObservation, VolumeObservation]],
    utc_now: Callable[[], datetime],
) -> dict[str, object]:
    # Reuse only the already-reviewed low-level APFS/descriptor primitives.  The
    # bounded file set, identities, caps, and finalization are owned by this module.
    from giclab.harness.lambda_archive import (
        _HeldDirectory,
        _open_or_create_archive_root,
        _read_regular_at,
        _same_identity,
        _validate_external,
        _validate_system,
        _write_exclusive_at,
    )

    started = time.monotonic()
    external_pre, system_pre = volume_observer()
    external_floor = _validate_external(
        cast(Any, external_pre), incremental_bytes=MAX_ARCHIVE_BYTES
    )
    _validate_system(cast(Any, system_pre), floor_bytes=MAC_PREWRITE_FLOOR_BYTES)
    if external_floor != EXTERNAL_RETAINED_FLOOR_BYTES:
        raise BoundedSupervisorError("external retained-free floor drifted")
    external = _HeldDirectory.open(EXTERNAL_MOUNT)
    archive_parent = None
    staging_fd = -1
    directories: dict[str, int] = {}
    try:
        archive_parent = _open_or_create_archive_root(external, EXTERNAL_PARENT)
        if archive_parent.device != external.device:
            raise BoundedSupervisorError("archive root fell back to another device")
        for name in (HOST_RUN_ID, f".{HOST_RUN_ID}.partial"):
            try:
                os.stat(name, dir_fd=archive_parent.descriptor, follow_symlinks=False)
            except FileNotFoundError:
                continue
            raise BoundedSupervisorError("external archive identity is not fresh")
        staging_name = f".{HOST_RUN_ID}.partial"
        os.mkdir(staging_name, mode=0o700, dir_fd=archive_parent.descriptor)
        staging_fd = os.open(
            staging_name,
            os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=archive_parent.descriptor,
        )
        manifest_rows: list[dict[str, object]] = []
        total = 0
        directories = {"": staging_fd}
        reviewed_upload_names = {
            "upload-bundle/t07-bounded-repository.tar",
            "upload-bundle/t07-bounded-bootstrap.py",
        }
        for item in files:
            relative = item.relative
            source = item.path
            expected_bytes = item.byte_count
            expected_sha256 = item.sha256
            relative_encoded = relative.encode("utf-8", "strict")
            if any(pattern.search(relative_encoded) for pattern in _SECRET_PREFIX_SHAPES):
                raise BoundedSupervisorError("archive source path contains credential material")
            parts = relative.split("/")
            parent_key = ""
            for component in parts[:-1]:
                key = f"{parent_key}/{component}" if parent_key else component
                if key not in directories:
                    with contextlib.suppress(FileExistsError):
                        os.mkdir(component, mode=0o700, dir_fd=directories[parent_key])
                    directories[key] = os.open(
                        component,
                        os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
                        dir_fd=directories[parent_key],
                    )
                parent_key = key
            encoded = _read_regular(source, max_bytes=MAX_ARCHIVE_BYTES - total)
            if len(encoded) != expected_bytes or sha256_bytes(encoded) != expected_sha256:
                raise BoundedSupervisorError("archive source changed after verification")
            if item.content_class == "runtime_evidence" and _contains_artifact_secret(encoded):
                raise BoundedSupervisorError("archive source contains credential-shaped material")
            if (
                item.content_class == "reviewed_repository_upload"
                and relative not in reviewed_upload_names
            ):
                raise BoundedSupervisorError("reviewed upload archive class is misapplied")
            total += len(encoded)
            if total > MAX_ARCHIVE_BYTES or len(manifest_rows) >= MAX_ARCHIVE_PAYLOAD_FILES:
                raise BoundedSupervisorError("bounded archive cap exceeded")
            _write_exclusive_at(directories[parent_key], parts[-1], encoded)
            copied = _read_regular_at(directories[parent_key], parts[-1], max_bytes=len(encoded))
            if copied != encoded:
                raise BoundedSupervisorError("archive destination hash verification failed")
            manifest_rows.append(
                {
                    "path": relative,
                    "bytes": len(encoded),
                    "sha256": sha256_bytes(encoded),
                    "content_class": item.content_class,
                    "secret_scan": (
                        "semantic-runtime-evidence-scan"
                        if item.content_class == "runtime_evidence"
                        else "exact-reviewed-tracked-source-set-before-secret-access"
                    ),
                }
            )
        manifest = {
            "schema_version": SCHEMA_VERSION,
            "plan_id": PLAN_ID,
            "run_id": HOST_RUN_ID,
            "disposition": disposition,
            "files": manifest_rows,
            "file_count": len(manifest_rows),
            "total_file_count": len(manifest_rows) + 3,
            "payload_bytes": total,
            "source_retained": True,
        }
        manifest_encoded = canonical_json_bytes(manifest)
        copy_record = {
            "schema_version": SCHEMA_VERSION,
            "plan_id": PLAN_ID,
            "run_id": HOST_RUN_ID,
            "destination": str(EXTERNAL_FINAL),
            "copied_at_utc": _utc_text(utc_now()),
            "external_volume_uuid": external_pre.volume_uuid,
            "external_physical_store_uuid": external_pre.physical_store_uuid,
            "external_precopy_free_bytes": external_pre.free_bytes,
            "external_retained_floor_bytes": external_floor,
            "mac_precopy_free_bytes": system_pre.free_bytes,
            "mac_retained_floor_bytes": MAC_RETAINED_FLOOR_BYTES,
            "held_no_follow_descriptors": True,
            "atomic_finalization": True,
            "source_retained": True,
            "internal_fallback": False,
        }
        copy_encoded = canonical_json_bytes(copy_record)
        seal = {
            "schema_version": SCHEMA_VERSION,
            "plan_id": PLAN_ID,
            "run_id": HOST_RUN_ID,
            "manifest_sha256": sha256_bytes(manifest_encoded),
            "copy_record_sha256": sha256_bytes(copy_encoded),
            "payload_bytes": total,
        }
        seal_encoded = canonical_json_bytes(seal)
        for name, encoded in (
            ("MANIFEST.json", manifest_encoded),
            ("COPY_RECORD.json", copy_encoded),
            ("SEAL.json", seal_encoded),
        ):
            _write_exclusive_at(staging_fd, name, encoded)
            copied = _read_regular_at(staging_fd, name, max_bytes=len(encoded))
            if copied != encoded:
                raise BoundedSupervisorError("archive metadata verification failed")
        if (
            total + len(manifest_encoded) + len(copy_encoded) + len(seal_encoded)
            > MAX_ARCHIVE_BYTES
        ):
            raise BoundedSupervisorError("bounded archive aggregate cap exceeded")
        for descriptor in sorted(set(directories.values()), reverse=True):
            os.fsync(descriptor)
        os.fsync(archive_parent.descriptor)
        os.rename(
            staging_name,
            HOST_RUN_ID,
            src_dir_fd=archive_parent.descriptor,
            dst_dir_fd=archive_parent.descriptor,
        )
        os.fsync(archive_parent.descriptor)
        external_post, system_post = volume_observer()
        if (
            not _same_identity(cast(Any, external_pre), cast(Any, external_post))
            or not _same_identity(cast(Any, system_pre), cast(Any, system_post))
            or external_post.free_bytes < EXTERNAL_RETAINED_FLOOR_BYTES
            or system_post.free_bytes < MAC_RETAINED_FLOOR_BYTES
            or time.monotonic() - started > ARCHIVE_WALL_SECONDS
        ):
            raise BoundedSupervisorError("post-copy storage identity/floor/wall check failed")
        return {
            "schema_version": SCHEMA_VERSION,
            "plan_id": PLAN_ID,
            "run_id": HOST_RUN_ID,
            "disposition": disposition,
            "destination": str(EXTERNAL_FINAL),
            "manifest_sha256": sha256_bytes(manifest_encoded),
            "copy_record_sha256": sha256_bytes(copy_encoded),
            "seal_sha256": sha256_bytes(seal_encoded),
            "file_count": len(manifest_rows),
            "total_file_count": len(manifest_rows) + 3,
            "payload_bytes": total,
            "source_destination_hashes_verified": True,
            "source_retained": True,
            "no_internal_fallback": True,
        }
    finally:
        for descriptor in {
            value for key, value in directories.items() if key and value != staging_fd
        }:
            with contextlib.suppress(OSError):
                os.close(descriptor)
        if staging_fd >= 0:
            os.close(staging_fd)
        if archive_parent is not None:
            archive_parent.close()
        external.close()


def archive_evidence(
    root: Path,
    *,
    plan: Mapping[str, object],
    plan_sha256: str,
    expected_commit: str,
    authorization_path: Path,
    authorization_sha256: str,
    private_binding_path: Path,
    private_binding_sha256: str,
    disposition: str,
    volume_observer: Callable[[], tuple[VolumeObservation, VolumeObservation]] | None = None,
    utc_now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> dict[str, object]:
    if disposition not in {"complete", "failed"}:
        raise BoundedSupervisorError("archive disposition is invalid")
    verify_repository_identity(root, expected_commit)
    authorization, private = _validate_authority_inputs(
        root,
        plan=plan,
        plan_sha256=plan_sha256,
        authorization_path=authorization_path,
        authorization_sha256=authorization_sha256,
        private_binding_path=private_binding_path,
        private_binding_sha256=private_binding_sha256,
        utc_now=utc_now,
        require_live=False,
    )
    state = _load_state(root)
    if disposition == "complete" and state.get("status") != "complete":
        raise BoundedSupervisorError("complete archive requires terminal observer evidence")
    if disposition == "failed" and state.get("status") not in {
        "cleanup_complete",
        "cleanup_incomplete",
    }:
        raise BoundedSupervisorError("failed archive requires a terminal cleanup disposition")
    inbound_verification, inbound_verification_sha256 = _revalidate_inbound_receipt(
        root,
        plan=plan,
        plan_sha256=plan_sha256,
        expected_commit=expected_commit,
        authorization=authorization,
        authorization_sha256=authorization_sha256,
        private=private,
        private_binding_sha256=private_binding_sha256,
        disposition=disposition,
    )
    observer_verification = _verify_observer_evidence(
        root,
        authorization=authorization,
        private=private,
        authorization_sha256=authorization_sha256,
        private_binding_sha256=private_binding_sha256,
        disposition=disposition,
    )
    _write_compute_closeout(
        root,
        authorization=authorization,
        state=state,
        disposition=disposition,
        inbound_verification=inbound_verification,
        observer_verification=observer_verification,
        inbound_verification_sha256=inbound_verification_sha256,
    )
    files = _safe_source_files(root, disposition=disposition)
    if volume_observer is None:
        from giclab.harness.lambda_archive import DiskutilVolumeObserver

        observer: Callable[[], tuple[VolumeObservation, VolumeObservation]] = cast(
            Callable[[], tuple[VolumeObservation, VolumeObservation]],
            DiskutilVolumeObserver(),
        )
    else:
        observer = volume_observer
    record = _copy_archive_tree(
        root,
        files=files,
        disposition=disposition,
        volume_observer=observer,
        utc_now=utc_now,
    )
    _write_exclusive(
        root / RUN_ROOT_RELATIVE / "ARCHIVE_LOCAL_VERIFICATION.json",
        canonical_json_bytes(record),
        mode=0o644,
    )
    return record


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--plan-sha256", required=True)
    parser.add_argument("--contract-file", type=Path, required=True)
    parser.add_argument("--contract-sha256", required=True)
    parser.add_argument("--expected-commit", required=True)
    subparsers = parser.add_subparsers(dest="operation", required=True)
    materialize = subparsers.add_parser("materialize")
    materialize.add_argument("--authorization-reference", required=True)
    materialize.add_argument("--source-parameters", type=Path, required=True)
    materialize.add_argument("--source-parameters-sha256", required=True)
    materialize.add_argument("--restoration-payload", type=Path, required=True)
    materialize.add_argument("--restoration-payload-sha256", required=True)
    for name in ("prepare-bundle", "observe", "release-bootstrap", "verify-inbound", "archive"):
        child = subparsers.add_parser(name)
        child.add_argument("--authorization", type=Path, required=True)
        child.add_argument("--authorization-sha256", required=True)
        child.add_argument("--private-binding", type=Path, required=True)
        child.add_argument("--private-binding-sha256", required=True)
        if name == "observe":
            child.add_argument("--phase", choices=PHASE_ORDER, required=True)
        elif name == "release-bootstrap":
            child.add_argument(
                "--provider-image-attestation",
                choices=("confirmed-in-provider-console",),
                required=True,
            )
        elif name in {"verify-inbound", "archive"}:
            child.add_argument("--disposition", choices=("complete", "failed"), required=True)
    return parser


def main(argv: Sequence[str] | None = None, *, contract: ModuleType | None = None) -> int:
    args = _parser().parse_args(argv)
    root = args.repository_root.resolve(strict=True)
    if root != args.repository_root.absolute():
        raise BoundedSupervisorError("repository root contains a symlink")
    if contract is None:
        raise BoundedSupervisorError("supervisor requires its hash-first bootstrap capability")
    plan = load_and_validate_plan(
        root,
        plan_path=args.plan,
        plan_sha256=args.plan_sha256,
        contract=contract,
    )
    if args.operation == "materialize":
        result = materialize_authority(
            root,
            plan=plan,
            plan_sha256=args.plan_sha256,
            expected_commit=args.expected_commit,
            authorization_reference=args.authorization_reference,
            source_parameters_path=args.source_parameters,
            source_parameters_sha256=args.source_parameters_sha256,
            restoration_path=args.restoration_payload,
            restoration_sha256=args.restoration_payload_sha256,
        )
    elif args.operation == "prepare-bundle":
        result = prepare_upload_bundle(
            root,
            plan=plan,
            plan_sha256=args.plan_sha256,
            expected_commit=args.expected_commit,
            authorization_path=args.authorization,
            authorization_sha256=args.authorization_sha256,
            private_binding_path=args.private_binding,
            private_binding_sha256=args.private_binding_sha256,
        )
    elif args.operation == "observe":
        result = execute_observer_phase(
            root,
            plan=plan,
            plan_sha256=args.plan_sha256,
            expected_commit=args.expected_commit,
            phase=args.phase,
            authorization_path=args.authorization,
            authorization_sha256=args.authorization_sha256,
            private_binding_path=args.private_binding,
            private_binding_sha256=args.private_binding_sha256,
            transport=LambdaHttpsBoundedTransport(),
            credential_provider=lambda: os.environ.get("LAMBDA_API_KEY"),
        )
    elif args.operation == "release-bootstrap":
        result = issue_bootstrap_release(
            root,
            plan=plan,
            plan_sha256=args.plan_sha256,
            expected_commit=args.expected_commit,
            authorization_path=args.authorization,
            authorization_sha256=args.authorization_sha256,
            private_binding_path=args.private_binding,
            private_binding_sha256=args.private_binding_sha256,
            provider_image_attestation=args.provider_image_attestation,
        )
    elif args.operation == "verify-inbound":
        result = verify_inbound_evidence(
            root,
            plan=plan,
            plan_sha256=args.plan_sha256,
            expected_commit=args.expected_commit,
            authorization_path=args.authorization,
            authorization_sha256=args.authorization_sha256,
            private_binding_path=args.private_binding,
            private_binding_sha256=args.private_binding_sha256,
            disposition=args.disposition,
        )
    else:
        result = archive_evidence(
            root,
            plan=plan,
            plan_sha256=args.plan_sha256,
            expected_commit=args.expected_commit,
            authorization_path=args.authorization,
            authorization_sha256=args.authorization_sha256,
            private_binding_path=args.private_binding,
            private_binding_sha256=args.private_binding_sha256,
            disposition=args.disposition,
        )
    # Only public-safe aliases, counts, paths, and hashes are printed by every operation.
    sys.stdout.buffer.write(canonical_json_bytes(result))
    return 0


__all__ = [
    "AUTHORIZATION_RELATIVE",
    "HOST_RUN_ID",
    "PHASE_REQUESTS",
    "PRIVATE_BINDING_RELATIVE",
    "RUN_ROOT_RELATIVE",
    "BoundedSupervisorError",
    "FsyncLedger",
    "HttpResponse",
    "LambdaHttpsBoundedTransport",
    "TransportFailure",
    "archive_evidence",
    "execute_observer_phase",
    "issue_bootstrap_release",
    "load_and_validate_plan",
    "main",
    "materialize_authority",
    "prepare_upload_bundle",
    "verify_inbound_evidence",
]
