"""Strict, hash-bound T07 Gate L1 V3 inventory-plan contract.

V1/V2 plans and their burned run identities remain immutable.  This module owns the
fresh seven-request V3/0003 identity, endpoint-schema bindings, recalculated finite
caps, and implementation manifest.  Loading performs local file I/O only.
"""

from __future__ import annotations

import hashlib
import json
import re
import stat
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Never

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

from .lambda_cloud import (
    API_BASE_URL,
    API_SPEC_SHA256,
    API_SPEC_VERSION,
    LAMBDA_BRANCH,
    MAX_INVENTORY_ARCHIVE_WALL_SECONDS,
    MAX_INVENTORY_LOCAL_RECORD_BYTES,
    MAX_INVENTORY_LOCAL_RETAINED_FLOOR_BYTES,
    MAX_INVENTORY_TOTAL_WALL_SECONDS,
    MAX_INVENTORY_WALL_SECONDS,
    MIN_INVENTORY_REQUEST_SPACING_SECONDS,
    HttpMethod,
    InventoryRequest,
    LambdaCloudContractError,
    secret_free_child_environment,
)
from .lambda_cloud_v3 import (
    ENDPOINT_SCHEMA_PATHS,
    EXPECTED_INVENTORY_REQUESTS_V3,
    INVENTORY_ATTEMPT_V3,
    INVENTORY_PLAN_V3_ID,
    INVENTORY_RUN_V3_ID,
    MAX_INVENTORY_CALLS_V3,
    MAX_INVENTORY_RETAINED_BYTES_V3,
    MAX_INVENTORY_TOTAL_RESPONSE_BYTES_V3,
    MAX_SCHEMA_EXTENSION_REPORT_BYTES,
    PENDING_AUTHORIZATION_REFERENCE_V4,
    EndpointSchemaBinding,
)

BASELINE_COMMIT_V3: Final = "258ccc3c524e96e0fadc3afc23a43fa40f6a7d7a"
API_SPEC_URL: Final = "https://docs.lambda.ai/api/cloud/spec.json"
API_SPEC_BYTES: Final = 239_644
API_SPEC_RETRIEVED_AT_UTC: Final = "2026-08-09T20:36:01Z"
API_SPEC_REVALIDATED_AT_UTC: Final = "2026-08-10T11:35:38Z"
TRANSPORT_KIND_V3: Final = "in-process-https"
TRANSPORT_IDENTITY_V3: Final = "giclab.harness.lambda_inventory_v3.LambdaHttpsInventoryTransportV3"

LEDGER_SCHEMA_RELATIVE_PATH: Final = "schemas/t07-lambda-request-ledger-v3.schema.json"
INVENTORY_SCHEMA_V3_RELATIVE_PATH: Final = "schemas/t07-lambda-inventory-v3.schema.json"
EXTENSION_SCHEMA_RELATIVE_PATH: Final = "schemas/t07-lambda-schema-extension-report.schema.json"
AUDIT_STRUCTURAL_SCHEMA_RELATIVE_PATH: Final = (
    "schemas/t07-lambda-audit-structural-report.schema.json"
)
SCHEMA_FILES_V3: Final = (
    AUDIT_STRUCTURAL_SCHEMA_RELATIVE_PATH,
    EXTENSION_SCHEMA_RELATIVE_PATH,
    INVENTORY_SCHEMA_V3_RELATIVE_PATH,
    LEDGER_SCHEMA_RELATIVE_PATH,
    *tuple(ENDPOINT_SCHEMA_PATHS.values()),
)
RUN_ROOT_RELATIVE_PATH_V3: Final = "artifacts/t07/lambda/gate-l1/RUN-T07-L1-LAMBDA-INVENTORY-0003"
LEDGER_RELATIVE_PATH_V3: Final = f"{RUN_ROOT_RELATIVE_PATH_V3}/request-ledger.jsonl"
INVENTORY_RELATIVE_PATH_V3: Final = f"{RUN_ROOT_RELATIVE_PATH_V3}/inventory-redacted.json"
COPY_RECORD_RELATIVE_PATH_V3: Final = f"{RUN_ROOT_RELATIVE_PATH_V3}/inventory-copy-record.json"
PREFLIGHT_DISPOSITION_ROOT_RELATIVE_PATH: Final = (
    "artifacts/t07/lambda/gate-l1/preflight-dispositions"
)
ARCHIVE_ROOT: Final = "/Volumes/Macintosh HD - Data/GIC-Lab/t07/sealed-artifacts"

