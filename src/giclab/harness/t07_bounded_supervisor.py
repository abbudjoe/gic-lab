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
import time
import zipfile
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path, PurePosixPath
from types import ModuleType
from typing import Final, Protocol

import yaml
from jsonschema import Draft202012Validator, FormatChecker

from .sira_storage import VolumeObservation

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
RESPONSES_RELATIVE: Final = RUN_ROOT_RELATIVE / "responses"

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
        rb"""(?ix)["']?(?:[a-z0-9]+[_-])?"""
        rb"""(?:api[_-]?key|token|secret|password|authorization|cookie)"""
        rb"""["']?[ \t]*[:=][ \t]*["']?[a-z0-9._~+/=-]{8,}"""
    ),
)
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
CONDITION_PLAN_SHA256: Final[Mapping[str, str]] = {
    "SIRA-REACTIVE": "7ca19470e550e48978090c9b7014e047c56d80962e40275b846f589b08bfb018",
    "SIRA-SIMULATIVE": "68f5f4a4a123620bab039ba7bc6844243cad229ed992df6562bf0d8562874436",
}


class BoundedSupervisorError(RuntimeError):
    """The bounded local control plane failed closed."""


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

        observer: Callable[[], tuple[VolumeObservation, VolumeObservation]] = (
            DiskutilVolumeObserver()
        )
    else:
        observer = volume_observer
    from giclab.harness.lambda_archive import _validate_external, _validate_system

    external_pre, system_pre = observer()
    external_floor = _validate_external(external_pre, incremental_bytes=MAX_ARCHIVE_BYTES)
    _validate_system(system_pre, floor_bytes=MAC_PREWRITE_FLOOR_BYTES)
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
    normalized = name.casefold()
    return normalized in _SENSITIVE_PROVIDER_KEYS or any(
        marker in normalized
        for marker in ("authorization", "cookie", "credential", "password", "secret", "token")
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
            output[key] = _project_to_declared_schema(child, child_schema, root_schema=root_schema)
        return output
    if isinstance(value, list):
        items = schema.get("items")
        prefix = schema.get("prefixItems")
        projected: list[object] = []
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
            projected.append(
                _project_to_declared_schema(child, item_schema, root_schema=root_schema)
            )
        return projected
    return value


def _sanitized_provider_receipt(
    root: Path,
    *,
    path: str,
    document: Mapping[str, object],
    received_bytes: int,
) -> bytes:
    schema, _ = _load_schema(root, ENDPOINT_SCHEMA_ROOT / ENDPOINT_SCHEMAS[path])
    projection = _project_to_declared_schema(document, schema, root_schema=schema)
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
    if any(pattern.search(encoded) for pattern in _SECRET_SHAPES):
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
        bound_rows = [item for item in instances if item.get("id") == instance_id]
        if len(bound_rows) > 1 or (
            bound_rows and bound_rows[0].get("status") not in {"terminated", "preempted"}
        ):
            raise BoundedSupervisorError("bound instance is not terminal or absent")
    else:
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
                and attached == {ruleset_id}
            ):
                candidates.append(item)
        if any(item.get("status") not in {"terminated", "preempted"} for item in candidates):
            raise BoundedSupervisorError("an unbound owned instance remains nonterminal")
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
                ),
            )
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
                utc_now=utc_now(),
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


def _safe_zip_member_name(name: str) -> str:
    if not name or "\\" in name or name.endswith("/"):
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
    except BoundedSupervisorError:
        raise
    except (OSError, RuntimeError, zipfile.BadZipFile):
        raise BoundedSupervisorError("inbound archive member could not be verified") from None
    if total != info.file_size:
        raise BoundedSupervisorError("inbound archive member length drifted")
    return total, digest.hexdigest(), bytes(retained) if retained is not None else None


