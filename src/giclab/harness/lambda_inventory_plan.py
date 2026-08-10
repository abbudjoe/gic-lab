"""Strict, hash-bound T07 Gate L1 V2 inventory-plan contract.

The V1 plan remains historical provenance in :mod:`lambda_cloud`.  This module owns
the unique V2 plan/run identity and the finite request-ledger contract that repairs
the V1 observability defect.  Loading a plan performs local file I/O only.
"""

from __future__ import annotations

import hashlib
import json
import re
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from jsonschema import Draft202012Validator

from .lambda_cloud import (
    API_BASE_URL,
    API_SPEC_SHA256,
    API_SPEC_VERSION,
    EXPECTED_INVENTORY_REQUESTS,
    INVENTORY_PLAN_V2_ID,
    INVENTORY_RUN_V2_ID,
    LAMBDA_BRANCH,
    MAX_INVENTORY_ARCHIVE_WALL_SECONDS,
    MAX_INVENTORY_CALLS,
    MAX_INVENTORY_LOCAL_COMMAND_CALLS,
    MAX_INVENTORY_LOCAL_COMMAND_OUTPUT_BYTES,
    MAX_INVENTORY_LOCAL_PREWRITE_FLOOR_BYTES,
    MAX_INVENTORY_LOCAL_RECORD_BYTES,
    MAX_INVENTORY_LOCAL_RETAINED_FLOOR_BYTES,
    MAX_INVENTORY_RETAINED_BYTES,
    MAX_INVENTORY_TOTAL_RESPONSE_BYTES,
    MAX_INVENTORY_TOTAL_WALL_SECONDS,
    MAX_INVENTORY_WALL_SECONDS,
    MIN_INVENTORY_REQUEST_SPACING_SECONDS,
    HttpMethod,
    InventoryRequest,
    LambdaCloudContractError,
)

INVENTORY_ATTEMPT_V2: Final = 2
PENDING_AUTHORIZATION_REFERENCE: Final = "AUTH-T07-GATE-L1-LAMBDA-INPROCESS-V3-PENDING"
BASELINE_COMMIT: Final = "f9a80332da409789fefc435583aa0f1a10d3eb11"
TRANSPORT_KIND: Final = "in-process-https"
TRANSPORT_IDENTITY: Final = "giclab.harness.lambda_inventory_v2.LambdaHttpsInventoryTransportV2"

LEDGER_SCHEMA_RELATIVE_PATH: Final = "schemas/t07-lambda-request-ledger.schema.json"
INVENTORY_SCHEMA_V2_RELATIVE_PATH: Final = "schemas/t07-lambda-inventory-v2.schema.json"
RUN_ROOT_RELATIVE_PATH: Final = "artifacts/t07/lambda/gate-l1/RUN-T07-L1-LAMBDA-INVENTORY-0002"
LEDGER_RELATIVE_PATH: Final = f"{RUN_ROOT_RELATIVE_PATH}/request-ledger.jsonl"
INVENTORY_RELATIVE_PATH: Final = f"{RUN_ROOT_RELATIVE_PATH}/inventory-redacted.json"
COPY_RECORD_RELATIVE_PATH: Final = f"{RUN_ROOT_RELATIVE_PATH}/inventory-copy-record.json"
PREFLIGHT_DISPOSITION_ROOT_RELATIVE_PATH: Final = (
    "artifacts/t07/lambda/gate-l1/preflight-dispositions"
)
ARCHIVE_ROOT: Final = "/Volumes/Macintosh HD - Data/GIC-Lab/t07/sealed-artifacts"

MAX_LEDGER_BYTES: Final = 262_144
MAX_LEDGER_EVENTS: Final = 96
MAX_LEDGER_EVENTS_PER_REQUEST: Final = 9
MAX_LEDGER_EVENT_BYTES: Final = 2_048
MAX_PREFLIGHT_DISPOSITION_BYTES: Final = 16_384
MAX_INVENTORY_ARCHIVE_BYTES_V2: Final = 1_048_576
MAX_INVENTORY_AGGREGATE_RETAINED_BYTES_V2: Final = 1_916_928
MAX_INVENTORY_LOCAL_FILE_CREATES_V2: Final = 4
MAX_INVENTORY_EXTERNAL_FILE_CREATES_V2: Final = 4
MAX_INVENTORY_EXTERNAL_DIRECTORY_CREATES_V2: Final = 4
MAX_IMPLEMENTATION_ARTIFACT_BYTES: Final = 5 * 1024 * 1024

