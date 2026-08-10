"""Typed, network-inert controls for the T07 Lambda host pivot.

This module deliberately contains no HTTP, SSH, subprocess, Docker, or provider
client.  It validates an authorization plan, parses already-captured bounded API
responses in memory, renders a fail-closed launch body, and validates the lifecycle
graph that a separately authorized operator must execute.
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Final, Never, Protocol


class LambdaCloudContractError(ValueError):
    """A Lambda inventory, selection, or lifecycle contract is unsafe."""


class SelectionFailureCode(StrEnum):
    EXISTING_T07_INSTANCE = "existing-t07-instance"
    GLOBAL_FIREWALL_NOT_SSH_ONLY = "global-firewall-not-ssh-only"
    NO_QUALIFYING_CANDIDATE = "no-qualifying-candidate"


class InstanceSelectionError(LambdaCloudContractError):
    """A typed, retainable instance-selection stop condition."""

    def __init__(self, code: SelectionFailureCode, message: str) -> None:
        super().__init__(message)
        self.code = code


class InventoryResponseFailureKind(StrEnum):
    JSON_DECODE = "json_decode"
    SCHEMA_VALIDATION = "schema_validation"
    PAGINATION = "pagination"


class InventoryResponseValidationError(LambdaCloudContractError):
    """Closed response-validation failure used by the observable V2 supervisor."""

    def __init__(self, kind: InventoryResponseFailureKind, stable_code: str) -> None:
        super().__init__(stable_code)
        self.kind = kind
        self.stable_code = stable_code


API_BASE_URL: Final = "https://cloud.lambda.ai"
API_SPEC_VERSION: Final = "1.10.0"
API_SPEC_SHA256: Final = "365488015cf79fda38e1268f44a9e2d4af4fe2794ad3c6878c78a7e1f98caded"
INVENTORY_PLAN_ID: Final = "PLAN-T07-GATE-L1-LAMBDA-READONLY-INVENTORY-V1"
INVENTORY_RUN_ID: Final = "RUN-T07-L1-LAMBDA-INVENTORY-0001"
INVENTORY_PLAN_V2_ID: Final = "PLAN-T07-GATE-L1-LAMBDA-READONLY-INVENTORY-V2"
INVENTORY_RUN_V2_ID: Final = "RUN-T07-L1-LAMBDA-INVENTORY-0002"
LAMBDA_BRANCH: Final = "phase-1/sira-smoke-lambda"
QUALIFICATION_INSTANCE_NAME: Final = "giclab-t07-l2-qualification"
QUALIFICATION_IMAGE_FAMILY: Final = "gpu-base-22-04"
MAX_PRICE_CENTS_PER_HOUR: Final = 150
MAX_QUALIFICATION_WALL_SECONDS: Final = 3600
MAX_PROVIDER_COMPUTE_CENTS: Final = 200
MAX_INVENTORY_CALLS: Final = 8
MAX_INVENTORY_RESPONSE_BYTES: Final = 262_144
MAX_INVENTORY_TOTAL_RESPONSE_BYTES: Final = 2_097_152
MAX_INVENTORY_RETAINED_BYTES: Final = 524_288
MAX_INVENTORY_WALL_SECONDS: Final = 60
MIN_INVENTORY_REQUEST_SPACING_SECONDS: Final = 1
MAX_INVENTORY_ARCHIVE_WALL_SECONDS: Final = 60
MAX_INVENTORY_TOTAL_WALL_SECONDS: Final = 180
MAX_INVENTORY_LOCAL_RECORD_BYTES: Final = 65_536
MAX_INVENTORY_ARCHIVE_BYTES: Final = 1_048_576
MAX_INVENTORY_AGGREGATE_RETAINED_BYTES: Final = 1_638_400
MAX_INVENTORY_LOCAL_PREWRITE_FLOOR_BYTES: Final = 8_591_048_704
MAX_INVENTORY_LOCAL_RETAINED_FLOOR_BYTES: Final = 8_589_934_592
MAX_INVENTORY_LOCAL_COMMAND_CALLS: Final = 14
MAX_INVENTORY_LOCAL_COMMAND_OUTPUT_BYTES: Final = 37_814_274
MAX_INVENTORY_LOCAL_FILE_CREATES: Final = 2
MAX_INVENTORY_EXTERNAL_FILE_CREATES: Final = 3
MAX_INVENTORY_EXTERNAL_DIRECTORY_CREATES: Final = 4
MIN_PROVIDER_REQUEST_SPACING_SECONDS: Final = 1
MAX_PROVIDER_API_CALLS: Final = 134
FORBIDDEN_CHILD_SECRET_VARIABLES: Final = frozenset(
    {"LAMBDA_API_KEY", "SIRA_API_KEY", "OPENAI_API_KEY"}
)
FIREWALL_UNENFORCED_REGIONS: Final = frozenset({"us-south-1"})
BUSYBOX_REFERENCE: Final = (
    "busybox@sha256:7a3ebe5bfd1a4a19797d20b0c0bb39d44393e9a03fd852c0865b0f540d868df0"
)
BUSYBOX_CONFIG_DIGEST: Final = (
    "sha256:db287cb6be81219cd18c1d82b70908f5d33eb028568b456f78eedff2ff2930e4"
)
BUSYBOX_LAYER_DIGEST: Final = (
    "sha256:436a1b1fd078ee8e117111472724c2827077657189af7a781829d0825d48d2ab"
)

_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_GIT_COMMIT = re.compile(r"^[a-f0-9]{40}$")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


def secret_free_child_environment() -> dict[str, str]:
    """Return the exact deterministic environment allowed for local child processes."""

    environment = {
        "PATH": os.defpath,
        "LANG": "C",
        "LC_ALL": "C",
        "PYTHONNOUSERSITE": "1",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": "/dev/null",
    }
    if FORBIDDEN_CHILD_SECRET_VARIABLES.intersection(environment):
        raise LambdaCloudContractError("secret variable reached child-process environment")
    return environment


class HttpMethod(StrEnum):
    GET = "GET"


@dataclass(frozen=True, slots=True)
class InventoryRequest:
    request_id: str
    method: HttpMethod
    path: str
    max_response_bytes: int

    def __post_init__(self) -> None:
        if _IDENTIFIER.fullmatch(self.request_id) is None:
            raise LambdaCloudContractError("inventory request ID is not canonical")
        if self.method is not HttpMethod.GET:
            raise LambdaCloudContractError("inventory permits GET only")
        if not self.path.startswith("/api/v1/") or "//" in self.path:
            raise LambdaCloudContractError("inventory path must be an exact relative API path")
        if self.max_response_bytes != MAX_INVENTORY_RESPONSE_BYTES:
            raise LambdaCloudContractError("inventory response cap drifted")


EXPECTED_INVENTORY_REQUESTS: Final = (
    InventoryRequest(
        "account-workspace-identity",
        HttpMethod.GET,
        "/api/v1/audit-events?resource_type=cloud.api_key",
        MAX_INVENTORY_RESPONSE_BYTES,
    ),
    InventoryRequest(
        "instance-types",
        HttpMethod.GET,
        "/api/v1/instance-types",
        MAX_INVENTORY_RESPONSE_BYTES,
    ),
    InventoryRequest("images", HttpMethod.GET, "/api/v1/images", MAX_INVENTORY_RESPONSE_BYTES),
    InventoryRequest("regions", HttpMethod.GET, "/api/v1/regions", MAX_INVENTORY_RESPONSE_BYTES),
    InventoryRequest("ssh-keys", HttpMethod.GET, "/api/v1/ssh-keys", MAX_INVENTORY_RESPONSE_BYTES),
    InventoryRequest(
        "firewall-rulesets",
        HttpMethod.GET,
        "/api/v1/firewall-rulesets",
        MAX_INVENTORY_RESPONSE_BYTES,
    ),
    InventoryRequest(
        "global-firewall-ruleset",
        HttpMethod.GET,
        "/api/v1/firewall-rulesets/global",
        MAX_INVENTORY_RESPONSE_BYTES,
    ),
    InventoryRequest(
        "running-instances",
        HttpMethod.GET,
        "/api/v1/instances",
        MAX_INVENTORY_RESPONSE_BYTES,
    ),
)


@dataclass(frozen=True, slots=True)
class ReadOnlyInventoryPlan:
    plan_id: str
    run_id: str
    provider: str
    api_base_url: str
    api_spec_version: str
    api_spec_sha256: str
    secret_variable: str
    requests: tuple[InventoryRequest, ...]
    max_calls: int
    max_total_response_bytes: int
    max_retained_output_bytes: int
    max_wall_seconds: int
    request_start_spacing_seconds: int
    max_archive_wall_seconds: int
    max_total_wall_seconds: int
    max_local_record_bytes: int
    max_archive_bytes: int
    max_aggregate_retained_bytes: int
    local_prewrite_floor_bytes: int
    local_retained_floor_bytes: int
    max_local_command_calls: int
    max_local_command_output_bytes: int
    max_local_file_creates: int
    max_external_file_creates: int
    max_external_directory_creates: int
    automatic_retries: int
    output_relative_path: str
    copy_record_relative_path: str
    archive_root: str
    authorized: bool

    def __post_init__(self) -> None:
        if self.plan_id != INVENTORY_PLAN_ID:
            raise LambdaCloudContractError("inventory plan ID drifted")
        if self.run_id != INVENTORY_RUN_ID:
            raise LambdaCloudContractError("inventory run ID drifted")
        if self.provider != "lambda-on-demand-cloud":
            raise LambdaCloudContractError("inventory provider drifted")
        if self.api_base_url != API_BASE_URL:
            raise LambdaCloudContractError("inventory API base URL drifted")
        if self.api_spec_version != API_SPEC_VERSION or self.api_spec_sha256 != API_SPEC_SHA256:
            raise LambdaCloudContractError("inventory API specification lock drifted")
        if self.secret_variable != "LAMBDA_API_KEY":
            raise LambdaCloudContractError("inventory secret variable drifted")
        if self.requests != EXPECTED_INVENTORY_REQUESTS:
            raise LambdaCloudContractError("inventory GET endpoint set or order drifted")
        if self.max_calls != MAX_INVENTORY_CALLS:
            raise LambdaCloudContractError("inventory call cap drifted")
        if self.max_total_response_bytes != MAX_INVENTORY_TOTAL_RESPONSE_BYTES:
            raise LambdaCloudContractError("inventory aggregate response cap drifted")
        if self.max_retained_output_bytes != MAX_INVENTORY_RETAINED_BYTES:
            raise LambdaCloudContractError("inventory retained-output cap drifted")
        if self.max_wall_seconds != MAX_INVENTORY_WALL_SECONDS:
            raise LambdaCloudContractError("inventory provider wall cap drifted")
        if self.request_start_spacing_seconds != MIN_INVENTORY_REQUEST_SPACING_SECONDS:
            raise LambdaCloudContractError("inventory request pacing drifted")
        if self.max_archive_wall_seconds != MAX_INVENTORY_ARCHIVE_WALL_SECONDS:
            raise LambdaCloudContractError("inventory archive wall cap drifted")
        if self.max_total_wall_seconds != MAX_INVENTORY_TOTAL_WALL_SECONDS:
            raise LambdaCloudContractError("inventory total wall cap drifted")
        if self.max_local_record_bytes != MAX_INVENTORY_LOCAL_RECORD_BYTES:
            raise LambdaCloudContractError("inventory local record cap drifted")
        if self.max_archive_bytes != MAX_INVENTORY_ARCHIVE_BYTES:
            raise LambdaCloudContractError("inventory archive byte cap drifted")
        if self.max_aggregate_retained_bytes != MAX_INVENTORY_AGGREGATE_RETAINED_BYTES:
            raise LambdaCloudContractError("inventory aggregate retained byte cap drifted")
        if self.local_prewrite_floor_bytes != MAX_INVENTORY_LOCAL_PREWRITE_FLOOR_BYTES:
            raise LambdaCloudContractError("inventory local prewrite floor drifted")
        if self.local_retained_floor_bytes != MAX_INVENTORY_LOCAL_RETAINED_FLOOR_BYTES:
            raise LambdaCloudContractError("inventory local retained floor drifted")
        if self.max_local_command_calls != MAX_INVENTORY_LOCAL_COMMAND_CALLS:
            raise LambdaCloudContractError("inventory local command-call cap drifted")
        if self.max_local_command_output_bytes != MAX_INVENTORY_LOCAL_COMMAND_OUTPUT_BYTES:
            raise LambdaCloudContractError("inventory local command-output cap drifted")
        if self.max_local_file_creates != MAX_INVENTORY_LOCAL_FILE_CREATES:
            raise LambdaCloudContractError("inventory local file-create cap drifted")
        if self.max_external_file_creates != MAX_INVENTORY_EXTERNAL_FILE_CREATES:
            raise LambdaCloudContractError("inventory external file-create cap drifted")
        if self.max_external_directory_creates != MAX_INVENTORY_EXTERNAL_DIRECTORY_CREATES:
            raise LambdaCloudContractError("inventory external directory-create cap drifted")
        if self.automatic_retries != 0:
            raise LambdaCloudContractError("inventory automatic retries must be zero")
        if self.output_relative_path != ("artifacts/t07/lambda/gate-l1/inventory-redacted.json"):
            raise LambdaCloudContractError("inventory output path drifted")
        if self.copy_record_relative_path != (
            "artifacts/t07/lambda/gate-l1/inventory-copy-record.json"
        ):
            raise LambdaCloudContractError("inventory copy-record path drifted")
        if self.archive_root != ("/Volumes/Macintosh HD - Data/GIC-Lab/t07/sealed-artifacts"):
            raise LambdaCloudContractError("inventory archive root drifted")
        if self.authorized:
            raise LambdaCloudContractError("committed Gate L1 plan must remain unauthorized")


@dataclass(frozen=True, slots=True)
class Region:
    name: str
    description: str


@dataclass(frozen=True, slots=True)
class InstanceSpecs:
    vcpus: int
    memory_gib: int
    storage_gib: int
    gpus: int


@dataclass(frozen=True, slots=True)
class InstanceTypeOffer:
    name: str
    description: str
    gpu_description: str
    architecture: str
    price_cents_per_hour: int
    specs: InstanceSpecs
    capacity_regions: tuple[Region, ...]


@dataclass(frozen=True, slots=True)
class ProviderImage:
    image_id: str
    name: str
    family: str
    version: str
    architecture: str
    region: Region


@dataclass(frozen=True, slots=True)
class SSHKeyIdentity:
    key_id: str
    name: str


@dataclass(frozen=True, slots=True)
class FirewallRule:
    protocol: str
    port_range: tuple[int, int] | None
    source_network: str
    description: str

    @property
    def is_ssh_only(self) -> bool:
        return self.protocol == "tcp" and self.port_range == (22, 22)


@dataclass(frozen=True, slots=True)
class FirewallRuleset:
    ruleset_id: str
    name: str
    scope: str
    region: Region | None
    rules: tuple[FirewallRule, ...]

    @property
    def is_ssh_only(self) -> bool:
        return bool(self.rules) and all(rule.is_ssh_only for rule in self.rules)


@dataclass(frozen=True, slots=True)
class RunningInstance:
    instance_id: str
    name: str | None
    status: str
    region_name: str
    instance_type_name: str
    file_system_count: int
    firewall_ruleset_ids: tuple[str, ...]
    t07_owned: bool


@dataclass(frozen=True, slots=True)
class AccountWorkspaceBinding:
    account_lrn_sha256: str
    workspace_lrn_sha256: str
    source_event_count: int
    source_page_complete: bool


@dataclass(frozen=True, slots=True)
class InventoryRunBinding:
    run_id: str
    repository_commit: str
    authorization_reference: str
    authorization_sha256: str

    def __post_init__(self) -> None:
        if self.run_id != INVENTORY_RUN_ID:
            raise LambdaCloudContractError("inventory run ID drifted")
        if _GIT_COMMIT.fullmatch(self.repository_commit) is None:
            raise LambdaCloudContractError("inventory repository commit is not canonical")
        if _IDENTIFIER.fullmatch(self.authorization_reference) is None:
            raise LambdaCloudContractError("inventory authorization reference is not canonical")
        if _SHA256.fullmatch(self.authorization_sha256) is None:
            raise LambdaCloudContractError("inventory authorization hash is not canonical")


@dataclass(frozen=True, slots=True)
class Inventory:
    binding: AccountWorkspaceBinding
    instance_types: tuple[InstanceTypeOffer, ...]
    images: tuple[ProviderImage, ...]
    regions: tuple[Region, ...]
    ssh_keys: tuple[SSHKeyIdentity, ...]
    firewall_rulesets: tuple[FirewallRuleset, ...]
    running_instances: tuple[RunningInstance, ...]


@dataclass(frozen=True, slots=True)
class ComputeCandidate:
    instance_type_name: str
    region_name: str
    image_id: str
    image_name: str
    image_family: str
    image_version: str
    architecture: str
    price_cents_per_hour: int
    vcpus: int
    memory_gib: int
    storage_gib: int
    gpus: int
    eligible_firewall_ruleset_ids: tuple[str, ...]
    qualification_list_price_cap_cents: int
    provider_compute_hard_cap_cents: int


@dataclass(frozen=True, slots=True)
class SelectedInfrastructure:
    account_lrn_sha256: str
    workspace_lrn_sha256: str
    candidate: ComputeCandidate
    ssh_key: SSHKeyIdentity
    firewall_ruleset: FirewallRuleset


class QualificationPhase(StrEnum):
    PRELAUNCH_REVALIDATED = "prelaunch-revalidated"
    LAUNCH_REQUESTED = "launch-requested"
    INSTANCE_ID_CAPTURED = "instance-id-captured"
    HOST_EVIDENCE_CAPTURED = "host-evidence-captured"
    CONTAINMENT_QUALIFIED = "containment-qualified"
    EVIDENCE_COPIED = "evidence-copied"
    TERMINATION_REQUESTED = "termination-requested"
    TERMINAL_CONFIRMED = "terminal-confirmed"


@dataclass(frozen=True, slots=True)
class QualificationLifecycleContract:
    phases: tuple[QualificationPhase, ...]
    max_launch_requests: int
    max_termination_targets: int
    max_termination_requests: int
    launch_retries: int
    terminate_by_provider_api: bool
    immutable_instance_id_required: bool
    terminate_on_every_post_launch_exit: bool
    require_terminal_nonbillable_state: bool

    def validate(self) -> None:
        if self.phases != tuple(QualificationPhase):
            raise LambdaCloudContractError("qualification lifecycle phase order drifted")
        if self.max_launch_requests != 1 or self.max_termination_targets != 1:
            raise LambdaCloudContractError(
                "qualification must launch and target exactly one instance"
            )
        if self.max_termination_requests != 3:
            raise LambdaCloudContractError("qualification termination request cap drifted")
        if self.launch_retries != 0:
            raise LambdaCloudContractError("qualification launch retries must be zero")
        if not all(
            (
                self.terminate_by_provider_api,
                self.immutable_instance_id_required,
                self.terminate_on_every_post_launch_exit,
                self.require_terminal_nonbillable_state,
            )
        ):
            raise LambdaCloudContractError("qualification termination coverage is incomplete")


def _pairs_without_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise LambdaCloudContractError("duplicate JSON key")
        result[key] = value
    return result


def _reject_json_constant(_: str) -> Never:
    raise ValueError


def _json_object(encoded: bytes, *, context: str) -> dict[str, object]:
    invalid = False
    try:
        value: object = json.loads(
            encoded,
            object_pairs_hook=_pairs_without_duplicates,
            parse_constant=_reject_json_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError, RecursionError):
        value = None
        invalid = True
    if invalid:
        raise LambdaCloudContractError(f"{context} is not strict UTF-8 JSON")
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise LambdaCloudContractError(f"{context} must be a JSON object")
    return value


def _expect_exact_keys(
    value: Mapping[str, object],
    required: set[str],
    *,
    context: str,
    optional: set[str] | None = None,
) -> None:
    optional = optional or set()
    observed = set(value)
    if not required.issubset(observed) or not observed.issubset(required | optional):
        # Provider-supplied field names are raw input and may themselves contain
        # sensitive material. Keep failure text categorical and secret-safe.
        raise LambdaCloudContractError(f"{context} schema drift: exact field set differs")


def _mapping(value: object, *, context: str) -> dict[str, object]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise LambdaCloudContractError(f"{context} must be an object")
    return value


def _list(value: object, *, context: str) -> list[object]:
    if not isinstance(value, list):
        raise LambdaCloudContractError(f"{context} must be an array")
    return value


def _string(value: object, *, context: str, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value):
        raise LambdaCloudContractError(f"{context} must be a nonempty string")
    return value


def _integer(value: object, *, context: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise LambdaCloudContractError(f"{context} must be an integer >= {minimum}")
    return value


def _region(value: object, *, context: str) -> Region:
    record = _mapping(value, context=context)
    _expect_exact_keys(record, {"name", "description"}, context=context)
    return Region(
        name=_string(record["name"], context=f"{context}.name"),
        description=_string(record["description"], context=f"{context}.description"),
    )


def load_inventory_plan(path: Path, *, expected_sha256: str) -> ReadOnlyInventoryPlan:
    """Load a committed, hash-bound, explicitly unauthorized inventory plan."""

    if _SHA256.fullmatch(expected_sha256) is None:
        raise LambdaCloudContractError("expected inventory plan hash is not canonical")
    encoded = path.read_bytes()
    if hashlib.sha256(encoded).hexdigest() != expected_sha256:
        raise LambdaCloudContractError("inventory plan SHA-256 mismatch")
    document = _json_object(encoded, context="inventory plan")
    _expect_exact_keys(
        document,
        {
            "schema_version",
            "plan_id",
            "decision_state",
            "provider",
            "api_base_url",
            "api_spec",
            "actor",
            "run_identity",
            "secret_contract",
            "requests",
            "limits",
            "output",
            "authorization",
        },
        context="inventory plan",
    )
    if document["schema_version"] != "0.1.0":
        raise LambdaCloudContractError("inventory plan schema version drifted")
    if document["decision_state"] != "unauthorized":
        raise LambdaCloudContractError("inventory plan decision state must be unauthorized")
    if document["actor"] != "future-codex-operator-gpt-5.6-luna-max":
        raise LambdaCloudContractError("inventory actor binding drifted")
    run_identity = _mapping(document["run_identity"], context="inventory plan.run_identity")
    _expect_exact_keys(
        run_identity,
        {"run_id", "attempt", "experiment_id", "profile_plan_id", "gate", "branch"},
        context="inventory plan.run_identity",
    )
    if run_identity != {
        "run_id": INVENTORY_RUN_ID,
        "attempt": 1,
        "experiment_id": "EXP-0001",
        "profile_plan_id": "PLAN-EXP0001-SMOKE",
        "gate": "T07-L1",
        "branch": LAMBDA_BRANCH,
    }:
        raise LambdaCloudContractError("inventory run identity drifted")
    api_spec = _mapping(document["api_spec"], context="inventory plan.api_spec")
    _expect_exact_keys(api_spec, {"version", "sha256"}, context="inventory plan.api_spec")
    credential_contract = _mapping(
        document["secret_contract"], context="inventory plan.secret_contract"
    )
    _expect_exact_keys(
        credential_contract,
        {
            "variable",
            "channel",
            "print_allowed",
            "hash_allowed",
            "persist_allowed",
            "return_allowed",
            "forbidden_fallbacks",
        },
        context="inventory plan.secret_contract",
    )
    if credential_contract != {
        "variable": "LAMBDA_API_KEY",
        "channel": "supervisor-secret-channel",
        "print_allowed": False,
        "hash_allowed": False,
        "persist_allowed": False,
        "return_allowed": False,
        "forbidden_fallbacks": ["SIRA_API_KEY", "OPENAI_API_KEY"],
    }:
        raise LambdaCloudContractError("inventory secret contract drifted")
    request_records = _list(document["requests"], context="inventory plan.requests")
    requests: list[InventoryRequest] = []
    for index, raw in enumerate(request_records):
        record = _mapping(raw, context=f"inventory plan.requests[{index}]")
        _expect_exact_keys(
            record,
            {"request_id", "method", "path", "max_response_bytes"},
            context=f"inventory plan.requests[{index}]",
        )
        try:
            method = HttpMethod(_string(record["method"], context="request method"))
        except ValueError as exc:
            raise LambdaCloudContractError("inventory request method must be GET") from exc
        requests.append(
            InventoryRequest(
                request_id=_string(record["request_id"], context="request ID"),
                method=method,
                path=_string(record["path"], context="request path"),
                max_response_bytes=_integer(
                    record["max_response_bytes"], context="request response cap", minimum=1
                ),
            )
        )
    limits = _mapping(document["limits"], context="inventory plan.limits")
    _expect_exact_keys(
        limits,
        {
            "max_calls",
            "max_total_response_bytes",
            "max_retained_output_bytes",
            "max_wall_seconds",
            "request_start_spacing_seconds",
            "max_archive_wall_seconds",
            "max_total_wall_seconds",
            "max_local_record_bytes",
            "max_archive_bytes",
            "max_aggregate_retained_bytes",
            "local_prewrite_floor_bytes",
            "local_retained_floor_bytes",
            "max_local_command_calls",
            "max_local_command_output_bytes",
            "max_local_file_creates",
            "max_external_file_creates",
            "max_external_directory_creates",
            "automatic_retries",
            "mutation_calls",
            "provider_cost_usd",
            "model_api_calls",
            "model_tokens",
            "browser_actions",
            "sira_executions",
        },
        context="inventory plan.limits",
    )
    if any(
        limits[field] != 0
        for field in (
            "mutation_calls",
            "provider_cost_usd",
            "model_api_calls",
            "model_tokens",
            "browser_actions",
            "sira_executions",
        )
    ):
        raise LambdaCloudContractError("inventory zero-use limits drifted")
    output = _mapping(document["output"], context="inventory plan.output")
    _expect_exact_keys(
        output,
        {
            "relative_path",
            "copy_record_relative_path",
            "archive_root",
            "archive_run_directory",
            "raw_response_persistence",
            "redaction_required",
            "sha256_required",
            "source_retention_required",
        },
        context="inventory plan.output",
    )
    if output != {
        "relative_path": "artifacts/t07/lambda/gate-l1/inventory-redacted.json",
        "copy_record_relative_path": ("artifacts/t07/lambda/gate-l1/inventory-copy-record.json"),
        "archive_root": "/Volumes/Macintosh HD - Data/GIC-Lab/t07/sealed-artifacts",
        "archive_run_directory": INVENTORY_RUN_ID,
        "raw_response_persistence": False,
        "redaction_required": True,
        "sha256_required": True,
        "source_retention_required": True,
    }:
        raise LambdaCloudContractError("inventory output contract drifted")
    authorization = _mapping(document["authorization"], context="inventory authorization")
    _expect_exact_keys(
        authorization,
        {"authorized", "authorization_reference"},
        context="inventory authorization",
    )
    if authorization != {"authorized": False, "authorization_reference": None}:
        raise LambdaCloudContractError("committed inventory plan cannot carry authority")
    return ReadOnlyInventoryPlan(
        plan_id=_string(document["plan_id"], context="inventory plan ID"),
        run_id=_string(run_identity["run_id"], context="inventory run ID"),
        provider=_string(document["provider"], context="inventory provider"),
        api_base_url=_string(document["api_base_url"], context="inventory API base"),
        api_spec_version=_string(api_spec["version"], context="API spec version"),
        api_spec_sha256=_string(api_spec["sha256"], context="API spec hash"),
        secret_variable=_string(credential_contract["variable"], context="secret variable"),
        requests=tuple(requests),
        max_calls=_integer(limits["max_calls"], context="inventory max calls", minimum=1),
        max_total_response_bytes=_integer(
            limits["max_total_response_bytes"], context="inventory response total", minimum=1
        ),
        max_retained_output_bytes=_integer(
            limits["max_retained_output_bytes"], context="inventory retained output", minimum=1
        ),
        max_wall_seconds=_integer(limits["max_wall_seconds"], context="inventory wall", minimum=1),
        request_start_spacing_seconds=_integer(
            limits["request_start_spacing_seconds"],
            context="inventory request pacing",
            minimum=1,
        ),
        max_archive_wall_seconds=_integer(
            limits["max_archive_wall_seconds"], context="inventory archive wall", minimum=1
        ),
        max_total_wall_seconds=_integer(
            limits["max_total_wall_seconds"], context="inventory total wall", minimum=1
        ),
        max_local_record_bytes=_integer(
            limits["max_local_record_bytes"], context="inventory local record", minimum=1
        ),
        max_archive_bytes=_integer(
            limits["max_archive_bytes"], context="inventory archive bytes", minimum=1
        ),
        max_aggregate_retained_bytes=_integer(
            limits["max_aggregate_retained_bytes"],
            context="inventory aggregate retained bytes",
            minimum=1,
        ),
        local_prewrite_floor_bytes=_integer(
            limits["local_prewrite_floor_bytes"],
            context="inventory local prewrite floor",
            minimum=1,
        ),
        local_retained_floor_bytes=_integer(
            limits["local_retained_floor_bytes"],
            context="inventory local retained floor",
            minimum=1,
        ),
        max_local_command_calls=_integer(
            limits["max_local_command_calls"],
            context="inventory local command calls",
            minimum=1,
        ),
        max_local_command_output_bytes=_integer(
            limits["max_local_command_output_bytes"],
            context="inventory local command output",
            minimum=1,
        ),
        max_local_file_creates=_integer(
            limits["max_local_file_creates"],
            context="inventory local file creates",
            minimum=1,
        ),
        max_external_file_creates=_integer(
            limits["max_external_file_creates"],
            context="inventory external file creates",
            minimum=1,
        ),
        max_external_directory_creates=_integer(
            limits["max_external_directory_creates"],
            context="inventory external directory creates",
            minimum=1,
        ),
        automatic_retries=_integer(
            limits["automatic_retries"], context="inventory retries", minimum=0
        ),
        output_relative_path=_string(output["relative_path"], context="inventory output path"),
        copy_record_relative_path=_string(
            output["copy_record_relative_path"], context="inventory copy-record path"
        ),
        archive_root=_string(output["archive_root"], context="inventory archive root"),
        authorized=bool(authorization["authorized"]),
    )


def _envelope(encoded: bytes, *, request: InventoryRequest) -> dict[str, object]:
    if len(encoded) > request.max_response_bytes:
        raise LambdaCloudContractError(f"{request.request_id} response exceeds its byte cap")
    return _json_object(encoded, context=request.request_id)


def _domain_hash(domain: str, value: str) -> str:
    return hashlib.sha256(f"giclab:t07:lambda:{domain}:v1\0{value}".encode()).hexdigest()


def _parse_account_binding(encoded: bytes, request: InventoryRequest) -> AccountWorkspaceBinding:
    envelope = _envelope(encoded, request=request)
    _expect_exact_keys(envelope, {"data", "page_token"}, context=request.request_id)
    events = _list(envelope["data"], context="audit data")
    if not events:
        raise LambdaCloudContractError("audit inventory returned no identity-bearing events")
    required = {
        "service_name",
        "resource_name",
        "action",
        "catalog_version",
        "event_id",
        "event_time",
        "actor_lrn",
        "actor_email",
        "actor_display_name",
        "resource_lrns",
        "resource_owner_lrn",
        "request_api_key_lrn",
        "workspace_lrn",
        "client_ip",
        "client_user_agent",
        "surface",
        "result",
        "additional_details",
    }
    accounts: set[str] = set()
    workspaces: set[str] = set()
    for index, raw in enumerate(events):
        event = _mapping(raw, context=f"audit event {index}")
        _expect_exact_keys(event, required, context=f"audit event {index}")
        account = event["resource_owner_lrn"]
        workspace = event["workspace_lrn"]
        if account is not None:
            accounts.add(_string(account, context="audit account LRN"))
        if workspace is not None:
            workspaces.add(_string(workspace, context="audit workspace LRN"))
    if len(accounts) != 1 or len(workspaces) != 1:
        raise LambdaCloudContractError("audit page does not bind exactly one account/workspace")
    next_page_value = envelope["page_token"]
    if next_page_value is not None and not isinstance(next_page_value, str):
        raise LambdaCloudContractError("audit page token schema drifted")
    return AccountWorkspaceBinding(
        account_lrn_sha256=_domain_hash("account", next(iter(accounts))),
        workspace_lrn_sha256=_domain_hash("workspace", next(iter(workspaces))),
        source_event_count=len(events),
        source_page_complete=next_page_value is None,
    )


def _parse_instance_type_record(value: object, *, context: str) -> InstanceTypeOffer:
    wrapper = _mapping(value, context=context)
    _expect_exact_keys(
        wrapper, {"instance_type", "regions_with_capacity_available"}, context=context
    )
    record = _mapping(wrapper["instance_type"], context=f"{context}.instance_type")
    _expect_exact_keys(
        record,
        {
            "name",
            "description",
            "gpu_description",
            "price_cents_per_hour",
            "specs",
            "architecture",
        },
        context=f"{context}.instance_type",
    )
    specs_raw = _mapping(record["specs"], context=f"{context}.specs")
    _expect_exact_keys(
        specs_raw, {"vcpus", "memory_gib", "storage_gib", "gpus"}, context=f"{context}.specs"
    )
    architecture = _string(record["architecture"], context=f"{context}.architecture")
    if architecture not in {"x86_64", "arm64"}:
        raise LambdaCloudContractError("instance architecture schema drifted")
    regions = tuple(
        _region(item, context=f"{context}.capacity_regions[{index}]")
        for index, item in enumerate(
            _list(wrapper["regions_with_capacity_available"], context=f"{context}.regions")
        )
    )
    return InstanceTypeOffer(
        name=_string(record["name"], context=f"{context}.name"),
        description=_string(record["description"], context=f"{context}.description"),
        gpu_description=_string(record["gpu_description"], context=f"{context}.gpu_description"),
        architecture=architecture,
        price_cents_per_hour=_integer(
            record["price_cents_per_hour"], context=f"{context}.price", minimum=0
        ),
        specs=InstanceSpecs(
            vcpus=_integer(specs_raw["vcpus"], context=f"{context}.vcpus", minimum=1),
            memory_gib=_integer(specs_raw["memory_gib"], context=f"{context}.memory", minimum=1),
            storage_gib=_integer(specs_raw["storage_gib"], context=f"{context}.storage", minimum=1),
            gpus=_integer(specs_raw["gpus"], context=f"{context}.gpus", minimum=0),
        ),
        capacity_regions=regions,
    )


def _parse_instance_types(
    encoded: bytes, request: InventoryRequest
) -> tuple[InstanceTypeOffer, ...]:
    envelope = _envelope(encoded, request=request)
    _expect_exact_keys(envelope, {"data"}, context=request.request_id)
    data = _mapping(envelope["data"], context="instance type data")
    offers: list[InstanceTypeOffer] = []
    for index, (key, value) in enumerate(data.items()):
        offer = _parse_instance_type_record(value, context=f"instance type {index}")
        if offer.name != key:
            raise LambdaCloudContractError("instance type map key/name mismatch")
        offers.append(offer)
    return tuple(sorted(offers, key=lambda item: item.name))


def _parse_images(encoded: bytes, request: InventoryRequest) -> tuple[ProviderImage, ...]:
    envelope = _envelope(encoded, request=request)
    _expect_exact_keys(envelope, {"data"}, context=request.request_id)
    images: list[ProviderImage] = []
    for index, raw in enumerate(_list(envelope["data"], context="image data")):
        record = _mapping(raw, context=f"image {index}")
        _expect_exact_keys(
            record,
            {
                "id",
                "created_time",
                "updated_time",
                "name",
                "description",
                "family",
                "version",
                "architecture",
                "region",
            },
            context=f"image {index}",
        )
        architecture = _string(record["architecture"], context=f"image {index}.architecture")
        if architecture not in {"x86_64", "arm64"}:
            raise LambdaCloudContractError("image architecture schema drifted")
        images.append(
            ProviderImage(
                image_id=_string(record["id"], context=f"image {index}.id"),
                name=_string(record["name"], context=f"image {index}.name"),
                family=_string(record["family"], context=f"image {index}.family"),
                version=_string(record["version"], context=f"image {index}.version"),
                architecture=architecture,
                region=_region(record["region"], context=f"image {index}.region"),
            )
        )
    return tuple(sorted(images, key=lambda item: (item.region.name, item.image_id)))


def _parse_regions(encoded: bytes, request: InventoryRequest) -> tuple[Region, ...]:
    envelope = _envelope(encoded, request=request)
    _expect_exact_keys(envelope, {"data"}, context=request.request_id)
    regions = tuple(
        _region(item, context=f"region {index}")
        for index, item in enumerate(_list(envelope["data"], context="region data"))
    )
    if len({region.name for region in regions}) != len(regions):
        raise LambdaCloudContractError("region inventory contains duplicate names")
    return tuple(sorted(regions, key=lambda item: item.name))


def _parse_ssh_keys(encoded: bytes, request: InventoryRequest) -> tuple[SSHKeyIdentity, ...]:
    envelope = _envelope(encoded, request=request)
    _expect_exact_keys(envelope, {"data"}, context=request.request_id)
    keys: list[SSHKeyIdentity] = []
    for index, raw in enumerate(_list(envelope["data"], context="SSH key data")):
        record = _mapping(raw, context=f"SSH key {index}")
        _expect_exact_keys(record, {"id", "name", "public_key"}, context=f"SSH key {index}")
        _string(record["public_key"], context=f"SSH key {index}.public_key")
        keys.append(
            SSHKeyIdentity(
                key_id=_string(record["id"], context=f"SSH key {index}.id"),
                name=_string(record["name"], context=f"SSH key {index}.name"),
            )
        )
    if len({key.key_id for key in keys}) != len(keys) or len({key.name for key in keys}) != len(
        keys
    ):
        raise LambdaCloudContractError("SSH key IDs and names must be unique")
    return tuple(sorted(keys, key=lambda item: (item.name, item.key_id)))


def _parse_firewall_rule(value: object, *, context: str) -> FirewallRule:
    record = _mapping(value, context=context)
    _expect_exact_keys(
        record,
        {"protocol", "source_network", "description"},
        optional={"port_range"},
        context=context,
    )
    protocol = _string(record["protocol"], context=f"{context}.protocol")
    if protocol not in {"tcp", "udp", "icmp", "all"}:
        raise LambdaCloudContractError("firewall protocol schema drifted")
    raw_range = record.get("port_range")
    port_range: tuple[int, int] | None = None
    if raw_range is not None:
        values = _list(raw_range, context=f"{context}.port_range")
        if len(values) != 2:
            raise LambdaCloudContractError("firewall port range must contain two values")
        port_range = (
            _integer(values[0], context=f"{context}.port_start", minimum=1),
            _integer(values[1], context=f"{context}.port_end", minimum=1),
        )
        if port_range[0] > port_range[1] or port_range[1] > 65_535:
            raise LambdaCloudContractError("firewall port range is invalid")
    if protocol == "icmp" and port_range is not None:
        raise LambdaCloudContractError("ICMP firewall rule cannot contain a port range")
    if protocol != "icmp" and port_range is None:
        raise LambdaCloudContractError("TCP/UDP/all firewall rule requires a port range")
    source_network = _string(record["source_network"], context=f"{context}.source_network")
    invalid_network = False
    try:
        network = ipaddress.ip_network(source_network, strict=False)
    except ValueError:
        network = None
        invalid_network = True
    if invalid_network:
        raise LambdaCloudContractError("firewall source network is not valid IPv4 CIDR")
    if not isinstance(network, ipaddress.IPv4Network):
        raise LambdaCloudContractError("firewall source network must be IPv4")
    return FirewallRule(
        protocol=protocol,
        port_range=port_range,
        source_network=network.with_prefixlen,
        description=_string(
            record["description"], context=f"{context}.description", allow_empty=True
        ),
    )


def _parse_regional_firewall_rulesets(
    regional_encoded: bytes, regional_request: InventoryRequest
) -> tuple[FirewallRuleset, ...]:
    regional_envelope = _envelope(regional_encoded, request=regional_request)
    _expect_exact_keys(regional_envelope, {"data"}, context=regional_request.request_id)
    rulesets: list[FirewallRuleset] = []
    for index, raw in enumerate(_list(regional_envelope["data"], context="regional firewall data")):
        record = _mapping(raw, context=f"regional firewall ruleset {index}")
        _expect_exact_keys(
            record,
            {"id", "name", "region", "rules", "created", "instance_ids"},
            context=f"regional firewall ruleset {index}",
        )
        _string(record["created"], context=f"regional firewall ruleset {index}.created")
        instance_ids = _list(
            record["instance_ids"], context=f"regional firewall ruleset {index}.instance_ids"
        )
        for instance_id in instance_ids:
            _string(instance_id, context="regional firewall instance ID")
        rulesets.append(
            FirewallRuleset(
                ruleset_id=_string(record["id"], context=f"regional ruleset {index}.id"),
                name=_string(record["name"], context=f"regional ruleset {index}.name"),
                scope="regional",
                region=_region(record["region"], context=f"regional ruleset {index}.region"),
                rules=tuple(
                    _parse_firewall_rule(
                        item, context=f"regional ruleset {index}.rule {rule_index}"
                    )
                    for rule_index, item in enumerate(
                        _list(record["rules"], context=f"regional ruleset {index}.rules")
                    )
                ),
            )
        )
    if len({item.ruleset_id for item in rulesets}) != len(rulesets):
        raise LambdaCloudContractError("regional firewall ruleset IDs must be unique")
    return tuple(sorted(rulesets, key=lambda item: item.ruleset_id))


def _parse_global_firewall_ruleset(
    global_encoded: bytes, global_request: InventoryRequest
) -> FirewallRuleset:
    global_envelope = _envelope(global_encoded, request=global_request)
    _expect_exact_keys(global_envelope, {"data"}, context=global_request.request_id)
    global_record = _mapping(global_envelope["data"], context="global firewall ruleset")
    _expect_exact_keys(global_record, {"id", "name", "rules"}, context="global ruleset")
    if global_record["id"] != "global":
        raise LambdaCloudContractError("global firewall ruleset ID drifted")
    return FirewallRuleset(
        ruleset_id="global",
        name=_string(global_record["name"], context="global ruleset name"),
        scope="global",
        region=None,
        rules=tuple(
            _parse_firewall_rule(item, context=f"global ruleset rule {index}")
            for index, item in enumerate(
                _list(global_record["rules"], context="global ruleset rules")
            )
        ),
    )


def _parse_firewall_rulesets(
    regional_encoded: bytes,
    regional_request: InventoryRequest,
    global_encoded: bytes,
    global_request: InventoryRequest,
) -> tuple[FirewallRuleset, ...]:
    rulesets = [
        *_parse_regional_firewall_rulesets(regional_encoded, regional_request),
        _parse_global_firewall_ruleset(global_encoded, global_request),
    ]
    if len({item.ruleset_id for item in rulesets}) != len(rulesets):
        raise LambdaCloudContractError("firewall ruleset IDs must be unique")
    return tuple(sorted(rulesets, key=lambda item: (item.scope, item.ruleset_id)))


def _parse_running_instances(
    encoded: bytes, request: InventoryRequest
) -> tuple[RunningInstance, ...]:
    envelope = _envelope(encoded, request=request)
    _expect_exact_keys(envelope, {"data"}, context=request.request_id)
    required = {
        "id",
        "status",
        "ssh_key_names",
        "file_system_names",
        "region",
        "instance_type",
        "actions",
    }
    optional = {
        "name",
        "ip",
        "private_ip",
        "file_system_mounts",
        "hostname",
        "jupyter_token",
        "jupyter_url",
        "tags",
        "firewall_rulesets",
    }
    instances: list[RunningInstance] = []
    for index, raw in enumerate(_list(envelope["data"], context="running instance data")):
        record = _mapping(raw, context=f"running instance {index}")
        _expect_exact_keys(record, required, optional=optional, context=f"running instance {index}")
        instance_type = _parse_instance_type_record(
            {
                "instance_type": record["instance_type"],
                "regions_with_capacity_available": [],
            },
            context=f"running instance {index}.instance_type",
        )
        tags: list[tuple[str, str]] = []
        for tag_index, raw_tag in enumerate(
            _list(record.get("tags", []), context=f"running instance {index}.tags")
        ):
            tag = _mapping(raw_tag, context=f"running instance {index}.tag {tag_index}")
            _expect_exact_keys(tag, {"key", "value"}, context=f"instance tag {tag_index}")
            tags.append(
                (
                    _string(tag["key"], context="instance tag key"),
                    _string(tag["value"], context="instance tag value", allow_empty=True),
                )
            )
        firewall_ids: list[str] = []
        for fw_index, raw_fw in enumerate(
            _list(
                record.get("firewall_rulesets", []),
                context=f"running instance {index}.firewall_rulesets",
            )
        ):
            fw = _mapping(raw_fw, context=f"instance firewall ruleset {fw_index}")
            _expect_exact_keys(fw, {"id"}, context=f"instance firewall ruleset {fw_index}")
            firewall_ids.append(_string(fw["id"], context="instance firewall ruleset ID"))
        filesystems = _list(
            record["file_system_names"], context=f"running instance {index}.filesystems"
        )
        for filesystem in filesystems:
            _string(filesystem, context="running instance filesystem")
        name_value = record.get("name")
        if name_value is not None and not isinstance(name_value, str):
            raise LambdaCloudContractError("running instance name schema drifted")
        instances.append(
            RunningInstance(
                instance_id=_string(record["id"], context=f"running instance {index}.id"),
                name=name_value,
                status=_string(record["status"], context=f"running instance {index}.status"),
                region_name=_region(
                    record["region"], context=f"running instance {index}.region"
                ).name,
                instance_type_name=instance_type.name,
                file_system_count=len(filesystems),
                firewall_ruleset_ids=tuple(sorted(firewall_ids)),
                t07_owned=(
                    ("giclab.experiment", "EXP-0001") in tags and ("giclab.gate", "T07-L2") in tags
                ),
            )
        )
    if len({item.instance_id for item in instances}) != len(instances):
        raise LambdaCloudContractError("running instance IDs must be unique")
    return tuple(sorted(instances, key=lambda item: item.instance_id))


class InventoryResponsePlan(Protocol):
    @property
    def requests(self) -> tuple[InventoryRequest, ...]: ...

    @property
    def max_total_response_bytes(self) -> int: ...


_PAGINATION_KEYS: Final = frozenset(
    {
        "page_token",
        "next_page_token",
        "next_token",
        "continuation_token",
        "cursor",
        "has_more",
    }
)


def _pagination_marker_present(value: object) -> bool:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if key in _PAGINATION_KEYS and child not in (None, False, "", [], {}):
                return True
            if _pagination_marker_present(child):
                return True
    elif isinstance(value, list):
        return any(_pagination_marker_present(child) for child in value)
    return False


@dataclass(slots=True)
class IncrementalInventoryParser:
    """Validate and normalize each V2 response before the next request intent."""

    plan: InventoryResponsePlan
    accepted_requests: int = 0
    total_response_bytes: int = 0
    binding: AccountWorkspaceBinding | None = None
    instance_types: tuple[InstanceTypeOffer, ...] | None = None
    images: tuple[ProviderImage, ...] | None = None
    regions: tuple[Region, ...] | None = None
    ssh_keys: tuple[SSHKeyIdentity, ...] | None = None
    regional_firewall_rulesets: tuple[FirewallRuleset, ...] | None = None
    global_firewall_ruleset: FirewallRuleset | None = None
    running_instances: tuple[RunningInstance, ...] | None = None

    def accept(self, request: InventoryRequest, encoded: bytes) -> None:
        if self.accepted_requests >= len(self.plan.requests):
            raise InventoryResponseValidationError(
                InventoryResponseFailureKind.SCHEMA_VALIDATION,
                "L1_RESPONSE_SET_OVERFLOW",
            )
        if request != self.plan.requests[self.accepted_requests]:
            raise InventoryResponseValidationError(
                InventoryResponseFailureKind.SCHEMA_VALIDATION,
                "L1_RESPONSE_ORDER_DRIFT",
            )
        if (
            len(encoded) > request.max_response_bytes
            or self.total_response_bytes + len(encoded) > self.plan.max_total_response_bytes
        ):
            raise InventoryResponseValidationError(
                InventoryResponseFailureKind.SCHEMA_VALIDATION,
                "L1_RESPONSE_SIZE_DRIFT",
            )
        try:
            decoded = _json_object(encoded, context="incremental inventory response")
        except LambdaCloudContractError:
            raise InventoryResponseValidationError(
                InventoryResponseFailureKind.JSON_DECODE,
                "L1_RESPONSE_JSON_INVALID",
            ) from None
        if _pagination_marker_present(decoded):
            raise InventoryResponseValidationError(
                InventoryResponseFailureKind.PAGINATION,
                "L1_RESPONSE_PAGINATION_PRESENT",
            )
        try:
            if request.request_id == "account-workspace-identity":
                binding = _parse_account_binding(encoded, request)
                if not binding.source_page_complete:
                    raise InventoryResponseValidationError(
                        InventoryResponseFailureKind.PAGINATION,
                        "L1_RESPONSE_PAGINATION_PRESENT",
                    )
                self.binding = binding
            elif request.request_id == "instance-types":
                self.instance_types = _parse_instance_types(encoded, request)
            elif request.request_id == "images":
                self.images = _parse_images(encoded, request)
            elif request.request_id == "regions":
                self.regions = _parse_regions(encoded, request)
            elif request.request_id == "ssh-keys":
                self.ssh_keys = _parse_ssh_keys(encoded, request)
            elif request.request_id == "firewall-rulesets":
                self.regional_firewall_rulesets = _parse_regional_firewall_rulesets(
                    encoded, request
                )
            elif request.request_id == "global-firewall-ruleset":
                self.global_firewall_ruleset = _parse_global_firewall_ruleset(encoded, request)
            elif request.request_id == "running-instances":
                self.running_instances = _parse_running_instances(encoded, request)
            else:
                raise LambdaCloudContractError("inventory response ID drifted")
        except InventoryResponseValidationError:
            raise
        except LambdaCloudContractError:
            raise InventoryResponseValidationError(
                InventoryResponseFailureKind.SCHEMA_VALIDATION,
                "L1_RESPONSE_SCHEMA_DRIFT",
            ) from None
        self.total_response_bytes += len(encoded)
        self.accepted_requests += 1

    def finish(self) -> Inventory:
        if self.accepted_requests != len(self.plan.requests):
            raise InventoryResponseValidationError(
                InventoryResponseFailureKind.SCHEMA_VALIDATION,
                "L1_RESPONSE_SET_INCOMPLETE",
            )
        if (
            self.binding is None
            or self.instance_types is None
            or self.images is None
            or self.regions is None
            or self.ssh_keys is None
            or self.regional_firewall_rulesets is None
            or self.global_firewall_ruleset is None
            or self.running_instances is None
        ):
            raise InventoryResponseValidationError(
                InventoryResponseFailureKind.SCHEMA_VALIDATION,
                "L1_RESPONSE_TYPED_STATE_INCOMPLETE",
            )
        firewall_rulesets = (
            *self.regional_firewall_rulesets,
            self.global_firewall_ruleset,
        )
        if len({item.ruleset_id for item in firewall_rulesets}) != len(firewall_rulesets):
            raise InventoryResponseValidationError(
                InventoryResponseFailureKind.SCHEMA_VALIDATION,
                "L1_FIREWALL_IDENTITY_DRIFT",
            )
        inventory = Inventory(
            binding=self.binding,
            instance_types=self.instance_types,
            images=self.images,
            regions=self.regions,
            ssh_keys=self.ssh_keys,
            firewall_rulesets=tuple(
                sorted(firewall_rulesets, key=lambda item: (item.scope, item.ruleset_id))
            ),
            running_instances=self.running_instances,
        )
        if not inventory.regions:
            raise InventoryResponseValidationError(
                InventoryResponseFailureKind.SCHEMA_VALIDATION,
                "L1_REGION_INVENTORY_EMPTY",
            )
        known_regions = {region.name for region in inventory.regions}
        if any(
            region.name not in known_regions
            for offer in inventory.instance_types
            for region in offer.capacity_regions
        ) or any(image.region.name not in known_regions for image in inventory.images):
            raise InventoryResponseValidationError(
                InventoryResponseFailureKind.SCHEMA_VALIDATION,
                "L1_REGION_REFERENCE_DRIFT",
            )
        return inventory


def parse_inventory_responses(
    responses: Mapping[str, bytes], plan: ReadOnlyInventoryPlan
) -> Inventory:
    """Strictly parse bounded responses without persisting raw provider data."""

    expected_ids = {request.request_id for request in plan.requests}
    if set(responses) != expected_ids:
        raise LambdaCloudContractError("inventory response set differs from the authorized GET set")
    if sum(len(body) for body in responses.values()) > plan.max_total_response_bytes:
        raise LambdaCloudContractError("inventory aggregate responses exceed the byte cap")
    requests = {request.request_id: request for request in plan.requests}
    inventory = Inventory(
        binding=_parse_account_binding(
            responses["account-workspace-identity"], requests["account-workspace-identity"]
        ),
        instance_types=_parse_instance_types(
            responses["instance-types"], requests["instance-types"]
        ),
        images=_parse_images(responses["images"], requests["images"]),
        regions=_parse_regions(responses["regions"], requests["regions"]),
        ssh_keys=_parse_ssh_keys(responses["ssh-keys"], requests["ssh-keys"]),
        firewall_rulesets=_parse_firewall_rulesets(
            responses["firewall-rulesets"],
            requests["firewall-rulesets"],
            responses["global-firewall-ruleset"],
            requests["global-firewall-ruleset"],
        ),
        running_instances=_parse_running_instances(
            responses["running-instances"], requests["running-instances"]
        ),
    )
    if not inventory.regions:
        raise LambdaCloudContractError("region inventory is empty")
    known_regions = {region.name for region in inventory.regions}
    if any(
        region.name not in known_regions
        for offer in inventory.instance_types
        for region in offer.capacity_regions
    ):
        raise LambdaCloudContractError("capacity references an undeclared region")
    if any(image.region.name not in known_regions for image in inventory.images):
        raise LambdaCloudContractError("image references an undeclared region")
    return inventory


def select_compute_candidate(inventory: Inventory) -> ComputeCandidate:
    """Select the cheapest exact type/region/image tuple or fail without escalation."""

    if any(
        instance.t07_owned or instance.name == QUALIFICATION_INSTANCE_NAME
        for instance in inventory.running_instances
    ):
        raise InstanceSelectionError(
            SelectionFailureCode.EXISTING_T07_INSTANCE,
            "an existing T07 qualification instance blocks launch",
        )
    global_rulesets = [item for item in inventory.firewall_rulesets if item.scope == "global"]
    if len(global_rulesets) != 1 or not global_rulesets[0].is_ssh_only:
        raise InstanceSelectionError(
            SelectionFailureCode.GLOBAL_FIREWALL_NOT_SSH_ONLY,
            "effective global firewall is not strictly SSH-only",
        )
    regional_ssh_rulesets: dict[str, list[FirewallRuleset]] = {}
    for ruleset in inventory.firewall_rulesets:
        if ruleset.scope == "regional" and ruleset.region is not None and ruleset.is_ssh_only:
            regional_ssh_rulesets.setdefault(ruleset.region.name, []).append(ruleset)
    candidates: list[tuple[InstanceTypeOffer, Region, ProviderImage, tuple[str, ...]]] = []
    for offer in inventory.instance_types:
        if (
            offer.architecture != "x86_64"
            or offer.specs.gpus > 1
            or offer.specs.vcpus < 8
            or offer.specs.memory_gib < 16
            or offer.specs.storage_gib < 100
            or offer.price_cents_per_hour > MAX_PRICE_CENTS_PER_HOUR
        ):
            continue
        for region in offer.capacity_regions:
            if region.name in FIREWALL_UNENFORCED_REGIONS:
                continue
            rulesets = regional_ssh_rulesets.get(region.name, [])
            if not rulesets:
                continue
            for image in inventory.images:
                if (
                    image.region.name == region.name
                    and image.architecture == "x86_64"
                    and image.family == QUALIFICATION_IMAGE_FAMILY
                ):
                    candidates.append(
                        (
                            offer,
                            region,
                            image,
                            tuple(sorted(item.ruleset_id for item in rulesets)),
                        )
                    )
    if not candidates:
        raise InstanceSelectionError(
            SelectionFailureCode.NO_QUALIFYING_CANDIDATE,
            "no currently available x86_64 candidate satisfies "
            "price/resource/image/firewall policy",
        )
    offer, region, image, ruleset_ids = min(
        candidates,
        key=lambda item: (
            item[0].price_cents_per_hour,
            item[0].name,
            item[1].name,
            item[2].image_id,
        ),
    )
    list_cap = qualification_list_price_cap_cents(
        offer.price_cents_per_hour, MAX_QUALIFICATION_WALL_SECONDS
    )
    if list_cap > MAX_PROVIDER_COMPUTE_CENTS:
        raise LambdaCloudContractError("selected candidate exceeds provider compute hard cap")
    return ComputeCandidate(
        instance_type_name=offer.name,
        region_name=region.name,
        image_id=image.image_id,
        image_name=image.name,
        image_family=image.family,
        image_version=image.version,
        architecture=offer.architecture,
        price_cents_per_hour=offer.price_cents_per_hour,
        vcpus=offer.specs.vcpus,
        memory_gib=offer.specs.memory_gib,
        storage_gib=offer.specs.storage_gib,
        gpus=offer.specs.gpus,
        eligible_firewall_ruleset_ids=ruleset_ids,
        qualification_list_price_cap_cents=list_cap,
        provider_compute_hard_cap_cents=MAX_PROVIDER_COMPUTE_CENTS,
    )


def qualification_list_price_cap_cents(price_cents_per_hour: int, wall_seconds: int) -> int:
    """Return the exact minute-rounded list-price ceiling in whole cents."""

    if type(price_cents_per_hour) is not int or price_cents_per_hour < 0:
        raise LambdaCloudContractError("hourly price must be a nonnegative integer cents value")
    if type(wall_seconds) is not int or wall_seconds < 1:
        raise LambdaCloudContractError("wall limit must be a positive integer")
    billed_minutes = (wall_seconds + 59) // 60
    numerator = price_cents_per_hour * billed_minutes
    return (numerator + 59) // 60


def bind_selected_infrastructure(
    inventory: Inventory,
    candidate: ComputeCandidate,
    *,
    approved_ssh_key_id: str,
    approved_ssh_key_name: str,
    approved_firewall_ruleset_id: str,
) -> SelectedInfrastructure:
    """Bind exact pre-existing identities chosen after inventory review."""

    # Never accept a caller-constructed candidate. Recompute the deterministic
    # selection from the exact inventory and require value equality before binding
    # an account resource or rendering a launch request.
    if candidate != select_compute_candidate(inventory):
        raise LambdaCloudContractError("candidate is not the exact inventory selection")

    matching_keys = [
        key
        for key in inventory.ssh_keys
        if key.key_id == approved_ssh_key_id and key.name == approved_ssh_key_name
    ]
    if len(matching_keys) != 1:
        raise LambdaCloudContractError("approved SSH key ID/name pair is absent or ambiguous")
    matching_rulesets = [
        item
        for item in inventory.firewall_rulesets
        if item.ruleset_id == approved_firewall_ruleset_id
        and item.ruleset_id in candidate.eligible_firewall_ruleset_ids
        and item.scope == "regional"
        and item.region is not None
        and item.region.name == candidate.region_name
        and item.is_ssh_only
    ]
    if len(matching_rulesets) != 1:
        raise LambdaCloudContractError("approved firewall identity is not eligible and SSH-only")
    return SelectedInfrastructure(
        account_lrn_sha256=inventory.binding.account_lrn_sha256,
        workspace_lrn_sha256=inventory.binding.workspace_lrn_sha256,
        candidate=candidate,
        ssh_key=matching_keys[0],
        firewall_ruleset=matching_rulesets[0],
    )


def render_no_filesystem_launch_request(
    selected: SelectedInfrastructure, *, authorization_reference: str
) -> dict[str, object]:
    """Render the exact future one-instance request; this function performs no request."""

    if _IDENTIFIER.fullmatch(authorization_reference) is None:
        raise LambdaCloudContractError("launch authorization reference is not secret-safe")
    body: dict[str, object] = {
        "region_name": selected.candidate.region_name,
        "instance_type_name": selected.candidate.instance_type_name,
        "ssh_key_names": [selected.ssh_key.name],
        "file_system_names": [],
        "file_system_mounts": [],
        "name": QUALIFICATION_INSTANCE_NAME,
        "image": {"id": selected.candidate.image_id},
        "tags": [
            {"key": "giclab.experiment", "value": "EXP-0001"},
            {"key": "giclab.gate", "value": "T07-L2"},
            {"key": "giclab.authorization", "value": authorization_reference},
        ],
        "firewall_rulesets": [{"id": selected.firewall_ruleset.ruleset_id}],
    }
    validate_no_filesystem_launch_request(body, selected)
    return body


def validate_no_filesystem_launch_request(
    body: Mapping[str, object], selected: SelectedInfrastructure
) -> None:
    expected_keys = {
        "region_name",
        "instance_type_name",
        "ssh_key_names",
        "file_system_names",
        "file_system_mounts",
        "name",
        "image",
        "tags",
        "firewall_rulesets",
    }
    _expect_exact_keys(body, expected_keys, context="qualification launch body")
    if body["region_name"] != selected.candidate.region_name:
        raise LambdaCloudContractError("launch region is not inventory-bound")
    if body["instance_type_name"] != selected.candidate.instance_type_name:
        raise LambdaCloudContractError("launch type is not inventory-bound")
    if body["ssh_key_names"] != [selected.ssh_key.name]:
        raise LambdaCloudContractError("launch must bind exactly one approved SSH key")
    if body["file_system_names"] != [] or body["file_system_mounts"] != []:
        raise LambdaCloudContractError("qualification launch must attach no filesystem")
    if body["name"] != QUALIFICATION_INSTANCE_NAME:
        raise LambdaCloudContractError("qualification instance name drifted")
    if body["image"] != {"id": selected.candidate.image_id}:
        raise LambdaCloudContractError("launch must use the exact inventory image ID")
    if body["firewall_rulesets"] != [{"id": selected.firewall_ruleset.ruleset_id}]:
        raise LambdaCloudContractError("launch firewall binding drifted")
    tags = _list(body["tags"], context="launch tags")
    if len(tags) != 3:
        raise LambdaCloudContractError("launch tag identity set drifted")
    normalized_tags: list[dict[str, object]] = []
    for index, raw_tag in enumerate(tags):
        tag = _mapping(raw_tag, context=f"launch tag {index}")
        _expect_exact_keys(tag, {"key", "value"}, context=f"launch tag {index}")
        normalized_tags.append(tag)
    if normalized_tags[:2] != [
        {"key": "giclab.experiment", "value": "EXP-0001"},
        {"key": "giclab.gate", "value": "T07-L2"},
    ]:
        raise LambdaCloudContractError("launch ownership tags drifted")
    authorization_tag = normalized_tags[2]
    if authorization_tag.get("key") != "giclab.authorization" or not isinstance(
        authorization_tag.get("value"), str
    ):
        raise LambdaCloudContractError("launch authorization tag drifted")
    authorization_value = str(authorization_tag["value"])
    if _IDENTIFIER.fullmatch(authorization_value) is None:
        raise LambdaCloudContractError("launch authorization tag is not secret-safe")
    if "user_data" in body or "quantity" in body:
        raise LambdaCloudContractError("qualification launch forbids hidden config and quantity")


class InventoryArtifactRunBinding(Protocol):
    @property
    def run_id(self) -> str: ...

    @property
    def repository_commit(self) -> str: ...

    @property
    def authorization_reference(self) -> str: ...

    @property
    def authorization_sha256(self) -> str: ...


def inventory_document(
    inventory: Inventory,
    candidate: ComputeCandidate | None,
    *,
    observed_at_utc: str,
    inventory_plan_sha256: str,
    run_binding: InventoryArtifactRunBinding,
    selection_failure: InstanceSelectionError | None = None,
    plan_id: str = INVENTORY_PLAN_ID,
    run_attempt: int = 1,
    limits_document: Mapping[str, int] | None = None,
    request_ledger_contract: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Return the bounded redacted L1 artifact; no raw secret-bearing fields survive."""

    def region_document(region: Region) -> dict[str, str]:
        return {"name": region.name}

    if not observed_at_utc.endswith("Z") or "T" not in observed_at_utc:
        raise LambdaCloudContractError("inventory observation time must be an explicit UTC value")
    if _SHA256.fullmatch(inventory_plan_sha256) is None:
        raise LambdaCloudContractError("inventory artifact plan hash is not canonical")
    is_v1 = (
        plan_id == INVENTORY_PLAN_ID and run_binding.run_id == INVENTORY_RUN_ID and run_attempt == 1
    )
    is_v2 = (
        plan_id == INVENTORY_PLAN_V2_ID
        and run_binding.run_id == INVENTORY_RUN_V2_ID
        and run_attempt == 2
    )
    if not (is_v1 or is_v2):
        raise LambdaCloudContractError("inventory artifact plan/run identity drifted")
    if is_v1 and (limits_document is not None or request_ledger_contract is not None):
        raise LambdaCloudContractError("historical V1 inventory cannot carry V2 controls")
    if is_v2 and (limits_document is None or request_ledger_contract is None):
        raise LambdaCloudContractError("V2 inventory requires ledger and limit bindings")
    if (candidate is None) == (selection_failure is None):
        raise LambdaCloudContractError(
            "inventory artifact requires exactly one selected candidate or typed selection failure"
        )
    selection: dict[str, object]
    if candidate is not None:
        selection = {
            "state": "selected",
            "instance_type_name": candidate.instance_type_name,
            "region_name": candidate.region_name,
            "image_id": candidate.image_id,
            "image_name": candidate.image_name,
            "image_family": candidate.image_family,
            "image_version": candidate.image_version,
            "architecture": candidate.architecture,
            "price_cents_per_hour": candidate.price_cents_per_hour,
            "vcpus": candidate.vcpus,
            "memory_gib": candidate.memory_gib,
            "storage_gib": candidate.storage_gib,
            "gpus": candidate.gpus,
            "eligible_firewall_ruleset_ids": list(candidate.eligible_firewall_ruleset_ids),
            "qualification_list_price_cap_cents": (candidate.qualification_list_price_cap_cents),
            "provider_compute_hard_cap_cents": candidate.provider_compute_hard_cap_cents,
            "ssh_key_binding": None,
            "firewall_ruleset_binding": None,
        }
    else:
        assert selection_failure is not None
        selection = {
            "state": "blocked",
            "reason_code": selection_failure.code.value,
            "ssh_key_binding": None,
            "firewall_ruleset_binding": None,
        }
    default_limits: dict[str, int] = {
        "provider_api_calls": MAX_INVENTORY_CALLS,
        "provider_wall_seconds": MAX_INVENTORY_WALL_SECONDS,
        "request_start_spacing_seconds": MIN_INVENTORY_REQUEST_SPACING_SECONDS,
        "archive_wall_seconds": MAX_INVENTORY_ARCHIVE_WALL_SECONDS,
        "total_wall_seconds": MAX_INVENTORY_TOTAL_WALL_SECONDS,
        "raw_response_bytes": MAX_INVENTORY_TOTAL_RESPONSE_BYTES,
        "retained_output_bytes": MAX_INVENTORY_RETAINED_BYTES,
        "local_copy_record_bytes": MAX_INVENTORY_LOCAL_RECORD_BYTES,
        "external_archive_bytes": MAX_INVENTORY_ARCHIVE_BYTES,
        "aggregate_retained_bytes": MAX_INVENTORY_AGGREGATE_RETAINED_BYTES,
        "local_command_calls": MAX_INVENTORY_LOCAL_COMMAND_CALLS,
        "local_command_output_bytes": MAX_INVENTORY_LOCAL_COMMAND_OUTPUT_BYTES,
        "local_file_creates": MAX_INVENTORY_LOCAL_FILE_CREATES,
        "external_file_creates": MAX_INVENTORY_EXTERNAL_FILE_CREATES,
        "external_directory_creates": MAX_INVENTORY_EXTERNAL_DIRECTORY_CREATES,
        "local_prewrite_floor_bytes": MAX_INVENTORY_LOCAL_PREWRITE_FLOOR_BYTES,
        "local_retained_floor_bytes": MAX_INVENTORY_LOCAL_RETAINED_FLOOR_BYTES,
        "automatic_retries": 0,
        "cloud_mutations": 0,
        "provider_cost_cents": 0,
        "model_calls": 0,
        "model_tokens": 0,
        "browser_actions": 0,
        "sira_executions": 0,
    }
    document: dict[str, object] = {
        "schema_version": "0.1.0" if is_v1 else "0.2.0",
        "provider": "lambda-on-demand-cloud",
        "api_spec": {"version": API_SPEC_VERSION, "sha256": API_SPEC_SHA256},
        "inventory_plan": {
            "plan_id": plan_id,
            "sha256": inventory_plan_sha256,
        },
        "run_identity": {
            "run_id": run_binding.run_id,
            "attempt": run_attempt,
            "experiment_id": "EXP-0001",
            "profile_plan_id": "PLAN-EXP0001-SMOKE",
            "gate": "T07-L1",
            "branch": LAMBDA_BRANCH,
            "repository_commit": run_binding.repository_commit,
        },
        "authorization_binding": {
            "authorization_reference": run_binding.authorization_reference,
            "authorization_sha256": run_binding.authorization_sha256,
            "authorized": True,
        },
        "limits": default_limits if limits_document is None else dict(limits_document),
        "observed_at_utc": observed_at_utc,
        "account_binding": {
            "account_lrn_sha256": inventory.binding.account_lrn_sha256,
            "workspace_lrn_sha256": inventory.binding.workspace_lrn_sha256,
            "source_event_count": inventory.binding.source_event_count,
            "source_page_complete": inventory.binding.source_page_complete,
        },
        "instance_types": [
            {
                "name": offer.name,
                "architecture": offer.architecture,
                "price_cents_per_hour": offer.price_cents_per_hour,
                "specs": {
                    "vcpus": offer.specs.vcpus,
                    "memory_gib": offer.specs.memory_gib,
                    "storage_gib": offer.specs.storage_gib,
                    "gpus": offer.specs.gpus,
                },
                "capacity_regions": [region_document(region) for region in offer.capacity_regions],
            }
            for offer in inventory.instance_types
        ],
        "images": [
            {
                "id": item.image_id,
                "name": item.name,
                "family": item.family,
                "version": item.version,
                "architecture": item.architecture,
                "region": region_document(item.region),
            }
            for item in inventory.images
        ],
        "regions": [region_document(item) for item in inventory.regions],
        "ssh_keys": [{"id": item.key_id, "name": item.name} for item in inventory.ssh_keys],
        "firewall_rulesets": [
            {
                "id": item.ruleset_id,
                "name": item.name,
                "scope": item.scope,
                "region_name": item.region.name if item.region is not None else None,
                "ssh_only": item.is_ssh_only,
                "rules": [
                    {
                        "protocol": rule.protocol,
                        "port_range": list(rule.port_range) if rule.port_range else None,
                        "source_network": rule.source_network,
                    }
                    for rule in item.rules
                ],
            }
            for item in inventory.firewall_rulesets
        ],
        "running_instances": [
            {
                "id": item.instance_id,
                "name": item.name,
                "status": item.status,
                "region_name": item.region_name,
                "instance_type_name": item.instance_type_name,
                "file_system_count": item.file_system_count,
                "firewall_ruleset_ids": list(item.firewall_ruleset_ids),
                "t07_owned": item.t07_owned,
            }
            for item in inventory.running_instances
        ],
        "selection": selection,
        "redaction": {
            "raw_responses_retained": False,
            "api_key_retained": False,
            "ssh_public_keys_retained": False,
            "instance_ip_addresses_retained": False,
            "firewall_source_cidrs_retained": True,
            "jupyter_credentials_retained": False,
            "audit_actor_fields_retained": False,
        },
    }
    if request_ledger_contract is not None:
        document["request_ledger"] = dict(request_ledger_contract)
    encoded = json.dumps(document, allow_nan=False, sort_keys=True, separators=(",", ":")).encode()
    if len(encoded) > MAX_INVENTORY_RETAINED_BYTES:
        raise LambdaCloudContractError("redacted inventory artifact exceeds retained-output cap")
    return document