MAX_LEDGER_BYTES_V3: Final = 172_032
MAX_LEDGER_EVENTS_V3: Final = 84
MAX_LEDGER_EVENTS_PER_REQUEST_V3: Final = 9
MAX_LEDGER_EVENT_BYTES_V3: Final = 2_048
MAX_PREFLIGHT_DISPOSITION_BYTES: Final = 16_384
MAX_INVENTORY_ARCHIVE_BYTES_V3: Final = 1_048_576
MAX_INVENTORY_AGGREGATE_RETAINED_BYTES_V3: Final = 1_826_816
MAX_INVENTORY_LOCAL_PREWRITE_FLOOR_BYTES_V3: Final = 8_590_868_480
MAX_INVENTORY_LOCAL_FILE_CREATES_V3: Final = 4
MAX_INVENTORY_EXTERNAL_FILE_CREATES_V3: Final = 4
MAX_INVENTORY_EXTERNAL_DIRECTORY_CREATES_V3: Final = 4
MAX_INVENTORY_LOCAL_COMMAND_CALLS_V3: Final = 15
MAX_INVENTORY_LOCAL_COMMAND_OUTPUT_BYTES_V3: Final = 37_879_810
MAX_IMPLEMENTATION_ARTIFACT_BYTES: Final = 5 * 1024 * 1024