IMPLEMENTATION_ARTIFACT_PATHS: Final = (
    "pyproject.toml",
    "uv.lock",
    "src/giclab/harness/lambda_cloud.py",
    "src/giclab/harness/lambda_archive.py",
    "src/giclab/harness/lambda_archive_v2.py",
    "src/giclab/harness/lambda_inventory.py",
    "src/giclab/harness/lambda_inventory_plan.py",
    "src/giclab/harness/lambda_inventory_v2.py",
    "src/giclab/harness/lambda_request_ledger.py",
    "src/giclab/harness/sira_storage.py",
    "src/giclab/validation.py",
    "schemas/t07-lambda-inventory-v2.schema.json",
    "schemas/t07-lambda-request-ledger.schema.json",
)

LEDGER_EVENT_TYPES: Final = (
    "run_preflight_started",
    "run_preflight_passed",
    "run_preflight_failed",
    "secret_presence_check_passed",
    "secret_presence_check_failed",
    "request_intent_committed",
    "request_send_started",
    "response_headers_received",
    "response_body_progress",
    "response_body_completed",
    "response_validation_passed",
    "request_failed",
    "request_outcome_unknown_after_send",
    "run_stopped",
    "inventory_validation_started",
    "inventory_validation_passed",
    "inventory_validation_failed",
    "archive_started",
    "archive_passed",
    "archive_failed",
)

FAILURE_STAGES: Final = (
    "secret_source",
    "dns",
    "tcp_connect",
    "tls_handshake",
    "request_write",
    "response_headers",
    "response_body",
    "http_status",
    "redirect",
    "rate_limit",
    "content_type",
    "response_size",
    "json_decode",
    "schema_validation",
    "pagination",
    "ledger_io",
    "archive_io",
    "unknown",
)

FAILURE_CLASSES: Final = (
    "secret_missing",
    "secret_malformed",
    "dns_failure",
    "tcp_connect_failure",
    "tls_failure",
    "request_write_failure",
    "response_headers_failure",
    "response_body_failure",
    "http_unauthorized",
    "http_forbidden",
    "http_rate_limited",
    "http_redirect",
    "http_unexpected_status",
    "unexpected_content_type",
    "response_too_large",
    "malformed_json",
    "schema_drift",
    "pagination_present",
    "ledger_create_failed",
    "ledger_write_failed",
    "archive_failed",
    "outcome_unknown",
    "deadline_exceeded",
    "internal_failure",
)

_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_GIT_COMMIT = re.compile(r"^[a-f0-9]{40}$")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


@dataclass(frozen=True, slots=True)
class LedgerLimits:
    max_bytes: int = MAX_LEDGER_BYTES
    max_events: int = MAX_LEDGER_EVENTS
    max_events_per_request: int = MAX_LEDGER_EVENTS_PER_REQUEST
    max_event_bytes: int = MAX_LEDGER_EVENT_BYTES
    max_preflight_disposition_bytes: int = MAX_PREFLIGHT_DISPOSITION_BYTES

    def __post_init__(self) -> None:
        if (
            self.max_bytes,
            self.max_events,
            self.max_events_per_request,
            self.max_event_bytes,
            self.max_preflight_disposition_bytes,
        ) != (
            MAX_LEDGER_BYTES,
            MAX_LEDGER_EVENTS,
            MAX_LEDGER_EVENTS_PER_REQUEST,
            MAX_LEDGER_EVENT_BYTES,
            MAX_PREFLIGHT_DISPOSITION_BYTES,
        ):
            raise LambdaCloudContractError("request-ledger limits drifted")
        if self.max_events * self.max_event_bytes > self.max_bytes:
            raise LambdaCloudContractError("request-ledger capacity cannot reserve every event")
        if self.max_events_per_request * MAX_INVENTORY_CALLS >= self.max_events:
            raise LambdaCloudContractError("request-ledger leaves no global-event capacity")


@dataclass(frozen=True, slots=True)
class InventoryRunBindingV2:
    run_id: str
    repository_commit: str
    authorization_reference: str
    authorization_sha256: str
    plan_id: str = INVENTORY_PLAN_V2_ID
    attempt: int = INVENTORY_ATTEMPT_V2

    def __post_init__(self) -> None:
        if self.plan_id != INVENTORY_PLAN_V2_ID or self.run_id != INVENTORY_RUN_V2_ID:
            raise LambdaCloudContractError("Gate L1 V2 plan/run identity drifted")
        if self.attempt != INVENTORY_ATTEMPT_V2:
            raise LambdaCloudContractError("Gate L1 V2 attempt identity drifted")
        if _GIT_COMMIT.fullmatch(self.repository_commit) is None:
            raise LambdaCloudContractError("Gate L1 V2 repository commit is not canonical")
        if (
            _IDENTIFIER.fullmatch(self.authorization_reference) is None
            or self.authorization_reference == PENDING_AUTHORIZATION_REFERENCE
        ):
            raise LambdaCloudContractError("Gate L1 V2 authorization reference is not fresh")
        if _SHA256.fullmatch(self.authorization_sha256) is None:
            raise LambdaCloudContractError("Gate L1 V2 authorization hash is not canonical")