def canonical_inventory_bytes(document: Mapping[str, object]) -> bytes:
    encoded = (
        json.dumps(document, allow_nan=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()
    if len(encoded) > MAX_INVENTORY_RETAINED_BYTES:
        raise LambdaCloudContractError("redacted inventory artifact exceeds retained-output cap")
    return encoded


def qualification_lifecycle_contract() -> QualificationLifecycleContract:
    contract = QualificationLifecycleContract(
        phases=tuple(QualificationPhase),
        max_launch_requests=1,
        max_termination_targets=1,
        max_termination_requests=3,
        launch_retries=0,
        terminate_by_provider_api=True,
        immutable_instance_id_required=True,
        terminate_on_every_post_launch_exit=True,
        require_terminal_nonbillable_state=True,
    )
    contract.validate()
    return contract


def validate_termination_request(
    body: Mapping[str, object], *, minted_instance_id: str, unrelated_instance_ids: Sequence[str]
) -> None:
    """Reject termination of anything except the exact instance minted by this attempt."""

    _expect_exact_keys(body, {"instance_ids"}, context="termination body")
    if body["instance_ids"] != [minted_instance_id]:
        raise LambdaCloudContractError("termination must target only the minted instance ID")
    if minted_instance_id in set(unrelated_instance_ids):
        raise LambdaCloudContractError("minted instance ID collides with pre-launch inventory")


def validate_host_qualification_evidence_semantics(
    instance: Mapping[str, object],
) -> list[str]:
    """Enforce success-evidence relations that JSON Schema cannot express."""

    errors: list[str] = []

    def child(name: str) -> dict[str, object]:
        value = instance.get(name)
        if not isinstance(value, Mapping) or any(not isinstance(key, str) for key in value):
            return {}
        return dict(value)

    authorization = child("authorization")
    run_identity = child("run_identity")
    provider = child("provider_identity")
    budget = child("budget")
    pacing = child("provider_request_pacing")
    launch = child("launch")
    request_body_raw = launch.get("request_body")
    request_body = (
        dict(request_body_raw)
        if isinstance(request_body_raw, Mapping)
        and all(isinstance(key, str) for key in request_body_raw)
        else {}
    )
    containment = child("containment_probe")
    local_storage = child("local_active_storage")
    labels_raw = containment.get("labels")
    labels = (
        dict(labels_raw)
        if isinstance(labels_raw, Mapping) and all(isinstance(key, str) for key in labels_raw)
        else {}
    )
    copy = child("evidence_copy")
    archive_copy = child("archive_copy")
    termination = child("termination")
    usage = child("actual_usage")
    compute_ledger = child("compute_ledger")
    ssh_trust = child("ssh_trust")
    if authorization.get("authorized") is not True:
        errors.append("authorization.authorized: successful evidence requires true authority")
    authorization_reference = authorization.get("authorization_reference")
    if labels.get("authorization") != authorization_reference:
        errors.append("containment_probe.labels.authorization: does not match authorization")
    if labels.get("repository_commit") != run_identity.get("repository_commit"):
        errors.append("containment_probe.labels.repository_commit: does not match run identity")
    if labels.get("attempt") != run_identity.get("run_id"):
        errors.append("containment_probe.labels.attempt: does not match run identity")
    expected_known_hosts = f"artifacts/t07/lambda/gate-l2/{run_identity.get('run_id')}/known_hosts"
    if ssh_trust.get("attempt_known_hosts_path") != expected_known_hosts:
        errors.append("ssh_trust.attempt_known_hosts_path: does not match run identity")
    if launch.get("deadline_minted_before_launch_post") is not True:
        errors.append("launch.deadline_minted_before_launch_post: must precede the launch POST")
    provider_calls = usage.get("provider_api_calls")
    pacing_count = pacing.get("request_start_count")
    minimum_spacing_ms = pacing.get("minimum_observed_start_spacing_milliseconds")
    if pacing_count != provider_calls:
        errors.append("provider_request_pacing.request_start_count: does not match API usage")
    if (
        type(pacing_count) is int
        and pacing_count > 1
        and (
            type(minimum_spacing_ms) is not int
            or minimum_spacing_ms < MIN_PROVIDER_REQUEST_SPACING_SECONDS * 1000
        )
    ):
        errors.append("provider_request_pacing: request starts were less than one second apart")
    if budget.get("minimum_provider_request_start_spacing_seconds") != (
        MIN_PROVIDER_REQUEST_SPACING_SECONDS
    ):
        errors.append("budget.minimum_provider_request_start_spacing_seconds: drifted")
    if budget.get("automatic_provider_request_retries") != 0:
        errors.append("budget.automatic_provider_request_retries: must be zero")

    instance_id = provider.get("instance_id")
    if labels.get("provider_instance_id") != instance_id:
        errors.append("containment_probe.labels.provider_instance_id: does not match provider")
    if launch.get("minted_instance_id") != instance_id:
        errors.append("launch.minted_instance_id: does not match provider instance ID")
    if termination.get("instance_ids") != [instance_id]:
        errors.append("termination.instance_ids: must contain only the minted instance ID")

    if copy.get("source_sha256") != copy.get("destination_sha256"):
        errors.append("evidence_copy: source and destination SHA-256 values differ")
    if copy.get("hashes_match") is not True:
        errors.append("evidence_copy.hashes_match: successful evidence requires true")
    if archive_copy.get("source_sha256") != archive_copy.get("destination_sha256"):
        errors.append("archive_copy: source and destination SHA-256 values differ")
    if usage.get("transfer_bytes") != copy.get("bytes"):
        errors.append("actual_usage.transfer_bytes: does not match evidence copy")
    if usage.get("mac_active_evidence_bytes") != archive_copy.get("bytes"):
        errors.append("actual_usage.mac_active_evidence_bytes: does not match archive source")
    if usage.get("sealed_copy_bytes") != archive_copy.get("bytes"):
        errors.append("actual_usage.sealed_copy_bytes: does not match archive destination")
    expected_local_root = f"artifacts/t07/lambda/gate-l2/{run_identity.get('run_id')}"
    if local_storage.get("relative_root") != expected_local_root:
        errors.append("local_active_storage.relative_root: does not match run identity")
    local_headroom = local_storage.get("operational_headroom_bytes")
    local_incremental = local_storage.get("max_incremental_bytes")
    local_required = local_storage.get("required_prewrite_free_bytes")
    if (
        type(local_headroom) is int
        and type(local_incremental) is int
        and local_required != local_headroom + local_incremental
    ):
        errors.append("local_active_storage: prewrite floor equation drifted")
    observed_prewrite = local_storage.get("observed_prewrite_free_bytes")
    if (
        type(local_required) is int
        and type(observed_prewrite) is int
        and observed_prewrite < local_required
    ):
        errors.append("local_active_storage.observed_prewrite_free_bytes: below floor")
    local_retained = local_storage.get("retained_free_floor_bytes")
    observed_postseal = local_storage.get("observed_postseal_free_bytes")
    if (
        type(local_retained) is int
        and type(observed_postseal) is int
        and observed_postseal < local_retained
    ):
        errors.append("local_active_storage.observed_postseal_free_bytes: below floor")

    archive_capacity = archive_copy.get("container_capacity_bytes")
    if type(archive_capacity) is int and archive_capacity > 0:
        archive_floor = max(150 * 1024**3, (archive_capacity + 4) // 5)
        archive_required = archive_floor + 67_108_864
        if archive_copy.get("retained_free_floor_bytes") != archive_floor:
            errors.append("archive_copy.retained_free_floor_bytes: dynamic floor drifted")
        if archive_copy.get("required_pre_copy_free_bytes") != archive_required:
            errors.append("archive_copy.required_pre_copy_free_bytes: dynamic floor drifted")
        observed_pre = archive_copy.get("observed_pre_copy_free_bytes")
        observed_post = archive_copy.get("observed_post_copy_free_bytes")
        if type(observed_pre) is int and observed_pre < archive_required:
            errors.append("archive_copy.observed_pre_copy_free_bytes: below pre-copy floor")
        if type(observed_post) is int and observed_post < archive_floor:
            errors.append("archive_copy.observed_post_copy_free_bytes: below retained floor")

    if containment.get("image_reference") != BUSYBOX_REFERENCE:
        errors.append("containment_probe.image_reference: qualification image drifted")
    if containment.get("image_id") != BUSYBOX_CONFIG_DIGEST:
        errors.append("containment_probe.image_id: must equal the pinned config digest")
    if containment.get("config_digest") != BUSYBOX_CONFIG_DIGEST:
        errors.append("containment_probe.config_digest: qualification config drifted")
    if containment.get("layer_digest") != BUSYBOX_LAYER_DIGEST:
        errors.append("containment_probe.layer_digest: qualification layer drifted")
    if containment.get("kill_escalated") is not True:
        errors.append("containment_probe.kill_escalated: adversarial TERM must escalate")

    expected_request = {
        "region_name": provider.get("region_name"),
        "instance_type_name": provider.get("instance_type_name"),
        "ssh_key_names": [provider.get("ssh_key_name")],
        "file_system_names": [],
        "file_system_mounts": [],
        "name": QUALIFICATION_INSTANCE_NAME,
        "image": {"id": provider.get("image_id")},
        "tags": [
            {"key": "giclab.experiment", "value": "EXP-0001"},
            {"key": "giclab.gate", "value": "T07-L2"},
            {"key": "giclab.authorization", "value": authorization_reference},
        ],
        "firewall_rulesets": [{"id": provider.get("firewall_ruleset_id")}],
    }
    if request_body != expected_request:
        errors.append("launch.request_body: does not match provider and authorization bindings")
    if request_body:
        request_sha256 = hashlib.sha256(
            json.dumps(request_body, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        if launch.get("request_sha256") != request_sha256:
            errors.append("launch.request_sha256: does not match canonical request body")

    price = provider.get("price_cents_per_hour")
    wall = usage.get("provider_wall_seconds")
    billed_minutes = usage.get("billed_minutes")
    estimated_cost = usage.get("estimated_list_cost_cents")
    if type(price) is int and type(wall) is int and wall > 0:
        expected_minutes = (wall + 59) // 60
        if billed_minutes != expected_minutes:
            errors.append("actual_usage.billed_minutes: does not match provider wall rounding")
        expected_cost = qualification_list_price_cap_cents(price, wall)
        if estimated_cost != expected_cost:
            errors.append("actual_usage.estimated_list_cost_cents: does not match list price")
        if budget.get("max_list_price_cents") != qualification_list_price_cap_cents(
            price, MAX_QUALIFICATION_WALL_SECONDS
        ):
            errors.append("budget.max_list_price_cents: does not match selected hourly price")
    if type(estimated_cost) is int and estimated_cost > MAX_PROVIDER_COMPUTE_CENTS:
        errors.append("actual_usage.estimated_list_cost_cents: exceeds compute hard cap")

    accelerator_count = provider.get("accelerator_count")
    accelerator_seconds = usage.get("allocated_accelerator_seconds")
    rational_raw = usage.get("allocated_accelerator_hours")
    rational = (
        dict(rational_raw)
        if isinstance(rational_raw, Mapping) and all(isinstance(key, str) for key in rational_raw)
        else {}
    )
    if type(accelerator_count) is int and type(wall) is int:
        expected_seconds = accelerator_count * wall
        if budget.get("max_accelerator_hours") != accelerator_count:
            errors.append("budget.max_accelerator_hours: does not match selected accelerators")
        if accelerator_seconds != expected_seconds:
            errors.append(
                "actual_usage.allocated_accelerator_seconds: does not match allocation wall"
            )
        if rational != {"numerator": expected_seconds, "denominator": 3600}:
            errors.append("actual_usage.allocated_accelerator_hours: exact rational drifted")
        if compute_ledger.get("allocated_accelerator_hours") != rational:
            errors.append("compute_ledger.allocated_accelerator_hours: does not match usage")
    if compute_ledger.get("run_id") != run_identity.get("run_id"):
        errors.append("compute_ledger.run_id: does not match run identity")
    if compute_ledger.get("estimated_list_cost_cents") != estimated_cost:
        errors.append("compute_ledger.estimated_list_cost_cents: does not match usage")

    return errors


def validate_host_qualification_incident_semantics(
    instance: Mapping[str, object],
) -> list[str]:
    """Validate fail-closed lifecycle relations for partial/incident evidence."""

    errors: list[str] = []

    def child(name: str) -> dict[str, object]:
        value = instance.get(name)
        if not isinstance(value, Mapping) or any(not isinstance(key, str) for key in value):
            return {}
        return dict(value)

    lifecycle = child("lifecycle")
    usage = child("actual_usage")
    pacing = child("provider_request_pacing")
    retained = child("retained_evidence")
    storage = child("storage_observation")
    run_identity = child("run_identity")
    compute_ledger = child("compute_ledger")
    credential_evidence = child("secret_contract")
    launch_requests = lifecycle.get("launch_requests")
    provider_calls = usage.get("provider_api_calls")
    pacing_count = pacing.get("request_start_count")
    spacing_ms = pacing.get("minimum_observed_start_spacing_milliseconds")
    spacing_violations = pacing.get("spacing_violations")
    pacing_state = pacing.get("state")
    if pacing_count != provider_calls:
        errors.append("provider_request_pacing.request_start_count: does not match API usage")
    if pacing_count == 0:
        if pacing_state != "no-requests" or spacing_ms is not None or spacing_violations != 0:
            errors.append("provider_request_pacing: zero-request state is inconsistent")
    elif pacing_count == 1:
        if pacing_state != "single-request" or spacing_ms is not None or spacing_violations != 0:
            errors.append("provider_request_pacing: single-request state is inconsistent")
    elif type(pacing_count) is int and pacing_count > 1:
        if type(spacing_violations) is not int or not 0 <= spacing_violations <= pacing_count - 1:
            errors.append("provider_request_pacing.spacing_violations: exceeds interval count")
        observed_violation = type(spacing_ms) is not int or spacing_ms < 1000
        counted_violation = type(spacing_violations) is int and spacing_violations > 0
        if observed_violation is not counted_violation:
            errors.append("provider_request_pacing: minimum spacing contradicts violation count")
        expected_state = "violated" if counted_violation else "compliant"
        if pacing_state != expected_state:
            errors.append("provider_request_pacing.state: contradicts observed spacing")
    if type(pacing_count) is int and pacing_count > 0:
        if pacing.get("aggregate_deadline_minted_before_first_request") is not True:
            errors.append("provider_request_pacing: aggregate deadline was armed too late")
        if pacing.get("all_spacing_delay_counted_inside_aggregate_deadline") is not True:
            errors.append("provider_request_pacing: spacing delay escaped aggregate deadline")
    if launch_requests == 1 and pacing.get("launch_deadline_did_not_extend_aggregate") is not True:
        errors.append("provider_request_pacing: launch checkpoint extended aggregate deadline")
    mac_raw = storage.get("mac_active")
    mac = (
        dict(mac_raw)
        if isinstance(mac_raw, Mapping) and all(isinstance(key, str) for key in mac_raw)
        else {}
    )
    mac_required = mac.get("required_prewrite_free_bytes")
    mac_observed = mac.get("observed_prewrite_free_bytes")
    if (
        type(mac_required) is int
        and type(mac_observed) is int
        and mac.get("preflight_passed") is not (mac_observed >= mac_required)
    ):
        errors.append("storage_observation.mac_active.preflight_passed: contradicts floor")
    external_raw = storage.get("external_archive")
    external = (
        dict(external_raw)
        if isinstance(external_raw, Mapping) and all(isinstance(key, str) for key in external_raw)
        else {}
    )
    external_capacity = external.get("container_capacity_bytes")
    if type(external_capacity) is int and external_capacity > 0:
        external_floor = max(150 * 1024**3, (external_capacity + 4) // 5)
        external_required = external_floor + 67_108_864
        if external.get("retained_free_floor_bytes") != external_floor:
            errors.append("storage_observation.external_archive: retained floor drifted")
        if external.get("required_pre_copy_free_bytes") != external_required:
            errors.append("storage_observation.external_archive: pre-copy floor drifted")
        if external.get("state") == "copied-verified":
            pre = external.get("observed_pre_copy_free_bytes")
            post = external.get("observed_post_copy_free_bytes")
            if type(pre) is not int or pre < external_required:
                errors.append("storage_observation.external_archive: copied below pre-floor")
            if type(post) is not int or post < external_floor:
                errors.append("storage_observation.external_archive: copied below retained floor")
    elif external.get("state") == "copied-verified":
        errors.append("storage_observation.external_archive: copied without capacity binding")
    minted = lifecycle.get("minted_instance_id")
    targets = lifecycle.get("termination_target_ids")
    launch_outcome = lifecycle.get("launch_outcome")
    recovery_attempted = lifecycle.get("recovery_lookup_attempted")
    recovery_matches = lifecycle.get("recovery_match_instance_ids")
    if launch_requests == 0:
        if launch_outcome != "not-sent" or minted is not None:
            errors.append("lifecycle.launch_outcome: zero launches require not-sent/no ID")
        if recovery_attempted is not False or recovery_matches != []:
            errors.append("lifecycle.recovery: zero launches cannot perform recovery")
    elif launch_requests == 1:
        if lifecycle.get("deadline_minted_before_launch_post") is not True:
            errors.append("lifecycle.deadline_minted_before_launch_post: required for launch")
        if launch_outcome == "response-with-id":
            if not isinstance(minted, str) or recovery_attempted is not False:
                errors.append("lifecycle.launch_outcome: response-with-id binding drifted")
        elif launch_outcome == "response-lost-id-recovered":
            if (
                not isinstance(minted, str)
                or recovery_attempted is not True
                or recovery_matches != [minted]
            ):
                errors.append("lifecycle.recovery: recovered launch requires one exact match")
        elif launch_outcome == "response-ambiguous":
            if (
                minted is not None
                or recovery_attempted is not True
                or not isinstance(recovery_matches, list)
                or len(recovery_matches) == 1
            ):
                errors.append("lifecycle.recovery: ambiguous launch must remain unresolved")
        elif launch_outcome == "provider-rejected":
            if minted is not None or recovery_attempted is not False:
                errors.append("lifecycle.launch_outcome: provider rejection binding drifted")
        else:
            errors.append("lifecycle.launch_outcome: one launch has invalid outcome")
    secret_available = credential_evidence.get("available_through_terminal_confirmation")
    if launch_requests == 1 and secret_available is False:
        if credential_evidence.get("loss_response") != (
            "stop-workload-open-billing-incident-request-secret-restoration"
        ):
            errors.append("secret_contract.loss_response: secret loss response drifted")
        if lifecycle.get("billing_incident_open") is not True:
            errors.append("secret_contract: post-launch secret loss requires open billing incident")
    elif secret_available is True and credential_evidence.get("loss_response") != "not-applicable":
        errors.append("secret_contract.loss_response: available secret requires not-applicable")
    if isinstance(minted, str):
        if launch_requests != 1:
            errors.append("lifecycle.launch_requests: minted instance requires one launch")
        if lifecycle.get("termination_required") is not True:
            errors.append("lifecycle.termination_required: minted instance requires termination")
        if targets != [minted]:
            errors.append("lifecycle.termination_target_ids: must contain only minted instance")
    else:
        if targets != []:
            errors.append("lifecycle.termination_target_ids: cannot exist without minted ID")
        if lifecycle.get("termination_requests") != 0:
            errors.append("lifecycle.termination_requests: cannot occur without minted ID")
        expected_termination_required = launch_outcome == "response-ambiguous"
        if lifecycle.get("termination_required") is not expected_termination_required:
            errors.append("lifecycle.termination_required: unresolved launch binding drifted")

    terminal = lifecycle.get("terminal_state")
    nonbillable = lifecycle.get("provider_nonbillable_confirmed")
    incident_open = lifecycle.get("billing_incident_open")
    if terminal in {"terminated", "not-launched"}:
        if nonbillable is not True or incident_open is not False:
            errors.append("lifecycle: terminal/nonlaunched state must close billing incident")
    elif nonbillable is not False or incident_open is not True:
        errors.append("lifecycle: active/unknown state must retain an open billing incident")
    if terminal == "terminated" and not isinstance(minted, str):
        errors.append("lifecycle.terminal_state: terminated requires a minted instance")
    if terminal == "not-launched" and (
        minted is not None or launch_outcome not in {"not-sent", "provider-rejected"}
    ):
        errors.append("lifecycle.terminal_state: not-launched contradicts launch identity")
    if terminal in {"active", "unknown"} and lifecycle.get("launch_requests") != 1:
        errors.append("lifecycle.terminal_state: active/unknown requires one launch request")

    copy_state = lifecycle.get("evidence_copy_state")
    source_hash = retained.get("source_sha256")
    destination_hash = retained.get("destination_sha256")
    if copy_state == "verified":
        if not isinstance(source_hash, str) or source_hash != destination_hash:
            errors.append("retained_evidence: verified copy requires matching source/destination")
    elif destination_hash is not None and destination_hash == source_hash:
        errors.append("retained_evidence: matching destination contradicts unverified copy state")

    accelerator_count = usage.get("accelerator_count")
    wall = usage.get("provider_wall_seconds")
    seconds = usage.get("allocated_accelerator_seconds")
    rational_raw = usage.get("allocated_accelerator_hours")
    rational = (
        dict(rational_raw)
        if isinstance(rational_raw, Mapping) and all(isinstance(key, str) for key in rational_raw)
        else {}
    )
    if type(accelerator_count) is int and type(wall) is int:
        expected = accelerator_count * wall
        if seconds != expected or rational != {"numerator": expected, "denominator": 3600}:
            errors.append("actual_usage: accelerator allocation accounting drifted")
    expected_disposition = (
        "billing-incident-open"
        if lifecycle.get("billing_incident_open") is True
        else "terminal-reconciled-failure"
    )
    if compute_ledger.get("disposition") != expected_disposition:
        errors.append("compute_ledger.disposition: does not match billing lifecycle")
    if compute_ledger.get("run_id") != run_identity.get("run_id"):
        errors.append("compute_ledger.run_id: does not match run identity")
    if compute_ledger.get("estimated_list_cost_cents") != usage.get("estimated_list_cost_cents"):
        errors.append("compute_ledger.estimated_list_cost_cents: does not match usage")
    if compute_ledger.get("allocated_accelerator_hours") != rational:
        errors.append("compute_ledger.allocated_accelerator_hours: does not match usage")
    return errors
