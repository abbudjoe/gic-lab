"""Endpoint-specific, additive-compatible Lambda inventory parsing for Gate L1 V3.

The historical V1/V2 parser remains frozen.  This module owns the fresh seven-GET
contract.  It validates documented required fields and types, permits additive
object keys only where the pinned public schema leaves them open, records only
unknown key names and JSON types, and never retains unknown scalar values.

Importing this module performs no I/O and no network operation.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final, Never, Protocol, cast

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import SchemaError

from .lambda_cloud import (
    API_BASE_URL,
    API_SPEC_SHA256,
    API_SPEC_VERSION,
    LAMBDA_BRANCH,
    MAX_PRICE_CENTS_PER_HOUR,
    MAX_PROVIDER_COMPUTE_CENTS,
    MAX_QUALIFICATION_WALL_SECONDS,
    QUALIFICATION_IMAGE_FAMILY,
    QUALIFICATION_INSTANCE_NAME,
    ComputeCandidate,
    FirewallRule,
    FirewallRuleset,
    HttpMethod,
    InstanceSelectionError,
    InstanceSpecs,
    InstanceTypeOffer,
    Inventory,
    InventoryRequest,
    InventoryResponseFailureKind,
    InventoryResponseValidationError,
    LambdaCloudContractError,
    ProviderImage,
    Region,
    RunningInstance,
    SelectionFailureCode,
    SSHKeyIdentity,
    _parse_global_firewall_ruleset,
    _parse_images,
    _parse_instance_types,
    _parse_regional_firewall_rulesets,
    _parse_regions,
    _parse_running_instances,
    _parse_ssh_keys,
    qualification_list_price_cap_cents,
)

INVENTORY_PLAN_V3_ID: Final = "PLAN-T07-GATE-L1-LAMBDA-READONLY-INVENTORY-V3"
INVENTORY_RUN_V3_ID: Final = "RUN-T07-L1-LAMBDA-INVENTORY-0003"
INVENTORY_ATTEMPT_V3: Final = 3
PENDING_AUTHORIZATION_REFERENCE_V4: Final = "AUTH-T07-GATE-L1-LAMBDA-INPROCESS-V4-PENDING"

MAX_INVENTORY_CALLS_V3: Final = 7
MAX_INVENTORY_RESPONSE_BYTES_V3: Final = 262_144
MAX_INVENTORY_TOTAL_RESPONSE_BYTES_V3: Final = 1_835_008
MAX_INVENTORY_RETAINED_BYTES_V3: Final = 524_288
MAX_SCHEMA_EXTENSION_REPORT_BYTES: Final = 65_536

ENDPOINT_SCHEMA_ROOT: Final = "containers/sira-smoke/lambda/endpoint-schemas-v3"
ENDPOINT_SCHEMA_PATHS: Final[dict[str, str]] = {
    "instance-types": f"{ENDPOINT_SCHEMA_ROOT}/instance-types.schema.json",
    "images": f"{ENDPOINT_SCHEMA_ROOT}/images.schema.json",
    "regions": f"{ENDPOINT_SCHEMA_ROOT}/regions.schema.json",
    "ssh-keys": f"{ENDPOINT_SCHEMA_ROOT}/ssh-keys.schema.json",
    "firewall-rulesets": f"{ENDPOINT_SCHEMA_ROOT}/firewall-rulesets.schema.json",
    "global-firewall-ruleset": (f"{ENDPOINT_SCHEMA_ROOT}/global-firewall-ruleset.schema.json"),
    "running-instances": f"{ENDPOINT_SCHEMA_ROOT}/instances.schema.json",
}

EXPECTED_INVENTORY_REQUESTS_V3: Final = (
    InventoryRequest(
        "instance-types",
        HttpMethod.GET,
        "/api/v1/instance-types",
        MAX_INVENTORY_RESPONSE_BYTES_V3,
    ),
    InventoryRequest(
        "images",
        HttpMethod.GET,
        "/api/v1/images",
        MAX_INVENTORY_RESPONSE_BYTES_V3,
    ),
    InventoryRequest(
        "regions",
        HttpMethod.GET,
        "/api/v1/regions",
        MAX_INVENTORY_RESPONSE_BYTES_V3,
    ),
    InventoryRequest(
        "ssh-keys",
        HttpMethod.GET,
        "/api/v1/ssh-keys",
        MAX_INVENTORY_RESPONSE_BYTES_V3,
    ),
    InventoryRequest(
        "firewall-rulesets",
        HttpMethod.GET,
        "/api/v1/firewall-rulesets",
        MAX_INVENTORY_RESPONSE_BYTES_V3,
    ),
    InventoryRequest(
        "global-firewall-ruleset",
        HttpMethod.GET,
        "/api/v1/firewall-rulesets/global",
        MAX_INVENTORY_RESPONSE_BYTES_V3,
    ),
    InventoryRequest(
        "running-instances",
        HttpMethod.GET,
        "/api/v1/instances",
        MAX_INVENTORY_RESPONSE_BYTES_V3,
    ),
)

_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_CONTINUATION_TOKEN_KEYS: Final = frozenset(
    {
        "page_token",
        "next_page_token",
        "next_token",
        "continuation_token",
        "cursor",
    }
)
_AUDIT_REQUIRED_EVENT_FIELDS: Final = frozenset(
    {
        "service_name",
        "resource_name",
        "action",
        "catalog_version",
        "event_id",
        "event_time",
        "actor_lrn",
        "resource_lrns",
        "resource_owner_lrn",
        "request_api_key_lrn",
        "additional_details",
    }
)
_AUDIT_NULLABLE_FIELDS: Final = frozenset(
    {"actor_lrn", "resource_owner_lrn", "request_api_key_lrn"}
)


class InventoryResponsePlanV3(Protocol):
    @property
    def requests(self) -> tuple[InventoryRequest, ...]: ...

    @property
    def max_total_response_bytes(self) -> int: ...

    @property
    def endpoint_schema_bindings(self) -> Mapping[str, EndpointSchemaBinding]: ...

    @property
    def extension_schema_relative_path(self) -> str: ...

    @property
    def extension_schema_sha256(self) -> str: ...

    @property
    def max_schema_extension_report_bytes(self) -> int: ...


@dataclass(frozen=True, slots=True)
class EndpointSchemaBinding:
    request_id: str
    path: str
    sha256: str

    def __post_init__(self) -> None:
        if self.request_id not in ENDPOINT_SCHEMA_PATHS:
            raise LambdaCloudContractError("Gate L1 V3 endpoint schema request ID drifted")
        if self.path != ENDPOINT_SCHEMA_PATHS[self.request_id]:
            raise LambdaCloudContractError("Gate L1 V3 endpoint schema path drifted")
        if _SHA256.fullmatch(self.sha256) is None:
            raise LambdaCloudContractError("Gate L1 V3 endpoint schema hash is not canonical")


@dataclass(frozen=True, slots=True)
class InventoryV3:
    instance_types: tuple[InstanceTypeOffer, ...]
    images: tuple[ProviderImage, ...]
    regions: tuple[Region, ...]
    ssh_keys: tuple[SSHKeyIdentity, ...]
    firewall_rulesets: tuple[FirewallRuleset, ...]
    running_instances: tuple[RunningInstance, ...]


@dataclass(frozen=True, slots=True)
class SelectedInfrastructureV3:
    candidate: ComputeCandidate
    ssh_key: SSHKeyIdentity
    firewall_ruleset: FirewallRuleset


@dataclass(frozen=True, slots=True)
class EndpointOutcomeV3:
    request_id: str
    method: str
    path: str
    http_status: int
    response_bytes: int
    schema_path: str
    schema_sha256: str
    validation_state: str

    def __post_init__(self) -> None:
        expected = {item.request_id: item for item in EXPECTED_INVENTORY_REQUESTS_V3}.get(
            self.request_id
        )
        if (
            expected is None
            or self.method != "GET"
            or self.path != expected.path
            or self.http_status != 200
            or not 0 <= self.response_bytes <= expected.max_response_bytes
            or self.schema_path != ENDPOINT_SCHEMA_PATHS[self.request_id]
            or _SHA256.fullmatch(self.schema_sha256) is None
            or self.validation_state not in {"exact", "compatible_extension_observed"}
        ):
            raise LambdaCloudContractError("Gate L1 V3 endpoint outcome drifted")


def _pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError
        result[key] = value
    return result


def _reject_constant(value: str) -> Never:
    del value
    raise ValueError


def _strict_json_object(encoded: bytes) -> dict[str, object]:
    try:
        value = json.loads(
            encoded,
            object_pairs_hook=_pairs,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError, RecursionError):
        raise InventoryResponseValidationError(
            InventoryResponseFailureKind.JSON_DECODE,
            "L1_V3_RESPONSE_JSON_INVALID",
        ) from None
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise InventoryResponseValidationError(
            InventoryResponseFailureKind.SCHEMA_VALIDATION,
            "L1_V3_RESPONSE_ENVELOPE_INCOMPATIBLE",
        )
    return value


def _json_type(value: object) -> str:
    if value is None:
        return "null"
    if type(value) is bool:
        return "boolean"
    if type(value) is int:
        return "integer"
    if type(value) is float:
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    return "object"


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()


def _resolve_schema(
    schema: Mapping[str, object], root: Mapping[str, object]
) -> Mapping[str, object]:
    reference = schema.get("$ref")
    if not isinstance(reference, str):
        return schema
    if not reference.startswith("#/"):
        raise LambdaCloudContractError("Gate L1 V3 endpoint schema has a nonlocal reference")
    target: object = root
    for part in reference[2:].split("/"):
        if not isinstance(target, Mapping) or part not in target:
            raise LambdaCloudContractError("Gate L1 V3 endpoint schema reference is invalid")
        target = target[part]
    if not isinstance(target, Mapping):
        raise LambdaCloudContractError("Gate L1 V3 endpoint schema reference is not an object")
    return target


def _pagination_present(value: object) -> bool:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if key in _CONTINUATION_TOKEN_KEYS and child is not None:
                return True
            if key == "has_more" and child is not None and child is not False:
                return True
            if _pagination_present(child):
                return True
    elif isinstance(value, list):
        return any(_pagination_present(child) for child in value)
    return False


def _unknown_locations(
    value: object,
    schema: Mapping[str, object],
    *,
    root: Mapping[str, object],
    path: str = "$",
) -> list[dict[str, object]]:
    schema = _resolve_schema(schema, root)
    locations: list[dict[str, object]] = []
    if isinstance(value, Mapping):
        raw_properties = schema.get("properties", {})
        properties = raw_properties if isinstance(raw_properties, Mapping) else {}
        additional = schema.get("additionalProperties", True)
        unknown: dict[str, object] = {}
        for key, child in value.items():
            child_schema = properties.get(key)
            if isinstance(child_schema, Mapping):
                locations.extend(
                    _unknown_locations(child, child_schema, root=root, path=f"{path}/{key}")
                )
            elif isinstance(additional, Mapping):
                locations.extend(_unknown_locations(child, additional, root=root, path=f"{path}/*"))
            else:
                unknown[key] = child
        if unknown:
            names = sorted(unknown)
            locations.append(
                {
                    "path": path,
                    "key_names": names,
                    "value_types": {name: _json_type(unknown[name]) for name in names},
                }
            )
    elif isinstance(value, list):
        items = schema.get("items")
        if isinstance(items, Mapping):
            for index, child in enumerate(value):
                locations.extend(
                    _unknown_locations(child, items, root=root, path=f"{path}/{index}")
                )
    return locations


def _strip_unknown(
    value: object,
    schema: Mapping[str, object],
    *,
    root: Mapping[str, object],
) -> object:
    schema = _resolve_schema(schema, root)
    if isinstance(value, Mapping):
        raw_properties = schema.get("properties", {})
        properties = raw_properties if isinstance(raw_properties, Mapping) else {}
        additional = schema.get("additionalProperties", True)
        result: dict[str, object] = {}
        for key, child in value.items():
            child_schema = properties.get(key)
            if isinstance(child_schema, Mapping):
                result[key] = _strip_unknown(child, child_schema, root=root)
            elif isinstance(additional, Mapping):
                result[key] = _strip_unknown(child, additional, root=root)
            # Boolean-open additive keys are deliberately omitted.
        return result
    if isinstance(value, list):
        items = schema.get("items")
        if isinstance(items, Mapping):
            return [_strip_unknown(child, items, root=root) for child in value]
        return list(value)
    return value


def load_endpoint_schema(
    repository_root: Path,
    binding: EndpointSchemaBinding,
) -> dict[str, object]:
    path = repository_root / binding.path
    try:
        encoded = path.read_bytes()
        if hashlib.sha256(encoded).hexdigest() != binding.sha256:
            raise ValueError
        schema = json.loads(
            encoded,
            object_pairs_hook=_pairs,
            parse_constant=_reject_constant,
        )
        if not isinstance(schema, dict):
            raise ValueError
        Draft202012Validator.check_schema(schema)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, SchemaError, ValueError):
        raise LambdaCloudContractError("Gate L1 V3 endpoint schema binding failed") from None
    return schema


def _empty_extension_observation(request_id: str) -> dict[str, object]:
    summary = {"request_id": request_id, "unknown_locations": []}
    return {
        "request_id": request_id,
        "validation_state": "exact",
        "unknown_locations": [],
        "structural_summary_sha256": hashlib.sha256(_canonical(summary)).hexdigest(),
    }


def _extension_report_document(
    observations: list[dict[str, object]],
    *,
    pad_remaining: bool,
) -> dict[str, object]:
    expected_ids = [request.request_id for request in EXPECTED_INVENTORY_REQUESTS_V3]
    observed_ids = [str(observation.get("request_id")) for observation in observations]
    if observed_ids != expected_ids[: len(observed_ids)]:
        raise LambdaCloudContractError("Gate L1 V3 extension observation order drifted")
    complete = list(observations)
    if pad_remaining:
        complete.extend(
            _empty_extension_observation(request_id) for request_id in expected_ids[len(complete) :]
        )
    report: dict[str, object] = {
        "schema_version": "0.1.0",
        "policy": "documented-required-strict-additive-keys-report-only",
        "unknown_scalar_values_retained": False,
        "observations": complete,
    }
    report["report_sha256"] = hashlib.sha256(_canonical(report)).hexdigest()
    return report


def validate_schema_extension_report_integrity(report: Mapping[str, object]) -> None:
    """Verify ordered structural hashes without inspecting unknown scalar values."""

    if set(report) != {
        "schema_version",
        "policy",
        "unknown_scalar_values_retained",
        "observations",
        "report_sha256",
    }:
        raise LambdaCloudContractError("Gate L1 V3 extension report fields drifted")
    raw_observations = report.get("observations")
    if not isinstance(raw_observations, list) or len(raw_observations) != len(
        EXPECTED_INVENTORY_REQUESTS_V3
    ):
        raise LambdaCloudContractError("Gate L1 V3 extension report cardinality drifted")
    for expected, raw_observation in zip(
        EXPECTED_INVENTORY_REQUESTS_V3,
        raw_observations,
        strict=True,
    ):
        if not isinstance(raw_observation, Mapping) or set(raw_observation) != {
            "request_id",
            "validation_state",
            "unknown_locations",
            "structural_summary_sha256",
        }:
            raise LambdaCloudContractError("Gate L1 V3 extension observation fields drifted")
        unknown_locations = raw_observation.get("unknown_locations")
        if raw_observation.get("request_id") != expected.request_id or not isinstance(
            unknown_locations, list
        ):
            raise LambdaCloudContractError("Gate L1 V3 extension observation order drifted")
        for raw_location in unknown_locations:
            if not isinstance(raw_location, Mapping) or set(raw_location) != {
                "path",
                "key_names",
                "value_types",
            }:
                raise LambdaCloudContractError("Gate L1 V3 extension location fields drifted")
            key_names = raw_location.get("key_names")
            value_types = raw_location.get("value_types")
            if (
                not isinstance(key_names, list)
                or not isinstance(value_types, Mapping)
                or any(not isinstance(name, str) for name in key_names)
                or any(not isinstance(key, str) for key in value_types)
                or key_names != sorted(key_names)
                or key_names != sorted(value_types)
            ):
                raise LambdaCloudContractError("Gate L1 V3 extension location keys drifted")
        expected_state = "compatible_extension_observed" if unknown_locations else "exact"
        if raw_observation.get("validation_state") != expected_state:
            raise LambdaCloudContractError("Gate L1 V3 extension validation state drifted")
        summary = {
            "request_id": expected.request_id,
            "unknown_locations": unknown_locations,
        }
        expected_summary_hash = hashlib.sha256(_canonical(summary)).hexdigest()
        if raw_observation.get("structural_summary_sha256") != expected_summary_hash:
            raise LambdaCloudContractError("Gate L1 V3 extension structural hash drifted")
    unsigned_report = dict(report)
    reported_hash = unsigned_report.pop("report_sha256")
    if reported_hash != hashlib.sha256(_canonical(unsigned_report)).hexdigest():
        raise LambdaCloudContractError("Gate L1 V3 extension report hash drifted")


def _validate_incremental_extension_report(
    repository_root: Path,
    plan: InventoryResponsePlanV3,
    observations: list[dict[str, object]],
) -> None:
    schema_path = repository_root / plan.extension_schema_relative_path
    try:
        encoded_schema = schema_path.read_bytes()
        if hashlib.sha256(encoded_schema).hexdigest() != plan.extension_schema_sha256:
            raise ValueError
        schema = json.loads(
            encoded_schema,
            object_pairs_hook=_pairs,
            parse_constant=_reject_constant,
        )
        if not isinstance(schema, dict):
            raise ValueError
        Draft202012Validator.check_schema(schema)
        projected = _extension_report_document(observations, pad_remaining=True)
        if len(_canonical(projected)) > plan.max_schema_extension_report_bytes:
            raise ValueError
        if any(Draft202012Validator(schema).iter_errors(projected)):
            raise ValueError
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, SchemaError, ValueError):
        raise InventoryResponseValidationError(
            InventoryResponseFailureKind.SCHEMA_VALIDATION,
            "L1_V3_EXTENSION_REPORT_INELIGIBLE",
        ) from None


@dataclass(slots=True)
class IncrementalInventoryParserV3:
    """Validate and normalize seven responses before a later request can start."""

    repository_root: Path
    plan: InventoryResponsePlanV3
    accepted_requests: int = 0
    total_response_bytes: int = 0
    instance_types: tuple[InstanceTypeOffer, ...] | None = None
    images: tuple[ProviderImage, ...] | None = None
    regions: tuple[Region, ...] | None = None
    ssh_keys: tuple[SSHKeyIdentity, ...] | None = None
    regional_firewall_rulesets: tuple[FirewallRuleset, ...] | None = None
    global_firewall_ruleset: FirewallRuleset | None = None
    running_instances: tuple[RunningInstance, ...] | None = None
    observations: list[dict[str, object]] = field(default_factory=list)
    response_bytes: dict[str, int] = field(default_factory=dict)

    def accept(self, request: InventoryRequest, encoded: bytes) -> None:
        if self.accepted_requests >= len(self.plan.requests):
            raise InventoryResponseValidationError(
                InventoryResponseFailureKind.SCHEMA_VALIDATION,
                "L1_V3_RESPONSE_SET_OVERFLOW",
            )
        if request != self.plan.requests[self.accepted_requests]:
            raise InventoryResponseValidationError(
                InventoryResponseFailureKind.SCHEMA_VALIDATION,
                "L1_V3_RESPONSE_ORDER_DRIFT",
            )
        if (
            len(encoded) > request.max_response_bytes
            or self.total_response_bytes + len(encoded) > self.plan.max_total_response_bytes
        ):
            raise InventoryResponseValidationError(
                InventoryResponseFailureKind.SCHEMA_VALIDATION,
                "L1_V3_RESPONSE_SIZE_DRIFT",
            )
        decoded = _strict_json_object(encoded)
        if _pagination_present(decoded):
            raise InventoryResponseValidationError(
                InventoryResponseFailureKind.PAGINATION,
                "L1_V3_RESPONSE_PAGINATION_PRESENT",
            )
        try:
            binding = self.plan.endpoint_schema_bindings[request.request_id]
        except KeyError:
            raise InventoryResponseValidationError(
                InventoryResponseFailureKind.SCHEMA_VALIDATION,
                "L1_V3_ENDPOINT_SCHEMA_UNBOUND",
            ) from None
        schema = load_endpoint_schema(self.repository_root, binding)
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        if any(validator.iter_errors(decoded)):
            raise InventoryResponseValidationError(
                InventoryResponseFailureKind.SCHEMA_VALIDATION,
                "L1_V3_RESPONSE_SCHEMA_INCOMPATIBLE",
            )
        locations = _unknown_locations(decoded, schema, root=schema)
        normalized_locations = sorted(locations, key=lambda item: str(item["path"]))
        summary = {
            "request_id": request.request_id,
            "unknown_locations": normalized_locations,
        }
        observation: dict[str, object] = {
            "request_id": request.request_id,
            "validation_state": (
                "compatible_extension_observed" if normalized_locations else "exact"
            ),
            "unknown_locations": normalized_locations,
            "structural_summary_sha256": hashlib.sha256(_canonical(summary)).hexdigest(),
        }
        _validate_incremental_extension_report(
            self.repository_root,
            self.plan,
            [*self.observations, observation],
        )
        sanitized = _strip_unknown(decoded, schema, root=schema)
        sanitized_encoded = _canonical(sanitized)
        try:
            if request.request_id == "instance-types":
                self.instance_types = _parse_instance_types(sanitized_encoded, request)
            elif request.request_id == "images":
                self.images = _parse_images(sanitized_encoded, request)
            elif request.request_id == "regions":
                self.regions = _parse_regions(sanitized_encoded, request)
            elif request.request_id == "ssh-keys":
                self.ssh_keys = _parse_ssh_keys(sanitized_encoded, request)
            elif request.request_id == "firewall-rulesets":
                self.regional_firewall_rulesets = _parse_regional_firewall_rulesets(
                    sanitized_encoded, request
                )
            elif request.request_id == "global-firewall-ruleset":
                self.global_firewall_ruleset = _parse_global_firewall_ruleset(
                    sanitized_encoded, request
                )
            elif request.request_id == "running-instances":
                self.running_instances = _parse_running_instances(sanitized_encoded, request)
            else:
                raise LambdaCloudContractError("Gate L1 V3 response ID drifted")
        except LambdaCloudContractError:
            raise InventoryResponseValidationError(
                InventoryResponseFailureKind.SCHEMA_VALIDATION,
                "L1_V3_RESPONSE_SEMANTICALLY_INCOMPATIBLE",
            ) from None
        self.observations.append(observation)
        self.response_bytes[request.request_id] = len(encoded)
        self.total_response_bytes += len(encoded)
        self.accepted_requests += 1

    def finish(self) -> InventoryV3:
        if self.accepted_requests != len(EXPECTED_INVENTORY_REQUESTS_V3):
            raise InventoryResponseValidationError(
                InventoryResponseFailureKind.SCHEMA_VALIDATION,
                "L1_V3_RESPONSE_SET_INCOMPLETE",
            )
        if (
            self.instance_types is None
            or self.images is None
            or self.regions is None
            or self.ssh_keys is None
            or self.regional_firewall_rulesets is None
            or self.global_firewall_ruleset is None
            or self.running_instances is None
        ):
            raise InventoryResponseValidationError(
                InventoryResponseFailureKind.SCHEMA_VALIDATION,
                "L1_V3_TYPED_STATE_INCOMPLETE",
            )
        rulesets = (*self.regional_firewall_rulesets, self.global_firewall_ruleset)
        if len({item.ruleset_id for item in rulesets}) != len(rulesets):
            raise InventoryResponseValidationError(
                InventoryResponseFailureKind.SCHEMA_VALIDATION,
                "L1_V3_FIREWALL_IDENTITY_DRIFT",
            )
        if not self.regions:
            raise InventoryResponseValidationError(
                InventoryResponseFailureKind.SCHEMA_VALIDATION,
                "L1_V3_REGION_INVENTORY_EMPTY",
            )
        known_regions = {region.name for region in self.regions}
        if any(
            region.name not in known_regions
            for offer in self.instance_types
            for region in offer.capacity_regions
        ) or any(image.region.name not in known_regions for image in self.images):
            raise InventoryResponseValidationError(
                InventoryResponseFailureKind.SCHEMA_VALIDATION,
                "L1_V3_REGION_REFERENCE_DRIFT",
            )
        return InventoryV3(
            instance_types=self.instance_types,
            images=self.images,
            regions=self.regions,
            ssh_keys=self.ssh_keys,
            firewall_rulesets=tuple(
                sorted(rulesets, key=lambda item: (item.scope, item.ruleset_id))
            ),
            running_instances=self.running_instances,
        )

    def extension_report(self) -> dict[str, object]:
        if len(self.observations) != len(EXPECTED_INVENTORY_REQUESTS_V3):
            raise LambdaCloudContractError("Gate L1 V3 extension report requires seven responses")
        report = _extension_report_document(self.observations, pad_remaining=False)
        if len(_canonical(report)) > self.plan.max_schema_extension_report_bytes:
            raise LambdaCloudContractError("Gate L1 V3 extension report exceeds its cap")
        validate_schema_extension_report_integrity(report)
        return report


def select_compute_candidate_v3(inventory: InventoryV3) -> ComputeCandidate:
    """Select using the frozen scientific-neutral host policy, without account LRNs."""

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
    regional: dict[str, list[FirewallRuleset]] = {}
    for ruleset in inventory.firewall_rulesets:
        if ruleset.scope == "regional" and ruleset.region is not None and ruleset.is_ssh_only:
            regional.setdefault(ruleset.region.name, []).append(ruleset)
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
            rulesets = regional.get(region.name, [])
            for image in inventory.images:
                if (
                    rulesets
                    and image.region.name == region.name
                    and image.architecture == offer.architecture
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
            "no currently available x86_64 candidate satisfies policy",
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


def selection_document_v3(
    candidate: ComputeCandidate | None,
    selection_failure: InstanceSelectionError | None,
) -> dict[str, object]:
    """Render the exact deterministic selection state for creation and verification."""

    if (candidate is None) == (selection_failure is None):
        raise LambdaCloudContractError("Gate L1 V3 selection state is ambiguous")
    if candidate is not None:
        return {
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
            "qualification_list_price_cap_cents": candidate.qualification_list_price_cap_cents,
            "provider_compute_hard_cap_cents": candidate.provider_compute_hard_cap_cents,
            "ssh_key_binding": None,
            "firewall_ruleset_binding": None,
        }
    assert selection_failure is not None
    return {
        "state": "blocked",
        "reason_code": selection_failure.code.value,
        "ssh_key_binding": None,
        "firewall_ruleset_binding": None,
    }


def _redacted_mapping(value: object, *, context: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or any(not isinstance(key, str) for key in value):
        raise LambdaCloudContractError(f"Gate L1 V3 redacted {context} drifted")
    return value


def _redacted_list(value: object, *, context: str) -> list[object]:
    if not isinstance(value, list):
        raise LambdaCloudContractError(f"Gate L1 V3 redacted {context} drifted")
    return value


def _redacted_string(value: object, *, context: str) -> str:
    if not isinstance(value, str):
        raise LambdaCloudContractError(f"Gate L1 V3 redacted {context} drifted")
    return value


def _redacted_integer(value: object, *, context: str) -> int:
    if type(value) is not int:
        raise LambdaCloudContractError(f"Gate L1 V3 redacted {context} drifted")
    return value


def inventory_v3_from_redacted_document(document: Mapping[str, object]) -> InventoryV3:
    """Rebuild the selector's typed state from a schema-validated redacted artifact."""

    regions = tuple(
        Region(
            _redacted_string(
                _redacted_mapping(raw, context="region").get("name"),
                context="region name",
            ),
            "",
        )
        for raw in _redacted_list(document.get("regions"), context="regions")
    )
    region_by_name = {region.name: region for region in regions}
    if len(region_by_name) != len(regions):
        raise LambdaCloudContractError("Gate L1 V3 redacted region identities drifted")

    def region_reference(value: object, *, context: str) -> Region:
        name = _redacted_string(
            _redacted_mapping(value, context=context).get("name"),
            context=f"{context} name",
        )
        try:
            return region_by_name[name]
        except KeyError:
            raise LambdaCloudContractError(
                f"Gate L1 V3 redacted {context} reference drifted"
            ) from None

    instance_types: list[InstanceTypeOffer] = []
    for raw in _redacted_list(document.get("instance_types"), context="instance types"):
        record = _redacted_mapping(raw, context="instance type")
        specs = _redacted_mapping(record.get("specs"), context="instance specs")
        instance_types.append(
            InstanceTypeOffer(
                name=_redacted_string(record.get("name"), context="instance type name"),
                description="",
                gpu_description="",
                architecture=_redacted_string(
                    record.get("architecture"), context="instance architecture"
                ),
                price_cents_per_hour=_redacted_integer(
                    record.get("price_cents_per_hour"), context="instance price"
                ),
                specs=InstanceSpecs(
                    vcpus=_redacted_integer(specs.get("vcpus"), context="instance vcpus"),
                    memory_gib=_redacted_integer(
                        specs.get("memory_gib"), context="instance memory"
                    ),
                    storage_gib=_redacted_integer(
                        specs.get("storage_gib"), context="instance storage"
                    ),
                    gpus=_redacted_integer(specs.get("gpus"), context="instance gpus"),
                ),
                capacity_regions=tuple(
                    region_reference(item, context="capacity region")
                    for item in _redacted_list(
                        record.get("capacity_regions"), context="capacity regions"
                    )
                ),
            )
        )
    if len({item.name for item in instance_types}) != len(instance_types):
        raise LambdaCloudContractError("Gate L1 V3 redacted instance identities drifted")

    images: list[ProviderImage] = []
    for raw in _redacted_list(document.get("images"), context="images"):
        record = _redacted_mapping(raw, context="image")
        images.append(
            ProviderImage(
                image_id=_redacted_string(record.get("id"), context="image ID"),
                name=_redacted_string(record.get("name"), context="image name"),
                family=_redacted_string(record.get("family"), context="image family"),
                version=_redacted_string(record.get("version"), context="image version"),
                architecture=_redacted_string(
                    record.get("architecture"), context="image architecture"
                ),
                region=region_reference(record.get("region"), context="image region"),
            )
        )
    if len({item.image_id for item in images}) != len(images):
        raise LambdaCloudContractError("Gate L1 V3 redacted image identities drifted")

    ssh_keys = tuple(
        SSHKeyIdentity(
            key_id=_redacted_string(
                _redacted_mapping(raw, context="SSH key").get("id"),
                context="SSH key ID",
            ),
            name=_redacted_string(
                _redacted_mapping(raw, context="SSH key").get("name"),
                context="SSH key name",
            ),
        )
        for raw in _redacted_list(document.get("ssh_keys"), context="SSH keys")
    )
    if len({item.key_id for item in ssh_keys}) != len(ssh_keys):
        raise LambdaCloudContractError("Gate L1 V3 redacted SSH key identities drifted")

    firewall_rulesets: list[FirewallRuleset] = []
    for raw in _redacted_list(document.get("firewall_rulesets"), context="firewall rulesets"):
        record = _redacted_mapping(raw, context="firewall ruleset")
        raw_region_name = record.get("region_name")
        rules: list[FirewallRule] = []
        for raw_rule in _redacted_list(record.get("rules"), context="firewall rules"):
            rule_record = _redacted_mapping(raw_rule, context="firewall rule")
            raw_range = rule_record.get("port_range")
            port_range = (
                None
                if raw_range is None
                else tuple(
                    _redacted_integer(value, context="firewall port")
                    for value in _redacted_list(raw_range, context="firewall port range")
                )
            )
            if port_range is not None and len(port_range) != 2:
                raise LambdaCloudContractError("Gate L1 V3 redacted firewall range drifted")
            rules.append(
                FirewallRule(
                    protocol=_redacted_string(
                        rule_record.get("protocol"), context="firewall protocol"
                    ),
                    port_range=port_range,
                    source_network=_redacted_string(
                        rule_record.get("source_network"), context="firewall source"
                    ),
                    description="",
                )
            )
        region = (
            None
            if raw_region_name is None
            else region_by_name.get(
                _redacted_string(raw_region_name, context="firewall region name")
            )
        )
        ruleset = FirewallRuleset(
            ruleset_id=_redacted_string(record.get("id"), context="firewall ruleset ID"),
            name=_redacted_string(record.get("name"), context="firewall ruleset name"),
            scope=_redacted_string(record.get("scope"), context="firewall scope"),
            region=region,
            rules=tuple(rules),
        )
        if (
            (ruleset.scope == "regional" and ruleset.region is None)
            or (ruleset.scope == "global" and ruleset.region is not None)
            or record.get("ssh_only") is not ruleset.is_ssh_only
        ):
            raise LambdaCloudContractError("Gate L1 V3 redacted firewall semantics drifted")
        firewall_rulesets.append(ruleset)
    if len({item.ruleset_id for item in firewall_rulesets}) != len(firewall_rulesets):
        raise LambdaCloudContractError("Gate L1 V3 redacted firewall identities drifted")

    running_instances: list[RunningInstance] = []
    for raw in _redacted_list(document.get("running_instances"), context="running instances"):
        record = _redacted_mapping(raw, context="running instance")
        raw_name = record.get("name")
        running_instances.append(
            RunningInstance(
                instance_id=_redacted_string(record.get("id"), context="instance ID"),
                name=(
                    None
                    if raw_name is None
                    else _redacted_string(raw_name, context="instance name")
                ),
                status=_redacted_string(record.get("status"), context="instance status"),
                region_name=_redacted_string(record.get("region_name"), context="instance region"),
                instance_type_name=_redacted_string(
                    record.get("instance_type_name"), context="instance type"
                ),
                file_system_count=_redacted_integer(
                    record.get("file_system_count"), context="instance filesystem count"
                ),
                firewall_ruleset_ids=tuple(
                    _redacted_string(value, context="instance firewall ID")
                    for value in _redacted_list(
                        record.get("firewall_ruleset_ids"),
                        context="instance firewall IDs",
                    )
                ),
                t07_owned=(record.get("t07_owned") is True),
            )
        )
    if len({item.instance_id for item in running_instances}) != len(running_instances):
        raise LambdaCloudContractError("Gate L1 V3 redacted instance identities drifted")
    return InventoryV3(
        instance_types=tuple(instance_types),
        images=tuple(images),
        regions=regions,
        ssh_keys=ssh_keys,
        firewall_rulesets=tuple(firewall_rulesets),
        running_instances=tuple(running_instances),
    )


