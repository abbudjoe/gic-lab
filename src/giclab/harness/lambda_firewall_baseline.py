"""Lossless T07 Lambda global-firewall baseline and capture contracts.

Importing this module is inert.  It contains no credential read, HTTP call, cloud
mutation, console, SSH, browser, container, model, or SiRA action.  A future capture
entry point may perform one explicitly authorized read-only GET through an injected
in-process transport; tests use fakes only.
"""

from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import os
import re
import secrets
import stat
import subprocess
import sys
import time
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Final, Protocol

from jsonschema import Draft202012Validator, FormatChecker

from .lambda_archive import (
    DiskutilVolumeObserver,
    InventoryArchiveError,
    _HeldDirectory,
    _open_or_create_archive_root,
    _read_regular_at,
    _same_identity,
    _validate_external,
    _validate_system,
    _write_exclusive_at,
)
from .sira_storage import APPROVED_MOUNT, SYSTEM_DATA_MOUNT, VolumeObservation


class FirewallBaselineError(ValueError):
    """A firewall baseline, capture plan, ledger, or seal violated its contract."""


CANONICALIZATION_VERSION: Final = "t07-firewall-canonical-v1"
CAPTURE_PLAN_ID: Final = "PLAN-T07-GATE-L2M-FIREWALL-BASELINE-CAPTURE-V1"
CAPTURE_RUN_ID: Final = "RUN-T07-L2M-FIREWALL-BASELINE-CAPTURE-0001"
CAPTURE_AUTHORIZATION_PLACEHOLDER: Final = "AUTH-T07-GATE-L2M-FIREWALL-BASELINE-CAPTURE-V1-PENDING"
CAPTURE_TERMINAL_DECISION: Final = "fresh-readonly-firewall-baseline-required"
CAPTURE_PLAN_RELATIVE: Final = Path(
    "containers/sira-smoke/lambda/manual-console/gate-l2m-firewall-baseline-capture-plan-v1.json"
)
CAPTURE_RUN_ROOT_RELATIVE: Final = Path("artifacts/t07/lambda/gate-l2m") / CAPTURE_RUN_ID
CAPTURE_LEDGER_RELATIVE: Final = CAPTURE_RUN_ROOT_RELATIVE / "request-ledger.jsonl"
CAPTURE_BOOTSTRAP_RELATIVE: Final = Path(
    "containers/sira-smoke/lambda/manual-console/firewall_baseline_capture_bootstrap.py"
)
CAPTURE_LEDGER_SCHEMA_RELATIVE: Final = Path(
    "schemas/t07-lambda-firewall-baseline-capture-ledger.schema.json"
)
BASELINE_SCHEMA_RELATIVE: Final = Path("schemas/t07-lambda-firewall-baseline.schema.json")
CANONICAL_REPORT_SCHEMA_RELATIVE: Final = Path(
    "schemas/t07-lambda-firewall-canonical-report.schema.json"
)
RESTORATION_SCHEMA_RELATIVE: Final = Path(
    "schemas/t07-lambda-firewall-restoration-payload.schema.json"
)
PUBLIC_CONTRACT_RELATIVE: Final = Path(
    "containers/sira-smoke/lambda/manual-console/public-firewall-contract-l2m-1.json"
)
HISTORICAL_ADJUDICATION_RELATIVE: Final = Path(
    "docs/harness/evidence/T07_RUN_0003_FIREWALL_BASELINE_ADJUDICATION.json"
)
HISTORICAL_STRUCTURAL_REPORT_RELATIVE: Final = Path(
    "docs/harness/evidence/T07_RUN_0003_FIREWALL_STRUCTURAL_REPORT.json"
)

HISTORICAL_PLAN_ID: Final = "PLAN-T07-GATE-L2M-MANUAL-CONSOLE-HOST-QUALIFICATION-V3"
HISTORICAL_RUN_ID: Final = "RUN-T07-L2M-MANUAL-CONSOLE-HOST-QUALIFICATION-0003"
HISTORICAL_PLAN_RELATIVE: Final = Path(
    "containers/sira-smoke/lambda/manual-console/gate-l2m-host-qualification-plan-v3.json"
)
HISTORICAL_PLAN_SHA256: Final = "1931fcacda4194063c0116ff9630d82f3b8f4ec07ff9b0310342335db629f654"
HISTORICAL_JOURNAL_RELATIVE: Final = (
    Path("artifacts/t07/lambda/gate-l2m") / HISTORICAL_RUN_ID / "observer-v1/observer-journal.jsonl"
)
HISTORICAL_JOURNAL_SHA256: Final = (
    "732ca7f649292ca9d87924d722ccd9d563320529b97c05686c2754d1a2718e4a"
)
HISTORICAL_OBSERVATION_RELATIVE: Final = (
    Path("artifacts/t07/lambda/gate-l2m")
    / HISTORICAL_RUN_ID
    / "observer-v1/observer-journal-provider-observations/observation-0006.json"
)
HISTORICAL_OBSERVATION_BYTES: Final = 782
HISTORICAL_OBSERVATION_SHA256: Final = (
    "7168f04f6ad961db10fde3431daa59052f3fc4539128b1bbc2c510e66d37ca25"
)

OPENAPI_URL: Final = "https://docs-api.lambda.ai/api/cloud/spec.json"
OPENAPI_VERSION: Final = "3.1.0"
API_VERSION: Final = "1.10.0"
OPENAPI_BYTES: Final = 240_288
OPENAPI_SHA256: Final = "320f4877924984f060b179e86595ed58918a1d0696b60b99cae548ec164934f4"
API_BASE_URL: Final = "https://cloud.lambda.ai"
GLOBAL_FIREWALL_PATH: Final = "/api/v1/firewall-rulesets/global"

MAX_CAPTURE_RESPONSE_BYTES: Final = 262_144
MAX_CAPTURE_LEDGER_BYTES: Final = 65_536
MAX_CAPTURE_LEDGER_EVENTS: Final = 24
MAX_CAPTURE_EVENT_BYTES: Final = 4_096
MAX_CAPTURE_LOCAL_ARTIFACT_BYTES: Final = 1_048_576
MAX_CAPTURE_ARCHIVE_BYTES: Final = 2_097_152
MAX_CAPTURE_PROVIDER_WALL_SECONDS: Final = 60
MAX_CAPTURE_ARCHIVE_WALL_SECONDS: Final = 60
MAX_CAPTURE_TOTAL_WALL_SECONDS: Final = 180
MIN_LOCAL_PREWRITE_FREE_BYTES: Final = 8_725_200_896
MIN_LOCAL_RETAINED_FREE_BYTES: Final = 8_589_934_592
MAX_INCIDENT_BUNDLE_BYTES: Final = 1_048_576

_SHA256: Final = re.compile(r"^[a-f0-9]{64}$")
_AUTHORIZATION: Final = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{2,127}$")
_ALIAS: Final = re.compile(r"^l2m-firewall-baseline-[a-f0-9]{12}$")
_CANONICAL_FIELDS: Final = frozenset({"protocol", "port_range", "source_network", "description"})
_REQUIRED_RULE_FIELDS: Final = frozenset({"protocol", "source_network", "description"})
_PROTOCOLS: Final = frozenset({"tcp", "udp", "icmp", "all"})
_COMMIT: Final = re.compile(r"^[a-f0-9]{40}$")
_CAPTURE_AUTHORIZATION: Final = re.compile(
    r"^AUTH-T07-GATE-L2M-FIREWALL-BASELINE-CAPTURE-V[0-9]+-[A-Z0-9._:-]{3,96}$"
)
MAX_GIT_OUTPUT_BYTES: Final = 65_536
GIT_TIMEOUT_SECONDS: Final = 10


def canonical_json_bytes(value: object) -> bytes:
    """Encode stable UTF-8 JSON while preserving decoded Unicode code points."""

    return (
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        + b"\n"
    )


def sha256_bytes(encoded: bytes) -> str:
    return hashlib.sha256(encoded).hexdigest()


