"""Exact provider lifecycle for the one authorized T09 pragmatic campaign.

This module is inert on import.  It reuses the provider request pattern retained by
the successful T07 pragmatic run, but makes its previously implicit lifecycle
contract explicit: one plan-derived campaign clock, one durable launch intent, one
owned instance, bounded read-only polls, exact-target termination, and source-bound
entry/closeout receipts.  It is deliberately a small linear lifecycle utility, not a
general cloud platform or an independent watchdog.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import http.client
import json
import os
import re
import ssl
import stat
import subprocess
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final, Protocol, cast

import yaml

from giclab.harness.lambda_campaign_lifecycle import ObserverLifecycleLimits

PLAN_ID: Final = "PLAN-EXP0001-PILOT-V3"
HOST_RUN_ID: Final = "RUN-T09-PILOT-HOST-0001"
AUTHORIZATION_SOURCE_SHA256: Final = (
    "1f8285ea3fc52f4084a945f1712870203463cb7fb92cc61ac2eeae47d119e4c7"
)
API_HOST: Final = "cloud.lambda.ai"
API_PORT: Final = 443
INSTANCE_TYPE: Final = "gpu_1x_a10"
REGION: Final = "us-east-1"
IMAGE_ID: Final = "44fab622-b98a-49fe-ac6d-e4ce5531532f"
SSH_KEY_NAME: Final = "fractal-lambda-codex"
INSTANCE_NAME: Final = "giclab-t09-pilot-v3-0001"
PRICE_CENTS_PER_HOUR: Final = 129
MAX_RESPONSE_BYTES: Final = 16_777_216
MAX_REQUEST_BYTES: Final = 65_536
MAX_ENTRY_POLLS: Final = 120
MAX_TERMINATION_POLLS: Final = 120
MAX_TERMINATION_POSTS: Final = 3
POLL_SECONDS: Final = 5.0
REQUEST_TIMEOUT_SECONDS: Final = 60.0
MAX_DOTENV_BYTES: Final = 65_536
TERMINAL_STATES: Final = frozenset({"terminated", "preempted"})
ALLOWED_PATHS: Final = frozenset(
    {
        "/api/v1/instance-types",
        "/api/v1/images",
        "/api/v1/ssh-keys",
        "/api/v1/firewall-rulesets",
        "/api/v1/firewall-rulesets/global",
        "/api/v1/instances",
        "/api/v1/instance-operations/launch",
        "/api/v1/instance-operations/terminate",
    }
)
_HEX40 = re.compile(r"^[a-f0-9]{40}$")
_HEX64 = re.compile(r"^[a-f0-9]{64}$")
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$")
_DOTENV_VALUE = re.compile(rb"^[A-Za-z0-9._:/+\-=]{16,4096}$")


class T09ProviderError(RuntimeError):
    """The exact pragmatic provider lifecycle failed closed."""


class ProviderOutcomeUnknown(T09ProviderError):
    """A request crossed send-start but no trustworthy response was retained."""

    def __init__(self, operation: str) -> None:
        super().__init__(f"provider operation outcome is unknown: {operation}")
        self.operation = operation


@dataclass(frozen=True, slots=True)
class CampaignLifecycle:
    observer_limits: ObserverLifecycleLimits
    max_instances: int
    max_launches: int
    persistent_filesystems: int

    def __post_init__(self) -> None:
        if (
            self.observer_limits != ObserverLifecycleLimits.t09_pragmatic_v3()
            or self.max_instances != 1
            or self.max_launches != 1
            or self.persistent_filesystems != 0
        ):
            raise T09ProviderError("pilot provider lifecycle drifted")

    @property
    def wall_seconds(self) -> int:
        return self.observer_limits.campaign_provider_wall_seconds

    @property
    def cleanup_reserve_seconds(self) -> int:
        return self.observer_limits.cleanup_reserve_seconds

    @property
    def termination_cutoff_seconds(self) -> int:
        return self.observer_limits.normal_termination_cutoff_seconds

    def elapsed(self, *, started_at_epoch: float, now_epoch: float) -> float:
        if now_epoch < started_at_epoch:
            raise T09ProviderError("provider clock moved before its billable origin")
        return now_epoch - started_at_epoch

    def termination_due(self, *, started_at_epoch: float, now_epoch: float) -> bool:
        return self.elapsed(started_at_epoch=started_at_epoch, now_epoch=now_epoch) >= (
            self.termination_cutoff_seconds
        )


@dataclass(frozen=True, slots=True)
class ProviderResponse:
    status: int
    content_type: str
    body: bytes = field(repr=False)
    received_at_epoch: float


class ProviderTransport(Protocol):
    def send(
        self,
        method: str,
        path: str,
        *,
        body: bytes | None,
        credential: bytearray,
    ) -> ProviderResponse: ...


class LambdaTransport:
    """Exact-host HTTPS transport with no proxy, redirect, or environment handling."""

    def __init__(
        self,
        *,
        context: ssl.SSLContext | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._context = context or ssl.create_default_context()
        self._clock = clock

    def send(
        self,
        method: str,
        path: str,
        *,
        body: bytes | None,
        credential: bytearray,
    ) -> ProviderResponse:
        if method not in {"GET", "POST"} or path not in ALLOWED_PATHS:
            raise T09ProviderError("provider route escaped the exact allowlist")
        if method == "GET" and body is not None:
            raise T09ProviderError("GET request unexpectedly has a body")
        if method == "POST" and (body is None or len(body) > MAX_REQUEST_BYTES):
            raise T09ProviderError("POST request body is absent or oversized")
        if not 16 <= len(credential) <= 4_096 or any(
            marker in credential for marker in (b"\r", b"\n", b"\0")
        ):
            raise T09ProviderError("Lambda credential is malformed")
        connection = http.client.HTTPSConnection(
            API_HOST,
            API_PORT,
            timeout=REQUEST_TIMEOUT_SECONDS,
            context=self._context,
        )
        headers = {
            "Accept": "application/json",
            "Authorization": "Bearer " + credential.decode("ascii", "strict"),
            "User-Agent": "giclab-t09-pragmatic-provider-v1/1",
        }
        if body is not None:
            headers["Content-Type"] = "application/json"
        try:
            connection.request(method, path, body=body, headers=headers)
            response = connection.getresponse()
            content_type = response.getheader("Content-Type", "").split(";", 1)[0].casefold()
            if 300 <= response.status <= 399:
                raise T09ProviderError("provider redirect is forbidden")
            if content_type != "application/json":
                raise T09ProviderError("provider response is not JSON")
            chunks = bytearray()
            while chunk := response.read(65_536):
                chunks.extend(chunk)
                if len(chunks) > MAX_RESPONSE_BYTES:
                    raise T09ProviderError("provider response exceeds its byte cap")
            return ProviderResponse(
                response.status,
                content_type,
                bytes(chunks),
                self._clock(),
            )
        except (OSError, ssl.SSLError, http.client.HTTPException) as exc:
            raise T09ProviderError("provider transport outcome is unavailable") from exc
        finally:
            with contextlib.suppress(OSError):
                connection.close()


def _canonical_bytes(value: object) -> bytes:
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


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1_048_576):
            digest.update(chunk)
    return digest.hexdigest()


def _fsync_parent(path: Path) -> None:
    descriptor = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def write_exclusive(path: Path, value: object, *, mode: int = 0o600) -> None:
    encoded = _canonical_bytes(value)
    descriptor = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        mode,
    )
    try:
        written = os.write(descriptor, encoded)
        if written != len(encoded):
            raise OSError("short write")
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    _fsync_parent(path)


def write_bytes_exclusive(path: Path, value: bytes) -> None:
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
                raise OSError("short write")
            offset += written
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    _fsync_parent(path)


def _append_jsonl(path: Path, value: object) -> None:
    encoded = _canonical_bytes(value)
    descriptor = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        if os.write(descriptor, encoded) != len(encoded):
            raise OSError("short append")
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _load_json(path: Path, *, maximum_bytes: int = MAX_RESPONSE_BYTES) -> dict[str, object]:
    metadata = path.stat(follow_symlinks=False)
    if (
        not stat.S_ISREG(metadata.st_mode)
        or metadata.st_nlink != 1
        or not 0 < metadata.st_size <= maximum_bytes
    ):
        raise T09ProviderError(f"unsafe JSON evidence: {path.name}")
    try:
        value: object = json.loads(path.read_bytes())
    except (OSError, json.JSONDecodeError) as exc:
        raise T09ProviderError(f"malformed JSON evidence: {path.name}") from exc
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise T09ProviderError(f"JSON evidence is not an object: {path.name}")
    return cast(dict[str, object], value)


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise T09ProviderError(f"{label} is not an object")
    return cast(dict[str, object], value)


def _list(value: object, *, label: str) -> list[object]:
    if not isinstance(value, list):
        raise T09ProviderError(f"{label} is not a list")
    return value


def _string(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise T09ProviderError(f"{label} is not a string")
    return value


def _integer(value: object, *, label: str) -> int:
    if type(value) is not int:
        raise T09ProviderError(f"{label} is not an integer")
    return value


def _number(value: object, *, label: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise T09ProviderError(f"{label} is not numeric")
    return float(value)


def _envelope(document: Mapping[str, object], *, label: str) -> object:
    if set(document) != {"data"}:
        raise T09ProviderError(f"{label} provider envelope drifted")
    return document["data"]


def _reject_pagination(document: Mapping[str, object], *, label: str) -> None:
    if any(key.casefold() in {"next", "next_page", "cursor", "pagination"} for key in document):
        raise T09ProviderError(f"{label} pagination is unsupported")


def _instance_identity_sha256(instance_id: str) -> str:
    if _SAFE_ID.fullmatch(instance_id) is None:
        raise T09ProviderError("provider instance identity is unsafe")
    return hashlib.sha256(b"giclab-t09-owned-instance-v1\0" + instance_id.encode()).hexdigest()


def _network_identity_sha256(value: str) -> str:
    return hashlib.sha256(b"giclab-t09-source-cidr-v1\0" + value.encode()).hexdigest()


def _project_firewall_rule(value: object) -> dict[str, object]:
    rule = _mapping(value, label="provider firewall rule")
    source = _string(rule.get("source_network"), label="provider firewall source")
    return {
        "protocol": rule.get("protocol"),
        "port_range": rule.get("port_range"),
        "source_network_identity_sha256": _network_identity_sha256(source),
    }


def _project_instance(value: object) -> dict[str, object]:
    row = _mapping(value, label="provider instance")
    instance_id = _string(row.get("id"), label="provider instance ID")
    file_systems = row.get("file_system_names", [])
    return {
        "instance_identity_sha256": _instance_identity_sha256(instance_id),
        "name": row.get("name"),
        "status": row.get("status"),
        "instance_type": _instance_type_name(row),
        "region": _region_name(row),
        "persistent_filesystem_count": len(
            _list(file_systems, label="provider instance filesystems")
        ),
        "access_target_present": isinstance(row.get("ip"), str) and bool(row.get("ip")),
    }


def _project_provider_response(operation: str, body: bytes) -> bytes:
    """Retain a source-verifiable projection without access or account values."""

    try:
        document = _mapping(json.loads(body), label=f"{operation} response")
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise T09ProviderError(f"{operation} response is not JSON") from exc
    _reject_pagination(document, label=operation)
    data = _envelope(document, label=operation)
    if operation in {"prelaunch-instances", "active-instances", "termination-instances"}:
        projected: object = [
            _project_instance(item) for item in _list(data, label=f"{operation} instances")
        ]
    elif operation == "launch":
        launch = _mapping(data, label="launch response data")
        ids = [
            _string(item, label="launch response instance ID")
            for item in _list(launch.get("instance_ids"), label="launch response IDs")
        ]
        projected = {"instance_identity_sha256s": [_instance_identity_sha256(item) for item in ids]}
    elif operation == "terminate":
        termination = _mapping(data, label="termination response data")
        ids = [
            _string(_mapping(item, label="terminated instance").get("id"), label="terminated ID")
            for item in _list(
                termination.get("terminated_instances"), label="terminated instances"
            )
        ]
        projected = {"instance_identity_sha256s": [_instance_identity_sha256(item) for item in ids]}
    elif operation in {"global-firewall", "post-global-firewall"}:
        firewall = _mapping(data, label="global firewall response data")
        projected = {
            "name": firewall.get("name"),
            "rules": [
                _project_firewall_rule(item)
                for item in _list(firewall.get("rules"), label="global firewall rules")
            ],
        }
    elif operation in {"regional-rulesets", "post-regional-rulesets"}:
        projected = {
            "ruleset_semantic_sha256s": sorted(
                _sha256_bytes(_canonical_bytes(_mapping(item, label="provider ruleset")))
                for item in _list(data, label="provider rulesets")
            )
        }
    elif operation == "ssh-keys":
        projected = [
            {
                "name": _mapping(item, label="provider SSH key").get("name"),
                "public_key": _mapping(item, label="provider SSH key").get("public_key"),
            }
            for item in _list(data, label="provider SSH keys")
        ]
    else:
        projected = data
    return _canonical_bytes({"data": projected})


def load_campaign_lifecycle(repository: Path) -> CampaignLifecycle:
    root = repository.resolve(strict=True)
    plan_path = root / "experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/pilot.yaml"
    if plan_path.stat().st_size > 65_536:
        raise T09ProviderError("provider lifecycle plan exceeds its byte cap")
    loaded = yaml.safe_load(plan_path.read_bytes())
    profile = _mapping(loaded, label="pilot plan")
    if profile.get("plan_id") != PLAN_ID:
        raise T09ProviderError("provider lifecycle loaded the wrong pilot plan")
    raw = _mapping(profile.get("provider_lifecycle"), label="provider lifecycle")
    if raw.get("campaign_clock_origin") != "provider-launch-send-started-conservative" or set(
        raw
    ) != {
        "campaign_clock_origin",
        "campaign_provider_wall_seconds",
        "normal_cleanup_reserve_seconds",
        "provider_termination_cutoff_seconds",
        "max_lambda_instances",
        "max_launch_count",
        "persistent_filesystems",
        "admission_rule",
        "control_plane",
    }:
        raise T09ProviderError("provider lifecycle plan surface drifted")
    return CampaignLifecycle(
        observer_limits=ObserverLifecycleLimits(
            campaign_provider_wall_seconds=_integer(
                raw["campaign_provider_wall_seconds"], label="campaign wall"
            ),
            cleanup_reserve_seconds=_integer(
                raw["normal_cleanup_reserve_seconds"], label="cleanup reserve"
            ),
            normal_termination_cutoff_seconds=_integer(
                raw["provider_termination_cutoff_seconds"], label="termination cutoff"
            ),
            max_provider_cost_cents=516,
        ),
        max_instances=_integer(raw["max_lambda_instances"], label="instance cap"),
        max_launches=_integer(raw["max_launch_count"], label="launch cap"),
        persistent_filesystems=_integer(raw["persistent_filesystems"], label="filesystem cap"),
    )


def _verify_clean_package(repository: Path, package_commit: str) -> None:
    if _HEX40.fullmatch(package_commit) is None:
        raise T09ProviderError("package commit is malformed")
    environment = {
        "PATH": os.defpath,
        "LANG": "C",
        "LC_ALL": "C",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": "/dev/null",
    }
    try:
        head = (
            subprocess.run(
                ["git", "-C", str(repository), "rev-parse", "HEAD"],
                env=environment,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                check=True,
                timeout=10,
            )
            .stdout.decode("ascii", "strict")
            .strip()
        )
        dirty = subprocess.run(
            ["git", "-C", str(repository), "status", "--porcelain=v1"],
            env=environment,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            check=True,
            timeout=10,
        ).stdout
    except (OSError, subprocess.SubprocessError, UnicodeDecodeError) as exc:
        raise T09ProviderError("clean package identity could not be verified") from exc
    if head != package_commit or dirty:
        raise T09ProviderError("provider mutation requires the exact clean package commit")


def validate_authorization_ledger(
    path: Path,
    *,
    repository: Path,
    package_commit: str,
) -> dict[str, object]:
    metadata = path.stat(follow_symlinks=False)
    if (
        not stat.S_ISREG(metadata.st_mode)
        or metadata.st_uid != os.getuid()
        or metadata.st_nlink != 1
        or stat.S_IMODE(metadata.st_mode) != 0o600
    ):
        raise T09ProviderError("private authorization ledger metadata is unsafe")
    value = _load_json(path, maximum_bytes=65_536)
    plan_path = repository / "experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/pilot.yaml"
    required = {
        "schema_version": "0.1.0",
        "authorization_source_sha256": AUTHORIZATION_SOURCE_SHA256,
        "authorization_reference": "AUTH-T09-PRAGMATIC-PILOT-2026-08-13",
        "authorized": True,
        "single_use": True,
        "clean_package_commit": package_commit,
        "plan_id": PLAN_ID,
        "plan_sha256": file_sha256(plan_path),
        "max_lambda_instances": 1,
        "max_launch_count": 1,
        "persistent_filesystems": 0,
        "lambda_cost_cap_usd": 5.16,
        "openai_cost_cap_usd": 40.0,
        "aggregate_cost_cap_usd": 45.16,
        "artifact_destination": ("/Volumes/Macintosh HD - Data/GIC-Lab/t09/sealed-artifacts"),
    }
    if value != required:
        raise T09ProviderError("private authorization ledger drifted")
    return value


def load_dotenv_assignment(path: Path, name: str) -> bytearray:
    if name != "LAMBDA_API_KEY" or not path.is_absolute():
        raise T09ProviderError("Lambda dotenv binding is invalid")
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_uid != os.getuid()
            or metadata.st_nlink != 1
            or metadata.st_mode & 0o022
            or not 0 < metadata.st_size <= MAX_DOTENV_BYTES
        ):
            raise T09ProviderError("dotenv metadata is unsafe")
        raw = os.read(descriptor, MAX_DOTENV_BYTES + 1)
        after = os.fstat(descriptor)
        if len(raw) != metadata.st_size or (
            metadata.st_dev,
            metadata.st_ino,
            metadata.st_size,
            metadata.st_mtime_ns,
        ) != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
            raise T09ProviderError("dotenv changed while held")
    finally:
        os.close(descriptor)
    selected: bytearray | None = None
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(b"#"):
            continue
        if b"=" not in stripped:
            raise T09ProviderError("dotenv syntax is unsupported")
        raw_name, raw_value = stripped.split(b"=", 1)
        if raw_name == name.encode():
            if selected is not None or _DOTENV_VALUE.fullmatch(raw_value) is None:
                raise T09ProviderError("Lambda dotenv assignment is ambiguous")
            selected = bytearray(raw_value)
    if selected is None:
        raise T09ProviderError("Lambda dotenv assignment is missing")
    return selected


def _destroy_bytearray(value: bytearray) -> None:
    for index in range(len(value)):
        value[index] = 0
    value.clear()


def _destroy_operational_file(path: Path) -> None:
    try:
        descriptor = os.open(path, os.O_RDWR | getattr(os, "O_NOFOLLOW", 0))
    except FileNotFoundError:
        return
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
            raise T09ProviderError("private operational state is unsafe")
        remaining = metadata.st_size
        os.lseek(descriptor, 0, os.SEEK_SET)
        zeros = b"\0" * min(max(remaining, 1), 65_536)
        while remaining:
            written = os.write(descriptor, zeros[: min(remaining, len(zeros))])
            if written <= 0:
                raise T09ProviderError("private operational state destruction failed")
            remaining -= written
        os.ftruncate(descriptor, 0)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    path.unlink()
    _fsync_parent(path)


@dataclass(slots=True)
class RequestRecorder:
    root: Path
    transport: ProviderTransport
    credential: bytearray = field(repr=False)
    clock: Callable[[], float] = time.time
    next_ordinal: int = 1

    def request(
        self,
        operation: str,
        method: str,
        path: str,
        *,
        body: Mapping[str, object] | None = None,
        target_identity_sha256: str | None = None,
    ) -> ProviderResponse:
        if path not in ALLOWED_PATHS or method not in {"GET", "POST"}:
            raise T09ProviderError("recorded request escaped the allowlist")
        ordinal = self.next_ordinal
        self.next_ordinal += 1
        encoded = None if body is None else _canonical_bytes(body)
        intent = {
            "schema_version": "0.1.0",
            "ordinal": ordinal,
            "operation": operation,
            "method": method,
            "host": API_HOST,
            "port": API_PORT,
            "path": path,
            "request_body_sha256": None if encoded is None else _sha256_bytes(encoded),
            "send_started_at_epoch": self.clock(),
            "automatic_retry": False,
            "target_identity_sha256": target_identity_sha256,
        }
        if (operation == "terminate") != (
            isinstance(target_identity_sha256, str)
            and _HEX64.fullmatch(target_identity_sha256) is not None
        ):
            raise T09ProviderError("provider target identity binding drifted")
        _append_jsonl(self.root / "request-journal.jsonl", {**intent, "event": "send-started"})
        try:
            response = self.transport.send(
                method,
                path,
                body=encoded,
                credential=self.credential,
            )
        except BaseException:
            _append_jsonl(
                self.root / "request-journal.jsonl",
                {
                    **intent,
                    "event": "response-unknown",
                    "outcome_observed_at_epoch": self.clock(),
                },
            )
            raise ProviderOutcomeUnknown(operation) from None
        if response.status < 200 or response.status >= 300:
            _append_jsonl(
                self.root / "request-journal.jsonl",
                {
                    **intent,
                    "event": "response-rejected",
                    "http_status": response.status,
                    "response_received_at_epoch": response.received_at_epoch,
                    "response_sha256": _sha256_bytes(response.body),
                    "response_bytes": len(response.body),
                },
            )
            raise T09ProviderError(f"provider operation {operation} returned non-2xx")
        retained = _project_provider_response(operation, response.body)
        filename = f"{ordinal:03d}-{operation}.json"
        write_bytes_exclusive(self.root / filename, retained)
        _append_jsonl(
            self.root / "request-journal.jsonl",
            {
                **intent,
                "event": "response-complete",
                "http_status": response.status,
                "content_type": response.content_type,
                "response_received_at_epoch": response.received_at_epoch,
                "response_sha256": _sha256_bytes(retained),
                "response_bytes": len(retained),
                "raw_response_sha256": _sha256_bytes(response.body),
                "raw_response_bytes": len(response.body),
                "retention_projection": "t09-provider-structural-redaction-v1",
                "response_file": filename,
            },
        )
        return response


def _journal_events(root: Path) -> list[dict[str, object]]:
    path = root / "request-journal.jsonl"
    if path.stat().st_size > 2_097_152:
        raise T09ProviderError("provider journal exceeds its cap")
    events: list[dict[str, object]] = []
    for line in path.read_bytes().splitlines():
        try:
            value: object = json.loads(line)
        except json.JSONDecodeError as exc:
            raise T09ProviderError("provider journal is malformed") from exc
        events.append(_mapping(value, label="provider journal event"))
    return events


def _response_documents(root: Path) -> dict[str, list[tuple[dict[str, object], dict[str, object]]]]:
    events = _journal_events(root)
    if not events or len(events) % 2:
        raise T09ProviderError("provider journal has an incomplete request")
    completed: list[dict[str, object]] = []
    for index in range(0, len(events), 2):
        sent, response = events[index : index + 2]
        ordinal = index // 2 + 1
        shared = ("ordinal", "operation", "method", "host", "port", "path")
        if (
            sent.get("event") != "send-started"
            or response.get("event")
            not in {"response-complete", "response-unknown", "response-rejected"}
            or sent.get("ordinal") != ordinal
            or response.get("ordinal") != ordinal
            or any(sent.get(key) != response.get(key) for key in shared)
            or sent.get("host") != API_HOST
            or sent.get("port") != API_PORT
            or sent.get("path") not in ALLOWED_PATHS
            or sent.get("method") not in {"GET", "POST"}
            or sent.get("automatic_retry") is not False
            or response.get("automatic_retry") is not False
        ):
            raise T09ProviderError("provider journal request sequence drifted")
        if response.get("event") == "response-complete":
            completed.append(response)
    result: dict[str, list[tuple[dict[str, object], dict[str, object]]]] = {}
    for event in completed:
        filename = _string(event.get("response_file"), label="response file")
        body_path = root / filename
        if body_path.parent != root or file_sha256(body_path) != event.get("response_sha256"):
            raise T09ProviderError("provider response hash drifted from its journal")
        document = _load_json(body_path)
        _reject_pagination(document, label=str(event.get("operation")))
        result.setdefault(str(event.get("operation")), []).append((event, document))
    return result


def _instance_rows(document: Mapping[str, object], *, label: str) -> list[dict[str, object]]:
    return [
        _mapping(item, label=f"{label} instance")
        for item in _list(_envelope(document, label=label), label=f"{label} data")
    ]


def _instance_type_name(row: Mapping[str, object]) -> str:
    value = row.get("instance_type")
    if isinstance(value, str):
        return value
    return _string(_mapping(value, label="instance type").get("name"), label="instance type")


def _region_name(row: Mapping[str, object]) -> str:
    value = row.get("region")
    if isinstance(value, str):
        return value
    return _string(_mapping(value, label="instance region").get("name"), label="region")


def _validate_prelaunch_documents(
    documents: Mapping[str, list[tuple[dict[str, object], dict[str, object]]]],
    *,
    expected_public_key: str,
    expected_public_ipv4: str | None = None,
    expected_source_cidr_sha256: str | None = None,
) -> None:
    required_once = {
        "instance-types",
        "images",
        "ssh-keys",
        "global-firewall",
        "regional-rulesets",
        "prelaunch-instances",
        "launch",
    }
    if any(len(documents.get(name, [])) != 1 for name in required_once):
        raise T09ProviderError("provider entry request set drifted")
    types = _mapping(
        _envelope(documents["instance-types"][0][1], label="instance types"),
        label="instance types data",
    )
    offer = _mapping(types.get(INSTANCE_TYPE), label="A10 offer")
    identity = _mapping(offer.get("instance_type"), label="A10 identity")
    regions = [
        _mapping(item, label="capacity region")
        for item in _list(offer.get("regions_with_capacity_available"), label="capacity")
    ]
    if (
        identity.get("name") != INSTANCE_TYPE
        or identity.get("price_cents_per_hour") != PRICE_CENTS_PER_HOUR
        or not any(region.get("name") == REGION for region in regions)
    ):
        raise T09ProviderError("A10 capacity or price drifted")
    images = _list(
        _envelope(documents["images"][0][1], label="images"),
        label="images data",
    )
    selected_images = [
        _mapping(item, label="image")
        for item in images
        if isinstance(item, dict) and item.get("id") == IMAGE_ID
    ]
    if len(selected_images) != 1 or _region_name(selected_images[0]) != REGION:
        raise T09ProviderError("frozen pragmatic image is unavailable in us-east-1")
    keys = _list(
        _envelope(documents["ssh-keys"][0][1], label="SSH keys"),
        label="SSH keys data",
    )
    matching_keys = [
        _mapping(item, label="SSH key")
        for item in keys
        if isinstance(item, dict) and item.get("name") == SSH_KEY_NAME
    ]
    if (
        len(matching_keys) != 1
        or _string(matching_keys[0].get("public_key"), label="provider SSH public key").strip()
        != expected_public_key.strip()
    ):
        raise T09ProviderError("provider SSH key does not match the exact local public key")
    global_firewall = _mapping(
        _envelope(documents["global-firewall"][0][1], label="global firewall"),
        label="global firewall data",
    )
    rules = _list(global_firewall.get("rules"), label="global firewall rules")
    source_cidr_sha256 = expected_source_cidr_sha256 or _network_identity_sha256(
        f"{expected_public_ipv4}/32"
    )
    exact_ssh = [
        _mapping(item, label="firewall rule")
        for item in rules
        if isinstance(item, dict)
        and item.get("protocol") == "tcp"
        and item.get("source_network_identity_sha256")
        == source_cidr_sha256
        and item.get("port_range") in [[22, 22], [22]]
    ]
    if len(exact_ssh) != 1:
        raise T09ProviderError("current source IPv4 lacks one exact SSH firewall rule")
    if _instance_rows(documents["prelaunch-instances"][0][1], label="prelaunch instances"):
        raise T09ProviderError("prelaunch provider inventory is not zero")
    launch = _mapping(_envelope(documents["launch"][0][1], label="launch"), label="launch data")
    if documents["launch"][0][0].get("request_body_sha256") != _sha256_bytes(
        _canonical_bytes(_launch_body())
    ):
        raise T09ProviderError("launch request body drifted from the exact no-filesystem body")
    instance_ids = _list(
        launch.get("instance_identity_sha256s"), label="launch instance identities"
    )
    if (
        len(instance_ids) != 1
        or not isinstance(instance_ids[0], str)
        or _HEX64.fullmatch(instance_ids[0]) is None
    ):
        raise T09ProviderError("launch did not return exactly one safe instance ID")


def _launch_body() -> dict[str, object]:
    return {
        "region_name": REGION,
        "instance_type_name": INSTANCE_TYPE,
        "ssh_key_names": [SSH_KEY_NAME],
        "file_system_names": [],
        "file_system_mounts": [],
        "name": INSTANCE_NAME,
        "hostname": INSTANCE_NAME,
        "image": {"id": IMAGE_ID},
    }


def _terminate_body(instance_id: str) -> dict[str, object]:
    if _SAFE_ID.fullmatch(instance_id) is None:
        raise T09ProviderError("owned instance identity is unsafe")
    return {"instance_ids": [instance_id]}


def _manifest(root: Path) -> dict[str, object]:
    files: list[dict[str, object]] = []
    total = 0
    excluded = {"source-manifest.json", "entry-receipt.json", "closeout-receipt.json"}
    for path in sorted(root.iterdir()):
        if not path.is_file() or path.name in excluded:
            continue
        size = path.stat().st_size
        total += size
        if total > 33_554_432:
            raise T09ProviderError("provider source bundle exceeds its cap")
        files.append({"path": path.name, "bytes": size, "sha256": file_sha256(path)})
    return {
        "schema_version": "0.1.0",
        "source_observer": "t09-plan-driven-pragmatic-provider-v1",
        "plan_id": PLAN_ID,
        "host_run_id": HOST_RUN_ID,
        "files": files,
        "total_bytes": total,
    }


def seal_source_bundle(root: Path) -> dict[str, object]:
    manifest = _manifest(root)
    write_exclusive(root / "source-manifest.json", manifest)
    return manifest


def validate_source_manifest(root: Path) -> dict[str, object]:
    manifest = _load_json(root / "source-manifest.json", maximum_bytes=1_048_576)
    if manifest != _manifest(root):
        raise T09ProviderError("provider source manifest does not match retained bytes")
    return manifest


def _entry_projection(
    root: Path,
    *,
    package_commit: str,
    plan_sha256: str,
    expected_public_key: str,
    expected_public_ipv4: str | None = None,
    expected_source_cidr_sha256: str | None = None,
) -> dict[str, object]:
    manifest = validate_source_manifest(root)
    documents = _response_documents(root)
    _validate_prelaunch_documents(
        documents,
        expected_public_key=expected_public_key,
        expected_public_ipv4=expected_public_ipv4,
        expected_source_cidr_sha256=expected_source_cidr_sha256,
    )
    launch_event, launch_document = documents["launch"][0]
    launch_data = _mapping(_envelope(launch_document, label="launch"), label="launch data")
    instance_identity_sha256 = _string(
        _list(
            launch_data.get("instance_identity_sha256s"), label="launch identities"
        )[0],
        label="instance identity",
    )
    active_documents = documents.get("active-instances", [])
    if not active_documents:
        raise T09ProviderError("entry bundle lacks an active-instance observation")
    matching: list[dict[str, object]] = []
    for _, document in active_documents:
        matching = [
            row
            for row in _instance_rows(document, label="active instances")
            if row.get("instance_identity_sha256") == instance_identity_sha256
            and row.get("name") == INSTANCE_NAME
            and row.get("status") == "active"
        ]
        if matching:
            break
    if (
        len(matching) != 1
        or _instance_type_name(matching[0]) != INSTANCE_TYPE
        or (_region_name(matching[0]) != REGION)
    ):
        raise T09ProviderError("owned instance never reached the exact active identity")
    launch_started = launch_event.get("send_started_at_epoch")
    captured = active_documents[-1][0].get("response_received_at_epoch")
    if not isinstance(launch_started, (int, float)) or not isinstance(captured, (int, float)):
        raise T09ProviderError("provider entry chronology is unavailable")
    if not 0 <= float(captured) - float(launch_started) <= 1_800:
        raise T09ProviderError("provider entry observation exceeded its bounded window")
    return {
        "schema_version": "0.1.0",
        "receipt_type": "t09-pragmatic-provider-entry",
        "plan_id": PLAN_ID,
        "host_run_id": HOST_RUN_ID,
        "package_commit": package_commit,
        "plan_sha256": plan_sha256,
        "captured_at_epoch": float(captured),
        "lambda_started_at_epoch": float(launch_started),
        "owned_instance_identity_sha256": instance_identity_sha256,
        "source_manifest_sha256": file_sha256(root / "source-manifest.json"),
        "source_bundle_bytes": manifest["total_bytes"],
        "source_observer": "t09-plan-driven-pragmatic-provider-v1",
        "ssh_public_key_sha256": hashlib.sha256(expected_public_key.strip().encode()).hexdigest(),
        "source_ipv4_cidr_sha256": expected_source_cidr_sha256
        or _network_identity_sha256(f"{expected_public_ipv4}/32"),
        "zero_prior_nonterminal_instances": True,
        "launch_count": 1,
        "max_instances": 1,
        "instance_type": INSTANCE_TYPE,
        "region": REGION,
        "persistent_filesystems": 0,
        "hourly_price_usd": 1.29,
        "billable_clock_source": "provider-launch-send-started-conservative",
        "raw_source_retained_private": True,
        "structural_redaction_passed": True,
    }


def create_entry_receipt(
    root: Path,
    *,
    package_commit: str,
    plan_sha256: str,
    expected_public_key: str,
    expected_public_ipv4: str,
) -> Path:
    receipt = _entry_projection(
        root,
        package_commit=package_commit,
        plan_sha256=plan_sha256,
        expected_public_key=expected_public_key,
        expected_public_ipv4=expected_public_ipv4,
    )
    path = root / "entry-receipt.json"
    write_exclusive(path, receipt)
    return path


def validate_entry_receipt(
    receipt_path: Path,
    source_root: Path,
    *,
    package_commit: str,
    plan_sha256: str,
    expected_public_key: str,
    expected_public_ipv4: str,
) -> dict[str, object]:
    observed = _load_json(receipt_path, maximum_bytes=65_536)
    expected = _entry_projection(
        source_root,
        package_commit=package_commit,
        plan_sha256=plan_sha256,
        expected_public_key=expected_public_key,
        expected_public_ipv4=expected_public_ipv4,
    )
    if observed != expected:
        raise T09ProviderError("provider entry receipt is not derived from its source bundle")
    return observed


def validate_entry_receipt_source_bound(
    receipt_path: Path,
    source_root: Path,
    *,
    package_commit: str,
    plan_sha256: str,
) -> dict[str, object]:
    """Reconstruct an entry receipt from raw provider bytes without private prose."""

    observed = _load_json(receipt_path, maximum_bytes=65_536)
    documents = _response_documents(source_root)
    key_rows = [
        _mapping(item, label="SSH key")
        for item in _list(
            _envelope(documents["ssh-keys"][0][1], label="SSH keys"),
            label="SSH key data",
        )
        if isinstance(item, dict) and item.get("name") == SSH_KEY_NAME
    ]
    if len(key_rows) != 1:
        raise T09ProviderError("entry source lacks the one selected SSH key")
    public_key = _string(key_rows[0].get("public_key"), label="SSH public key")
    if hashlib.sha256(public_key.strip().encode()).hexdigest() != observed.get(
        "ssh_public_key_sha256"
    ):
        raise T09ProviderError("entry SSH-key binding is not source-derived")
    firewall = _mapping(
        _envelope(documents["global-firewall"][0][1], label="global firewall"),
        label="global firewall data",
    )
    candidate_cidrs = [
        source_hash
        for rule in (
            _mapping(item, label="firewall rule")
            for item in _list(firewall.get("rules"), label="firewall rules")
        )
        if rule.get("protocol") == "tcp"
        and rule.get("port_range") in [[22, 22], [22]]
        and isinstance((source_hash := rule.get("source_network_identity_sha256")), str)
        and source_hash == observed.get("source_ipv4_cidr_sha256")
    ]
    if len(candidate_cidrs) != 1:
        raise T09ProviderError("entry source-CIDR binding is not uniquely source-derived")
    expected = _entry_projection(
        source_root,
        package_commit=package_commit,
        plan_sha256=plan_sha256,
        expected_public_key=public_key,
        expected_source_cidr_sha256=candidate_cidrs[0],
    )
    if observed != expected:
        raise T09ProviderError("provider entry receipt is not derived from its source bundle")
    return observed


def _security_projection(document: Mapping[str, object]) -> str:
    data = _mapping(_envelope(document, label="firewall"), label="firewall data")
    projection = {
        "name": data.get("name"),
        "rules": data.get("rules"),
    }
    return _sha256_bytes(_canonical_bytes(projection))


def _rulesets_projection(document: Mapping[str, object]) -> str:
    data = _mapping(_envelope(document, label="rulesets"), label="rulesets data")
    hashes = _list(data.get("ruleset_semantic_sha256s"), label="ruleset hashes")
    if any(not isinstance(item, str) or _HEX64.fullmatch(item) is None for item in hashes):
        raise T09ProviderError("ruleset semantic projection is malformed")
    return _sha256_bytes(_canonical_bytes(hashes))


def _closeout_projection(
    root: Path,
    *,
    entry_receipt: Mapping[str, object],
    entry_source_root: Path,
    package_commit: str,
    plan_sha256: str,
    lifecycle: CampaignLifecycle,
) -> dict[str, object]:
    manifest = validate_source_manifest(root)
    documents = _response_documents(root)
    owned_state = _load_json(root / "owned-state-binding.json", maximum_bytes=65_536)
    owned_identity_sha256 = _string(
        owned_state.get("owned_instance_identity_sha256"), label="owned instance identity"
    )
    started = _number(entry_receipt["lambda_started_at_epoch"], label="Lambda start")
    if owned_state.get("owned_instance_identity_sha256") != entry_receipt.get(
        "owned_instance_identity_sha256"
    ):
        raise T09ProviderError("closeout owned identity drifted from entry")
    journal = _journal_events(root)
    termination_sends = [
        event
        for event in journal
        if event.get("event") == "send-started" and event.get("operation") == "terminate"
    ]
    if not 1 <= len(termination_sends) <= MAX_TERMINATION_POSTS:
        raise T09ProviderError("closeout has no bounded exact-target termination request")
    if any(
        event.get("method") != "POST"
        or event.get("path") != "/api/v1/instance-operations/terminate"
        or event.get("target_identity_sha256") != owned_identity_sha256
        for event in termination_sends
    ):
        raise T09ProviderError("termination request target drifted from the exact owned target")
    terminations = documents.get("terminate", [])
    for _, document in terminations:
        data = _mapping(_envelope(document, label="termination"), label="termination data")
        terminated_rows = _list(
            data.get("instance_identity_sha256s"), label="terminated instances"
        )
        if owned_identity_sha256 not in terminated_rows:
            raise T09ProviderError("termination response did not bind the exact owned instance")
    termination_started = min(
        _number(event["send_started_at_epoch"], label="termination send time")
        for event in termination_sends
    )
    terminal_at: float | None = None
    zero_at: float | None = None
    for event, document in documents.get("termination-instances", []):
        rows = _instance_rows(document, label="termination instances")
        owned = [
            row
            for row in rows
            if row.get("instance_identity_sha256") == owned_identity_sha256
        ]
        t09 = [row for row in rows if row.get("name") == INSTANCE_NAME]
        timestamp = _number(event["response_received_at_epoch"], label="poll response time")
        if not owned or all(row.get("status") in TERMINAL_STATES for row in owned):
            terminal_at = timestamp
        if not t09 or all(row.get("status") in TERMINAL_STATES for row in t09):
            zero_at = timestamp
        if terminal_at is not None and zero_at is not None:
            break
    if terminal_at is None or zero_at is None:
        raise T09ProviderError("closeout lacks terminal and zero-T09 observations")
    if (
        len(documents.get("post-global-firewall", [])) != 1
        or len(documents.get("post-regional-rulesets", [])) != 1
    ):
        raise T09ProviderError("closeout lacks final security observations")
    pre_global = _load_json(entry_source_root / "004-global-firewall.json")
    pre_rulesets = _load_json(entry_source_root / "005-regional-rulesets.json")
    post_global = documents["post-global-firewall"][0][1]
    post_rulesets = documents["post-regional-rulesets"][0][1]
    security_restored = _security_projection(pre_global) == _security_projection(
        post_global
    ) and _rulesets_projection(pre_rulesets) == _rulesets_projection(post_rulesets)
    captured = max(
        _number(
            documents["post-global-firewall"][0][0]["response_received_at_epoch"],
            label="firewall response time",
        ),
        _number(
            documents["post-regional-rulesets"][0][0]["response_received_at_epoch"],
            label="ruleset response time",
        ),
        terminal_at,
        zero_at,
    )
    termination_elapsed = termination_started - started
    terminal_elapsed = max(terminal_at, zero_at) - started
    if termination_elapsed > lifecycle.termination_cutoff_seconds:
        campaign_exception = "termination-cutoff-violated"
    elif terminal_elapsed > lifecycle.wall_seconds:
        campaign_exception = "best-effort-termination-provider-control-plane-delay"
    else:
        campaign_exception = "none"
    return {
        "schema_version": "0.1.0",
        "receipt_type": "t09-pragmatic-provider-closeout",
        "plan_id": PLAN_ID,
        "host_run_id": HOST_RUN_ID,
        "package_commit": package_commit,
        "plan_sha256": plan_sha256,
        "captured_at_epoch": captured,
        "lambda_started_at_epoch": started,
        "termination_started_at_epoch": termination_started,
        "terminal_observed_at_epoch": terminal_at,
        "zero_instance_observed_at_epoch": zero_at,
        "owned_instance_identity_sha256": entry_receipt["owned_instance_identity_sha256"],
        "termination_target_identity_sha256": owned_identity_sha256,
        "entry_receipt_sha256": entry_receipt["receipt_sha256"],
        "source_manifest_sha256": file_sha256(root / "source-manifest.json"),
        "source_bundle_bytes": manifest["total_bytes"],
        "source_observer": "t09-plan-driven-pragmatic-provider-v1",
        "termination_request_count": len(termination_sends),
        "terminal_or_absent": True,
        "zero_t09_instances": True,
        "security_restored": security_restored,
        "raw_source_retained_private": True,
        "structural_redaction_passed": True,
        "campaign_wall_exception": campaign_exception,
    }


def create_closeout_receipt(
    root: Path,
    *,
    entry_receipt_path: Path,
    entry_source_root: Path,
    package_commit: str,
    plan_sha256: str,
    lifecycle: CampaignLifecycle,
) -> Path:
    entry = _load_json(entry_receipt_path, maximum_bytes=65_536)
    entry["receipt_sha256"] = file_sha256(entry_receipt_path)
    receipt = _closeout_projection(
        root,
        entry_receipt=entry,
        entry_source_root=entry_source_root,
        package_commit=package_commit,
        plan_sha256=plan_sha256,
        lifecycle=lifecycle,
    )
    path = root / "closeout-receipt.json"
    write_exclusive(path, receipt)
    return path


def validate_closeout_receipt(
    receipt_path: Path,
    source_root: Path,
    *,
    entry_receipt_path: Path,
    entry_source_root: Path,
    package_commit: str,
    plan_sha256: str,
    lifecycle: CampaignLifecycle,
) -> dict[str, object]:
    observed = _load_json(receipt_path, maximum_bytes=65_536)
    entry = validate_entry_receipt_source_bound(
        entry_receipt_path,
        entry_source_root,
        package_commit=package_commit,
        plan_sha256=plan_sha256,
    )
    entry["receipt_sha256"] = file_sha256(entry_receipt_path)
    expected = _closeout_projection(
        source_root,
        entry_receipt=entry,
        entry_source_root=entry_source_root,
        package_commit=package_commit,
        plan_sha256=plan_sha256,
        lifecycle=lifecycle,
    )
    if observed != expected:
        raise T09ProviderError("provider closeout receipt is not derived from its source bundle")
    if observed.get("campaign_wall_exception") == "termination-cutoff-violated":
        raise T09ProviderError("provider termination began after the 13,500-second cutoff")
    if observed.get("security_restored") is not True:
        raise T09ProviderError("provider security state was not restored")
    return observed


def _read_public_file(path: Path, *, maximum_bytes: int) -> str:
    metadata = path.stat(follow_symlinks=False)
    if not stat.S_ISREG(metadata.st_mode) or not 1 <= metadata.st_size <= maximum_bytes:
        raise T09ProviderError("bound local public file is unsafe")
    return path.read_text(encoding="utf-8").strip()


def _load_or_recover_owned_state(private_root: Path, package_commit: str) -> dict[str, object]:
    del package_commit
    for name in ("owned-state-active.json", "owned-state.json"):
        candidate = private_root / name
        if candidate.is_file():
            return _load_json(candidate, maximum_bytes=65_536)
    raise T09ProviderError(
        "owned instance state is unavailable; do not relaunch; terminate the unique exact "
        "instance name through the Lambda console and verify it absent"
    )


def launch_campaign(
    *,
    repository: Path,
    package_commit: str,
    authorization_ledger: Path,
    dotenv: Path,
    private_root: Path,
    public_ipv4_file: Path,
    ssh_public_key_file: Path,
    transport: ProviderTransport,
    clock: Callable[[], float] = time.time,
    sleeper: Callable[[float], None] = time.sleep,
) -> Path:
    repository = repository.resolve(strict=True)
    _verify_clean_package(repository, package_commit)
    validate_authorization_ledger(
        authorization_ledger,
        repository=repository,
        package_commit=package_commit,
    )
    lifecycle = load_campaign_lifecycle(repository)
    del lifecycle
    if private_root.exists():
        raise T09ProviderError("provider private root already exists; launch is single use")
    private_root.mkdir(mode=0o700, parents=True, exist_ok=False)
    entry_root = private_root / "entry-source"
    entry_root.mkdir(mode=0o700)
    expected_public_ipv4 = _read_public_file(public_ipv4_file, maximum_bytes=64)
    expected_public_key = _read_public_file(ssh_public_key_file, maximum_bytes=16_384)
    credential = load_dotenv_assignment(dotenv, "LAMBDA_API_KEY")
    recorder = RequestRecorder(entry_root, transport, credential, clock)
    try:
        for operation, path in (
            ("instance-types", "/api/v1/instance-types"),
            ("images", "/api/v1/images"),
            ("ssh-keys", "/api/v1/ssh-keys"),
            ("global-firewall", "/api/v1/firewall-rulesets/global"),
            ("regional-rulesets", "/api/v1/firewall-rulesets"),
            ("prelaunch-instances", "/api/v1/instances"),
        ):
            recorder.request(operation, "GET", path)
            sleeper(1.0)
        documents = _response_documents(entry_root)
        # Validate every non-mutation fact before the one irreversible launch send.
        provisional = dict(documents)
        provisional["launch"] = [
            (
                {
                    "response_received_at_epoch": clock(),
                    "request_body_sha256": _sha256_bytes(_canonical_bytes(_launch_body())),
                },
                {"data": {"instance_identity_sha256s": ["0" * 64]}},
            )
        ]
        _validate_prelaunch_documents(
            provisional,
            expected_public_key=expected_public_key,
            expected_public_ipv4=expected_public_ipv4,
        )
        write_exclusive(
            private_root / "launch-intent.json",
            {
                "schema_version": "0.1.0",
                "plan_id": PLAN_ID,
                "host_run_id": HOST_RUN_ID,
                "package_commit": package_commit,
                "launch_body_sha256": _sha256_bytes(_canonical_bytes(_launch_body())),
                "launch_count_after_send": 1,
                "max_launch_count": 1,
                "created_at_epoch": clock(),
            },
        )
        try:
            launch_response = recorder.request(
                "launch",
                "POST",
                "/api/v1/instance-operations/launch",
                body=_launch_body(),
            )
        except ProviderOutcomeUnknown:
            write_exclusive(
                private_root / "LAUNCH_OUTCOME_UNKNOWN.json",
                {
                    "schema_version": "0.1.0",
                    "plan_id": PLAN_ID,
                    "host_run_id": HOST_RUN_ID,
                    "instance_name": INSTANCE_NAME,
                    "launch_body_sha256": _sha256_bytes(_canonical_bytes(_launch_body())),
                    "second_launch_forbidden": True,
                    "required_action": (
                        "inspect the Lambda console for the unique exact instance name; "
                        "terminate any matching instance; verify no matching instance remains"
                    ),
                },
            )
            seal_source_bundle(entry_root)
            raise T09ProviderError(
                "launch outcome is unknown; do not launch again; perform the exact "
                "console cleanup in LAUNCH_OUTCOME_UNKNOWN.json"
            ) from None
        raw_launch = _mapping(
            json.loads(launch_response.body),
            label="raw launch response",
        )
        launch_data = _mapping(
            _envelope(raw_launch, label="raw launch"), label="raw launch data"
        )
        instance_id = _string(
            _list(launch_data.get("instance_ids"), label="launch IDs")[0],
            label="instance ID",
        )
        owned_hash = _instance_identity_sha256(instance_id)
        documents = _response_documents(entry_root)
        write_exclusive(
            private_root / "owned-state.json",
            {
                "schema_version": "0.1.0",
                "plan_id": PLAN_ID,
                "host_run_id": HOST_RUN_ID,
                "package_commit": package_commit,
                "instance_id": instance_id,
                "owned_instance_identity_sha256": owned_hash,
                "instance_name": INSTANCE_NAME,
                "lambda_started_at_epoch": documents["launch"][0][0]["send_started_at_epoch"],
            },
        )
        for _ in range(MAX_ENTRY_POLLS):
            sleeper(POLL_SECONDS)
            active_response = recorder.request(
                "active-instances", "GET", "/api/v1/instances"
            )
            rows = _instance_rows(
                _response_documents(entry_root)["active-instances"][-1][1],
                label="active instances",
            )
            active = [
                row
                for row in rows
                if row.get("instance_identity_sha256") == owned_hash
                and row.get("name") == INSTANCE_NAME
                and row.get("status") == "active"
            ]
            if len(active) == 1:
                raw_active = _mapping(
                    json.loads(active_response.body), label="raw active response"
                )
                raw_rows = _instance_rows(raw_active, label="raw active instances")
                raw_match = [
                    row
                    for row in raw_rows
                    if row.get("id") == instance_id
                    and row.get("name") == INSTANCE_NAME
                    and row.get("status") == "active"
                ]
                if len(raw_match) != 1:
                    raise T09ProviderError("active instance projection drifted from raw response")
                ip_value = raw_match[0].get("ip")
                if not isinstance(ip_value, str) or not ip_value:
                    raise T09ProviderError("active owned instance lacks its private SSH target")
                state = _load_json(private_root / "owned-state.json", maximum_bytes=65_536)
                state["ssh_target"] = ip_value
                write_exclusive(private_root / "owned-state-active.json", state)
                break
        else:
            raise T09ProviderError("owned instance did not become active in the bounded window")
        seal_source_bundle(entry_root)
        plan_path = (
            repository / "experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/pilot.yaml"
        )
        return create_entry_receipt(
            entry_root,
            package_commit=package_commit,
            plan_sha256=file_sha256(plan_path),
            expected_public_key=expected_public_key,
            expected_public_ipv4=expected_public_ipv4,
        )
    finally:
        _destroy_bytearray(credential)


def closeout_campaign(
    *,
    repository: Path,
    package_commit: str,
    authorization_ledger: Path,
    dotenv: Path,
    private_root: Path,
    transport: ProviderTransport,
    clock: Callable[[], float] = time.time,
    sleeper: Callable[[float], None] = time.sleep,
) -> Path:
    repository = repository.resolve(strict=True)
    validate_authorization_ledger(
        authorization_ledger,
        repository=repository,
        package_commit=package_commit,
    )
    lifecycle = load_campaign_lifecycle(repository)
    state = _load_or_recover_owned_state(private_root, package_commit)
    instance_id = _string(state.get("instance_id"), label="owned instance ID")
    started = _number(state["lambda_started_at_epoch"], label="Lambda start")
    closeout_root = private_root / "closeout-source"
    closeout_root.mkdir(mode=0o700, exist_ok=False)
    write_exclusive(
        closeout_root / "owned-state-binding.json",
        {
            "schema_version": "0.1.0",
            "plan_id": PLAN_ID,
            "host_run_id": HOST_RUN_ID,
            "package_commit": package_commit,
            "owned_instance_identity_sha256": state["owned_instance_identity_sha256"],
            "lambda_started_at_epoch": state["lambda_started_at_epoch"],
        },
    )
    credential = load_dotenv_assignment(dotenv, "LAMBDA_API_KEY")
    recorder = RequestRecorder(closeout_root, transport, credential, clock)
    try:
        termination_sent = False
        for _post_index in range(MAX_TERMINATION_POSTS):
            if not termination_sent:
                write_exclusive(
                    closeout_root / "termination-intent.json",
                    {
                        "schema_version": "0.1.0",
                        "owned_instance_identity_sha256": state["owned_instance_identity_sha256"],
                        "termination_target_identity_sha256": state[
                            "owned_instance_identity_sha256"
                        ],
                        "send_started_at_epoch": clock(),
                        "campaign_elapsed_seconds": clock() - started,
                        "termination_cutoff_seconds": lifecycle.termination_cutoff_seconds,
                    },
                )
                termination_sent = True
            # Once an exact-target POST crosses send-start, only fresh GETs can
            # determine whether a recovery POST is needed.  This is cleanup
            # recovery, never a scientific retry.
            with contextlib.suppress(T09ProviderError):
                recorder.request(
                    "terminate",
                    "POST",
                    "/api/v1/instance-operations/terminate",
                    body=_terminate_body(instance_id),
                    target_identity_sha256=_string(
                        state.get("owned_instance_identity_sha256"),
                        label="owned instance identity",
                    ),
                )
            for _ in range(MAX_TERMINATION_POLLS // MAX_TERMINATION_POSTS):
                sleeper(POLL_SECONDS)
                recorder.request("termination-instances", "GET", "/api/v1/instances")
                rows = _instance_rows(
                    _response_documents(closeout_root)["termination-instances"][-1][1],
                    label="termination instances",
                )
                owned = [row for row in rows if row.get("id") == instance_id]
                if not owned or all(row.get("status") in TERMINAL_STATES for row in owned):
                    break
            else:
                continue
            break
        else:
            raise T09ProviderError("owned instance did not terminate after bounded recovery")
        recorder.request("post-global-firewall", "GET", "/api/v1/firewall-rulesets/global")
        sleeper(1.0)
        recorder.request("post-regional-rulesets", "GET", "/api/v1/firewall-rulesets")
        seal_source_bundle(closeout_root)
        plan_path = (
            repository / "experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/pilot.yaml"
        )
        entry_path = private_root / "entry-source/entry-receipt.json"
        receipt = create_closeout_receipt(
            closeout_root,
            entry_receipt_path=entry_path,
            entry_source_root=private_root / "entry-source",
            package_commit=package_commit,
            plan_sha256=file_sha256(plan_path),
            lifecycle=lifecycle,
        )
        for name in ("owned-state-active.json", "owned-state.json"):
            _destroy_operational_file(private_root / name)
        return receipt
    finally:
        _destroy_bytearray(credential)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser()
    result.add_argument("--repository", type=Path, required=True)
    result.add_argument("--package-commit", required=True)
    result.add_argument("--authorization-ledger", type=Path, required=True)
    result.add_argument("--dotenv", type=Path, required=True)
    result.add_argument("--private-root", type=Path, required=True)
    operations = result.add_subparsers(dest="operation", required=True)
    launch = operations.add_parser("launch")
    launch.add_argument("--public-ipv4-file", type=Path, required=True)
    launch.add_argument("--ssh-public-key-file", type=Path, required=True)
    operations.add_parser("closeout")
    return result


def main() -> int:
    args = parser().parse_args()
    transport = LambdaTransport()
    if args.operation == "launch":
        launch_campaign(
            repository=args.repository,
            package_commit=args.package_commit,
            authorization_ledger=args.authorization_ledger,
            dotenv=args.dotenv,
            private_root=args.private_root,
            public_ipv4_file=args.public_ipv4_file,
            ssh_public_key_file=args.ssh_public_key_file,
            transport=transport,
        )
        return 0
    if args.operation == "closeout":
        closeout_campaign(
            repository=args.repository,
            package_commit=args.package_commit,
            authorization_ledger=args.authorization_ledger,
            dotenv=args.dotenv,
            private_root=args.private_root,
            transport=transport,
        )
        return 0
    raise T09ProviderError("unknown provider lifecycle operation")


if __name__ == "__main__":
    raise SystemExit(main())