def bind_selected_infrastructure_v3(
    inventory: InventoryV3,
    candidate: ComputeCandidate,
    *,
    approved_ssh_key_id: str,
    approved_ssh_key_name: str,
    approved_firewall_ruleset_id: str,
) -> SelectedInfrastructureV3:
    """Bind user-reviewed resource identities without an account-history query."""

    if candidate != select_compute_candidate_v3(inventory):
        raise LambdaCloudContractError("candidate is not the exact V3 inventory selection")
    keys = [
        key
        for key in inventory.ssh_keys
        if key.key_id == approved_ssh_key_id and key.name == approved_ssh_key_name
    ]
    rulesets = [
        item
        for item in inventory.firewall_rulesets
        if item.ruleset_id == approved_firewall_ruleset_id
        and item.ruleset_id in candidate.eligible_firewall_ruleset_ids
        and item.scope == "regional"
        and item.region is not None
        and item.region.name == candidate.region_name
        and item.is_ssh_only
    ]
    if len(keys) != 1 or len(rulesets) != 1:
        raise LambdaCloudContractError("approved Gate L2 resource identity is absent")
    return SelectedInfrastructureV3(candidate, keys[0], rulesets[0])


def audit_structural_report(
    encoded: bytes,
    *,
    source_run_id: str = "RUN-T07-L1-LAMBDA-INVENTORY-0002",
) -> dict[str, object]:
    """Return structure only; no audit scalar value or scalar-value hash is retained."""

    if len(encoded) > MAX_INVENTORY_RESPONSE_BYTES_V3:
        raise LambdaCloudContractError("audit structural source exceeds its historical cap")
    decoded = _strict_json_object(encoded)
    top_names = sorted(decoded)
    top_types = {name: _json_type(decoded[name]) for name in top_names}
    raw_data = decoded.get("data")
    items = raw_data if isinstance(raw_data, list) else []
    item_key_sets: list[list[str]] = []
    event_maps: list[Mapping[str, object]] = []
    unknown_names: set[str] = set(top_names) - {"data", "page_token"}
    omissions: set[str] = set()
    type_mismatches: list[dict[str, str]] = []
    if not isinstance(raw_data, list):
        type_mismatches.append(
            {"path": "$/data", "expected": "array", "observed": _json_type(raw_data)}
        )
    for index, item in enumerate(items):
        if not isinstance(item, Mapping):
            type_mismatches.append(
                {"path": f"$/data/{index}", "expected": "object", "observed": _json_type(item)}
            )
            item_key_sets.append([])
            continue
        event_maps.append(item)
        names = sorted(str(key) for key in item)
        item_key_sets.append(names)
        unknown_names.update(set(names) - _AUDIT_REQUIRED_EVENT_FIELDS)
        omissions.update(_AUDIT_REQUIRED_EVENT_FIELDS - set(names))
        expected_types: dict[str, tuple[str, ...]] = {
            "service_name": ("string",),
            "resource_name": ("string",),
            "action": ("string",),
            "catalog_version": ("string",),
            "event_id": ("string",),
            "event_time": ("string",),
            "actor_lrn": ("string", "null"),
            "resource_lrns": ("array",),
            "resource_owner_lrn": ("string", "null"),
            "request_api_key_lrn": ("string", "null"),
            "additional_details": ("object",),
        }
        for name, expected in expected_types.items():
            if name in item and _json_type(item[name]) not in expected:
                type_mismatches.append(
                    {
                        "path": f"$/data/{index}/{name}",
                        "expected": "|".join(expected),
                        "observed": _json_type(item[name]),
                    }
                )
        resource_lrns = item.get("resource_lrns")
        if isinstance(resource_lrns, list) and any(
            not isinstance(value, str) for value in resource_lrns
        ):
            type_mismatches.append(
                {
                    "path": f"$/data/{index}/resource_lrns/*",
                    "expected": "string",
                    "observed": next(
                        _json_type(value) for value in resource_lrns if not isinstance(value, str)
                    ),
                }
            )
    nullability: dict[str, str] = {}
    for name in sorted(_AUDIT_REQUIRED_EVENT_FIELDS):
        if not event_maps or all(name not in event for event in event_maps):
            state = "absent"
        else:
            values = [event.get(name) for event in event_maps if name in event]
            null_count = sum(value is None for value in values)
            state = (
                "always_null"
                if null_count == len(values)
                else "sometimes_null"
                if null_count
                else "never_null"
            )
        nullability[name] = state
    continuation_value = decoded.get("page_token", object())
    if "page_token" not in decoded:
        page_state = "absent"
    elif continuation_value is None:
        page_state = "null"
    elif isinstance(continuation_value, str):
        page_state = "non_null"
    else:
        page_state = "wrong_type"
        type_mismatches.append(
            {
                "path": "$/page_token",
                "expected": "string|null",
                "observed": _json_type(continuation_value),
            }
        )
    report: dict[str, object] = {
        "schema_version": "0.1.0",
        "source_run_id": source_run_id,
        "source_response_bytes": len(encoded),
        "top_level_key_names": top_names,
        "top_level_value_types": top_types,
        "data_array_length": len(items) if isinstance(raw_data, list) else None,
        "item_key_name_sets": item_key_sets,
        "nullability_observations": nullability,
        "unknown_key_names": sorted(unknown_names),
        "required_key_omissions": sorted(omissions),
        "type_mismatches": type_mismatches,
        "page_token_state": page_state,
        "sensitive_scalar_values_retained": False,
    }
    report["summary_sha256"] = hashlib.sha256(_canonical(report)).hexdigest()
    return report