def _mapping(value: object, *, context: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or any(not isinstance(key, str) for key in value):
        raise FirewallBaselineError(f"{context} must be an object")
    return value


def _sequence(value: object, *, context: str) -> Sequence[object]:
    if not isinstance(value, list):
        raise FirewallBaselineError(f"{context} must be an array")
    return value


def _string(value: object, *, context: str, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value):
        raise FirewallBaselineError(f"{context} must be a string")
    return value


def _read_regular_no_follow(path: Path, *, max_bytes: int) -> bytes:
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except OSError:
        raise FirewallBaselineError("required evidence is unavailable or unsafe") from None
    try:
        observed = os.fstat(descriptor)
        if (
            not stat.S_ISREG(observed.st_mode)
            or observed.st_nlink != 1
            or observed.st_size > max_bytes
        ):
            raise FirewallBaselineError("required evidence identity is unsafe")
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(descriptor, min(65_536, max_bytes + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > max_bytes:
                raise FirewallBaselineError("required evidence exceeds its byte cap")
        encoded = b"".join(chunks)
        if len(encoded) != observed.st_size:
            raise FirewallBaselineError("required evidence size drifted")
        return encoded
    finally:
        os.close(descriptor)


def _load_json(encoded: bytes, *, context: str) -> Mapping[str, object]:
    try:
        return _mapping(json.loads(encoded), context=context)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise FirewallBaselineError(f"{context} is not valid JSON") from None


def _load_schema(repository_root: Path, relative: Path) -> tuple[Mapping[str, object], str]:
    encoded = _read_regular_no_follow(repository_root / relative, max_bytes=262_144)
    schema = _load_json(encoded, context=f"schema {relative}")
    try:
        Draft202012Validator.check_schema(schema)
    except Exception:
        raise FirewallBaselineError("firewall schema is invalid") from None
    return schema, sha256_bytes(encoded)


@dataclass(frozen=True, slots=True)
class PrivateFirewallRule:
    protocol: str
    port_range: tuple[int, int] | None
    source_network: str = field(repr=False)
    canonical_source_network: str = field(repr=False)
    description: str = field(repr=False)

    def canonical_document(self) -> dict[str, object]:
        return {
            "description": self.description,
            "port_range": (
                {"state": "absent"}
                if self.port_range is None
                else {"state": "present", "value": list(self.port_range)}
            ),
            "protocol": self.protocol,
            "source_network": self.canonical_source_network,
        }

    def restoration_document(self) -> dict[str, object]:
        document: dict[str, object] = {
            "description": self.description,
            "protocol": self.protocol,
            "source_network": self.source_network,
        }
        if self.port_range is not None:
            document["port_range"] = list(self.port_range)
        return document


@dataclass(frozen=True, slots=True)
class CanonicalFirewallBaseline:
    alias: str
    version: str
    semantic_sha256: str
    rule_count: int
    duplicate_rule_count: int
    rules: tuple[PrivateFirewallRule, ...] = field(repr=False)
    encoded: bytes = field(repr=False)


def _parse_firewall_rule(value: object) -> PrivateFirewallRule:
    rule = _mapping(value, context="firewall rule")
    unknown = set(rule) - _CANONICAL_FIELDS
    missing = _REQUIRED_RULE_FIELDS - set(rule)
    if unknown:
        raise FirewallBaselineError("unknown additive firewall rule field requires review")
    if missing:
        raise FirewallBaselineError("firewall rule omits a required authoritative field")
    protocol = _string(rule.get("protocol"), context="firewall protocol")
    if protocol not in _PROTOCOLS:
        raise FirewallBaselineError("firewall protocol is outside the official enum")
    description = _string(rule.get("description"), context="firewall description", allow_empty=True)
    if len(description) > 128:
        raise FirewallBaselineError("firewall description exceeds the official limit")
    source = _string(rule.get("source_network"), context="firewall source network")
    if len(source) > 18 or source != source.strip():
        raise FirewallBaselineError("firewall source network is not canonical input text")
    try:
        parsed_network = ipaddress.ip_network(source, strict=False)
    except ValueError:
        raise FirewallBaselineError("firewall source network is not an IPv4 CIDR") from None
    if parsed_network.version != 4:
        raise FirewallBaselineError("firewall source network is not IPv4")
    port_present = "port_range" in rule
    if protocol == "icmp":
        if port_present:
            raise FirewallBaselineError("ICMP firewall rule must omit port_range")
        ports: tuple[int, int] | None = None
    else:
        if not port_present:
            raise FirewallBaselineError("non-ICMP firewall rule must include port_range")
        raw_ports = _sequence(rule.get("port_range"), context="firewall port range")
        if len(raw_ports) != 2:
            raise FirewallBaselineError("firewall port range is invalid")
        first_port = raw_ports[0]
        second_port = raw_ports[1]
        if (
            type(first_port) is not int
            or type(second_port) is not int
            or not 1 <= first_port <= 65_535
            or not 1 <= second_port <= 65_535
            or first_port > second_port
        ):
            raise FirewallBaselineError("firewall port range is invalid")
        ports = (first_port, second_port)
    return PrivateFirewallRule(protocol, ports, source, str(parsed_network), description)


def canonicalize_firewall_rules(rules: object) -> CanonicalFirewallBaseline:
    """Canonicalize complete rule semantics as an order-insensitive multiset."""

    parsed = tuple(_parse_firewall_rule(value) for value in _sequence(rules, context="rules"))
    sorted_rules = sorted(
        (rule.canonical_document() for rule in parsed),
        key=canonical_json_bytes,
    )
    encoded = canonical_json_bytes(
        {"canonicalization_version": CANONICALIZATION_VERSION, "rules": sorted_rules}
    )
    digest = sha256_bytes(encoded)
    alias = f"l2m-firewall-baseline-{digest[:12]}"
    counts = Counter(canonical_json_bytes(rule) for rule in sorted_rules)
    return CanonicalFirewallBaseline(
        alias,
        CANONICALIZATION_VERSION,
        digest,
        len(parsed),
        sum(count - 1 for count in counts.values()),
        parsed,
        encoded,
    )


def build_exact_restoration_payload(
    rules: object, *, repository_root: Path
) -> tuple[dict[str, object], bytes, str]:
    """Build the exact private PATCH body without response-only fields or defaults."""

    parsed = tuple(_parse_firewall_rule(value) for value in _sequence(rules, context="rules"))
    document: dict[str, object] = {"rules": [rule.restoration_document() for rule in parsed]}
    schema, _ = _load_schema(repository_root, RESTORATION_SCHEMA_RELATIVE)
    if next(Draft202012Validator(schema).iter_errors(document), None) is not None:
        raise FirewallBaselineError("restoration payload failed the bound PATCH schema")
    encoded = canonical_json_bytes(document)
    return document, encoded, sha256_bytes(encoded)


def verify_exact_firewall_baseline(
    current_ruleset: object,
    *,
    expected_ruleset_id: str,
    expected_ruleset_name: str,
    expected_semantic_sha256: str,
) -> None:
    current = _mapping(current_ruleset, context="current global ruleset")
    if set(current) != {"id", "name", "rules"}:
        raise FirewallBaselineError("global ruleset authoritative field set drifted")
    if (
        current.get("id") != expected_ruleset_id
        or current.get("name") != expected_ruleset_name
        or expected_ruleset_id != "global"
        or _SHA256.fullmatch(expected_semantic_sha256) is None
    ):
        raise FirewallBaselineError("global ruleset identity drifted")
    observed = canonicalize_firewall_rules(current.get("rules"))
    if observed.semantic_sha256 != expected_semantic_sha256:
        raise FirewallBaselineError("global firewall differs from the exact sealed baseline")


def structural_report_for_historical_projection(
    observation: Mapping[str, object],
) -> dict[str, object]:
    """Return only non-sensitive shape/count observations for historical run 0003."""

    data = _mapping(observation.get("data"), context="historical observation data")
    rules = _sequence(data.get("rules"), context="historical observation rules")
    shapes: list[dict[str, object]] = []
    protocols: set[str] = set()
    empty_descriptions = 0
    nonempty_descriptions = 0
    all_required = True
    all_ports_distinguished = True
    for value in rules:
        rule = _mapping(value, context="historical observation rule")
        fields = sorted(key for key in rule if key in _CANONICAL_FIELDS)
        shapes.append(
            {
                "fields": fields,
                "types": {
                    key: (
                        "array"
                        if key in rule and isinstance(rule[key], list)
                        else "string"
                        if key in rule and isinstance(rule[key], str)
                        else "absent"
                    )
                    for key in sorted(_CANONICAL_FIELDS)
                },
            }
        )
        all_required = all_required and set(rule) >= _REQUIRED_RULE_FIELDS
        protocol = rule.get("protocol")
        if isinstance(protocol, str) and protocol in _PROTOCOLS:
            protocols.add(protocol)
        description = rule.get("description")
        empty_descriptions += int(description == "")
        nonempty_descriptions += int(isinstance(description, str) and description != "")
        all_ports_distinguished = all_ports_distinguished and (
            "port_range" in rule and isinstance(rule.get("port_range"), list)
        )
    return {
        "schema_version": "0.1.0",
        "evidence_classification": "incomplete_or_transformed_baseline",
        "canonicalization_version": CANONICALIZATION_VERSION,
        "baseline_alias": None,
        "canonical_semantic_sha256": None,
        "rule_count": len(rules),
        "rule_shapes": shapes,
        "empty_description_count": empty_descriptions,
        "nonempty_description_count": nonempty_descriptions,
        "protocol_classes": sorted(protocols),
        "all_current_required_fields_present": all_required,
        "all_port_range_presence_distinguished": all_ports_distinguished,
        "raw_response_retained": False,
        "unknown_raw_key_structure_retained": False,
        "sensitive_scalar_values_retained": False,
    }


@dataclass(frozen=True, slots=True)
class HistoricalAdjudication:
    document: Mapping[str, object]
    structural_report: Mapping[str, object]
    original_observation: bytes = field(repr=False)
    original_journal: bytes = field(repr=False)


def adjudicate_historical_run(repository_root: Path) -> HistoricalAdjudication:
    """Validate immutable run-0003 evidence and classify its private projection."""

    root = repository_root.resolve(strict=True)
    identities = (
        (HISTORICAL_PLAN_RELATIVE, HISTORICAL_PLAN_SHA256, 262_144),
        (HISTORICAL_JOURNAL_RELATIVE, HISTORICAL_JOURNAL_SHA256, 262_144),
        (
            HISTORICAL_OBSERVATION_RELATIVE,
            HISTORICAL_OBSERVATION_SHA256,
            HISTORICAL_OBSERVATION_BYTES,
        ),
    )
    encoded: dict[Path, bytes] = {}
    for relative, expected, cap in identities:
        value = _read_regular_no_follow(root / relative, max_bytes=cap)
        if sha256_bytes(value) != expected:
            raise FirewallBaselineError("historical run evidence identity drifted")
        encoded[relative] = value
    observation = _load_json(
        encoded[HISTORICAL_OBSERVATION_RELATIVE], context="historical observation"
    )
    journal_rows = [
        _mapping(json.loads(line), context="historical journal event")
        for line in encoded[HISTORICAL_JOURNAL_RELATIVE].splitlines()
        if line
    ]
    terminal = [
        event
        for event in journal_rows
        if event.get("event_type") == "observation_failed" and event.get("request_ordinal") == 6
    ]
    if (
        len(journal_rows) != 20
        or len(terminal) != 1
        or terminal[0].get("method") != "GET"
        or terminal[0].get("path") is not None
        or terminal[0].get("http_status") != 200
        or terminal[0].get("bytes_received") != 660
        or terminal[0].get("response_sha256") != observation.get("raw_response_sha256")
        or terminal[0].get("sanitized_outcome") != "schema_failure"
        or journal_rows[-1].get("event_type") != "run_stopped"
        or journal_rows[-1].get("sanitized_outcome") != "schema_failure"
    ):
        raise FirewallBaselineError("historical journal provenance drifted")
    report = structural_report_for_historical_projection(observation)
    document: dict[str, object] = {
        "schema_version": "0.1.0",
        "historical_run_id": HISTORICAL_RUN_ID,
        "historical_plan_id": HISTORICAL_PLAN_ID,
        "historical_plan_path": str(HISTORICAL_PLAN_RELATIVE),
        "historical_plan_sha256": HISTORICAL_PLAN_SHA256,
        "observer_journal_path": str(HISTORICAL_JOURNAL_RELATIVE),
        "observer_journal_sha256": HISTORICAL_JOURNAL_SHA256,
        "observation_path": str(HISTORICAL_OBSERVATION_RELATIVE),
        "observation_bytes": HISTORICAL_OBSERVATION_BYTES,
        "observation_sha256": HISTORICAL_OBSERVATION_SHA256,
        "official_contract": {
            "url": OPENAPI_URL,
            "openapi_version": OPENAPI_VERSION,
            "api_version": API_VERSION,
            "bytes": OPENAPI_BYTES,
            "sha256": OPENAPI_SHA256,
        },
        "request": {
            "ordinal": 6,
            "method": "GET",
            "path": GLOBAL_FIREWALL_PATH,
            "http_status": 200,
            "response_bytes": 660,
            "endpoint_schema_passed": True,
        },
        "original_failure_classification": "schema_failure",
        "adjudicated_classification": "incomplete_or_transformed_baseline",
        "reason_codes": [
            "raw_response_not_retained",
            "projection_drops_unknown_raw_key_structure",
            "historical_l1_baseline_omitted_required_description",
        ],
        "no_mutation_occurred": True,
        "run_replay_allowed": False,
        "manual_plan_generation_allowed": False,
        "next_required_state": CAPTURE_TERMINAL_DECISION,
        "sensitive_scalar_values_retained": False,
    }
    return HistoricalAdjudication(
        document,
        report,
        encoded[HISTORICAL_OBSERVATION_RELATIVE],
        encoded[HISTORICAL_JOURNAL_RELATIVE],
    )


def _artifact_identity(repository_root: Path, relative: Path) -> dict[str, object]:
    encoded = _read_regular_no_follow(repository_root / relative, max_bytes=4_194_304)
    return {"path": str(relative), "bytes": len(encoded), "sha256": sha256_bytes(encoded)}


def render_capture_plan(
    repository_root: Path, *, reviewed_implementation_commit: str
) -> dict[str, object]:
    """Render a fresh, unauthorized one-GET plan with no mutation surface."""

    root = repository_root.resolve(strict=True)
    if re.fullmatch(r"[a-f0-9]{40}", reviewed_implementation_commit) is None:
        raise FirewallBaselineError("reviewed implementation commit is invalid")
    artifacts = [
        Path("src/giclab/harness/lambda_firewall_baseline.py"),
        CAPTURE_BOOTSTRAP_RELATIVE,
        BASELINE_SCHEMA_RELATIVE,
        CANONICAL_REPORT_SCHEMA_RELATIVE,
        RESTORATION_SCHEMA_RELATIVE,
        CAPTURE_LEDGER_SCHEMA_RELATIVE,
        PUBLIC_CONTRACT_RELATIVE,
    ]
    return {
        "schema_version": "0.1.0",
        "plan_id": CAPTURE_PLAN_ID,
        "run_id": CAPTURE_RUN_ID,
        "terminal_decision": CAPTURE_TERMINAL_DECISION,
        "authorization": {
            "authorization_reference": CAPTURE_AUTHORIZATION_PLACEHOLDER,
            "authorized": False,
            "cloud_mutation_allowed": False,
            "paid_compute_allowed": False,
            "prototype_execution_allowed": False,
            "scientific_interpretation_allowed": False,
        },
        "request": {
            "ordinal": 1,
            "method": "GET",
            "scheme": "https",
            "host": "cloud.lambda.ai",
            "path": GLOBAL_FIREWALL_PATH,
            "query_key_names": [],
            "redirect_follows": 0,
            "pagination_requests": 0,
            "automatic_retries": 0,
        },
        "transport": {
            "kind": "in-process-https",
            "implementation": (
                "giclab.harness.lambda_l2m_observer.LambdaHttpsL2MObserverTransport"
            ),
            "http_subprocesses": 0,
        },
        "caps": {
            "account_gets": 1,
            "raw_response_bytes": MAX_CAPTURE_RESPONSE_BYTES,
            "request_ledger_bytes": MAX_CAPTURE_LEDGER_BYTES,
            "request_ledger_events": MAX_CAPTURE_LEDGER_EVENTS,
            "request_ledger_event_bytes": MAX_CAPTURE_EVENT_BYTES,
            "local_artifact_bytes": MAX_CAPTURE_LOCAL_ARTIFACT_BYTES,
            "external_archive_bytes": MAX_CAPTURE_ARCHIVE_BYTES,
            "provider_wall_seconds": MAX_CAPTURE_PROVIDER_WALL_SECONDS,
            "archive_wall_seconds": MAX_CAPTURE_ARCHIVE_WALL_SECONDS,
            "total_wall_seconds": MAX_CAPTURE_TOTAL_WALL_SECONDS,
            "automatic_retries": 0,
            "pagination_requests": 0,
            "redirect_follows": 0,
            "cloud_mutations": 0,
            "paid_compute_cents": 0,
            "ssh_operations": 0,
            "jupyter_actions": 0,
            "browser_actions": 0,
            "container_actions": 0,
            "model_calls": 0,
            "model_tokens": 0,
            "sira_executions": 0,
        },
        "evidence": {
            "ledger_path": str(CAPTURE_LEDGER_RELATIVE),
            "ledger_schema_path": str(CAPTURE_LEDGER_SCHEMA_RELATIVE),
            "raw_response_relative_path": "raw-global-firewall-response.json",
            "baseline_relative_path": "firewall-baseline.json",
            "restoration_payload_relative_path": "restoration-payload.json",
            "canonical_report_relative_path": "canonical-report.json",
            "byte_preserve_raw_response": True,
            "source_retained": True,
            "destination_hashes_verified": True,
        },
        "storage": {
            "local_run_root": str(CAPTURE_RUN_ROOT_RELATIVE),
            "external_archive_root": str(APPROVED_MOUNT / "GIC-Lab/t07/sealed-artifacts"),
            "external_archive_identity": CAPTURE_RUN_ID,
            "external_volume_uuid": "8478609D-FA37-4ED5-875D-47AE912B9151",
            "external_physical_store_uuid": "7904A6F1-F483-4ED7-9E34-BFECAB31C63E",
            "local_prewrite_floor_bytes": MIN_LOCAL_PREWRITE_FREE_BYTES,
            "local_retained_floor_bytes": MIN_LOCAL_RETAINED_FREE_BYTES,
            "held_no_follow_descriptors": True,
            "atomic_finalization": True,
            "one_way_copy": True,
            "internal_fallback": False,
        },
        "firewall_contract": {
            "public_record_path": str(PUBLIC_CONTRACT_RELATIVE),
            "url": OPENAPI_URL,
            "openapi_version": OPENAPI_VERSION,
            "api_version": API_VERSION,
            "bytes": OPENAPI_BYTES,
            "sha256": OPENAPI_SHA256,
            "canonicalization_version": CANONICALIZATION_VERSION,
            "baseline_schema_path": str(BASELINE_SCHEMA_RELATIVE),
            "canonical_report_schema_path": str(CANONICAL_REPORT_SCHEMA_RELATIVE),
            "restoration_payload_schema_path": str(RESTORATION_SCHEMA_RELATIVE),
        },
        "historical_binding": {
            "run_id": HISTORICAL_RUN_ID,
            "plan_sha256": HISTORICAL_PLAN_SHA256,
            "journal_sha256": HISTORICAL_JOURNAL_SHA256,
            "observation_sha256": HISTORICAL_OBSERVATION_SHA256,
            "classification": "incomplete_or_transformed_baseline",
            "replay_allowed": False,
        },
        "implementation_binding": {
            "branch": "phase-1/sira-smoke-lambda",
            "required_execution_commit": "<EXACT-FINAL-CLEAN-L2M-1-HANDOFF-COMMIT>",
            "reviewed_implementation_commit": reviewed_implementation_commit,
            "artifacts": [_artifact_identity(root, path) for path in artifacts],
        },
        "scientific_lock": {
            "experiment": "EXP-0001",
            "profile": "PLAN-EXP0001-SMOKE",
            "condition_order": ["SIRA-REACTIVE", "SIRA-SIMULATIVE"],
            "pair": "PAIR-EXP0001-SMOKE-0000",
            "model": "gpt-4o-2024-11-20",
            "reproduction_level": "directional reproduction",
            "interpretation_allowed": False,
            "pilot_authorized": False,
            "training": False,
            "gate_scope": "read-only-firewall-baseline-capture-only",
        },
        "capture_invocation": [
            ".venv/bin/python",
            "-I",
            str(CAPTURE_BOOTSTRAP_RELATIVE),
            "--repository-root",
            ".",
            "--plan",
            str(CAPTURE_PLAN_RELATIVE),
            "--plan-sha256",
            "<EXACT-PLAN-SHA256-FROM-FRESH-AUTHORIZATION>",
            "--expected-commit",
            "<EXACT-FINAL-CLEAN-L2M-1-HANDOFF-COMMIT>",
            "--authorization-reference",
            "<FRESH-AUTHORIZATION-REFERENCE>",
            "--authorization-sha256",
            "<FRESH-AUTHORIZATION-SHA256>",
        ],
    }


def validate_capture_plan(plan: Mapping[str, object], *, repository_root: Path) -> None:
    """Fail closed unless a plan is the exact unauthorized capture contract."""

    expected = render_capture_plan(
        repository_root,
        reviewed_implementation_commit=_string(
            _mapping(plan.get("implementation_binding"), context="implementation binding").get(
                "reviewed_implementation_commit"
            ),
            context="reviewed implementation commit",
        ),
    )
    if dict(plan) != expected:
        raise FirewallBaselineError("firewall baseline capture plan drifted")


def _strict_json(encoded: bytes, *, context: str) -> dict[str, object]:
    def pairs(values: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in values:
            if key in result:
                raise FirewallBaselineError(f"{context} contains a duplicate key")
            result[key] = value
        return result

    try:
        value = json.loads(encoded, object_pairs_hook=pairs)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise FirewallBaselineError(f"{context} is not strict JSON") from None
    if not isinstance(value, dict):
        raise FirewallBaselineError(f"{context} is not an object")
    return value


def _git(repository_root: Path, *arguments: str) -> str:
    try:
        completed = subprocess.run(
            ["/usr/bin/git", "-C", str(repository_root), *arguments],
            check=False,
            capture_output=True,
            timeout=GIT_TIMEOUT_SECONDS,
            env={"LC_ALL": "C", "PATH": "/usr/bin:/bin"},
        )
    except (OSError, subprocess.SubprocessError):
        raise FirewallBaselineError("read-only Git capture preflight failed") from None
    if len(completed.stdout) + len(completed.stderr) > MAX_GIT_OUTPUT_BYTES:
        raise FirewallBaselineError("read-only Git capture preflight exceeded its cap")
    if completed.returncode != 0:
        raise FirewallBaselineError("read-only Git capture preflight returned failure")
    try:
        return completed.stdout.decode("utf-8", "strict").strip()
    except UnicodeDecodeError:
        raise FirewallBaselineError("read-only Git output was not UTF-8") from None


def _verify_capture_artifacts(repository_root: Path, plan: Mapping[str, object]) -> str:
    binding = _mapping(plan.get("implementation_binding"), context="implementation binding")
    reviewed = _string(
        binding.get("reviewed_implementation_commit"),
        context="reviewed implementation commit",
    )
    if _COMMIT.fullmatch(reviewed) is None:
        raise FirewallBaselineError("reviewed implementation commit is invalid")
    artifacts = _sequence(binding.get("artifacts"), context="implementation artifacts")
    if not artifacts:
        raise FirewallBaselineError("implementation artifact binding is empty")
    for value in artifacts:
        artifact = _mapping(value, context="implementation artifact")
        relative = Path(_string(artifact.get("path"), context="implementation path"))
        if relative.is_absolute() or ".." in relative.parts:
            raise FirewallBaselineError("implementation artifact path is unsafe")
        encoded = _read_regular_no_follow(repository_root / relative, max_bytes=4_194_304)
        if artifact.get("bytes") != len(encoded) or artifact.get("sha256") != sha256_bytes(encoded):
            raise FirewallBaselineError("plan-bound implementation artifact drifted")
    return reviewed


def verify_capture_preflight(
    repository_root: Path,
    *,
    plan_path: Path,
    expected_plan_sha256: str,
    authorization: CaptureAuthorization,
    volume_observer: Callable[[], tuple[VolumeObservation, VolumeObservation]] | None = None,
) -> CapturePreflight:
    """Complete repository, storage, and identity checks before a secret read."""

    authorization.validate()
    root = repository_root.resolve(strict=True)
    if root != repository_root.absolute() or root != Path.cwd().resolve(strict=True):
        raise FirewallBaselineError("capture must start in the canonical repository root")
    exact_plan = root / CAPTURE_PLAN_RELATIVE
    if plan_path.absolute() != exact_plan:
        raise FirewallBaselineError("capture plan path differs from the exact contract")
    encoded = _read_regular_no_follow(exact_plan, max_bytes=1_048_576)
    if (
        _SHA256.fullmatch(expected_plan_sha256) is None
        or sha256_bytes(encoded) != expected_plan_sha256
    ):
        raise FirewallBaselineError("capture plan SHA-256 drifted")
    plan = _strict_json(encoded, context="capture plan")
    validate_capture_plan(plan, repository_root=root)
    if (
        plan.get("plan_id") != CAPTURE_PLAN_ID
        or plan.get("run_id") != CAPTURE_RUN_ID
        or plan.get("terminal_decision") != CAPTURE_TERMINAL_DECISION
    ):
        raise FirewallBaselineError("capture plan identity drifted")
    if (
        _git(root, "branch", "--show-current") != "phase-1/sira-smoke-lambda"
        or _git(root, "rev-parse", "HEAD") != authorization.expected_commit
        or _git(root, "status", "--short")
    ):
        raise FirewallBaselineError("capture requires the exact clean branch and commit")
    reviewed = _verify_capture_artifacts(root, plan)
    _git(root, "merge-base", "--is-ancestor", reviewed, authorization.expected_commit)
    run_root = root / CAPTURE_RUN_ROOT_RELATIVE
    if run_root.exists() or run_root.is_symlink():
        raise FirewallBaselineError("capture run identity is not fresh")
    local_free = os.statvfs(root).f_bavail * os.statvfs(root).f_frsize
    if local_free < MIN_LOCAL_PREWRITE_FREE_BYTES + MAX_CAPTURE_LOCAL_ARTIFACT_BYTES:
        raise FirewallBaselineError("capture local prewrite floor failed")

    observer = DiskutilVolumeObserver() if volume_observer is None else volume_observer
    archive_root: _HeldDirectory | None = None
    try:
        external, system = observer()
        _validate_external(external, incremental_bytes=MAX_CAPTURE_ARCHIVE_BYTES)
        _validate_system(system, floor_bytes=MIN_LOCAL_PREWRITE_FREE_BYTES)
        external_mount = _HeldDirectory.open(APPROVED_MOUNT)
        try:
            archive_root = _open_or_create_archive_root(
                external_mount, APPROVED_MOUNT / "GIC-Lab/t07/sealed-artifacts"
            )
        finally:
            external_mount.close()
        for name in (CAPTURE_RUN_ID, f".{CAPTURE_RUN_ID}.partial"):
            try:
                os.stat(name, dir_fd=archive_root.descriptor, follow_symlinks=False)
            except FileNotFoundError:
                continue
            raise FirewallBaselineError("capture external archive identity is not fresh")
    except InventoryArchiveError:
        raise FirewallBaselineError("capture storage preflight failed") from None
    finally:
        if archive_root is not None:
            archive_root.close()
    return CapturePreflight(plan, expected_plan_sha256, reviewed)


@dataclass(frozen=True, slots=True)
class CaptureResponse:
    status: int
    content_type: str
    body: bytes = field(repr=False)
    elapsed_ms: int


class CaptureTransport(Protocol):
    def fetch(
        self,
        *,
        credential: str,
        timeout_seconds: float,
        max_response_bytes: int,
    ) -> CaptureResponse: ...


@dataclass(frozen=True, slots=True)
class CaptureEvidence:
    baseline_alias: str
    baseline_sha256: str
    restoration_payload_sha256: str
    raw_response_sha256: str
    ledger_sha256: str
    ledger_events: int
    root: Path = field(repr=False)


def complete_canonical_report(baseline: CanonicalFirewallBaseline) -> dict[str, object]:
    """Return the public-safe shape and hash report for a complete private baseline."""

    shapes: list[dict[str, object]] = []
    empty = 0
    nonempty = 0
    protocols: set[str] = set()
    for rule in baseline.rules:
        fields = ["description", "protocol", "source_network"]
        if rule.port_range is not None:
            fields.append("port_range")
        shapes.append(
            {
                "fields": sorted(fields),
                "types": {
                    "description": "string",
                    "port_range": "array" if rule.port_range is not None else "absent",
                    "protocol": "string",
                    "source_network": "string",
                },
            }
        )
        empty += int(rule.description == "")
        nonempty += int(rule.description != "")
        protocols.add(rule.protocol)
    return {
        "schema_version": "0.1.0",
        "evidence_classification": "complete_pre_mutation_provider_baseline",
        "canonicalization_version": baseline.version,
        "baseline_alias": baseline.alias,
        "canonical_semantic_sha256": baseline.semantic_sha256,
        "rule_count": baseline.rule_count,
        "rule_shapes": shapes,
        "empty_description_count": empty,
        "nonempty_description_count": nonempty,
        "protocol_classes": sorted(protocols),
        "all_current_required_fields_present": True,
        "all_port_range_presence_distinguished": True,
        "raw_response_retained": True,
        "unknown_raw_key_structure_retained": True,
        "sensitive_scalar_values_retained": False,
    }


@dataclass(frozen=True, slots=True)
class CaptureAuthorization:
    expected_commit: str
    authorization_reference: str
    authorization_sha256: str

    def validate(self) -> None:
        if (
            _COMMIT.fullmatch(self.expected_commit) is None
            or _CAPTURE_AUTHORIZATION.fullmatch(self.authorization_reference) is None
            or self.authorization_reference.endswith("-PENDING")
            or _SHA256.fullmatch(self.authorization_sha256) is None
        ):
            raise FirewallBaselineError("fresh capture authorization binding is invalid")


@dataclass(frozen=True, slots=True)
class CapturePreflight:
    plan: Mapping[str, object]
    plan_sha256: str
    reviewed_implementation_commit: str


_CAPTURE_EVENT_ORDER: Final = {
    "run_preflight_started": 1,
    "ledger_capacity_reserved": 2,
    "secret_presence_check_passed": 3,
    "run_preflight_passed": 4,
    "request_intent_committed": 5,
    "request_send_started": 6,
    "response_headers_received": 7,
    "response_body_completed": 8,
    "response_validation_passed": 9,
    "baseline_seal_started": 10,
    "baseline_seal_passed": 11,
}


@dataclass(slots=True)
class CaptureLedger:
    descriptor: int
    path: Path
    validator: Draft202012Validator
    authorization_reference: str
    events: int = 0
    bytes_written: int = 0
    terminal: bool = False

    @classmethod
    def create(
        cls,
        repository_root: Path,
        *,
        authorization_reference: str,
    ) -> CaptureLedger:
        if _AUTHORIZATION.fullmatch(authorization_reference) is None or (
            authorization_reference.endswith("-PENDING")
        ):
            raise FirewallBaselineError("capture authorization reference is pending or invalid")
        root = repository_root.resolve(strict=True)
        run_root = root / CAPTURE_RUN_ROOT_RELATIVE
        if run_root.exists() or run_root.is_symlink():
            raise FirewallBaselineError("capture run identity is not fresh")
        try:
            run_root.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            run_root.mkdir(mode=0o700)
            parent_fd = os.open(
                run_root.parent,
                os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
            )
            try:
                os.fsync(parent_fd)
            finally:
                os.close(parent_fd)
            descriptor = os.open(
                run_root / "request-ledger.jsonl",
                os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0),
                0o600,
            )
        except OSError:
            raise FirewallBaselineError("capture ledger could not be created exclusively") from None
        schema, _ = _load_schema(root, CAPTURE_LEDGER_SCHEMA_RELATIVE)
        return cls(
            descriptor,
            run_root / "request-ledger.jsonl",
            Draft202012Validator(schema, format_checker=FormatChecker()),
            authorization_reference,
        )

    def append(
        self,
        event_type: str,
        *,
        request: bool = False,
        bytes_received: int = 0,
        status: int | None = None,
        content_type: str | None = None,
        elapsed_ms: int | None = None,
        response_sha256: str | None = None,
        failure_stage: str | None = None,
        failure_class: str | None = None,
    ) -> None:
        if self.terminal:
            raise FirewallBaselineError("capture ledger is terminal")
        sequence = self.events + 1
        expected = _CAPTURE_EVENT_ORDER.get(event_type)
        if expected is not None and sequence != expected:
            raise FirewallBaselineError("capture ledger event order drifted")
        document: dict[str, object] = {
            "schema_version": "0.1.0",
            "event_type": event_type,
            "run_id": CAPTURE_RUN_ID,
            "plan_id": CAPTURE_PLAN_ID,
            "authorization_reference": self.authorization_reference,
            "event_sequence": sequence,
            "request_ordinal": 1 if request else None,
            "method": "GET" if request else None,
            "scheme": "https" if request else None,
            "host": "cloud.lambda.ai" if request else None,
            "path": GLOBAL_FIREWALL_PATH if request else None,
            "monotonic_timestamp_ns": time.monotonic_ns(),
            "wall_timestamp_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "bytes_received_so_far": bytes_received,
            "http_status": status,
            "content_type": content_type,
            "elapsed_ms": elapsed_ms,
            "response_sha256": response_sha256,
            "sanitized_failure_stage": failure_stage,
            "sanitized_failure_class": failure_class,
            "retry_count": 0,
            "pagination_request": False,
        }
        if next(self.validator.iter_errors(document), None) is not None:
            raise FirewallBaselineError("capture ledger event failed schema validation")
        encoded = canonical_json_bytes(document)
        if (
            len(encoded) > MAX_CAPTURE_EVENT_BYTES
            or sequence > MAX_CAPTURE_LEDGER_EVENTS
            or self.bytes_written + len(encoded) > MAX_CAPTURE_LEDGER_BYTES
        ):
            raise FirewallBaselineError("capture ledger cap exceeded")
        try:
            view = memoryview(encoded)
            while view:
                written = os.write(self.descriptor, view)
                if written <= 0:
                    raise OSError
                view = view[written:]
            os.fsync(self.descriptor)
        except OSError:
            raise FirewallBaselineError("capture ledger append durability failed") from None
        self.events = sequence
        self.bytes_written += len(encoded)
        if event_type == "run_stopped":
            self.terminal = True

    def close(self) -> tuple[int, str]:
        try:
            os.fsync(self.descriptor)
            os.lseek(self.descriptor, 0, os.SEEK_SET)
            encoded = os.read(self.descriptor, MAX_CAPTURE_LEDGER_BYTES + 1)
            if len(encoded) != self.bytes_written or len(encoded.splitlines()) != self.events:
                raise FirewallBaselineError("capture ledger final identity drifted")
            return len(encoded), sha256_bytes(encoded)
        finally:
            os.close(self.descriptor)


def _write_private_file(run_root: Path, name: str, encoded: bytes, *, cap: int) -> None:
    if not encoded or len(encoded) > cap:
        raise FirewallBaselineError("capture private artifact exceeds its cap")
    directory = os.open(
        run_root,
        os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
    )
    try:
        _write_exclusive_at(directory, name, encoded)
        os.fsync(directory)
    except InventoryArchiveError:
        raise FirewallBaselineError("capture private artifact write failed") from None
    finally:
        os.close(directory)


def capture_with_fakeable_transport(
    repository_root: Path,
    *,
    authorization_reference: str,
    credential_provider: Callable[[], str | None],
    transport: CaptureTransport,
) -> CaptureEvidence:
    """Exercise one complete capture locally; callers must establish live authority."""

    root = repository_root.resolve(strict=True)
    ledger = CaptureLedger.create(root, authorization_reference=authorization_reference)
    run_root = root / CAPTURE_RUN_ROOT_RELATIVE
    try:
        ledger.append("run_preflight_started")
        free_bytes = os.statvfs(run_root).f_bavail * os.statvfs(run_root).f_frsize
        if free_bytes < MIN_LOCAL_PREWRITE_FREE_BYTES + MAX_CAPTURE_LEDGER_BYTES:
            raise FirewallBaselineError("capture ledger capacity cannot be reserved")
        ledger.append("ledger_capacity_reserved")
        credential = credential_provider()
        if (
            not isinstance(credential, str)
            or not credential
            or len(credential) > 4_096
            or any(c in credential for c in "\r\n\x00")
        ):
            raise FirewallBaselineError("capture secret presence contract failed")
        ledger.append("secret_presence_check_passed")
        ledger.append("run_preflight_passed")
        ledger.append("request_intent_committed", request=True)
        ledger.append("request_send_started", request=True)
        try:
            response = transport.fetch(
                credential=credential,
                timeout_seconds=MAX_CAPTURE_PROVIDER_WALL_SECONDS,
                max_response_bytes=MAX_CAPTURE_RESPONSE_BYTES,
            )
        except BaseException:
            with suppress(FirewallBaselineError):
                ledger.append(
                    "request_outcome_unknown_after_send",
                    request=True,
                    failure_stage="transport",
                    failure_class="outcome_unknown",
                )
                ledger.append(
                    "run_stopped",
                    failure_stage="transport",
                    failure_class="outcome_unknown",
                )
            raise
        response_sha256 = sha256_bytes(response.body)
        normalized_content_type = (
            "application/json"
            if response.content_type.split(";", 1)[0].casefold() == "application/json"
            else "unexpected"
        )
        ledger.append(
            "response_headers_received",
            request=True,
            status=response.status,
            content_type=normalized_content_type,
            elapsed_ms=response.elapsed_ms,
            response_sha256=response_sha256,
        )
        if (
            response.status != 200
            or normalized_content_type != "application/json"
            or not 0 < len(response.body) <= MAX_CAPTURE_RESPONSE_BYTES
        ):
            ledger.append(
                "request_failed",
                request=True,
                bytes_received=len(response.body),
                status=response.status,
                content_type=normalized_content_type,
                elapsed_ms=response.elapsed_ms,
                response_sha256=response_sha256,
                failure_stage=("http_status" if response.status != 200 else "content_type"),
                failure_class=(
                    "http_failure" if response.status != 200 else "unexpected_content_type"
                ),
            )
            ledger.append(
                "run_stopped",
                failure_stage="schema_validation",
                failure_class="schema_drift",
            )
            raise FirewallBaselineError("capture response failed status/content contract")
        ledger.append(
            "response_body_completed",
            request=True,
            bytes_received=len(response.body),
            status=response.status,
            content_type="application/json",
            elapsed_ms=response.elapsed_ms,
            response_sha256=response_sha256,
        )
        envelope = _load_json(response.body, context="capture response")
        if set(envelope) != {"data"}:
            raise FirewallBaselineError("capture response envelope has unknown or missing fields")
        ruleset = _mapping(envelope.get("data"), context="capture global ruleset")
        if set(ruleset) != {"id", "name", "rules"} or ruleset.get("id") != "global":
            raise FirewallBaselineError("capture global ruleset has unknown or missing fields")
        rules = _sequence(ruleset.get("rules"), context="capture global rules")
        baseline = canonicalize_firewall_rules(rules)
        _, restoration_encoded, restoration_sha256 = build_exact_restoration_payload(
            rules, repository_root=root
        )
        ledger.append(
            "response_validation_passed",
            request=True,
            bytes_received=len(response.body),
            status=200,
            content_type="application/json",
            elapsed_ms=response.elapsed_ms,
            response_sha256=response_sha256,
        )
        ledger.append("baseline_seal_started")
        baseline_document: dict[str, object] = {
            "schema_version": "0.1.0",
            "baseline_alias": baseline.alias,
            "canonicalization_version": CANONICALIZATION_VERSION,
            "capture_plan_id": CAPTURE_PLAN_ID,
            "capture_run_id": CAPTURE_RUN_ID,
            "authorization_reference": authorization_reference,
            "provider": "lambda-on-demand-cloud",
            "api_base_url": API_BASE_URL,
            "retrieved_at_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "official_contract": {
                "url": OPENAPI_URL,
                "api_version": API_VERSION,
                "openapi_version": OPENAPI_VERSION,
                "bytes": OPENAPI_BYTES,
                "sha256": OPENAPI_SHA256,
            },
            "request": {
                "method": "GET",
                "path": GLOBAL_FIREWALL_PATH,
                "http_status": 200,
                "response_bytes": len(response.body),
                "response_sha256": response_sha256,
            },
            "raw_response": {
                "relative_path": "raw-global-firewall-response.json",
                "bytes": len(response.body),
                "sha256": response_sha256,
                "byte_preserved": True,
            },
            "global_ruleset": dict(ruleset),
            "canonical_semantic_sha256": baseline.semantic_sha256,
            "restoration_payload_sha256": restoration_sha256,
            "unknown_fields": {
                "envelope": [],
                "global_ruleset": [],
                "rules": [[] for _ in rules],
            },
        }
        baseline_schema, _ = _load_schema(root, BASELINE_SCHEMA_RELATIVE)
        if (
            next(
                Draft202012Validator(baseline_schema, format_checker=FormatChecker()).iter_errors(
                    baseline_document
                ),
                None,
            )
            is not None
        ):
            raise FirewallBaselineError("capture baseline failed its private schema")
        baseline_encoded = canonical_json_bytes(baseline_document)
        canonical_report = complete_canonical_report(baseline)
        canonical_report_schema, _ = _load_schema(root, CANONICAL_REPORT_SCHEMA_RELATIVE)
        if (
            next(
                Draft202012Validator(canonical_report_schema).iter_errors(canonical_report),
                None,
            )
            is not None
        ):
            raise FirewallBaselineError("capture canonical report failed its schema")
        canonical_report_encoded = canonical_json_bytes(canonical_report)
        _write_private_file(
            run_root,
            "raw-global-firewall-response.json",
            response.body,
            cap=MAX_CAPTURE_RESPONSE_BYTES,
        )
        _write_private_file(
            run_root,
            "firewall-baseline.json",
            baseline_encoded,
            cap=MAX_CAPTURE_LOCAL_ARTIFACT_BYTES,
        )
        _write_private_file(
            run_root,
            "restoration-payload.json",
            restoration_encoded,
            cap=MAX_CAPTURE_LOCAL_ARTIFACT_BYTES,
        )
        _write_private_file(
            run_root,
            "canonical-report.json",
            canonical_report_encoded,
            cap=MAX_CAPTURE_LOCAL_ARTIFACT_BYTES,
        )
        ledger.append("baseline_seal_passed")
        ledger.append("run_stopped")
        _, ledger_sha256 = ledger.close()
        return CaptureEvidence(
            baseline.alias,
            sha256_bytes(baseline_encoded),
            restoration_sha256,
            response_sha256,
            ledger_sha256,
            ledger.events,
            run_root,
        )
    except BaseException:
        if not ledger.terminal:
            with suppress(FirewallBaselineError):
                ledger.append(
                    "request_failed",
                    request=ledger.events >= 6,
                    failure_stage="schema_validation",
                    failure_class="schema_drift",
                )
                ledger.append(
                    "run_stopped",
                    failure_stage="schema_validation",
                    failure_class="schema_drift",
                )
        with suppress(OSError, FirewallBaselineError):
            ledger.close()
        raise


class L2MObserverCaptureTransport:
    """Adapt the reviewed GET-only observer transport to the one-request capture."""

    def fetch(
        self,
        *,
        credential: str,
        timeout_seconds: float,
        max_response_bytes: int,
    ) -> CaptureResponse:
        # Local import avoids a module cycle when the manual observer imports the
        # canonicalization primitive from this module.
        from .lambda_l2m_observer import (
            LambdaHttpsL2MObserverTransport,
            ObserverOperation,
            ObserverTransportFailure,
            observer_request,
        )

        active = LambdaHttpsL2MObserverTransport()
        try:
            response = active.send(
                observer_request(ObserverOperation.GET_GLOBAL_FIREWALL),
                credential=credential,
                timeout_seconds=timeout_seconds,
                absolute_deadline_monotonic_ns=(
                    time.monotonic_ns() + int(timeout_seconds * 1_000_000_000)
                ),
                max_response_bytes=max_response_bytes,
            )
        except ObserverTransportFailure:
            raise FirewallBaselineError("capture in-process HTTPS transport failed") from None
        return CaptureResponse(
            response.status,
            response.content_type,
            response.body,
            response.elapsed_ms,
        )


@dataclass(frozen=True, slots=True)
class CaptureArchiveSeal:
    archive_alias: str
    manifest_sha256: str
    external_seal_sha256: str
    external_copy_record_sha256: str
    destination_hashes_verified: bool
    source_retained: bool
    local_root: Path = field(repr=False)
    external_root: Path = field(repr=False)


_CAPTURE_SOURCE_NAMES: Final = (
    "request-ledger.jsonl",
    "raw-global-firewall-response.json",
    "firewall-baseline.json",
    "restoration-payload.json",
    "canonical-report.json",
)


def seal_capture_evidence_to_approved_external(
    repository_root: Path,
    *,
    plan_sha256: str,
    authorization_sha256: str,
    volume_observer: Callable[[], tuple[VolumeObservation, VolumeObservation]] | None = None,
    utc_now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> CaptureArchiveSeal:
    """Seal the complete capture one-way under held storage capabilities."""

    if _SHA256.fullmatch(plan_sha256) is None or _SHA256.fullmatch(authorization_sha256) is None:
        raise FirewallBaselineError("capture archive binding hash is invalid")
    root = repository_root.resolve(strict=True)
    local_root = root / CAPTURE_RUN_ROOT_RELATIVE
    local_members = {
        name: _read_regular_no_follow(local_root / name, max_bytes=MAX_CAPTURE_LOCAL_ARTIFACT_BYTES)
        for name in _CAPTURE_SOURCE_NAMES
    }
    if sum(len(value) for value in local_members.values()) > MAX_CAPTURE_LOCAL_ARTIFACT_BYTES:
        raise FirewallBaselineError("capture local evidence exceeds its aggregate cap")
    manifest = canonical_json_bytes(
        {
            "schema_version": "0.1.0",
            "plan_id": CAPTURE_PLAN_ID,
            "plan_sha256": plan_sha256,
            "run_id": CAPTURE_RUN_ID,
            "authorization_sha256": authorization_sha256,
            "files": [
                {"path": name, "bytes": len(encoded), "sha256": sha256_bytes(encoded)}
                for name, encoded in sorted(local_members.items())
            ],
            "source_retained": True,
            "contains_private_firewall_evidence": True,
        }
    )
    _write_private_file(
        local_root,
        "CAPTURE_MANIFEST.json",
        manifest,
        cap=MAX_CAPTURE_LOCAL_ARTIFACT_BYTES,
    )
    local_members["CAPTURE_MANIFEST.json"] = manifest
    archive_alias = f"l2m-firewall-capture-{sha256_bytes(manifest)[:12]}"
    archive_identity = CAPTURE_RUN_ID
    staging_name = f".{archive_identity}.partial"
    archive_root_path = APPROVED_MOUNT / "GIC-Lab/t07/sealed-artifacts"
    observer = DiskutilVolumeObserver() if volume_observer is None else volume_observer
    external_mount: _HeldDirectory | None = None
    system_mount: _HeldDirectory | None = None
    repository_handle: _HeldDirectory | None = None
    archive_root: _HeldDirectory | None = None
    staging_fd = -1
    started = time.monotonic()
    try:
        external_pre, system_pre = observer()
        external_floor = _validate_external(
            external_pre, incremental_bytes=MAX_CAPTURE_ARCHIVE_BYTES
        )
        _validate_system(system_pre, floor_bytes=MIN_LOCAL_PREWRITE_FREE_BYTES)
        external_mount = _HeldDirectory.open(APPROVED_MOUNT)
        system_mount = _HeldDirectory.open(SYSTEM_DATA_MOUNT)
        repository_handle = _HeldDirectory.open(root)
        if (
            external_mount.device == system_mount.device
            or repository_handle.device != system_mount.device
        ):
            raise FirewallBaselineError("capture source/destination topology drifted")
        archive_root = _open_or_create_archive_root(external_mount, archive_root_path)
        if archive_root.device != external_mount.device:
            raise FirewallBaselineError("capture archive used an internal fallback")
        for name in (archive_identity, staging_name):
            try:
                os.stat(name, dir_fd=archive_root.descriptor, follow_symlinks=False)
            except FileNotFoundError:
                continue
            raise FirewallBaselineError("capture archive identity is not fresh")
        os.mkdir(staging_name, mode=0o700, dir_fd=archive_root.descriptor)
        staging_fd = os.open(
            staging_name,
            os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=archive_root.descriptor,
        )
        for name, encoded in sorted(local_members.items()):
            _write_exclusive_at(staging_fd, name, encoded)
        copy_record = canonical_json_bytes(
            {
                "schema_version": "0.1.0",
                "action": "t07-l2m-firewall-baseline-capture-copy",
                "archive_alias": archive_alias,
                "plan_id": CAPTURE_PLAN_ID,
                "plan_sha256": plan_sha256,
                "run_id": CAPTURE_RUN_ID,
                "authorization_sha256": authorization_sha256,
                "copied_at_utc": utc_now().astimezone(UTC).isoformat().replace("+00:00", "Z"),
                "files": [
                    {"path": name, "bytes": len(encoded), "sha256": sha256_bytes(encoded)}
                    for name, encoded in sorted(local_members.items())
                ],
                "external_volume_uuid": external_pre.volume_uuid.upper(),
                "external_physical_store_uuid": (external_pre.physical_store_uuid or "").upper(),
                "external_retained_floor_bytes": external_floor,
                "source_retained": True,
                "destination_hashes_verified": True,
                "held_no_follow_descriptors": True,
                "atomic_finalization": True,
                "internal_fallback": False,
            }
        )
        external_seal = canonical_json_bytes(
            {
                "schema_version": "0.1.0",
                "archive_alias": archive_alias,
                "manifest_sha256": sha256_bytes(manifest),
                "copy_record_sha256": sha256_bytes(copy_record),
                "source_retained": True,
                "destination_hashes_verified": True,
                "cloud_mutation_occurred": False,
            }
        )
        if (
            sum(len(value) for value in local_members.values())
            + len(copy_record)
            + len(external_seal)
            > MAX_CAPTURE_ARCHIVE_BYTES
        ):
            raise FirewallBaselineError("capture external archive exceeds its cap")
        _write_exclusive_at(staging_fd, "COPY_RECORD.json", copy_record)
        _write_exclusive_at(staging_fd, "SEAL.json", external_seal)
        os.fsync(staging_fd)
        os.fchmod(staging_fd, 0o500)
        os.rename(
            staging_name,
            archive_identity,
            src_dir_fd=archive_root.descriptor,
            dst_dir_fd=archive_root.descriptor,
        )
        os.fsync(archive_root.descriptor)
        final_fd = os.open(
            archive_identity,
            os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=archive_root.descriptor,
        )
        try:
            expected_members = {
                **local_members,
                "COPY_RECORD.json": copy_record,
                "SEAL.json": external_seal,
            }
            for name, expected in expected_members.items():
                observed = _read_regular_at(final_fd, name, max_bytes=MAX_CAPTURE_ARCHIVE_BYTES)
                if observed != expected or sha256_bytes(observed) != sha256_bytes(expected):
                    raise FirewallBaselineError("capture destination hash verification failed")
        finally:
            os.close(final_fd)
        external_post, system_post = observer()
        if not _same_identity(external_pre, external_post) or not _same_identity(
            system_pre, system_post
        ):
            raise FirewallBaselineError("capture storage identity changed during copy")
        _validate_external(external_post, incremental_bytes=0)
        _validate_system(system_post, floor_bytes=MIN_LOCAL_RETAINED_FREE_BYTES)
        if external_post.free_bytes < external_floor:
            raise FirewallBaselineError("capture external retained floor failed")
        if time.monotonic() - started > MAX_CAPTURE_ARCHIVE_WALL_SECONDS:
            raise FirewallBaselineError("capture archive wall cap exceeded")
        local_record = canonical_json_bytes(
            {
                "schema_version": "0.1.0",
                "archive_alias": archive_alias,
                "external_copy_record_sha256": sha256_bytes(copy_record),
                "external_seal_sha256": sha256_bytes(external_seal),
                "source_retained": True,
                "destination_hashes_verified": True,
                "internal_fallback": False,
            }
        )
        _write_private_file(
            local_root,
            "EXTERNAL_COPY_VERIFICATION.json",
            local_record,
            cap=MAX_CAPTURE_LOCAL_ARTIFACT_BYTES,
        )
        return CaptureArchiveSeal(
            archive_alias,
            sha256_bytes(manifest),
            sha256_bytes(external_seal),
            sha256_bytes(copy_record),
            True,
            True,
            local_root,
            archive_root_path / archive_identity,
        )
    except InventoryArchiveError:
        raise FirewallBaselineError("capture archive storage contract failed") from None
    finally:
        if staging_fd >= 0:
            os.close(staging_fd)
        for handle in (archive_root, repository_handle, system_mount, external_mount):
            if handle is not None:
                handle.close()


@dataclass(frozen=True, slots=True)
class IncidentBundleSeal:
    incident_alias: str
    local_bundle_sha256: str
    external_seal_sha256: str
    external_copy_record_sha256: str
    destination_hashes_verified: bool
    source_retained: bool
    local_root: Path = field(repr=False)
    external_root: Path = field(repr=False)


def _incident_members(
    repository_root: Path, adjudication: HistoricalAdjudication
) -> dict[str, bytes]:
    adjudication_bytes = canonical_json_bytes(adjudication.document)
    structural_bytes = canonical_json_bytes(adjudication.structural_report)
    committed_adjudication = _read_regular_no_follow(
        repository_root / HISTORICAL_ADJUDICATION_RELATIVE, max_bytes=262_144
    )
    committed_structural = _read_regular_no_follow(
        repository_root / HISTORICAL_STRUCTURAL_REPORT_RELATIVE, max_bytes=262_144
    )
    if _strict_json(committed_adjudication, context="committed historical adjudication") != dict(
        adjudication.document
    ) or _strict_json(committed_structural, context="committed structural report") != dict(
        adjudication.structural_report
    ):
        raise FirewallBaselineError("committed historical adjudication drifted")
    return {
        "observer-journal.jsonl": adjudication.original_journal,
        "observation-0006.json": adjudication.original_observation,
        "historical-adjudication.json": adjudication_bytes,
        "sanitized-structural-report.json": structural_bytes,
        "historical-plan.json": _read_regular_no_follow(
            repository_root / HISTORICAL_PLAN_RELATIVE, max_bytes=262_144
        ),
    }


def seal_run_0003_incident_bundle(
    repository_root: Path,
    *,
    volume_observer: Callable[[], tuple[VolumeObservation, VolumeObservation]] | None = None,
    entropy: Callable[[int], bytes] = secrets.token_bytes,
    utc_now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> IncidentBundleSeal:
    """Additively seal run 0003 evidence locally and to the approved APFS archive."""

    root = repository_root.resolve(strict=True)
    observer = DiskutilVolumeObserver() if volume_observer is None else volume_observer
    adjudication = adjudicate_historical_run(root)
    members = _incident_members(root, adjudication)
    local_root = root / "artifacts/t07/lambda/gate-l2m" / HISTORICAL_RUN_ID / "incident-v1"
    if local_root.exists() or local_root.is_symlink():
        raise FirewallBaselineError("run-0003 incident bundle identity is not fresh")
    original_hashes = {
        HISTORICAL_JOURNAL_RELATIVE: sha256_bytes(adjudication.original_journal),
        HISTORICAL_OBSERVATION_RELATIVE: sha256_bytes(adjudication.original_observation),
    }
    try:
        local_root.mkdir(mode=0o700)
        local_fd = os.open(
            local_root,
            os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
        )
    except OSError:
        raise FirewallBaselineError("incident bundle local root creation failed") from None
    try:
        for name, encoded in members.items():
            _write_exclusive_at(local_fd, name, encoded)
        manifest = canonical_json_bytes(
            {
                "schema_version": "0.1.0",
                "historical_run_id": HISTORICAL_RUN_ID,
                "historical_plan_id": HISTORICAL_PLAN_ID,
                "historical_plan_sha256": HISTORICAL_PLAN_SHA256,
                "original_failure_disposition": "schema_failure",
                "adjudicated_classification": "incomplete_or_transformed_baseline",
                "no_mutation_occurred": True,
                "run_replay_allowed": False,
                "files": [
                    {"path": name, "bytes": len(encoded), "sha256": sha256_bytes(encoded)}
                    for name, encoded in sorted(members.items())
                ],
            }
        )
        _write_exclusive_at(local_fd, "INCIDENT_MANIFEST.json", manifest)
        local_seal = canonical_json_bytes(
            {
                "schema_version": "0.1.0",
                "historical_run_id": HISTORICAL_RUN_ID,
                "manifest_bytes": len(manifest),
                "manifest_sha256": sha256_bytes(manifest),
                "source_retained": True,
                "original_files_unchanged": True,
                "no_mutation_occurred": True,
                "run_replay_allowed": False,
            }
        )
        _write_exclusive_at(local_fd, "INCIDENT_SEAL.json", local_seal)
        os.fsync(local_fd)
    except InventoryArchiveError:
        raise FirewallBaselineError("incident bundle local seal failed") from None
    finally:
        os.close(local_fd)
    local_members = {
        **members,
        "INCIDENT_MANIFEST.json": manifest,
        "INCIDENT_SEAL.json": local_seal,
    }
    local_total = sum(len(value) for value in local_members.values())
    if local_total > MAX_INCIDENT_BUNDLE_BYTES:
        raise FirewallBaselineError("incident bundle exceeds its local cap")
    if any(
        sha256_bytes(_read_regular_no_follow(root / relative, max_bytes=262_144)) != digest
        for relative, digest in original_hashes.items()
    ):
        raise FirewallBaselineError("historical evidence changed during incident sealing")

    random_identity = entropy(16)
    if len(random_identity) != 16:
        raise FirewallBaselineError("incident archive entropy is invalid")
    archive_identity = f"{HISTORICAL_RUN_ID}-INCIDENT-{random_identity.hex()}"
    incident_alias = f"l2m-incident-{sha256_bytes(archive_identity.encode())[:12]}"
    staging_name = f".{archive_identity}.partial"
    archive_root_path = APPROVED_MOUNT / "GIC-Lab/t07/sealed-artifacts"
    external_mount: _HeldDirectory | None = None
    system_mount: _HeldDirectory | None = None
    repository_handle: _HeldDirectory | None = None
    archive_root: _HeldDirectory | None = None
    staging_fd = -1
    started = time.monotonic()
    try:
        external_pre, system_pre = observer()
        external_floor = _validate_external(
            external_pre, incremental_bytes=MAX_INCIDENT_BUNDLE_BYTES
        )
        _validate_system(system_pre, floor_bytes=MIN_LOCAL_PREWRITE_FREE_BYTES)
        external_mount = _HeldDirectory.open(APPROVED_MOUNT)
        system_mount = _HeldDirectory.open(SYSTEM_DATA_MOUNT)
        repository_handle = _HeldDirectory.open(root)
        if (
            external_mount.device == system_mount.device
            or repository_handle.device != system_mount.device
        ):
            raise FirewallBaselineError("incident source/destination topology drifted")
        archive_root = _open_or_create_archive_root(external_mount, archive_root_path)
        if archive_root.device != external_mount.device:
            raise FirewallBaselineError("incident archive used an internal fallback")
        for name in (archive_identity, staging_name):
            try:
                os.stat(name, dir_fd=archive_root.descriptor, follow_symlinks=False)
            except FileNotFoundError:
                continue
            raise FirewallBaselineError("incident external archive identity is not fresh")
        os.mkdir(staging_name, mode=0o700, dir_fd=archive_root.descriptor)
        staging_fd = os.open(
            staging_name,
            os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=archive_root.descriptor,
        )
        for name, encoded in sorted(local_members.items()):
            _write_exclusive_at(staging_fd, name, encoded)
        copied_at = utc_now().astimezone(UTC).isoformat().replace("+00:00", "Z")
        copy_record = canonical_json_bytes(
            {
                "schema_version": "0.1.0",
                "action": "t07-l2m-run-0003-incident-copy",
                "incident_alias": incident_alias,
                "historical_run_id": HISTORICAL_RUN_ID,
                "copied_at_utc": copied_at,
                "files": [
                    {"path": name, "bytes": len(encoded), "sha256": sha256_bytes(encoded)}
                    for name, encoded in sorted(local_members.items())
                ],
                "external_volume_uuid": external_pre.volume_uuid.upper(),
                "external_physical_store_uuid": (external_pre.physical_store_uuid or "").upper(),
                "external_retained_floor_bytes": external_floor,
                "source_retained": True,
                "destination_hashes_verified": True,
                "held_no_follow_descriptors": True,
                "atomic_finalization": True,
                "internal_fallback": False,
            }
        )
        external_seal = canonical_json_bytes(
            {
                "schema_version": "0.1.0",
                "incident_alias": incident_alias,
                "copy_record_sha256": sha256_bytes(copy_record),
                "local_bundle_sha256": sha256_bytes(local_seal),
                "source_retained": True,
                "destination_hashes_verified": True,
                "no_mutation_occurred": True,
                "run_replay_allowed": False,
            }
        )
        if local_total + len(copy_record) + len(external_seal) > MAX_INCIDENT_BUNDLE_BYTES:
            raise FirewallBaselineError("incident external archive exceeds its cap")
        _write_exclusive_at(staging_fd, "COPY_RECORD.json", copy_record)
        _write_exclusive_at(staging_fd, "SEAL.json", external_seal)
        os.fsync(staging_fd)
        os.fchmod(staging_fd, 0o500)
        os.rename(
            staging_name,
            archive_identity,
            src_dir_fd=archive_root.descriptor,
            dst_dir_fd=archive_root.descriptor,
        )
        os.fsync(archive_root.descriptor)
        final_fd = os.open(
            archive_identity,
            os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=archive_root.descriptor,
        )
        try:
            for name, expected in {
                **local_members,
                "COPY_RECORD.json": copy_record,
                "SEAL.json": external_seal,
            }.items():
                observed = _read_regular_at(final_fd, name, max_bytes=MAX_INCIDENT_BUNDLE_BYTES)
                if observed != expected:
                    raise FirewallBaselineError("incident destination hash verification failed")
        finally:
            os.close(final_fd)
        external_post, system_post = observer()
        if not _same_identity(external_pre, external_post) or not _same_identity(
            system_pre, system_post
        ):
            raise FirewallBaselineError("incident storage identity changed during copy")
        _validate_external(external_post, incremental_bytes=0)
        _validate_system(system_post, floor_bytes=MIN_LOCAL_RETAINED_FREE_BYTES)
        if external_post.free_bytes < external_floor:
            raise FirewallBaselineError("incident destination retained floor failed")
        if time.monotonic() - started > MAX_CAPTURE_ARCHIVE_WALL_SECONDS:
            raise FirewallBaselineError("incident archive wall cap exceeded")
        local_record = canonical_json_bytes(
            {
                "schema_version": "0.1.0",
                "incident_alias": incident_alias,
                "external_copy_record_sha256": sha256_bytes(copy_record),
                "external_seal_sha256": sha256_bytes(external_seal),
                "source_retained": True,
                "destination_hashes_verified": True,
                "internal_fallback": False,
            }
        )
        local_fd = os.open(
            local_root,
            os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
        )
        try:
            _write_exclusive_at(local_fd, "EXTERNAL_COPY_VERIFICATION.json", local_record)
            os.fsync(local_fd)
        finally:
            os.close(local_fd)
        return IncidentBundleSeal(
            incident_alias,
            sha256_bytes(local_seal),
            sha256_bytes(external_seal),
            sha256_bytes(copy_record),
            True,
            True,
            local_root,
            archive_root_path / archive_identity,
        )
    except InventoryArchiveError:
        raise FirewallBaselineError("incident archive storage contract failed") from None
    finally:
        if staging_fd >= 0:
            os.close(staging_fd)
        for handle in (archive_root, repository_handle, system_mount, external_mount):
            if handle is not None:
                handle.close()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--plan-sha256", required=True)
    parser.add_argument("--expected-commit", required=True)
    parser.add_argument("--authorization-reference", required=True)
    parser.add_argument("--authorization-sha256", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Execute only a separately authorized, one-GET baseline capture."""

    args = _parser().parse_args(list(sys.argv[1:] if argv is None else argv))
    authorization = CaptureAuthorization(
        args.expected_commit,
        args.authorization_reference,
        args.authorization_sha256,
    )
    started = time.monotonic()
    try:
        verify_capture_preflight(
            args.repository_root,
            plan_path=args.plan,
            expected_plan_sha256=args.plan_sha256,
            authorization=authorization,
        )
        capture_with_fakeable_transport(
            args.repository_root,
            authorization_reference=authorization.authorization_reference,
            credential_provider=lambda: os.environ.get("LAMBDA_API_KEY"),
            transport=L2MObserverCaptureTransport(),
        )
        seal_capture_evidence_to_approved_external(
            args.repository_root,
            plan_sha256=args.plan_sha256,
            authorization_sha256=authorization.authorization_sha256,
        )
        if time.monotonic() - started > MAX_CAPTURE_TOTAL_WALL_SECONDS:
            raise FirewallBaselineError("capture total wall cap exceeded")
    except (FirewallBaselineError, OSError, ValueError):
        print(
            "giclab-firewall-baseline: stopped; inspect private sealed evidence",
            file=sys.stderr,
        )
        return 1
    print("T07_L2M_FIREWALL_BASELINE_DISPOSITION=capture_complete", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
