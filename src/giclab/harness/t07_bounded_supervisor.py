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
import os
import re
import socket
import ssl
import stat
import subprocess
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
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
        "response_bytes": 0,
        "event_count": 0,
        "last_request_monotonic_ns": None,
        "selected_image_id": None,
        "owned_ruleset_id": None,
        "bound_instance_id": None,
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
        self._load()

    def _load(self) -> None:
        encoded = _read_regular(self.path, max_bytes=MAX_LEDGER_BYTES)
        if not encoded:
            self.event_count = 0
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
    instance_id = _text(state.get("bound_instance_id"), context="bound instance ID")
    instances = [
        _mapping(item, context="instance")
        for item in _sequence(responses["/api/v1/instances"].get("data"), context="instances")
    ]
    bound_rows = [item for item in instances if item.get("id") == instance_id]
    if len(bound_rows) > 1 or (
        bound_rows and bound_rows[0].get("status") not in {"terminated", "preempted"}
    ):
        raise BoundedSupervisorError("bound instance is not terminal or absent")
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": "termination",
        "provider_terminal_or_absent": True,
        "billing_stopped": True,
        "bound_instance_id_sha256": sha256_bytes(instance_id.encode()),
    }


def _validate_terminal(
    responses: Mapping[str, Mapping[str, object]],
    private: Mapping[str, object],
    state: dict[str, object],
) -> dict[str, object]:
    instance_id = _text(state.get("bound_instance_id"), context="bound instance ID")
    ruleset_id = _text(state.get("owned_ruleset_id"), context="bound ruleset ID")
    rulesets = [
        _mapping(item, context="ruleset")
        for item in _sequence(
            responses["/api/v1/firewall-rulesets"].get("data"), context="rulesets"
        )
    ]
    if any(
        item.get("id") == ruleset_id or item.get("name") == private.get("owned_ruleset_name")
        for item in rulesets
    ):
        raise BoundedSupervisorError("owned ruleset remains present")
    global_data = _mapping(
        responses["/api/v1/firewall-rulesets/global"].get("data"), context="global firewall"
    )
    if _firewall_semantic_sha256(global_data.get("rules")) != BASELINE_SEMANTIC_SHA256:
        raise BoundedSupervisorError("global firewall baseline was not restored")
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": "terminal",
        "provider_termination_previously_verified": True,
        "owned_regional_ruleset_match_count": 0,
        "global_firewall_baseline_sha256": BASELINE_SEMANTIC_SHA256,
        "bound_instance_id_sha256": sha256_bytes(instance_id.encode()),
        "owned_ruleset_id_sha256": sha256_bytes(ruleset_id.encode()),
    }


_PHASE_VALIDATORS: Final = {
    "prelaunch": _validate_prelaunch,
    "security": _validate_security,
    "post_launch": _validate_post_launch,
    "termination": _validate_termination,
    "terminal": _validate_terminal,
}


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
    )
    state = _load_state(root)
    if (
        state.get("next_phase") != phase
        or state.get("status") in {"burned", "complete"}
        or state.get("authorization_sha256") != authorization_sha256
        or state.get("private_binding_sha256") != private_binding_sha256
        or state.get("request_count") != PHASE_START_ORDINAL[phase] - 1
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
    if state.get("event_count") != ledger.event_count:
        raise BoundedSupervisorError("observer state/ledger event count drifted")
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
        state["status"] = "burned"
        state["next_phase"] = None
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
        state["status"] = "burned"
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
            response_path = root / RESPONSES_RELATIVE / f"{ordinal:03d}.json"
            _write_exclusive(response_path, response.body)
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
            state["request_count"] = ordinal
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
        report["raw_response_sha256s"] = [
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
        if state.get("status") != "burned":
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
            state["status"] = "burned"
            state["next_phase"] = None
            state["event_count"] = ledger.event_count
            with contextlib.suppress(OSError, BoundedSupervisorError):
                _atomic_write(root / STATE_RELATIVE, canonical_json_bytes(state))
        raise


def _safe_source_files(root: Path, *, disposition: str) -> list[tuple[str, Path]]:
    run_root = root / RUN_ROOT_RELATIVE
    required = {
        "authorization.json",
        "private-binding.json",
        "observer-state.json",
        "request-ledger.jsonl",
        "MATERIALIZATION_SUMMARY.json",
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
            if total > MAX_ARCHIVE_BYTES or len(manifest_rows) >= MAX_ARCHIVE_FILES:
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