def _finite_number(value: object, *, context: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise BoundedSupervisorError(f"{context} must be numeric")
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise BoundedSupervisorError(f"{context} is invalid")
    return number


def _verify_pair_reconstruction(
    captured: Mapping[str, bytes],
    *,
    plan: Mapping[str, object],
) -> None:
    required = {
        "pair-budget.json",
        "pair-equivalence.json",
        "compute-use.json",
        "normalized-events.jsonl",
        "reactive/provider-budget.json",
        "reactive/regulation-decision.json",
        "simulative/provider-budget.json",
        "simulative/regulation-decision.json",
    }
    if set(captured) != required:
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

    compute = _strict_json(captured["compute-use.json"], context="compute use")
    started = _parse_utc(compute.get("started_at_utc"), context="compute start")
    ended = _parse_utc(compute.get("ended_at_utc"), context="compute end")
    elapsed = (ended - started).total_seconds()
    observed_wall = _finite_number(compute.get("wall_clock_seconds"), context="compute wall")
    accelerator_hours = _finite_number(
        compute.get("accelerator_hours"), context="accelerator hours"
    )
    lambda_cost = _finite_number(compute.get("list_price_upper_bound_usd"), context="Lambda cost")
    api_cost = _finite_number(compute.get("observed_openai_api_cost_usd"), context="OpenAI cost")
    if (
        set(compute)
        != {
            "schema_version",
            "plan_id",
            "run_id",
            "provider",
            "hardware",
            "region",
            "started_at_utc",
            "ended_at_utc",
            "wall_clock_seconds",
            "accelerator_hours",
            "list_price_upper_bound_usd",
            "actual_provider_invoice_cost_usd",
            "observed_openai_api_cost_usd",
            "status",
            "within_wall_and_cost_caps",
            "repository_compute_record",
            "repository_closeout_required",
        }
        or compute.get("schema_version") != SCHEMA_VERSION
        or compute.get("plan_id") != PLAN_ID
        or compute.get("run_id") != HOST_RUN_ID
        or compute.get("provider") != "Lambda On-Demand Cloud"
        or compute.get("hardware") != "gpu_1x_a10"
        or compute.get("region") != "us-east-1"
        or compute.get("status") != "completed"
        or compute.get("within_wall_and_cost_caps") is not True
        or compute.get("actual_provider_invoice_cost_usd") is not None
        or compute.get("repository_compute_record") != "CMP-0001"
        or compute.get("repository_closeout_required") is not True
        or elapsed < 0
        or abs(observed_wall - elapsed) > 0.000001
        or abs(accelerator_hours - elapsed / 3_600) > 0.000001
        or abs(lambda_cost - math.ceil(elapsed / 60) * 129 / 6_000) > 0.000001
        or abs(api_cost - float(totals["cost_usd"])) > 0.000001
        or observed_wall > 3_600
        or lambda_cost > 2.0
        or api_cost > 4.0
    ):
        raise BoundedSupervisorError("compute-use closeout is incomplete")

    for mode, condition in (("reactive", "SIRA-REACTIVE"), ("simulative", "SIRA-SIMULATIVE")):
        budget_encoded = captured[f"{mode}/provider-budget.json"]
        budget_sha256 = sha256_bytes(budget_encoded)
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
                "provider_budget_reference",
                "provider_budget_sha256",
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
            or decision.get("provider_budget_reference") != f"{mode}/provider-budget.json"
            or decision.get("provider_budget_sha256") != budget_sha256
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
        for event_type in ("condition_assignment_bound", "condition_execution_completed"):
            expected_events.append(
                {
                    "schema_version": SCHEMA_VERSION,
                    "plan_id": PLAN_ID,
                    "host_run_id": HOST_RUN_ID,
                    "run_id": run_id,
                    "event_sequence": len(expected_events) + 1,
                    "event_type": event_type,
                    "condition": condition,
                    "source_kind": "experiment_assignment",
                    "evidence_reference": f"{mode}/regulation-decision.json",
                    "interpretation_allowed": False,
                }
            )
    if events != expected_events:
        raise BoundedSupervisorError("normalized reconstruction events drifted")


def _verify_zip_payload(
    root: Path,
    archive: Path,
    *,
    plan: Mapping[str, object],
    manifest_name: str,
    failure: bool,
) -> dict[str, object]:
    capture_names = {manifest_name}
    if not failure:
        capture_names.update(
            {
                "pair-budget.json",
                "pair-equivalence.json",
                "compute-use.json",
                "normalized-events.jsonl",
                "reactive/provider-budget.json",
                "reactive/regulation-decision.json",
                "simulative/provider-budget.json",
                "simulative/regulation-decision.json",
            }
        )
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
                    opened, info, capture=name in capture_names
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
    if not failure:
        _verify_pair_reconstruction(
            {
                name: captured[name]
                for name in capture_names
                if name != manifest_name and name in captured
            },
            plan=plan,
        )
    return {
        "archive_member_count": len(rows),
        "decoded_payload_bytes": total,
        "manifest_sha256": sha256_bytes(manifest_encoded),
        "all_member_hashes_verified": True,
        "decoded_secret_scan_passed": True,
    }


def _verify_inbound_evidence(
    root: Path,
    *,
    plan: Mapping[str, object],
    disposition: str,
) -> dict[str, object]:
    inbound = root / INBOUND_RELATIVE
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
    if not inbound.exists():
        if disposition == "complete":
            raise BoundedSupervisorError("complete evidence was not downloaded")
        return {
            "schema_version": SCHEMA_VERSION,
            "plan_id": PLAN_ID,
            "run_id": HOST_RUN_ID,
            "remote_archive_kind": "not-produced-before-bootstrap",
            "all_member_hashes_verified": False,
            "decoded_secret_scan_passed": True,
        }
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
    else:
        raise BoundedSupervisorError("inbound evidence set is incomplete or ambiguous")
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
    incident = _strict_json(
        _read_regular(inbound / "TERMINATE_REQUIRED.json", max_bytes=65_536),
        context="termination receipt",
    )
    if (
        incident.get("provider_termination_required") is not True
        or incident.get("message_retained") is not False
        or (not failure_kind and incident.get("bootstrap_complete") is not True)
        or (failure_kind and not isinstance(incident.get("failure_class"), str))
    ):
        raise BoundedSupervisorError("provider termination receipt drifted")
    result = _verify_zip_payload(
        root,
        archive,
        plan=plan,
        manifest_name=manifest_name,
        failure=failure_kind,
    )
    if failure_kind and identity.get("manifest_sha256") != result["manifest_sha256"]:
        raise BoundedSupervisorError("failure manifest identity verification failed")
    return {
        "schema_version": SCHEMA_VERSION,
        "plan_id": PLAN_ID,
        "run_id": HOST_RUN_ID,
        "remote_archive_kind": "failure" if failure_kind else "complete",
        "archive": archive_name,
        "archive_bytes": len(archive_encoded),
        "archive_sha256": sha256_bytes(archive_encoded),
        **result,
    }


def _safe_source_files(root: Path, *, disposition: str) -> list[tuple[str, Path]]:
    run_root = root / RUN_ROOT_RELATIVE
    required = {
        "authorization.json",
        "private-binding.json",
        "observer-state.json",
        "request-ledger.jsonl",
        "MATERIALIZATION_SUMMARY.json",
        "INBOUND_VERIFICATION.json",
    }
    files: list[tuple[str, Path]] = []
    for path in sorted(run_root.rglob("*")):
        if path.is_symlink() or not path.is_file():
            if path.is_symlink():
                raise BoundedSupervisorError("archive source contains a symlink")
            continue
        relative = path.relative_to(run_root).as_posix()
        if (
            relative.startswith("inbound/")
            or relative.startswith("responses/")
            or (
                "/" not in relative
                and (
                    relative in required
                    or relative.endswith("-report.json")
                    or relative in {"ARCHIVE_LOCAL_VERIFICATION.json"}
                )
            )
        ):
            files.append((relative, path))
    names = {name for name, _ in files}
    if not required.issubset(names):
        raise BoundedSupervisorError("archive source is incomplete")
    if disposition == "complete":
        expected = {
            *(f"responses/{ordinal:03d}.json" for ordinal in range(1, 14)),
            "prelaunch-report.json",
            "security-report.json",
            "post_launch-report.json",
            "termination-report.json",
            "terminal-report.json",
            "inbound/t07-bounded-evidence.zip",
            "inbound/ARCHIVE_IDENTITY.json",
            "inbound/TERMINATE_REQUIRED.json",
        }
        if not expected.issubset(names):
            raise BoundedSupervisorError("complete archive source is missing required evidence")
    if len(files) > MAX_ARCHIVE_PAYLOAD_FILES:
        raise BoundedSupervisorError("archive payload file count exceeds its exact cap")
    return files


def _copy_archive_tree(
    root: Path,
    *,
    files: Sequence[tuple[str, Path]],
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
    external_floor = _validate_external(external_pre, incremental_bytes=MAX_ARCHIVE_BYTES)
    _validate_system(system_pre, floor_bytes=MAC_PREWRITE_FLOOR_BYTES)
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
        for relative, source in files:
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
            if any(pattern.search(encoded) for pattern in _SECRET_SHAPES):
                raise BoundedSupervisorError("archive source contains credential-shaped material")
            total += len(encoded)
            if total > MAX_ARCHIVE_BYTES or len(manifest_rows) >= MAX_ARCHIVE_PAYLOAD_FILES:
                raise BoundedSupervisorError("bounded archive cap exceeded")
            _write_exclusive_at(directories[parent_key], parts[-1], encoded)
            copied = _read_regular_at(directories[parent_key], parts[-1], max_bytes=len(encoded))
            if copied != encoded:
                raise BoundedSupervisorError("archive destination hash verification failed")
            manifest_rows.append(
                {"path": relative, "bytes": len(encoded), "sha256": sha256_bytes(encoded)}
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
            not _same_identity(external_pre, external_post)
            or not _same_identity(system_pre, system_post)
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
    _validate_authority_inputs(
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
    inbound_verification = _verify_inbound_evidence(
        root,
        plan=plan,
        disposition=disposition,
    )
    _write_exclusive(
        root / RUN_ROOT_RELATIVE / "INBOUND_VERIFICATION.json",
        canonical_json_bytes(inbound_verification),
        mode=0o644,
    )
    files = _safe_source_files(root, disposition=disposition)
    if volume_observer is None:
        from giclab.harness.lambda_archive import DiskutilVolumeObserver

        observer: Callable[[], tuple[VolumeObservation, VolumeObservation]] = (
            DiskutilVolumeObserver()
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
    for name in ("observe", "archive"):
        child = subparsers.add_parser(name)
        child.add_argument("--authorization", type=Path, required=True)
        child.add_argument("--authorization-sha256", required=True)
        child.add_argument("--private-binding", type=Path, required=True)
        child.add_argument("--private-binding-sha256", required=True)
        if name == "observe":
            child.add_argument("--phase", choices=PHASE_ORDER, required=True)
        else:
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
    "load_and_validate_plan",
    "main",
    "materialize_authority",
]