IMPLEMENTATION_ARTIFACT_PATHS_V3: Final = (
    "pyproject.toml",
    "uv.lock",
    "src/giclab/harness/lambda_cloud.py",
    "src/giclab/harness/lambda_cloud_v3.py",
    "src/giclab/harness/lambda_archive.py",
    "src/giclab/harness/lambda_archive_v3.py",
    "src/giclab/harness/lambda_inventory.py",
    "src/giclab/harness/lambda_inventory_plan_v3.py",
    "src/giclab/harness/lambda_inventory_v3.py",
    "src/giclab/harness/lambda_request_ledger_v3.py",
    "src/giclab/harness/sira_storage.py",
    AUDIT_STRUCTURAL_SCHEMA_RELATIVE_PATH,
    INVENTORY_SCHEMA_V3_RELATIVE_PATH,
    LEDGER_SCHEMA_RELATIVE_PATH,
    EXTENSION_SCHEMA_RELATIVE_PATH,
    *tuple(ENDPOINT_SCHEMA_PATHS.values()),
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
class LedgerLimitsV3:
    max_bytes: int = MAX_LEDGER_BYTES_V3
    max_events: int = MAX_LEDGER_EVENTS_V3
    max_events_per_request: int = MAX_LEDGER_EVENTS_PER_REQUEST_V3
    max_event_bytes: int = MAX_LEDGER_EVENT_BYTES_V3
    max_preflight_disposition_bytes: int = MAX_PREFLIGHT_DISPOSITION_BYTES

    def __post_init__(self) -> None:
        if (
            self.max_bytes,
            self.max_events,
            self.max_events_per_request,
            self.max_event_bytes,
            self.max_preflight_disposition_bytes,
        ) != (
            MAX_LEDGER_BYTES_V3,
            MAX_LEDGER_EVENTS_V3,
            MAX_LEDGER_EVENTS_PER_REQUEST_V3,
            MAX_LEDGER_EVENT_BYTES_V3,
            MAX_PREFLIGHT_DISPOSITION_BYTES,
        ):
            raise LambdaCloudContractError("Gate L1 V3 request-ledger limits drifted")
        if self.max_events * self.max_event_bytes > self.max_bytes:
            raise LambdaCloudContractError("Gate L1 V3 ledger cannot reserve every event")
        if self.max_events_per_request * MAX_INVENTORY_CALLS_V3 >= self.max_events:
            raise LambdaCloudContractError("Gate L1 V3 ledger has no global-event capacity")


@dataclass(frozen=True, slots=True)
class InventoryRunBindingV3:
    run_id: str
    repository_commit: str
    implementation_commit: str
    authorization_reference: str
    authorization_sha256: str
    plan_id: str = INVENTORY_PLAN_V3_ID
    attempt: int = INVENTORY_ATTEMPT_V3

    def __post_init__(self) -> None:
        if (
            self.plan_id != INVENTORY_PLAN_V3_ID
            or self.run_id != INVENTORY_RUN_V3_ID
            or self.attempt != INVENTORY_ATTEMPT_V3
        ):
            raise LambdaCloudContractError("Gate L1 V3 plan/run identity drifted")
        if any(
            _GIT_COMMIT.fullmatch(value) is None
            for value in (self.repository_commit, self.implementation_commit)
        ):
            raise LambdaCloudContractError("Gate L1 V3 repository binding is not canonical")
        if (
            _IDENTIFIER.fullmatch(self.authorization_reference) is None
            or self.authorization_reference == PENDING_AUTHORIZATION_REFERENCE_V4
        ):
            raise LambdaCloudContractError("Gate L1 V3 authorization reference is not fresh")
        if _SHA256.fullmatch(self.authorization_sha256) is None:
            raise LambdaCloudContractError("Gate L1 V3 authorization hash is not canonical")


@dataclass(frozen=True, slots=True)
class ImplementationArtifactBindingV3:
    path: str
    sha256: str

    def __post_init__(self) -> None:
        candidate = Path(self.path)
        if (
            self.path not in IMPLEMENTATION_ARTIFACT_PATHS_V3
            or candidate.is_absolute()
            or ".." in candidate.parts
            or _SHA256.fullmatch(self.sha256) is None
        ):
            raise LambdaCloudContractError("Gate L1 V3 implementation artifact drifted")


@dataclass(frozen=True, slots=True)
class ReadOnlyInventoryPlanV3:
    implementation_commit: str
    implementation_artifacts: tuple[ImplementationArtifactBindingV3, ...]
    ledger_schema_sha256: str
    inventory_schema_sha256: str
    extension_schema_sha256: str
    endpoint_schema_bindings: Mapping[str, EndpointSchemaBinding]
    requests: tuple[InventoryRequest, ...] = EXPECTED_INVENTORY_REQUESTS_V3
    limits: LedgerLimitsV3 = LedgerLimitsV3()
    plan_id: str = INVENTORY_PLAN_V3_ID
    run_id: str = INVENTORY_RUN_V3_ID
    attempt: int = INVENTORY_ATTEMPT_V3
    provider: str = "lambda-on-demand-cloud"
    api_base_url: str = API_BASE_URL
    api_spec_version: str = API_SPEC_VERSION
    api_spec_sha256: str = API_SPEC_SHA256
    secret_variable: str = "LAMBDA_API_KEY"
    max_calls: int = MAX_INVENTORY_CALLS_V3
    max_total_response_bytes: int = MAX_INVENTORY_TOTAL_RESPONSE_BYTES_V3
    max_retained_output_bytes: int = MAX_INVENTORY_RETAINED_BYTES_V3
    max_schema_extension_report_bytes: int = MAX_SCHEMA_EXTENSION_REPORT_BYTES
    max_wall_seconds: int = MAX_INVENTORY_WALL_SECONDS
    request_start_spacing_seconds: int = MIN_INVENTORY_REQUEST_SPACING_SECONDS
    max_archive_wall_seconds: int = MAX_INVENTORY_ARCHIVE_WALL_SECONDS
    max_total_wall_seconds: int = MAX_INVENTORY_TOTAL_WALL_SECONDS
    max_local_record_bytes: int = MAX_INVENTORY_LOCAL_RECORD_BYTES
    max_archive_bytes: int = MAX_INVENTORY_ARCHIVE_BYTES_V3
    max_aggregate_retained_bytes: int = MAX_INVENTORY_AGGREGATE_RETAINED_BYTES_V3
    local_prewrite_floor_bytes: int = MAX_INVENTORY_LOCAL_PREWRITE_FLOOR_BYTES_V3
    local_retained_floor_bytes: int = MAX_INVENTORY_LOCAL_RETAINED_FLOOR_BYTES
    max_local_command_calls: int = MAX_INVENTORY_LOCAL_COMMAND_CALLS_V3
    max_local_command_output_bytes: int = MAX_INVENTORY_LOCAL_COMMAND_OUTPUT_BYTES_V3
    max_local_file_creates: int = MAX_INVENTORY_LOCAL_FILE_CREATES_V3
    max_external_file_creates: int = MAX_INVENTORY_EXTERNAL_FILE_CREATES_V3
    max_external_directory_creates: int = MAX_INVENTORY_EXTERNAL_DIRECTORY_CREATES_V3
    automatic_retries: int = 0
    run_root_relative_path: str = RUN_ROOT_RELATIVE_PATH_V3
    ledger_relative_path: str = LEDGER_RELATIVE_PATH_V3
    preflight_disposition_root_relative_path: str = PREFLIGHT_DISPOSITION_ROOT_RELATIVE_PATH
    output_relative_path: str = INVENTORY_RELATIVE_PATH_V3
    copy_record_relative_path: str = COPY_RECORD_RELATIVE_PATH_V3
    archive_root: str = ARCHIVE_ROOT
    inventory_schema_relative_path: str = INVENTORY_SCHEMA_V3_RELATIVE_PATH
    ledger_schema_relative_path: str = LEDGER_SCHEMA_RELATIVE_PATH
    extension_schema_relative_path: str = EXTENSION_SCHEMA_RELATIVE_PATH
    transport_kind: str = TRANSPORT_KIND_V3
    transport_identity: str = TRANSPORT_IDENTITY_V3
    authorized: bool = False

    def __post_init__(self) -> None:
        expected_artifact_paths = tuple(item.path for item in self.implementation_artifacts)
        if expected_artifact_paths != IMPLEMENTATION_ARTIFACT_PATHS_V3:
            raise LambdaCloudContractError("Gate L1 V3 implementation manifest order drifted")
        artifact_hashes = {
            binding.path: binding.sha256 for binding in self.implementation_artifacts
        }
        if _GIT_COMMIT.fullmatch(self.implementation_commit) is None:
            raise LambdaCloudContractError("Gate L1 V3 implementation commit is not canonical")
        if any(
            _SHA256.fullmatch(value) is None
            for value in (
                self.ledger_schema_sha256,
                self.inventory_schema_sha256,
                self.extension_schema_sha256,
            )
        ):
            raise LambdaCloudContractError("Gate L1 V3 schema hash is not canonical")
        if tuple(self.endpoint_schema_bindings) != tuple(ENDPOINT_SCHEMA_PATHS):
            raise LambdaCloudContractError("Gate L1 V3 endpoint schema order drifted")
        if any(
            self.endpoint_schema_bindings[key].path != path
            for key, path in ENDPOINT_SCHEMA_PATHS.items()
        ):
            raise LambdaCloudContractError("Gate L1 V3 endpoint schema binding drifted")
        schema_bindings = {
            AUDIT_STRUCTURAL_SCHEMA_RELATIVE_PATH: artifact_hashes[
                AUDIT_STRUCTURAL_SCHEMA_RELATIVE_PATH
            ],
            self.ledger_schema_relative_path: self.ledger_schema_sha256,
            self.inventory_schema_relative_path: self.inventory_schema_sha256,
            self.extension_schema_relative_path: self.extension_schema_sha256,
            **{binding.path: binding.sha256 for binding in self.endpoint_schema_bindings.values()},
        }
        if any(
            artifact_hashes.get(path) != expected_hash
            for path, expected_hash in schema_bindings.items()
        ):
            raise LambdaCloudContractError(
                "Gate L1 V3 schema binding is not cross-bound to the implementation manifest"
            )
        exact: dict[str, object] = {
            "plan_id": INVENTORY_PLAN_V3_ID,
            "run_id": INVENTORY_RUN_V3_ID,
            "attempt": INVENTORY_ATTEMPT_V3,
            "provider": "lambda-on-demand-cloud",
            "api_base_url": API_BASE_URL,
            "api_spec_version": API_SPEC_VERSION,
            "api_spec_sha256": API_SPEC_SHA256,
            "secret_variable": "LAMBDA_API_KEY",
            "requests": EXPECTED_INVENTORY_REQUESTS_V3,
            "max_calls": MAX_INVENTORY_CALLS_V3,
            "max_total_response_bytes": MAX_INVENTORY_TOTAL_RESPONSE_BYTES_V3,
            "max_retained_output_bytes": MAX_INVENTORY_RETAINED_BYTES_V3,
            "max_schema_extension_report_bytes": MAX_SCHEMA_EXTENSION_REPORT_BYTES,
            "max_wall_seconds": MAX_INVENTORY_WALL_SECONDS,
            "request_start_spacing_seconds": MIN_INVENTORY_REQUEST_SPACING_SECONDS,
            "max_archive_wall_seconds": MAX_INVENTORY_ARCHIVE_WALL_SECONDS,
            "max_total_wall_seconds": MAX_INVENTORY_TOTAL_WALL_SECONDS,
            "max_local_record_bytes": MAX_INVENTORY_LOCAL_RECORD_BYTES,
            "max_archive_bytes": MAX_INVENTORY_ARCHIVE_BYTES_V3,
            "max_aggregate_retained_bytes": MAX_INVENTORY_AGGREGATE_RETAINED_BYTES_V3,
            "local_prewrite_floor_bytes": MAX_INVENTORY_LOCAL_PREWRITE_FLOOR_BYTES_V3,
            "local_retained_floor_bytes": MAX_INVENTORY_LOCAL_RETAINED_FLOOR_BYTES,
            "max_local_command_calls": MAX_INVENTORY_LOCAL_COMMAND_CALLS_V3,
            "max_local_command_output_bytes": MAX_INVENTORY_LOCAL_COMMAND_OUTPUT_BYTES_V3,
            "max_local_file_creates": MAX_INVENTORY_LOCAL_FILE_CREATES_V3,
            "max_external_file_creates": MAX_INVENTORY_EXTERNAL_FILE_CREATES_V3,
            "max_external_directory_creates": MAX_INVENTORY_EXTERNAL_DIRECTORY_CREATES_V3,
            "automatic_retries": 0,
            "run_root_relative_path": RUN_ROOT_RELATIVE_PATH_V3,
            "ledger_relative_path": LEDGER_RELATIVE_PATH_V3,
            "preflight_disposition_root_relative_path": (PREFLIGHT_DISPOSITION_ROOT_RELATIVE_PATH),
            "output_relative_path": INVENTORY_RELATIVE_PATH_V3,
            "copy_record_relative_path": COPY_RECORD_RELATIVE_PATH_V3,
            "archive_root": ARCHIVE_ROOT,
            "inventory_schema_relative_path": INVENTORY_SCHEMA_V3_RELATIVE_PATH,
            "ledger_schema_relative_path": LEDGER_SCHEMA_RELATIVE_PATH,
            "extension_schema_relative_path": EXTENSION_SCHEMA_RELATIVE_PATH,
            "transport_kind": TRANSPORT_KIND_V3,
            "transport_identity": TRANSPORT_IDENTITY_V3,
            "authorized": False,
        }
        for name, expected in exact.items():
            if getattr(self, name) != expected:
                raise LambdaCloudContractError(f"Gate L1 V3 {name} drifted")


def _pairs(values: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in values:
        if key in result:
            raise ValueError
        result[key] = value
    return result


def _reject_constant(value: str) -> Never:
    del value
    raise ValueError


def _object(value: object, *, keys: set[str], context: str) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != keys:
        raise LambdaCloudContractError(f"{context} exact field set drifted")
    return value


def _string(value: object, *, context: str) -> str:
    if not isinstance(value, str) or not value:
        raise LambdaCloudContractError(f"{context} must be a nonempty string")
    return value


def _integer(value: object, *, context: str) -> int:
    if type(value) is not int or value < 0:
        raise LambdaCloudContractError(f"{context} must be a nonnegative integer")
    return value


def _artifact_bindings(value: object) -> tuple[ImplementationArtifactBindingV3, ...]:
    if not isinstance(value, list):
        raise LambdaCloudContractError("Gate L1 V3 implementation artifacts must be an array")
    bindings: list[ImplementationArtifactBindingV3] = []
    for raw in value:
        record = _object(raw, keys={"path", "sha256"}, context="implementation artifact")
        bindings.append(
            ImplementationArtifactBindingV3(
                _string(record["path"], context="implementation artifact path"),
                _string(record["sha256"], context="implementation artifact hash"),
            )
        )
    return tuple(bindings)


def load_inventory_plan_v3(path: Path, *, expected_sha256: str) -> ReadOnlyInventoryPlanV3:
    """Load an exact committed V3 plan without granting execution authority."""

    if _SHA256.fullmatch(expected_sha256) is None:
        raise LambdaCloudContractError("expected Gate L1 V3 plan hash is not canonical")
    try:
        encoded = path.read_bytes()
        if hashlib.sha256(encoded).hexdigest() != expected_sha256:
            raise ValueError
        raw = json.loads(
            encoded,
            object_pairs_hook=_pairs,
            parse_constant=_reject_constant,
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
        raise LambdaCloudContractError("Gate L1 V3 plan identity or JSON is invalid") from None
    document = _object(
        raw,
        keys={
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
            "schema_extension_contract",
            "ledger_contract",
            "limits",
            "output",
            "authorization",
        },
        context="Gate L1 V3 plan",
    )
    if (
        document["schema_version"] != "0.3.0"
        or document["plan_id"] != INVENTORY_PLAN_V3_ID
        or document["decision_state"] != "unauthorized"
        or document["provider"] != "lambda-on-demand-cloud"
        or document["api_base_url"] != API_BASE_URL
        or document["actor"] != "future-codex-operator-gpt-5.6-sol-max"
    ):
        raise LambdaCloudContractError("Gate L1 V3 plan header drifted")
    api_spec = _object(
        document["api_spec"],
        keys={
            "url",
            "version",
            "bytes",
            "sha256",
            "retrieved_at_utc",
            "revalidated_at_utc",
        },
        context="Gate L1 V3 api_spec",
    )
    if api_spec != {
        "url": API_SPEC_URL,
        "version": API_SPEC_VERSION,
        "bytes": API_SPEC_BYTES,
        "sha256": API_SPEC_SHA256,
        "retrieved_at_utc": API_SPEC_RETRIEVED_AT_UTC,
        "revalidated_at_utc": API_SPEC_REVALIDATED_AT_UTC,
    }:
        raise LambdaCloudContractError("Gate L1 V3 API specification binding drifted")
    implementation = _object(
        document["implementation_binding"],
        keys={
            "baseline_commit",
            "implementation_commit",
            "implementation_artifacts",
            "transport_identity",
        },
        context="Gate L1 V3 implementation binding",
    )
    if (
        implementation["baseline_commit"] != BASELINE_COMMIT_V3
        or implementation["transport_identity"] != TRANSPORT_IDENTITY_V3
    ):
        raise LambdaCloudContractError("Gate L1 V3 implementation identity drifted")
    implementation_commit = _string(
        implementation["implementation_commit"], context="implementation commit"
    )
    if _GIT_COMMIT.fullmatch(implementation_commit) is None:
        raise LambdaCloudContractError("Gate L1 V3 implementation commit is not canonical")
    artifacts = _artifact_bindings(implementation["implementation_artifacts"])
    run = _object(
        document["run_identity"],
        keys={"run_id", "attempt", "experiment_id", "profile_plan_id", "gate", "branch"},
        context="Gate L1 V3 run identity",
    )
    if run != {
        "run_id": INVENTORY_RUN_V3_ID,
        "attempt": INVENTORY_ATTEMPT_V3,
        "experiment_id": "EXP-0001",
        "profile_plan_id": "PLAN-EXP0001-SMOKE",
        "gate": "T07-L1",
        "branch": LAMBDA_BRANCH,
    }:
        raise LambdaCloudContractError("Gate L1 V3 run identity drifted")
    secret_contract = _object(
        document["secret_contract"],
        keys={
            "variable",
            "channel",
            "print_allowed",
            "hash_allowed",
            "persist_allowed",
            "return_allowed",
            "forbidden_fallbacks",
        },
        context="Gate L1 V3 secret contract",
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
        raise LambdaCloudContractError("Gate L1 V3 secret contract drifted")
    raw_requests = document["requests"]
    if not isinstance(raw_requests, list) or len(raw_requests) != MAX_INVENTORY_CALLS_V3:
        raise LambdaCloudContractError("Gate L1 V3 request count drifted")
    requests: list[InventoryRequest] = []
    endpoint_bindings: dict[str, EndpointSchemaBinding] = {}
    for raw_request, expected in zip(raw_requests, EXPECTED_INVENTORY_REQUESTS_V3, strict=True):
        record = _object(
            raw_request,
            keys={
                "request_id",
                "method",
                "path",
                "max_response_bytes",
                "response_schema_path",
                "response_schema_sha256",
            },
            context="Gate L1 V3 request",
        )
        request = InventoryRequest(
            _string(record["request_id"], context="request ID"),
            HttpMethod(_string(record["method"], context="request method")),
            _string(record["path"], context="request path"),
            _integer(record["max_response_bytes"], context="request byte cap"),
        )
        if request != expected:
            raise LambdaCloudContractError("Gate L1 V3 endpoint order drifted")
        endpoint_bindings[request.request_id] = EndpointSchemaBinding(
            request.request_id,
            _string(record["response_schema_path"], context="response schema path"),
            _string(record["response_schema_sha256"], context="response schema hash"),
        )
        requests.append(request)
    extension = _object(
        document["schema_extension_contract"],
        keys={
            "schema_path",
            "schema_sha256",
            "unknown_key_names_retained",
            "unknown_scalar_values_retained",
            "additive_keys_allowed_when_not_forbidden",
            "non_null_pagination_stops",
            "embedded_in_inventory",
        },
        context="Gate L1 V3 extension contract",
    )
    extension_sha = _string(extension["schema_sha256"], context="extension schema hash")
    if (
        extension
        != {
            "schema_path": EXTENSION_SCHEMA_RELATIVE_PATH,
            "schema_sha256": extension_sha,
            "unknown_key_names_retained": True,
            "unknown_scalar_values_retained": False,
            "additive_keys_allowed_when_not_forbidden": True,
            "non_null_pagination_stops": True,
            "embedded_in_inventory": True,
        }
        or _SHA256.fullmatch(extension_sha) is None
    ):
        raise LambdaCloudContractError("Gate L1 V3 extension contract drifted")
    ledger = _object(
        document["ledger_contract"],
        keys={
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
        context="Gate L1 V3 ledger contract",
    )
    ledger_sha = _string(ledger["schema_sha256"], context="ledger schema hash")
    expected_ledger_limits = {
        "max_bytes": MAX_LEDGER_BYTES_V3,
        "max_events": MAX_LEDGER_EVENTS_V3,
        "max_events_per_request": MAX_LEDGER_EVENTS_PER_REQUEST_V3,
        "max_event_bytes": MAX_LEDGER_EVENT_BYTES_V3,
        "max_preflight_disposition_bytes": MAX_PREFLIGHT_DISPOSITION_BYTES,
    }
    if (
        ledger["schema_path"] != LEDGER_SCHEMA_RELATIVE_PATH
        or _SHA256.fullmatch(ledger_sha) is None
        or ledger["relative_path"] != LEDGER_RELATIVE_PATH_V3
        or ledger["preflight_disposition_root_relative_path"]
        != PREFLIGHT_DISPOSITION_ROOT_RELATIVE_PATH
        or ledger["transport_kind"] != TRANSPORT_KIND_V3
        or ledger["event_types"] != list(LEDGER_EVENT_TYPES)
        or ledger["failure_stages"] != list(FAILURE_STAGES)
        or ledger["failure_classes"] != list(FAILURE_CLASSES)
        or ledger["capacity_reservation"] != "logical-cap-and-filesystem-free-space"
        or ledger["archive_eligible_after_event"] != "inventory_validation_passed"
        or ledger["limits"] != expected_ledger_limits
    ):
        raise LambdaCloudContractError("Gate L1 V3 ledger contract drifted")
    expected_limits = inventory_limits_document_v3_fields()
    if document["limits"] != expected_limits:
        raise LambdaCloudContractError("Gate L1 V3 limits drifted")
    output = _object(
        document["output"],
        keys={
            "run_root_relative_path",
            "relative_path",
            "copy_record_relative_path",
            "inventory_schema_path",
            "inventory_schema_sha256",
            "archive_root",
            "archive_run_directory",
            "raw_response_persistence",
            "redaction_required",
            "ledger_required_for_archive",
            "sha256_required",
            "source_retention_required",
        },
        context="Gate L1 V3 output",
    )
    inventory_sha = _string(output["inventory_schema_sha256"], context="inventory schema hash")
    if (
        output
        != {
            "run_root_relative_path": RUN_ROOT_RELATIVE_PATH_V3,
            "relative_path": INVENTORY_RELATIVE_PATH_V3,
            "copy_record_relative_path": COPY_RECORD_RELATIVE_PATH_V3,
            "inventory_schema_path": INVENTORY_SCHEMA_V3_RELATIVE_PATH,
            "inventory_schema_sha256": inventory_sha,
            "archive_root": ARCHIVE_ROOT,
            "archive_run_directory": INVENTORY_RUN_V3_ID,
            "raw_response_persistence": False,
            "redaction_required": True,
            "ledger_required_for_archive": True,
            "sha256_required": True,
            "source_retention_required": True,
        }
        or _SHA256.fullmatch(inventory_sha) is None
    ):
        raise LambdaCloudContractError("Gate L1 V3 output contract drifted")
    if document["authorization"] != {
        "authorized": False,
        "authorization_reference": PENDING_AUTHORIZATION_REFERENCE_V4,
    }:
        raise LambdaCloudContractError("Gate L1 V3 committed plan carries authority")
    return ReadOnlyInventoryPlanV3(
        implementation_commit=implementation_commit,
        implementation_artifacts=artifacts,
        ledger_schema_sha256=ledger_sha,
        inventory_schema_sha256=inventory_sha,
        extension_schema_sha256=extension_sha,
        endpoint_schema_bindings=endpoint_bindings,
        requests=tuple(requests),
    )


def inventory_limits_document_v3_fields() -> dict[str, int]:
    """Return exact committed numeric fields without a second policy source."""

    return {
        "max_calls": MAX_INVENTORY_CALLS_V3,
        "max_total_response_bytes": MAX_INVENTORY_TOTAL_RESPONSE_BYTES_V3,
        "max_retained_output_bytes": MAX_INVENTORY_RETAINED_BYTES_V3,
        "max_schema_extension_report_bytes": MAX_SCHEMA_EXTENSION_REPORT_BYTES,
        "max_wall_seconds": MAX_INVENTORY_WALL_SECONDS,
        "request_start_spacing_seconds": MIN_INVENTORY_REQUEST_SPACING_SECONDS,
        "max_archive_wall_seconds": MAX_INVENTORY_ARCHIVE_WALL_SECONDS,
        "max_total_wall_seconds": MAX_INVENTORY_TOTAL_WALL_SECONDS,
        "max_local_record_bytes": MAX_INVENTORY_LOCAL_RECORD_BYTES,
        "max_archive_bytes": MAX_INVENTORY_ARCHIVE_BYTES_V3,
        "max_aggregate_retained_bytes": MAX_INVENTORY_AGGREGATE_RETAINED_BYTES_V3,
        "local_prewrite_floor_bytes": MAX_INVENTORY_LOCAL_PREWRITE_FLOOR_BYTES_V3,
        "local_retained_floor_bytes": MAX_INVENTORY_LOCAL_RETAINED_FLOOR_BYTES,
        "max_local_command_calls": MAX_INVENTORY_LOCAL_COMMAND_CALLS_V3,
        "max_local_command_output_bytes": MAX_INVENTORY_LOCAL_COMMAND_OUTPUT_BYTES_V3,
        "max_local_file_creates": MAX_INVENTORY_LOCAL_FILE_CREATES_V3,
        "max_external_file_creates": MAX_INVENTORY_EXTERNAL_FILE_CREATES_V3,
        "max_external_directory_creates": MAX_INVENTORY_EXTERNAL_DIRECTORY_CREATES_V3,
        "automatic_retries": 0,
        "mutation_calls": 0,
        "provider_cost_usd": 0,
        "model_api_calls": 0,
        "model_tokens": 0,
        "browser_actions": 0,
        "ssh_operations": 0,
        "sira_executions": 0,
    }


def inventory_limits_document_v3(plan: ReadOnlyInventoryPlanV3) -> dict[str, int]:
    """Return inventory-artifact limit names for schema binding."""

    return {
        "provider_api_calls": plan.max_calls,
        "provider_wall_seconds": plan.max_wall_seconds,
        "request_start_spacing_seconds": plan.request_start_spacing_seconds,
        "archive_wall_seconds": plan.max_archive_wall_seconds,
        "total_wall_seconds": plan.max_total_wall_seconds,
        "raw_response_bytes": plan.max_total_response_bytes,
        "retained_output_bytes": plan.max_retained_output_bytes,
        "schema_extension_report_bytes": plan.max_schema_extension_report_bytes,
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


def inventory_ledger_contract_document_v3(
    plan: ReadOnlyInventoryPlanV3,
) -> dict[str, object]:
    return {
        "schema_path": plan.ledger_schema_relative_path,
        "schema_sha256": plan.ledger_schema_sha256,
        "relative_path": plan.ledger_relative_path,
        "archive_eligible_prefix_event": "inventory_validation_passed",
        "required_terminal_events": ["archive_passed", "run_stopped"],
        "complete_success_required": True,
        "unknown_after_send_allowed_for_gate_l2": False,
    }


def verify_repository_commit_ancestry_v3(
    repository_root: Path,
    *,
    implementation_commit: str,
    execution_commit: str,
) -> None:
    """Prove the authorized execution commit descends from the reviewed implementation."""

    if any(
        _GIT_COMMIT.fullmatch(value) is None for value in (implementation_commit, execution_commit)
    ):
        raise LambdaCloudContractError("Gate L1 V3 repository ancestry identity drifted")
    root = repository_root.resolve(strict=True)
    if root != repository_root.absolute():
        raise LambdaCloudContractError("Gate L1 V3 repository ancestry root is unsafe")
    try:
        result = subprocess.run(
            [
                "/usr/bin/git",
                "merge-base",
                "--is-ancestor",
                implementation_commit,
                execution_commit,
            ],
            cwd=root,
            check=False,
            capture_output=True,
            timeout=10,
            env=secret_free_child_environment(),
        )
    except (OSError, subprocess.SubprocessError):
        raise LambdaCloudContractError("Gate L1 V3 repository ancestry check failed") from None
    observed_output_bytes = len(result.stdout) + len(result.stderr)
    if result.returncode != 0 or observed_output_bytes > 65_536:
        raise LambdaCloudContractError("Gate L1 V3 repository ancestry check failed")


def verify_inventory_implementation_v3(
    repository_root: Path,
    plan: ReadOnlyInventoryPlanV3,
) -> None:
    """Hash-check every V3 runtime/schema artifact without a child process."""

    root = repository_root.resolve(strict=True)
    if root != repository_root.absolute():
        raise LambdaCloudContractError("Gate L1 V3 repository root contains a symlink")
    artifact_hashes = {binding.path: binding.sha256 for binding in plan.implementation_artifacts}
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
                "Gate L1 V3 implementation artifact is missing or unsafe"
            ) from None
        if hashlib.sha256(encoded).hexdigest() != binding.sha256:
            raise LambdaCloudContractError("Gate L1 V3 implementation artifact hash drifted")
    schema_bindings = (
        (
            AUDIT_STRUCTURAL_SCHEMA_RELATIVE_PATH,
            artifact_hashes[AUDIT_STRUCTURAL_SCHEMA_RELATIVE_PATH],
        ),
        (plan.extension_schema_relative_path, plan.extension_schema_sha256),
        (plan.inventory_schema_relative_path, plan.inventory_schema_sha256),
        (plan.ledger_schema_relative_path, plan.ledger_schema_sha256),
        *tuple(
            (binding.path, binding.sha256) for binding in plan.endpoint_schema_bindings.values()
        ),
    )
    if tuple(relative for relative, _ in schema_bindings) != SCHEMA_FILES_V3:
        raise LambdaCloudContractError("Gate L1 V3 schema registry order drifted")
    for relative, expected in schema_bindings:
        try:
            encoded = (root / relative).read_bytes()
            if hashlib.sha256(encoded).hexdigest() != expected:
                raise ValueError
            schema = json.loads(
                encoded,
                object_pairs_hook=_pairs,
                parse_constant=_reject_constant,
            )
            Draft202012Validator.check_schema(schema)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, SchemaError, ValueError):
            raise LambdaCloudContractError("Gate L1 V3 schema binding failed") from None