@dataclass(frozen=True, slots=True)
class ImplementationArtifactBinding:
    path: str
    sha256: str

    def __post_init__(self) -> None:
        candidate = Path(self.path)
        if (
            self.path not in IMPLEMENTATION_ARTIFACT_PATHS
            or candidate.is_absolute()
            or ".." in candidate.parts
            or _SHA256.fullmatch(self.sha256) is None
        ):
            raise LambdaCloudContractError("Gate L1 V2 implementation artifact drifted")


@dataclass(frozen=True, slots=True)
class ReadOnlyInventoryPlanV2:
    implementation_commit: str
    implementation_artifacts: tuple[ImplementationArtifactBinding, ...]
    ledger_schema_sha256: str
    inventory_schema_sha256: str
    requests: tuple[InventoryRequest, ...]
    limits: LedgerLimits = LedgerLimits()
    plan_id: str = INVENTORY_PLAN_V2_ID
    run_id: str = INVENTORY_RUN_V2_ID
    attempt: int = INVENTORY_ATTEMPT_V2
    provider: str = "lambda-on-demand-cloud"
    api_base_url: str = API_BASE_URL
    api_spec_version: str = API_SPEC_VERSION
    api_spec_sha256: str = API_SPEC_SHA256
    secret_variable: str = "LAMBDA_API_KEY"
    max_calls: int = MAX_INVENTORY_CALLS
    max_total_response_bytes: int = MAX_INVENTORY_TOTAL_RESPONSE_BYTES
    max_retained_output_bytes: int = MAX_INVENTORY_RETAINED_BYTES
    max_wall_seconds: int = MAX_INVENTORY_WALL_SECONDS
    request_start_spacing_seconds: int = MIN_INVENTORY_REQUEST_SPACING_SECONDS
    max_archive_wall_seconds: int = MAX_INVENTORY_ARCHIVE_WALL_SECONDS
    max_total_wall_seconds: int = MAX_INVENTORY_TOTAL_WALL_SECONDS
    max_local_record_bytes: int = MAX_INVENTORY_LOCAL_RECORD_BYTES
    max_archive_bytes: int = MAX_INVENTORY_ARCHIVE_BYTES_V2
    max_aggregate_retained_bytes: int = MAX_INVENTORY_AGGREGATE_RETAINED_BYTES_V2
    local_prewrite_floor_bytes: int = MAX_INVENTORY_LOCAL_PREWRITE_FLOOR_BYTES
    local_retained_floor_bytes: int = MAX_INVENTORY_LOCAL_RETAINED_FLOOR_BYTES
    max_local_command_calls: int = MAX_INVENTORY_LOCAL_COMMAND_CALLS
    max_local_command_output_bytes: int = MAX_INVENTORY_LOCAL_COMMAND_OUTPUT_BYTES
    max_local_file_creates: int = MAX_INVENTORY_LOCAL_FILE_CREATES_V2
    max_external_file_creates: int = MAX_INVENTORY_EXTERNAL_FILE_CREATES_V2
    max_external_directory_creates: int = MAX_INVENTORY_EXTERNAL_DIRECTORY_CREATES_V2
    automatic_retries: int = 0
    run_root_relative_path: str = RUN_ROOT_RELATIVE_PATH
    ledger_relative_path: str = LEDGER_RELATIVE_PATH
    preflight_disposition_root_relative_path: str = PREFLIGHT_DISPOSITION_ROOT_RELATIVE_PATH
    output_relative_path: str = INVENTORY_RELATIVE_PATH
    copy_record_relative_path: str = COPY_RECORD_RELATIVE_PATH
    archive_root: str = ARCHIVE_ROOT
    inventory_schema_relative_path: str = INVENTORY_SCHEMA_V2_RELATIVE_PATH
    ledger_schema_relative_path: str = LEDGER_SCHEMA_RELATIVE_PATH
    transport_kind: str = TRANSPORT_KIND
    transport_identity: str = TRANSPORT_IDENTITY
    authorized: bool = False

    def __post_init__(self) -> None:
        if _GIT_COMMIT.fullmatch(self.implementation_commit) is None:
            raise LambdaCloudContractError("Gate L1 V2 implementation commit is not canonical")
        if self.implementation_commit == BASELINE_COMMIT:
            raise LambdaCloudContractError("Gate L1 V2 implementation commit was not advanced")
        if tuple(item.path for item in self.implementation_artifacts) != (
            IMPLEMENTATION_ARTIFACT_PATHS
        ):
            raise LambdaCloudContractError("Gate L1 V2 implementation manifest drifted")
        if _SHA256.fullmatch(self.ledger_schema_sha256) is None:
            raise LambdaCloudContractError("request-ledger schema hash is not canonical")
        if _SHA256.fullmatch(self.inventory_schema_sha256) is None:
            raise LambdaCloudContractError("inventory V2 schema hash is not canonical")
        if self.requests != EXPECTED_INVENTORY_REQUESTS:
            raise LambdaCloudContractError("Gate L1 V2 endpoint set or order drifted")
        exact = {
            "plan_id": INVENTORY_PLAN_V2_ID,
            "run_id": INVENTORY_RUN_V2_ID,
            "attempt": INVENTORY_ATTEMPT_V2,
            "provider": "lambda-on-demand-cloud",
            "api_base_url": API_BASE_URL,
            "api_spec_version": API_SPEC_VERSION,
            "api_spec_sha256": API_SPEC_SHA256,
            "secret_variable": "LAMBDA_API_KEY",
            "max_calls": MAX_INVENTORY_CALLS,
            "max_total_response_bytes": MAX_INVENTORY_TOTAL_RESPONSE_BYTES,
            "max_retained_output_bytes": MAX_INVENTORY_RETAINED_BYTES,
            "max_wall_seconds": MAX_INVENTORY_WALL_SECONDS,
            "request_start_spacing_seconds": MIN_INVENTORY_REQUEST_SPACING_SECONDS,
            "max_archive_wall_seconds": MAX_INVENTORY_ARCHIVE_WALL_SECONDS,
            "max_total_wall_seconds": MAX_INVENTORY_TOTAL_WALL_SECONDS,
            "max_local_record_bytes": MAX_INVENTORY_LOCAL_RECORD_BYTES,
            "max_archive_bytes": MAX_INVENTORY_ARCHIVE_BYTES_V2,
            "max_aggregate_retained_bytes": MAX_INVENTORY_AGGREGATE_RETAINED_BYTES_V2,
            "local_prewrite_floor_bytes": MAX_INVENTORY_LOCAL_PREWRITE_FLOOR_BYTES,
            "local_retained_floor_bytes": MAX_INVENTORY_LOCAL_RETAINED_FLOOR_BYTES,
            "max_local_command_calls": MAX_INVENTORY_LOCAL_COMMAND_CALLS,
            "max_local_command_output_bytes": MAX_INVENTORY_LOCAL_COMMAND_OUTPUT_BYTES,
            "max_local_file_creates": MAX_INVENTORY_LOCAL_FILE_CREATES_V2,
            "max_external_file_creates": MAX_INVENTORY_EXTERNAL_FILE_CREATES_V2,
            "max_external_directory_creates": MAX_INVENTORY_EXTERNAL_DIRECTORY_CREATES_V2,
            "automatic_retries": 0,
            "run_root_relative_path": RUN_ROOT_RELATIVE_PATH,
            "ledger_relative_path": LEDGER_RELATIVE_PATH,
            "preflight_disposition_root_relative_path": PREFLIGHT_DISPOSITION_ROOT_RELATIVE_PATH,
            "output_relative_path": INVENTORY_RELATIVE_PATH,
            "copy_record_relative_path": COPY_RECORD_RELATIVE_PATH,
            "archive_root": ARCHIVE_ROOT,
            "inventory_schema_relative_path": INVENTORY_SCHEMA_V2_RELATIVE_PATH,
            "ledger_schema_relative_path": LEDGER_SCHEMA_RELATIVE_PATH,
            "transport_kind": TRANSPORT_KIND,
            "transport_identity": TRANSPORT_IDENTITY,
            "authorized": False,
        }
        for name, expected in exact.items():
            if getattr(self, name) != expected:
                raise LambdaCloudContractError(f"Gate L1 V2 {name} drifted")