def schema_extension_report_bytes(report: Mapping[str, object]) -> bytes:
    encoded = _canonical(report) + b"\n"
    if len(encoded) > MAX_SCHEMA_EXTENSION_REPORT_BYTES:
        raise LambdaCloudContractError("Gate L1 V3 extension report exceeds its cap")
    return encoded


def inventory_document_v3(
    inventory: InventoryV3,
    candidate: ComputeCandidate | None,
    *,
    observed_at_utc: str,
    inventory_plan_sha256: str,
    run_binding: object,
    endpoint_outcomes: tuple[EndpointOutcomeV3, ...],
    extension_report: Mapping[str, object],
    extension_schema_sha256: str,
    limits_document: Mapping[str, int],
    request_ledger_contract: Mapping[str, object],
    selection_failure: InstanceSelectionError | None = None,
) -> dict[str, object]:
    """Build the V3 redacted inventory with no account-history dependency."""

    validate_schema_extension_report_integrity(extension_report)
    if not observed_at_utc.endswith("Z") or "T" not in observed_at_utc:
        raise LambdaCloudContractError("Gate L1 V3 observation time must be UTC")
    if (
        _SHA256.fullmatch(inventory_plan_sha256) is None
        or _SHA256.fullmatch(extension_schema_sha256) is None
    ):
        raise LambdaCloudContractError("Gate L1 V3 artifact hash binding is not canonical")
    run_id = getattr(run_binding, "run_id", None)
    repository_commit = getattr(run_binding, "repository_commit", None)
    implementation_commit = getattr(run_binding, "implementation_commit", None)
    authorization_reference = getattr(run_binding, "authorization_reference", None)
    authorization_sha256 = getattr(run_binding, "authorization_sha256", None)
    if run_id != INVENTORY_RUN_V3_ID or not all(
        isinstance(value, str)
        for value in (
            repository_commit,
            implementation_commit,
            authorization_reference,
            authorization_sha256,
        )
    ):
        raise LambdaCloudContractError("Gate L1 V3 run binding drifted")
    if tuple(item.request_id for item in endpoint_outcomes) != tuple(
        item.request_id for item in EXPECTED_INVENTORY_REQUESTS_V3
    ):
        raise LambdaCloudContractError("Gate L1 V3 endpoint outcome order drifted")
    selection = selection_document_v3(candidate, selection_failure)

    def region(value: Region) -> dict[str, str]:
        return {"name": value.name}

    document: dict[str, object] = {
        "schema_version": "0.3.0",
        "provider": "lambda-on-demand-cloud",
        "api_base_url": API_BASE_URL,
        "api_spec": {"version": API_SPEC_VERSION, "sha256": API_SPEC_SHA256},
        "inventory_plan": {"plan_id": INVENTORY_PLAN_V3_ID, "sha256": inventory_plan_sha256},
        "run_identity": {
            "run_id": run_id,
            "attempt": INVENTORY_ATTEMPT_V3,
            "experiment_id": "EXP-0001",
            "profile_plan_id": "PLAN-EXP0001-SMOKE",
            "gate": "T07-L1",
            "branch": LAMBDA_BRANCH,
            "implementation_commit": implementation_commit,
            "repository_commit": repository_commit,
        },
        "authorization_binding": {
            "authorization_reference": authorization_reference,
            "authorization_sha256": authorization_sha256,
            "authorized": True,
        },
        "account_identity": {
            "state": "unavailable_not_required",
            "source": "audit_endpoint_not_requested",
        },
        "endpoint_outcomes": [
            {
                "request_id": item.request_id,
                "method": item.method,
                "path": item.path,
                "http_status": item.http_status,
                "response_bytes": item.response_bytes,
                "schema_path": item.schema_path,
                "schema_sha256": item.schema_sha256,
                "validation_state": item.validation_state,
            }
            for item in endpoint_outcomes
        ],
        "schema_extension_report": {
            "schema_path": "schemas/t07-lambda-schema-extension-report.schema.json",
            "schema_sha256": extension_schema_sha256,
            "report": dict(extension_report),
        },
        "limits": dict(limits_document),
        "request_ledger": dict(request_ledger_contract),
        "observed_at_utc": observed_at_utc,
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
                "capacity_regions": [region(item) for item in offer.capacity_regions],
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
                "region": region(item.region),
            }
            for item in inventory.images
        ],
        "regions": [region(item) for item in inventory.regions],
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
            "audit_history_requested": False,
            "unknown_scalar_values_retained": False,
        },
    }
    if len(_canonical(document) + b"\n") > MAX_INVENTORY_RETAINED_BYTES_V3:
        raise LambdaCloudContractError("Gate L1 V3 redacted inventory exceeds its cap")
    return document


def canonical_inventory_v3_bytes(document: Mapping[str, object]) -> bytes:
    encoded = _canonical(document) + b"\n"
    if len(encoded) > MAX_INVENTORY_RETAINED_BYTES_V3:
        raise LambdaCloudContractError("Gate L1 V3 redacted inventory exceeds its cap")
    return encoded


def cast_inventory_for_legacy_read_only_policy(inventory: InventoryV3) -> Inventory:
    """Explicitly document that legacy selection reads no account-binding field.

    Kept only for downstream compatibility tests; V3 production selection uses the
    native implementation above.
    """

    return cast(Inventory, inventory)