def _pairs(values: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in values:
        if key in result:
            raise LambdaCloudContractError("Gate L1 V2 plan contains a duplicate key")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> object:
    del value
    raise ValueError


def _object(value: object, *, context: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise LambdaCloudContractError(f"{context} must be an object")
    return value


def _array(value: object, *, context: str) -> list[object]:
    if not isinstance(value, list):
        raise LambdaCloudContractError(f"{context} must be an array")
    return value


def _exact_keys(value: dict[str, object], expected: set[str], *, context: str) -> None:
    if set(value) != expected:
        raise LambdaCloudContractError(f"{context} exact field set drifted")


def _string(value: object, *, context: str) -> str:
    if not isinstance(value, str) or not value:
        raise LambdaCloudContractError(f"{context} must be a nonempty string")
    return value


def _integer(value: object, *, context: str) -> int:
    if type(value) is not int or value < 0:
        raise LambdaCloudContractError(f"{context} must be a nonnegative integer")
    return value


def _request_records(value: object) -> tuple[InventoryRequest, ...]:
    requests: list[InventoryRequest] = []
    for index, raw in enumerate(_array(value, context="Gate L1 V2 requests")):
        record = _object(raw, context=f"Gate L1 V2 requests[{index}]")
        _exact_keys(
            record,
            {"request_id", "method", "path", "max_response_bytes"},
            context=f"Gate L1 V2 requests[{index}]",
        )
        try:
            method = HttpMethod(_string(record["method"], context="request method"))
        except ValueError:
            raise LambdaCloudContractError("Gate L1 V2 permits GET only") from None
        requests.append(
            InventoryRequest(
                request_id=_string(record["request_id"], context="request ID"),
                method=method,
                path=_string(record["path"], context="request path"),
                max_response_bytes=_integer(
                    record["max_response_bytes"], context="request response cap"
                ),
            )
        )
    return tuple(requests)


def _implementation_records(value: object) -> tuple[ImplementationArtifactBinding, ...]:
    bindings: list[ImplementationArtifactBinding] = []
    for index, raw in enumerate(_array(value, context="implementation artifacts")):
        record = _object(raw, context=f"implementation artifacts[{index}]")
        _exact_keys(
            record,
            {"path", "sha256"},
            context=f"implementation artifacts[{index}]",
        )
        bindings.append(
            ImplementationArtifactBinding(
                path=_string(record["path"], context="implementation artifact path"),
                sha256=_string(record["sha256"], context="implementation artifact hash"),
            )
        )
    return tuple(bindings)


def load_inventory_plan_v2(path: Path, *, expected_sha256: str) -> ReadOnlyInventoryPlanV2:
    """Load the unique, committed, unauthorized Gate L1 V2 plan."""

    if _SHA256.fullmatch(expected_sha256) is None:
        raise LambdaCloudContractError("expected Gate L1 V2 plan hash is not canonical")
    encoded = path.read_bytes()
    if hashlib.sha256(encoded).hexdigest() != expected_sha256:
        raise LambdaCloudContractError("Gate L1 V2 plan SHA-256 mismatch")
    try:
        raw = json.loads(
            encoded,
            object_pairs_hook=_pairs,
            parse_constant=_reject_json_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        raise LambdaCloudContractError("Gate L1 V2 plan is not strict UTF-8 JSON") from None
    document = _object(raw, context="Gate L1 V2 plan")
    _exact_keys(
        document,
        {
            "schema_version",
            "plan_id",
            "decision_state",
            "provider",
            "api_base_url",
            "api_spec",
            "actor",
            "implementation_binding",
            "run_identity",
            "secret_contract",
            "requests",
            "ledger_contract",
            "limits",
            "output",
            "authorization",
        },
        context="Gate L1 V2 plan",
    )
    if document["schema_version"] != "0.2.0":
        raise LambdaCloudContractError("Gate L1 V2 plan schema version drifted")
    if document["plan_id"] != INVENTORY_PLAN_V2_ID:
        raise LambdaCloudContractError("Gate L1 V2 plan ID drifted")
    if document["decision_state"] != "unauthorized":
        raise LambdaCloudContractError("Gate L1 V2 plan must remain unauthorized")
    if document["provider"] != "lambda-on-demand-cloud" or document["api_base_url"] != API_BASE_URL:
        raise LambdaCloudContractError("Gate L1 V2 provider binding drifted")
    if document["actor"] != "future-codex-operator-gpt-5.6-sol-max":
        raise LambdaCloudContractError("Gate L1 V2 actor binding drifted")

    api_spec = _object(document["api_spec"], context="Gate L1 V2 api_spec")
    _exact_keys(api_spec, {"version", "sha256"}, context="Gate L1 V2 api_spec")
    if api_spec != {"version": API_SPEC_VERSION, "sha256": API_SPEC_SHA256}:
        raise LambdaCloudContractError("Gate L1 V2 API specification lock drifted")

    implementation = _object(
        document["implementation_binding"], context="Gate L1 V2 implementation_binding"
    )
    _exact_keys(
        implementation,
        {
            "baseline_commit",
            "implementation_commit",
            "implementation_artifacts",
            "transport_identity",
        },
        context="Gate L1 V2 implementation_binding",
    )
    if implementation["baseline_commit"] != BASELINE_COMMIT:
        raise LambdaCloudContractError("Gate L1 V2 baseline commit drifted")
    implementation_commit = _string(
        implementation["implementation_commit"], context="implementation commit"
    )
    if _GIT_COMMIT.fullmatch(implementation_commit) is None:
        raise LambdaCloudContractError("Gate L1 V2 implementation commit is not canonical")
    if implementation["transport_identity"] != TRANSPORT_IDENTITY:
        raise LambdaCloudContractError("Gate L1 V2 transport identity drifted")
    implementation_artifacts = _implementation_records(implementation["implementation_artifacts"])

    run = _object(document["run_identity"], context="Gate L1 V2 run_identity")
    _exact_keys(
        run,
        {"run_id", "attempt", "experiment_id", "profile_plan_id", "gate", "branch"},
        context="Gate L1 V2 run_identity",
    )
    if run != {
        "run_id": INVENTORY_RUN_V2_ID,
        "attempt": INVENTORY_ATTEMPT_V2,
        "experiment_id": "EXP-0001",
        "profile_plan_id": "PLAN-EXP0001-SMOKE",
        "gate": "T07-L1",
        "branch": LAMBDA_BRANCH,
    }:
        raise LambdaCloudContractError("Gate L1 V2 run identity drifted")

    secret_contract = _object(document["secret_contract"], context="Gate L1 V2 secret_contract")
    _exact_keys(
        secret_contract,
        {
            "variable",
            "channel",
            "print_allowed",
            "hash_allowed",
            "persist_allowed",
            "return_allowed",
            "forbidden_fallbacks",
        },
        context="Gate L1 V2 secret_contract",
    )
    if secret_contract != {
        "variable": "LAMBDA_API_KEY",
        "channel": "supervisor-secret-channel",
        "print_allowed": False,
        "hash_allowed": False,
        "persist_allowed": False,
        "return_allowed": False,
        "forbidden_fallbacks": ["SIRA_API_KEY", "OPENAI_API_KEY"],
    }:
        raise LambdaCloudContractError("Gate L1 V2 secret contract drifted")

    requests = _request_records(document["requests"])
    if requests != EXPECTED_INVENTORY_REQUESTS:
        raise LambdaCloudContractError("Gate L1 V2 endpoint allowlist or order drifted")

    ledger = _object(document["ledger_contract"], context="Gate L1 V2 ledger_contract")
    _exact_keys(
        ledger,
        {
            "schema_path",
            "schema_sha256",
            "relative_path",
            "preflight_disposition_root_relative_path",
            "transport_kind",
            "event_types",
            "failure_stages",
            "failure_classes",
            "capacity_reservation",
            "archive_eligible_after_event",
            "limits",
        },
        context="Gate L1 V2 ledger_contract",
    )
    if ledger["schema_path"] != LEDGER_SCHEMA_RELATIVE_PATH:
        raise LambdaCloudContractError("Gate L1 V2 ledger schema path drifted")
    ledger_schema_sha256 = _string(ledger["schema_sha256"], context="ledger schema hash")
    if _SHA256.fullmatch(ledger_schema_sha256) is None:
        raise LambdaCloudContractError("Gate L1 V2 ledger schema hash is not canonical")
    if ledger["relative_path"] != LEDGER_RELATIVE_PATH:
        raise LambdaCloudContractError("Gate L1 V2 ledger path drifted")
    if ledger["preflight_disposition_root_relative_path"] != (
        PREFLIGHT_DISPOSITION_ROOT_RELATIVE_PATH
    ):
        raise LambdaCloudContractError("Gate L1 V2 preflight-disposition path drifted")
    if ledger["transport_kind"] != TRANSPORT_KIND:
        raise LambdaCloudContractError("Gate L1 V2 transport kind drifted")
    if ledger["event_types"] != list(LEDGER_EVENT_TYPES):
        raise LambdaCloudContractError("Gate L1 V2 ledger event set/order drifted")
    if ledger["failure_stages"] != list(FAILURE_STAGES):
        raise LambdaCloudContractError("Gate L1 V2 failure-stage taxonomy drifted")
    if ledger["failure_classes"] != list(FAILURE_CLASSES):
        raise LambdaCloudContractError("Gate L1 V2 failure-class taxonomy drifted")
    if ledger["capacity_reservation"] != "logical-cap-and-filesystem-free-space":
        raise LambdaCloudContractError("Gate L1 V2 ledger reservation contract drifted")
    if ledger["archive_eligible_after_event"] != "inventory_validation_passed":
        raise LambdaCloudContractError("Gate L1 V2 archive eligibility drifted")
    ledger_limits = _object(ledger["limits"], context="Gate L1 V2 ledger limits")
    expected_ledger_limits = {
        "max_bytes": MAX_LEDGER_BYTES,
        "max_events": MAX_LEDGER_EVENTS,
        "max_events_per_request": MAX_LEDGER_EVENTS_PER_REQUEST,
        "max_event_bytes": MAX_LEDGER_EVENT_BYTES,
        "max_preflight_disposition_bytes": MAX_PREFLIGHT_DISPOSITION_BYTES,
    }
    if ledger_limits != expected_ledger_limits:
        raise LambdaCloudContractError("Gate L1 V2 ledger limits drifted")

    limits = _object(document["limits"], context="Gate L1 V2 limits")
    expected_limits = {
        "max_calls": MAX_INVENTORY_CALLS,
        "max_total_response_bytes": MAX_INVENTORY_TOTAL_RESPONSE_BYTES,
        "max_retained_output_bytes": MAX_INVENTORY_RETAINED_BYTES,
        "max_wall_seconds": MAX_INVENTORY_WALL_SECONDS,
        "request_start_spacing_seconds": MIN_INVENTORY_REQUEST_SPACING_SECONDS,
        "max_archive_wall_seconds": MAX_INVENTORY_ARCHIVE_WALL_SECONDS,
        "max_total_wall_seconds": MAX_INVENTORY_TOTAL_WALL_SECONDS,
        "max_local_record_bytes": MAX_INVENTORY_LOCAL_RECORD_BYTES,
        "max_archive_bytes": MAX_INVENTORY_ARCHIVE_BYTES_V2,
        "max_aggregate_retained_bytes": MAX_INVENTORY_AGGREGATE_RETAINED_BYTES_V2,
        "local_prewrite_floor_bytes": MAX_INVENTORY_LOCAL_PREWRITE_FLOOR_BYTES,
        "local_retained_floor_bytes": MAX_INVENTORY_LOCAL_RETAINED_FLOOR_BYTES,
        "max_local_command_calls": MAX_INVENTORY_LOCAL_COMMAND_CALLS,
        "max_local_command_output_bytes": MAX_INVENTORY_LOCAL_COMMAND_OUTPUT_BYTES,
        "max_local_file_creates": MAX_INVENTORY_LOCAL_FILE_CREATES_V2,
        "max_external_file_creates": MAX_INVENTORY_EXTERNAL_FILE_CREATES_V2,
        "max_external_directory_creates": MAX_INVENTORY_EXTERNAL_DIRECTORY_CREATES_V2,
        "automatic_retries": 0,
        "mutation_calls": 0,
        "provider_cost_usd": 0,
        "model_api_calls": 0,
        "model_tokens": 0,
        "browser_actions": 0,
        "ssh_operations": 0,
        "sira_executions": 0,
    }
    if limits != expected_limits:
        raise LambdaCloudContractError("Gate L1 V2 limits drifted")

    output = _object(document["output"], context="Gate L1 V2 output")
    expected_output = {
        "run_root_relative_path": RUN_ROOT_RELATIVE_PATH,
        "relative_path": INVENTORY_RELATIVE_PATH,
        "copy_record_relative_path": COPY_RECORD_RELATIVE_PATH,
        "inventory_schema_path": INVENTORY_SCHEMA_V2_RELATIVE_PATH,
        "inventory_schema_sha256": output.get("inventory_schema_sha256"),
        "archive_root": ARCHIVE_ROOT,
        "archive_run_directory": INVENTORY_RUN_V2_ID,
        "raw_response_persistence": False,
        "redaction_required": True,
        "ledger_required_for_archive": True,
        "sha256_required": True,
        "source_retention_required": True,
    }
    _exact_keys(output, set(expected_output), context="Gate L1 V2 output")
    inventory_schema_sha256 = _string(
        output["inventory_schema_sha256"], context="inventory V2 schema hash"
    )
    if _SHA256.fullmatch(inventory_schema_sha256) is None:
        raise LambdaCloudContractError("inventory V2 schema hash is not canonical")
    expected_output["inventory_schema_sha256"] = inventory_schema_sha256
    if output != expected_output:
        raise LambdaCloudContractError("Gate L1 V2 output contract drifted")

    authorization = _object(document["authorization"], context="Gate L1 V2 authorization")
    if authorization != {
        "authorized": False,
        "authorization_reference": PENDING_AUTHORIZATION_REFERENCE,
    }:
        raise LambdaCloudContractError("Gate L1 V2 committed plan cannot carry authority")

    return ReadOnlyInventoryPlanV2(
        implementation_commit=implementation_commit,
        implementation_artifacts=implementation_artifacts,
        ledger_schema_sha256=ledger_schema_sha256,
        inventory_schema_sha256=inventory_schema_sha256,
        requests=requests,
    )


def verify_inventory_implementation_v2(
    repository_root: Path,
    plan: ReadOnlyInventoryPlanV2,
) -> None:
    """Hash-check every runtime artifact and the V2 inventory schema in process."""

    root = repository_root.resolve(strict=True)
    if root != repository_root.absolute():
        raise LambdaCloudContractError("Gate L1 V2 repository root contains a symlink")
    for binding in plan.implementation_artifacts:
        target = root / binding.path
        try:
            observed = target.stat(follow_symlinks=False)
            if (
                not stat.S_ISREG(observed.st_mode)
                or observed.st_nlink != 1
                or observed.st_size > MAX_IMPLEMENTATION_ARTIFACT_BYTES
                or target.is_symlink()
            ):
                raise OSError
            encoded = target.read_bytes()
        except OSError:
            raise LambdaCloudContractError(
                "Gate L1 V2 implementation artifact is missing or unsafe"
            ) from None
        if hashlib.sha256(encoded).hexdigest() != binding.sha256:
            raise LambdaCloudContractError("Gate L1 V2 implementation artifact hash drifted")
    schema_path = root / plan.inventory_schema_relative_path
    try:
        schema_encoded = schema_path.read_bytes()
        if hashlib.sha256(schema_encoded).hexdigest() != plan.inventory_schema_sha256:
            raise ValueError
        schema = json.loads(
            schema_encoded,
            object_pairs_hook=_pairs,
            parse_constant=_reject_json_constant,
        )
        Draft202012Validator.check_schema(schema)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
        raise LambdaCloudContractError("Gate L1 V2 inventory schema binding failed") from None


def inventory_limits_document_v2(plan: ReadOnlyInventoryPlanV2) -> dict[str, int]:
    """Return the exact V2 artifact limits without introducing a second policy plane."""

    return {
        "provider_api_calls": plan.max_calls,
        "provider_wall_seconds": plan.max_wall_seconds,
        "request_start_spacing_seconds": plan.request_start_spacing_seconds,
        "archive_wall_seconds": plan.max_archive_wall_seconds,
        "total_wall_seconds": plan.max_total_wall_seconds,
        "raw_response_bytes": plan.max_total_response_bytes,
        "retained_output_bytes": plan.max_retained_output_bytes,
        "request_ledger_bytes": plan.limits.max_bytes,
        "request_ledger_events": plan.limits.max_events,
        "request_ledger_events_per_request": plan.limits.max_events_per_request,
        "request_ledger_event_bytes": plan.limits.max_event_bytes,
        "preflight_disposition_bytes": plan.limits.max_preflight_disposition_bytes,
        "local_copy_record_bytes": plan.max_local_record_bytes,
        "external_archive_bytes": plan.max_archive_bytes,
        "aggregate_retained_bytes": plan.max_aggregate_retained_bytes,
        "local_command_calls": plan.max_local_command_calls,
        "local_command_output_bytes": plan.max_local_command_output_bytes,
        "local_file_creates": plan.max_local_file_creates,
        "external_file_creates": plan.max_external_file_creates,
        "external_directory_creates": plan.max_external_directory_creates,
        "local_prewrite_floor_bytes": plan.local_prewrite_floor_bytes,
        "local_retained_floor_bytes": plan.local_retained_floor_bytes,
        "automatic_retries": 0,
        "cloud_mutations": 0,
        "provider_cost_cents": 0,
        "model_calls": 0,
        "model_tokens": 0,
        "browser_actions": 0,
        "ssh_operations": 0,
        "sira_executions": 0,
    }


def inventory_ledger_contract_document_v2(
    plan: ReadOnlyInventoryPlanV2,
) -> dict[str, object]:
    """Bind Gate L2 eligibility to the durable V2 ledger and its terminal state."""

    return {
        "schema_path": plan.ledger_schema_relative_path,
        "schema_sha256": plan.ledger_schema_sha256,
        "relative_path": plan.ledger_relative_path,
        "archive_eligible_prefix_event": "inventory_validation_passed",
        "required_terminal_events": ["archive_passed", "run_stopped"],
        "complete_success_required": True,
        "unknown_after_send_allowed_for_gate_l2": False,
    }
