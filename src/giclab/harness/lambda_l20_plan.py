"""Offline Gate L2.0 decision materialization and host-plan controls.

This module is intentionally network and subprocess inert.  It validates the private
human decision through a no-follow descriptor, consumes only already sealed Gate L1 /
L1A evidence, materializes private request parameters under an ignored run root, and
renders/validates the public unauthorized Gate L2 plan.  A later, separately
authorized operator owns every provider, SSH, and Docker action.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import ipaddress
import json
import os
import re
import stat
from collections.abc import Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Final

from jsonschema import Draft202012Validator

from .lambda_archive import (
    DiskutilVolumeObserver,
    InventoryArchiveError,
    _HeldDirectory,
    _open_or_create_archive_root,
    _same_identity,
    _validate_external,
    _validate_system,
    _write_exclusive_at,
)
from .lambda_archive import (
    _read_regular_at as _archive_read_regular_at,
)
from .lambda_cloud import (
    API_BASE_URL,
    BUSYBOX_CONFIG_DIGEST,
    BUSYBOX_LAYER_DIGEST,
    BUSYBOX_REFERENCE,
)
from .lambda_inventory_plan_v3 import InventoryRunBindingV3, load_inventory_plan_v3
from .lambda_l13_security import (
    ALIAS_MAP_RELATIVE_ROOT,
    AUTHORIZATION_REFERENCE,
    AUTHORIZATION_SHA256,
    EXECUTION_COMMIT,
    IMPLEMENTATION_COMMIT,
    INVENTORY_SHA256,
    PLAN_SHA256,
    L13ContractError,
    build_resource_candidate_matrix,
    project_image_identities,
    validate_l13_gate_l2_evidence,
)


class L20ContractError(ValueError):
    """A Gate L2.0 decision, private binding, or public plan is unsafe."""


BRANCH: Final = "phase-1/sira-smoke-lambda"
STARTING_COMMIT: Final = "314270ecd27115d801ea6348ac7653d30d56a884"
PLAN_ID: Final = "PLAN-T07-GATE-L2-LAMBDA-HOST-QUALIFICATION-V1"
RUN_ID: Final = "RUN-T07-L2-LAMBDA-HOST-QUALIFICATION-0001"
AUTHORIZATION_PLACEHOLDER: Final = "AUTH-T07-GATE-L2-LAMBDA-HOST-QUALIFICATION-V1-PENDING"
DECISION_PATH: Final = Path.home() / ".config/gic-lab/t07/l2-human-decisions.json"
PRIVATE_ROOT_RELATIVE: Final = Path("artifacts/t07/lambda/gate-l2-0") / RUN_ID / "parameters-v2"
PRIVATE_DECISION_NAME: Final = "human-decision-private.json"
PRIVATE_DECISION_SEAL_NAME: Final = "HUMAN_DECISION_SEAL.json"
PRIVATE_PARAMETERS_NAME: Final = "private-parameters.json"
PRIVATE_PARAMETERS_SEAL_NAME: Final = "PRIVATE_PARAMETERS_SEAL.json"
PRIVATE_BUNDLE_SEAL_NAME: Final = "PRIVATE_BUNDLE_SEAL.json"
PRIVATE_COPY_RECORD_NAME: Final = "PRIVATE_ARCHIVE_COPY_RECORD.json"
EXTERNAL_COPY_RECORD_NAME: Final = "COPY_RECORD.json"
EXTERNAL_ARCHIVE_ROOT: Final = Path("/Volumes/Macintosh HD - Data/GIC-Lab/t07/sealed-artifacts")
EXTERNAL_ARCHIVE_ID: Final = f"{RUN_ID}-PRIVATE-PARAMETERS-V2"

HUMAN_DECISION_SCHEMA_PATH: Final = "schemas/t07-lambda-l2-human-decision.schema.json"
PRIVATE_PARAMETERS_SCHEMA_PATH: Final = "schemas/t07-lambda-l2-private-parameters.schema.json"
HOST_KEY_CHECKPOINT_SCHEMA_PATH: Final = "schemas/t07-lambda-l2-host-key-checkpoint.schema.json"
PLAN_SCHEMA_PATH: Final = "schemas/t07-lambda-l2-plan.schema.json"
PROVIDER_LEDGER_SCHEMA_PATH: Final = "schemas/t07-lambda-l2-provider-ledger.schema.json"
HOST_EVIDENCE_SCHEMA_PATH: Final = "schemas/t07-lambda-l2-host-evidence.schema.json"
INCIDENT_SCHEMA_PATH: Final = "schemas/t07-lambda-l2-incident.schema.json"

CURRENT_OPENAPI_VERSION: Final = "1.10.0"
CURRENT_OPENAPI_URL: Final = "https://docs-api.lambda.ai/api/cloud/spec.json"
CURRENT_OPENAPI_RETRIEVED_AT_UTC: Final = "2026-08-10T18:55:19.805786Z"
CURRENT_OPENAPI_BYTES: Final = 240_288
CURRENT_OPENAPI_SHA256: Final = "320f4877924984f060b179e86595ed58918a1d0696b60b99cae548ec164934f4"
PRIOR_OPENAPI_SHA256: Final = "365488015cf79fda38e1268f44a9e2d4af4fe2794ad3c6878c78a7e1f98caded"

EXPECTED_SELECTION: Final = {
    "selected_instance_type": "gpu_1x_a10",
    "selected_region": "us-east-1",
    "selected_image_alias": "img-0111",
    "expected_image_version": "22.4.5-2141",
    "selected_ssh_key_name": "fractal-lambda-codex",
    "ssh_private_access_mode": "preloaded-ssh-agent",
    "firewall_strategy": "temporary-global-ssh-only-plus-regional-ssh-only",
    "host_key_trust_method": "lambda-jupyter-independent-ed25519-fingerprint",
}

MAX_PROVIDER_WALL_SECONDS: Final = 3_600
MAX_PROVIDER_COST_CENTS: Final = 200
SELECTED_LIST_PRICE_CENTS_PER_HOUR: Final = 129
MAX_HUMAN_CHECKPOINT_SECONDS: Final = 600
MAX_PROVIDER_API_CALLS: Final = 140
MAX_READ_ONLY_PRELAUNCH_CALLS: Final = 7
MAX_FIREWALL_MUTATION_CALLS: Final = 4
MAX_FIREWALL_VERIFICATION_CALLS: Final = 5
MAX_LAUNCH_CALLS: Final = 1
MAX_LAUNCH_RECOVERY_CALLS: Final = 1
MAX_ACTIVE_POLLS: Final = 60
MAX_TERMINATION_CALLS: Final = 1
MAX_TERMINAL_POLLS: Final = 60
MAX_FINAL_ZERO_INSTANCE_CALLS: Final = 1
MIN_PROVIDER_REQUEST_SPACING_SECONDS: Final = 1
INSTANCE_POLL_SPACING_SECONDS: Final = 2
AUTOMATIC_RETRIES: Final = 0
MAX_PROVIDER_RESPONSE_BYTES_PER_CALL: Final = 1_048_576
MAX_PROVIDER_RESPONSE_BYTES_AGGREGATE: Final = 16_777_216
MAX_PROVIDER_LEDGER_BYTES: Final = 1_048_576
MAX_PROVIDER_LEDGER_EVENTS: Final = 768
MAX_PROVIDER_LEDGER_EVENT_BYTES: Final = 4_096
MAX_PROVIDER_REQUEST_BODY_BYTES: Final = 65_536
MAX_REGIONAL_CREATE_RECOVERY_CALLS: Final = 1
MAX_TCP_READINESS_PROBES: Final = 30
MAX_SSH_KEYSCAN_CALLS: Final = 1
MAX_SSH_AGENT_INSPECTION_CALLS: Final = 1
MAX_HOST_INSPECTION_COMMANDS: Final = 9
MAX_SSH_SESSIONS: Final = 33
MAX_REMOTE_COMMANDS: Final = 33
MAX_SSH_OUTPUT_BYTES_PER_CALL: Final = 1_048_576
MAX_SSH_OUTPUT_BYTES_AGGREGATE: Final = 16_777_216
MAX_SSH_TRANSFER_CALLS: Final = 33
MAX_DOCKER_CALLS: Final = 24
MAX_DOCKER_OUTPUT_BYTES_PER_CALL: Final = 1_048_576
MAX_DOCKER_OUTPUT_BYTES_AGGREGATE: Final = 16_777_216
MAX_REGISTRY_METADATA_CALLS_BEFORE_EXECUTION: Final = 3
MAX_REGISTRY_RESPONSE_BYTES: Final = 4_194_304
MAX_DOCKER_DISK_DELTA_BYTES: Final = 33_554_432
MIN_ROOT_FREE_BYTES: Final = 10_737_418_240
MIN_DOCKER_ROOT_FREE_BYTES: Final = 10_737_418_240
MAX_REMOTE_EVIDENCE_BYTES: Final = 62_914_560
MAX_TRANSFER_BYTES: Final = 62_914_560
MAX_MAC_ACTIVE_EVIDENCE_BYTES: Final = 67_108_864
MAX_ARCHIVE_BYTES: Final = 67_108_864
MAX_LOCAL_INCREMENTAL_BYTES: Final = 135_266_304
MIN_LOCAL_PREWRITE_FREE_BYTES: Final = 8_725_200_896
MIN_LOCAL_RETAINED_FREE_BYTES: Final = 8_589_934_592
MAX_ARCHIVE_COPY_CALLS: Final = 1
MAX_PRIVATE_BINDING_BYTES: Final = 262_144
MAX_PRIVATE_ARCHIVE_BYTES: Final = 1_048_576
EXTERNAL_CONTAINER_CAPACITY_BYTES: Final = 1_000_240_963_584
EXTERNAL_RETAINED_FREE_FLOOR_BYTES: Final = 200_048_192_717
EXTERNAL_PRECOPY_FREE_FLOOR_BYTES: Final = 200_115_301_581

CONTAINER_CPU: Final = "1.000"
CONTAINER_MEMORY_BYTES: Final = 268_435_456
CONTAINER_PID_LIMIT: Final = 64
CONTAINER_WALL_SECONDS: Final = 30
CONTAINER_OUTPUT_BYTES: Final = 16_777_216
CONTAINER_TMPFS_BYTES: Final = 16_777_216
CONTAINER_SHM_BYTES: Final = 16_777_216
CONTAINER_STOP_SECONDS: Final = 1

INVENTORY_RELATIVE_PATH: Final = Path(
    "artifacts/t07/lambda/gate-l1/RUN-T07-L1-LAMBDA-INVENTORY-0003/inventory-redacted.json"
)
L1A_PRIVATE_RELATIVE_PATH: Final = Path(
    "artifacts/t07/lambda/gate-l1a/"
    "RUN-T07-L1A-LAMBDA-SSH-KEY-FINGERPRINT-0001/private-evidence.json"
)
CONTAINMENT_FIXTURE_PATH: Final = "containers/sira-smoke/lambda/adversarial-containment.sh"
CONTAINMENT_FIXTURE_SHA256: Final = (
    "09838913b14d23da939225cb89411619e91cb9ee023a2721b5b7c3890ac90aea"
)

_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_COMMIT = re.compile(r"^[a-f0-9]{40}$")
_NONCE = re.compile(r"^[a-f0-9]{64}$")
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$")
_PRIVATE_PUBLIC_PATTERNS = (
    re.compile(r"(?:^|[^0-9])(?:[0-9]{1,3}\.){3}[0-9]{1,3}/32(?:$|[^0-9])"),
    re.compile(r"SHA256:[A-Za-z0-9+/]{20,}"),
    re.compile(r"(?:/Users/[^/]+/\.ssh/|~/\.ssh/|SSH_AUTH_SOCK=)"),
)


def canonical_bytes(value: object) -> bytes:
    """Return the single canonical JSON encoding used by every L2.0 hash."""

    return (
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        + b"\n"
    )


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _read_regular_no_follow(
    path: Path,
    *,
    max_bytes: int,
    required_mode: int | None = None,
    require_owner: bool = True,
) -> bytes:
    try:
        linked = os.lstat(path)
    except OSError:
        raise L20ContractError("required private or sealed input is unavailable") from None
    if not stat.S_ISREG(linked.st_mode) or stat.S_ISLNK(linked.st_mode):
        raise L20ContractError("required input is not one no-follow regular file")
    if require_owner and linked.st_uid != os.getuid():
        raise L20ContractError("required input is not owned by the current user")
    if required_mode is not None and stat.S_IMODE(linked.st_mode) != required_mode:
        raise L20ContractError("private input mode is not exact")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError:
        raise L20ContractError("required input could not be opened safely") from None
    try:
        opened = os.fstat(descriptor)
        if (
            not stat.S_ISREG(opened.st_mode)
            or opened.st_nlink != 1
            or (opened.st_dev, opened.st_ino) != (linked.st_dev, linked.st_ino)
        ):
            raise L20ContractError("required input identity changed during open")
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(descriptor, min(65_536, max_bytes + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > max_bytes:
                raise L20ContractError("required input exceeds its byte cap")
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def _strict_json(encoded: bytes, *, context: str) -> dict[str, object]:
    try:
        value = json.loads(encoded)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise L20ContractError(f"{context} is not valid JSON") from None
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise L20ContractError(f"{context} must be an object")
    return value


def _load_schema(repository_root: Path, relative: str) -> dict[str, object]:
    encoded = _read_regular_no_follow(
        repository_root / relative,
        max_bytes=256 * 1024,
        require_owner=False,
    )
    return _strict_json(encoded, context=relative)


def _validate_schema(
    document: Mapping[str, object],
    *,
    repository_root: Path,
    schema_relative_path: str,
) -> None:
    schema = _load_schema(repository_root, schema_relative_path)
    errors = sorted(
        Draft202012Validator(schema).iter_errors(document),
        key=lambda item: list(item.absolute_path),
    )
    if errors:
        raise L20ContractError(f"{schema_relative_path} rejected the document")


def _public_ipv4_32(value: object) -> str:
    if not isinstance(value, str):
        raise L20ContractError("source network is not a string")
    try:
        network = ipaddress.ip_network(value, strict=True)
    except ValueError:
        raise L20ContractError("source network is not a canonical public IPv4 /32") from None
    if (
        not isinstance(network, ipaddress.IPv4Network)
        or network.prefixlen != 32
        or not network.network_address.is_global
        or network.network_address.is_multicast
        or network.network_address.is_unspecified
        or network.network_address.is_loopback
        or network.network_address.is_link_local
        or network.network_address.is_reserved
    ):
        raise L20ContractError("source network is not a canonical public IPv4 /32")
    return str(network)


@dataclass(frozen=True, slots=True)
class ValidatedHumanDecision:
    path: Path = field(repr=False)
    encoded: bytes = field(repr=False)
    document: Mapping[str, object] = field(repr=False)
    sha256: str
    bytes: int


def validate_human_decision_document(document: Mapping[str, object]) -> None:
    """Enforce the human choices and non-scientific hard ceilings."""

    if (
        not isinstance(document.get("decision_nonce"), str)
        or _NONCE.fullmatch(str(document.get("decision_nonce"))) is None
    ):
        raise L20ContractError("decision nonce must be 32 random bytes in lowercase hex")
    _public_ipv4_32(document.get("source_ipv4_cidr"))
    for key, expected in EXPECTED_SELECTION.items():
        if document.get(key) != expected:
            raise L20ContractError("human resource or security selection differs from contract")
    if (
        document.get(
            "attest_no_other_workspace_resource_depends_on_current_global_inbound_rules_during_window"
        )
        is not True
        or document.get("approve_unique_ssh_key_match") is not True
        or document.get("approve_no_persistent_filesystem") is not True
        or document.get("persistent_filesystem") is not None
    ):
        raise L20ContractError("required human attestation or no-filesystem choice is absent")
    cost = document.get("max_provider_cost_usd")
    if not isinstance(cost, (int, float)) or isinstance(cost, bool) or float(cost) != 2.0:
        raise L20ContractError("provider cost ceiling differs from USD 2.00")
    if document.get("max_provider_wall_seconds") != MAX_PROVIDER_WALL_SECONDS:
        raise L20ContractError("provider wall ceiling differs from 3600 seconds")
    if document.get("max_host_key_checkpoint_seconds") != MAX_HUMAN_CHECKPOINT_SECONDS:
        raise L20ContractError("host-key checkpoint ceiling differs from 600 seconds")


def load_human_decision(
    repository_root: Path,
    *,
    path: Path = DECISION_PATH,
) -> ValidatedHumanDecision:
    """Open, schema-check, and semantically validate the private decision."""

    encoded = _read_regular_no_follow(path, max_bytes=16_384, required_mode=0o600)
    document = _strict_json(encoded, context="private human decision")
    _validate_schema(
        document,
        repository_root=repository_root,
        schema_relative_path=HUMAN_DECISION_SCHEMA_PATH,
    )
    validate_human_decision_document(document)
    return ValidatedHumanDecision(
        path=path,
        encoded=encoded,
        document=document,
        sha256=sha256_bytes(encoded),
        bytes=len(encoded),
    )


def _mapping(value: object, *, context: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or any(not isinstance(key, str) for key in value):
        raise L20ContractError(f"{context} is not an object")
    return value


def _sequence(value: object, *, context: str) -> Sequence[object]:
    if not isinstance(value, list):
        raise L20ContractError(f"{context} is not an array")
    return value


def _nonempty(value: object, *, context: str) -> str:
    if not isinstance(value, str) or not value:
        raise L20ContractError(f"{context} is not a nonempty string")
    return value


def _integer(value: object, *, context: str) -> int:
    if type(value) is not int or value < 0:
        raise L20ContractError(f"{context} is not a nonnegative integer")
    return value


def _load_bound_json(repository_root: Path, relative: Path, *, cap: int) -> dict[str, object]:
    return _strict_json(
        _read_regular_no_follow(repository_root / relative, max_bytes=cap),
        context=str(relative),
    )


def _version_key(version: str) -> tuple[int, ...]:
    try:
        return tuple(int(part) for part in version.replace("-", ".").split("."))
    except ValueError:
        raise L20ContractError("selected image version is not numeric and comparable") from None


@dataclass(frozen=True, slots=True)
class PrivateMaterialization:
    private_document: Mapping[str, object] = field(repr=False)
    decision_alias: str
    decision_sha256: str
    raw_image_id_bound: bool
    raw_ssh_key_id_bound: bool
    local_public_identity_bound: bool
    global_firewall_snapshot_bound: bool


def resolve_private_parameters(
    repository_root: Path,
    decision: ValidatedHumanDecision,
) -> PrivateMaterialization:
    """Resolve selected aliases to raw ignored evidence without exposing the values."""

    plan = load_inventory_plan_v3(
        repository_root / "containers/sira-smoke/lambda/gate-l1-readonly-inventory-plan-v3.json",
        expected_sha256=PLAN_SHA256,
    )
    run_binding = InventoryRunBindingV3(
        run_id="RUN-T07-L1-LAMBDA-INVENTORY-0003",
        repository_commit=EXECUTION_COMMIT,
        implementation_commit=IMPLEMENTATION_COMMIT,
        authorization_reference=AUTHORIZATION_REFERENCE,
        authorization_sha256=AUTHORIZATION_SHA256,
    )
    try:
        gate_evidence = validate_l13_gate_l2_evidence(
            repository_root,
            plan=plan,
            plan_sha256=PLAN_SHA256,
            run_binding=run_binding,
        )
    except L13ContractError:
        raise L20ContractError("sealed Gate L1/L1.3 evidence failed revalidation") from None
    if gate_evidence.inventory_sha256 != INVENTORY_SHA256:
        raise L20ContractError("sealed inventory binding drifted")

    inventory = _load_bound_json(
        repository_root,
        INVENTORY_RELATIVE_PATH,
        cap=524_288,
    )
    alias_map = _load_bound_json(
        repository_root,
        ALIAS_MAP_RELATIVE_ROOT / "image-id-alias-map.json",
        cap=65_536,
    )
    l1a = _load_bound_json(
        repository_root,
        L1A_PRIVATE_RELATIVE_PATH,
        cap=262_144,
    )

    if _sequence(inventory.get("running_instances"), context="running instances"):
        raise L20ContractError("sealed inventory contains a running instance")

    image_rows = _sequence(inventory.get("images"), context="images")
    projection = project_image_identities(image_rows)
    candidate_matrix = build_resource_candidate_matrix(inventory, projection)
    candidates = [
        _mapping(value, context="candidate")
        for value in _sequence(
            candidate_matrix.get("qualifying_candidates"),
            context="candidate matrix",
        )
    ]
    selected_candidates = [
        candidate
        for candidate in candidates
        if candidate.get("instance_type_name") == decision.document["selected_instance_type"]
        and candidate.get("region_name") == decision.document["selected_region"]
        and candidate.get("image_alias") == decision.document["selected_image_alias"]
        and candidate.get("image_version") == decision.document["expected_image_version"]
    ]
    if len(selected_candidates) != 1:
        raise L20ContractError("selected candidate is not unique in sealed evidence")
    selected_candidate = selected_candidates[0]
    if selected_candidate.get("price_cents_per_hour") != SELECTED_LIST_PRICE_CENTS_PER_HOUR:
        raise L20ContractError("selected candidate price drifted")
    selected_family_versions = [
        _nonempty(candidate.get("image_version"), context="candidate image version")
        for candidate in candidates
        if candidate.get("instance_type_name") == decision.document["selected_instance_type"]
        and candidate.get("region_name") == decision.document["selected_region"]
        and candidate.get("image_family") == "gpu-base-22-04"
    ]
    if _version_key(str(decision.document["expected_image_version"])) != max(
        _version_key(value) for value in selected_family_versions
    ):
        raise L20ContractError("selected image is not newest in the compatible selected family")

    alias_entries = [
        _mapping(value, context="image alias entry")
        for value in _sequence(alias_map.get("entries"), context="image alias entries")
    ]
    raw_image_matches = [
        _nonempty(entry.get("raw_image_id"), context="raw image ID")
        for entry in alias_entries
        if entry.get("alias") == decision.document["selected_image_alias"]
    ]
    if len(raw_image_matches) != 1:
        raise L20ContractError("selected image alias does not resolve uniquely")
    raw_image_id = raw_image_matches[0]
    matching_rows = [
        _mapping(value, context="selected image row")
        for value in image_rows
        if _mapping(value, context="image row").get("id") == raw_image_id
        and _mapping(_mapping(value, context="image row").get("region"), context="region").get(
            "name"
        )
        == decision.document["selected_region"]
    ]
    if not matching_rows or any(
        row.get("version") != decision.document["expected_image_version"]
        or row.get("family") != "gpu-base-22-04"
        or row.get("architecture") != "x86_64"
        for row in matching_rows
    ):
        raise L20ContractError("raw image binding conflicts with selected public metadata")

    account_matches = [
        _mapping(value, context="account key match")
        for value in _sequence(
            l1a.get("account_to_local_matches"),
            context="account key matches",
        )
        if _mapping(value, context="account key match").get("account_key_name")
        == decision.document["selected_ssh_key_name"]
    ]
    if len(account_matches) != 1 or account_matches[0].get("match_status") != "unique_match":
        raise L20ContractError("selected SSH key lacks one sealed local match")
    raw_ssh_key_id = _nonempty(
        account_matches[0].get("raw_api_key_id"),
        context="raw provider SSH key identity",
    )
    local_aliases = _sequence(
        account_matches[0].get("matching_local_key_aliases"),
        context="matching local key aliases",
    )
    if len(local_aliases) != 1:
        raise L20ContractError("selected SSH key local match is not unique")
    local_key_alias = _nonempty(local_aliases[0], context="local key alias")
    local_matches = [
        _mapping(value, context="local public key")
        for value in _sequence(l1a.get("local_public_keys"), context="local public keys")
        if _mapping(value, context="local public key").get("local_key_alias") == local_key_alias
    ]
    if len(local_matches) != 1 or local_matches[0].get("private_key_bytes_accessed") is not False:
        raise L20ContractError("local public identity evidence is unsafe")
    local_key = local_matches[0]
    if local_key.get("basename") != "fractal_lambda_ed25519.pub":
        raise L20ContractError("selected local public key basename drifted")
    if l1a.get("private_key_bytes_accessed") is not False or l1a.get("ssh_invoked") is not False:
        raise L20ContractError("Gate L1A evidence indicates prohibited private access or SSH")

    inventory_keys = [
        _mapping(value, context="inventory SSH key")
        for value in _sequence(inventory.get("ssh_keys"), context="inventory SSH keys")
        if _mapping(value, context="inventory SSH key").get("name")
        == decision.document["selected_ssh_key_name"]
    ]
    if len(inventory_keys) != 1 or inventory_keys[0].get("id") != raw_ssh_key_id:
        raise L20ContractError("provider SSH identity differs across sealed evidence")

    globals_found = [
        _mapping(value, context="global firewall ruleset")
        for value in _sequence(inventory.get("firewall_rulesets"), context="firewall rulesets")
        if _mapping(value, context="firewall ruleset").get("scope") == "global"
    ]
    if len(globals_found) != 1:
        raise L20ContractError("global firewall baseline is not unique")
    global_baseline = globals_found[0]
    original_rules = _sequence(global_baseline.get("rules"), context="global firewall rules")
    if len(original_rules) != 4:
        raise L20ContractError("global firewall baseline rule count drifted")
    regional = [
        value
        for value in _sequence(inventory.get("firewall_rulesets"), context="firewall rulesets")
        if _mapping(value, context="firewall ruleset").get("scope") != "global"
    ]
    if regional:
        raise L20ContractError("sealed inventory unexpectedly contains a regional ruleset")

    nonce = _nonempty(decision.document.get("decision_nonce"), context="decision nonce")
    suffix = hashlib.sha256(f"{nonce}:{PLAN_ID}".encode()).hexdigest()[:12]
    decision_alias = f"l2-decision-{suffix}"
    ruleset_name = f"giclab-t07-l2-rs-{suffix}"
    instance_name = f"giclab-t07-l2-{suffix}"
    hostname = f"giclab-t07-l2-{suffix}"
    source_cidr = _public_ipv4_32(decision.document.get("source_ipv4_cidr"))
    strict_rule = {
        "description": "T07 temporary qualification SSH",
        "port_range": [22, 22],
        "protocol": "tcp",
        "source_network": source_cidr,
    }
    tags = [
        {"key": "giclab-experiment", "value": "EXP-0001"},
        {"key": "giclab-gate", "value": "T07-L2"},
        {"key": "giclab-run", "value": RUN_ID},
        {"key": "giclab-owner", "value": suffix},
        {"key": "giclab-plan", "value": PLAN_ID},
    ]
    launch_template: dict[str, object] = {
        "region_name": decision.document["selected_region"],
        "instance_type_name": decision.document["selected_instance_type"],
        "ssh_key_names": [decision.document["selected_ssh_key_name"]],
        "file_system_names": [],
        "file_system_mounts": [],
        "name": instance_name,
        "hostname": hostname,
        "image": {"id": raw_image_id},
        "tags": tags,
        "authorization_tag_runtime_binding": "authorization_reference",
        "firewall_rulesets_runtime_binding": "owned_regional_ruleset_id",
    }
    private_document: dict[str, object] = {
        "schema_version": "0.1.0",
        "plan_id": PLAN_ID,
        "run_id": RUN_ID,
        "decision_alias": decision_alias,
        "decision_file_sha256": decision.sha256,
        "decision_nonce": nonce,
        "selected_resource": {
            "instance_type_name": decision.document["selected_instance_type"],
            "region_name": decision.document["selected_region"],
            "image_alias": decision.document["selected_image_alias"],
            "image_version": decision.document["expected_image_version"],
            "image_family": "gpu-base-22-04",
            "architecture": "x86_64",
            "raw_image_id": raw_image_id,
            "price_cents_per_hour": SELECTED_LIST_PRICE_CENTS_PER_HOUR,
            "ssh_key_name": decision.document["selected_ssh_key_name"],
            "raw_ssh_key_id": raw_ssh_key_id,
            "local_public_key_alias": local_key_alias,
            "local_public_key_basename": local_key["basename"],
            "local_public_identity_file": local_key["exact_path"],
            "local_public_key_fingerprint": local_key["fingerprint"],
        },
        "source_ipv4_cidr": source_cidr,
        "original_global_firewall": {
            "inventory_sha256": INVENTORY_SHA256,
            "rules": list(original_rules),
            "normalized_rules_sha256": sha256_bytes(canonical_bytes(list(original_rules))),
        },
        "owned_names": {
            "regional_ruleset_name": ruleset_name,
            "instance_name": instance_name,
            "hostname": hostname,
            "tags": tags,
        },
        "requests": {
            "strict_global_patch_body": {"rules": [strict_rule]},
            "regional_create_body": {
                "name": ruleset_name,
                "region": decision.document["selected_region"],
                "rules": [strict_rule],
            },
            "launch_body_template": launch_template,
            "terminate_body_template": {"instance_ids_runtime_binding": "owned_instance_id"},
            "restore_global_patch_body": {
                "rules_runtime_binding": "sealed_original_global_response.data.rules"
            },
        },
        "runtime_bindings": [
            {
                "name": "owned_regional_ruleset_id",
                "source_operation": "create-response-or-one-owned-name-recovery",
                "resolver": "giclab.harness.lambda_l20_plan.resolve_owned_regional_ruleset_id",
                "cardinality": 1,
            },
            {
                "name": "owned_instance_id",
                "source_operation": "launch-response-or-one-owned-name-tag-recovery",
                "resolver": "giclab.harness.lambda_l20_plan.resolve_owned_instance_id",
                "cardinality": 1,
            },
            {
                "name": "owned_instance_public_ipv4",
                "source_operation": "get-owned-instance-active",
                "resolver": "giclab.harness.lambda_l20_plan.resolve_owned_instance_active_ipv4",
                "cardinality": 1,
            },
            {
                "name": "approved_agent_socket",
                "source_operation": "local-agent-preflight",
                "resolver": "giclab.harness.lambda_l20_plan.require_unique_agent_match",
                "cardinality": 1,
            },
            {
                "name": "sealed_original_global_response.data.rules",
                "source_operation": "get-global-firewall-before-first-mutation",
                "resolver": "giclab.harness.lambda_l20_plan.render_global_restore_body",
                "cardinality": 1,
            },
        ],
        "access": {
            "mode": "preloaded-ssh-agent",
            "provider_username": "ubuntu",
            "private_key_file_read_allowed": False,
            "agent_forwarding_allowed": False,
            "host_key_method": "lambda-jupyter-independent-ed25519-fingerprint",
        },
        "persistent_filesystem_count": 0,
        "scientific_execution_allowed": False,
    }
    _validate_schema(
        private_document,
        repository_root=repository_root,
        schema_relative_path=PRIVATE_PARAMETERS_SCHEMA_PATH,
    )
    return PrivateMaterialization(
        private_document=private_document,
        decision_alias=decision_alias,
        decision_sha256=decision.sha256,
        raw_image_id_bound=True,
        raw_ssh_key_id_bound=True,
        local_public_identity_bound=True,
        global_firewall_snapshot_bound=True,
    )


def _directory_flags() -> int:
    return os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)


def _create_private_root(repository_root: Path) -> int:
    descriptor = os.open(repository_root, _directory_flags())
    try:
        for part in PRIVATE_ROOT_RELATIVE.parts:
            try:
                os.mkdir(part, 0o700, dir_fd=descriptor)
                os.fsync(descriptor)
            except FileExistsError:
                if part == PRIVATE_ROOT_RELATIVE.parts[-1]:
                    raise L20ContractError("private Gate L2 run root already exists") from None
            child = os.open(part, _directory_flags(), dir_fd=descriptor)
            observed = os.fstat(child)
            if (
                not stat.S_ISDIR(observed.st_mode)
                or observed.st_uid != os.getuid()
                or stat.S_IMODE(observed.st_mode) & 0o077
            ):
                os.close(child)
                raise L20ContractError("private Gate L2 run hierarchy is unsafe")
            os.close(descriptor)
            descriptor = child
        return descriptor
    except Exception:
        os.close(descriptor)
        raise


def _write_exclusive_fsync(directory_fd: int, name: str, encoded: bytes) -> None:
    descriptor = os.open(
        name,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        0o600,
        dir_fd=directory_fd,
    )
    try:
        view = memoryview(encoded)
        while view:
            written = os.write(descriptor, view)
            if written < 1:
                raise L20ContractError("private evidence write made no progress")
            view = view[written:]
        os.fsync(descriptor)
        os.fchmod(descriptor, 0o400)
    finally:
        os.close(descriptor)


def _read_regular_at(directory_fd: int, name: str, *, max_bytes: int) -> bytes:
    descriptor = os.open(name, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0), dir_fd=directory_fd)
    try:
        observed = os.fstat(descriptor)
        if not stat.S_ISREG(observed.st_mode) or observed.st_nlink != 1:
            raise L20ContractError("private evidence is not one regular file")
        output = bytearray()
        while True:
            chunk = os.read(descriptor, min(65_536, max_bytes + 1 - len(output)))
            if not chunk:
                break
            output.extend(chunk)
            if len(output) > max_bytes:
                raise L20ContractError("private evidence exceeds its byte cap")
        return bytes(output)
    finally:
        os.close(descriptor)


@dataclass(frozen=True, slots=True)
class PrivateBindingSeal:
    root: Path
    decision_alias: str
    decision_sha256: str
    decision_seal_sha256: str
    parameters_sha256: str
    parameters_seal_sha256: str
    bundle_seal_sha256: str
    total_bytes: int
    external_archive_path: str
    external_archive_seal_sha256: str
    external_copy_record_sha256: str

    def public_binding(self) -> dict[str, object]:
        if (
            not self.external_archive_path
            or _SHA256.fullmatch(self.external_archive_seal_sha256) is None
            or _SHA256.fullmatch(self.external_copy_record_sha256) is None
        ):
            raise L20ContractError("private binding has not been durably archived")
        return {
            "state": "ignored-sealed-local-and-external-evidence",
            "decision_alias": self.decision_alias,
            "decision_sha256": self.decision_sha256,
            "decision_seal_sha256": self.decision_seal_sha256,
            "parameters_sha256": self.parameters_sha256,
            "parameters_seal_sha256": self.parameters_seal_sha256,
            "bundle_seal_sha256": self.bundle_seal_sha256,
            "external_archive_id": EXTERNAL_ARCHIVE_ID,
            "external_archive_path": self.external_archive_path,
            "external_archive_seal_sha256": self.external_archive_seal_sha256,
            "external_copy_record_sha256": self.external_copy_record_sha256,
            "private_values_in_public_plan": False,
            "nonce_protected_hash_binding": True,
        }


def write_private_binding(
    repository_root: Path,
    *,
    decision: ValidatedHumanDecision,
    materialization: PrivateMaterialization,
) -> PrivateBindingSeal:
    """Write the decision and resolved parameters exactly once under ignored evidence."""

    root = repository_root.resolve(strict=True)
    if root != repository_root.absolute():
        raise L20ContractError("repository root is not canonical")
    ignored = _read_regular_no_follow(root / ".gitignore", max_bytes=65_536)
    if b"artifacts/" not in {line.strip() for line in ignored.splitlines()}:
        raise L20ContractError("private artifact root is not ignored by Git")
    parameter_bytes = canonical_bytes(materialization.private_document)
    if len(decision.encoded) + len(parameter_bytes) > MAX_PRIVATE_BINDING_BYTES:
        raise L20ContractError("private binding exceeds its aggregate cap")
    decision_seal = canonical_bytes(
        {
            "schema_version": "0.1.0",
            "plan_id": PLAN_ID,
            "run_id": RUN_ID,
            "decision_alias": materialization.decision_alias,
            "artifact_name": PRIVATE_DECISION_NAME,
            "artifact_bytes": len(decision.encoded),
            "artifact_sha256": decision.sha256,
            "random_nonce_present": True,
            "private_values_publicly_retained": False,
        }
    )
    parameter_sha = sha256_bytes(parameter_bytes)
    parameter_seal = canonical_bytes(
        {
            "schema_version": "0.1.0",
            "plan_id": PLAN_ID,
            "run_id": RUN_ID,
            "artifact_name": PRIVATE_PARAMETERS_NAME,
            "artifact_bytes": len(parameter_bytes),
            "artifact_sha256": parameter_sha,
            "decision_sha256": decision.sha256,
            "private_values_publicly_retained": False,
        }
    )
    bundle_payload = {
        PRIVATE_DECISION_NAME: (len(decision.encoded), decision.sha256),
        PRIVATE_DECISION_SEAL_NAME: (len(decision_seal), sha256_bytes(decision_seal)),
        PRIVATE_PARAMETERS_NAME: (len(parameter_bytes), parameter_sha),
        PRIVATE_PARAMETERS_SEAL_NAME: (len(parameter_seal), sha256_bytes(parameter_seal)),
    }
    bundle_seal = canonical_bytes(
        {
            "schema_version": "0.1.0",
            "plan_id": PLAN_ID,
            "run_id": RUN_ID,
            "archive_id": EXTERNAL_ARCHIVE_ID,
            "files": [
                {"name": name, "bytes": values[0], "sha256": values[1]}
                for name, values in sorted(bundle_payload.items())
            ],
            "source_retained": True,
        }
    )
    descriptor = _create_private_root(root)
    try:
        for name, encoded in (
            (PRIVATE_DECISION_NAME, decision.encoded),
            (PRIVATE_DECISION_SEAL_NAME, decision_seal),
            (PRIVATE_PARAMETERS_NAME, parameter_bytes),
            (PRIVATE_PARAMETERS_SEAL_NAME, parameter_seal),
            (PRIVATE_BUNDLE_SEAL_NAME, bundle_seal),
        ):
            _write_exclusive_fsync(descriptor, name, encoded)
        os.fsync(descriptor)
        for name, encoded in (
            (PRIVATE_DECISION_NAME, decision.encoded),
            (PRIVATE_DECISION_SEAL_NAME, decision_seal),
            (PRIVATE_PARAMETERS_NAME, parameter_bytes),
            (PRIVATE_PARAMETERS_SEAL_NAME, parameter_seal),
            (PRIVATE_BUNDLE_SEAL_NAME, bundle_seal),
        ):
            if _read_regular_at(descriptor, name, max_bytes=MAX_PRIVATE_BINDING_BYTES) != encoded:
                raise L20ContractError("private binding post-fsync readback drifted")
    finally:
        os.close(descriptor)
    return PrivateBindingSeal(
        root=root / PRIVATE_ROOT_RELATIVE,
        decision_alias=materialization.decision_alias,
        decision_sha256=decision.sha256,
        decision_seal_sha256=sha256_bytes(decision_seal),
        parameters_sha256=parameter_sha,
        parameters_seal_sha256=sha256_bytes(parameter_seal),
        bundle_seal_sha256=sha256_bytes(bundle_seal),
        total_bytes=sum(values[0] for values in bundle_payload.values()) + len(bundle_seal),
        external_archive_path="",
        external_archive_seal_sha256="",
        external_copy_record_sha256="",
    )


def archive_private_binding(binding: PrivateBindingSeal) -> PrivateBindingSeal:
    """Copy the sealed private bundle one way to the approved external archive.

    This is the only L2.0 function that observes storage or writes outside the
    repository.  It performs no network, provider, SSH, Docker, or secret action.
    """

    if binding.root != binding.root.resolve(strict=True):
        raise L20ContractError("private binding source root is not canonical")
    observer = DiskutilVolumeObserver()
    try:
        external_before, system_before = observer()
        _validate_external(external_before, incremental_bytes=MAX_PRIVATE_ARCHIVE_BYTES)
        _validate_system(system_before, floor_bytes=MIN_LOCAL_PREWRITE_FREE_BYTES)
    except InventoryArchiveError:
        raise L20ContractError("private archive storage preflight failed") from None

    external_handle: _HeldDirectory | None = None
    archive_handle: _HeldDirectory | None = None
    source_handle: _HeldDirectory | None = None
    staging_descriptor = -1
    final_descriptor = -1
    try:
        external_handle = _HeldDirectory.open(Path("/Volumes/Macintosh HD - Data"))
        archive_handle = _open_or_create_archive_root(external_handle, EXTERNAL_ARCHIVE_ROOT)
        source_handle = _HeldDirectory.open(binding.root)
        if source_handle.device == external_handle.device:
            raise L20ContractError("private archive source and destination share a volume")
        external_after, system_after = observer()
        if not _same_identity(external_before, external_after) or not _same_identity(
            system_before, system_after
        ):
            raise L20ContractError("private archive volume identity changed before write")
        _validate_external(external_after, incremental_bytes=MAX_PRIVATE_ARCHIVE_BYTES)
        _validate_system(system_after, floor_bytes=MIN_LOCAL_PREWRITE_FREE_BYTES)
        for handle in (external_handle, archive_handle, source_handle):
            handle.revalidate()

        staging_name = f".{EXTERNAL_ARCHIVE_ID}.partial"
        try:
            os.stat(EXTERNAL_ARCHIVE_ID, dir_fd=archive_handle.descriptor, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            raise L20ContractError("private external archive identity already exists")
        try:
            os.stat(staging_name, dir_fd=archive_handle.descriptor, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            raise L20ContractError("private external archive staging identity already exists")
        os.mkdir(staging_name, 0o700, dir_fd=archive_handle.descriptor)
        os.fsync(archive_handle.descriptor)
        staging_descriptor = os.open(
            staging_name,
            _directory_flags(),
            dir_fd=archive_handle.descriptor,
        )
        staging_stat = os.fstat(staging_descriptor)
        if staging_stat.st_dev != archive_handle.device or staging_stat.st_uid != os.getuid():
            raise L20ContractError("private external archive staging escaped its volume")

        names = (
            PRIVATE_DECISION_NAME,
            PRIVATE_DECISION_SEAL_NAME,
            PRIVATE_PARAMETERS_NAME,
            PRIVATE_PARAMETERS_SEAL_NAME,
            PRIVATE_BUNDLE_SEAL_NAME,
        )
        manifest: list[dict[str, object]] = []
        total = 0
        for name in names:
            encoded = _archive_read_regular_at(
                source_handle.descriptor,
                name,
                max_bytes=MAX_PRIVATE_BINDING_BYTES,
            )
            total += len(encoded)
            if total > MAX_PRIVATE_ARCHIVE_BYTES:
                raise L20ContractError("private external archive exceeds its byte cap")
            _write_exclusive_at(staging_descriptor, name, encoded)
            readback = _archive_read_regular_at(
                staging_descriptor,
                name,
                max_bytes=MAX_PRIVATE_BINDING_BYTES,
            )
            if readback != encoded:
                raise L20ContractError("private external archive file verification failed")
            manifest.append(
                {
                    "name": name,
                    "bytes": len(encoded),
                    "source_sha256": sha256_bytes(encoded),
                    "destination_sha256": sha256_bytes(readback),
                }
            )
        copy_record = canonical_bytes(
            {
                "schema_version": "0.1.0",
                "plan_id": PLAN_ID,
                "run_id": RUN_ID,
                "archive_id": EXTERNAL_ARCHIVE_ID,
                "source_relative_root": str(PRIVATE_ROOT_RELATIVE),
                "destination_path": str(EXTERNAL_ARCHIVE_ROOT / EXTERNAL_ARCHIVE_ID),
                "source_volume_role": "mac-mini-system-data",
                "destination_volume_uuid": "8478609D-FA37-4ED5-875D-47AE912B9151",
                "destination_physical_store_uuid": ("7904A6F1-F483-4ED7-9E34-BFECAB31C63E"),
                "held_no_follow_descriptors": True,
                "internal_fallback": False,
                "source_retained": True,
                "atomic_finalization": True,
                "files": manifest,
            }
        )
        copy_record_sha = sha256_bytes(copy_record)
        _write_exclusive_at(staging_descriptor, EXTERNAL_COPY_RECORD_NAME, copy_record)
        seal = canonical_bytes(
            {
                "schema_version": "0.1.0",
                "plan_id": PLAN_ID,
                "run_id": RUN_ID,
                "archive_id": EXTERNAL_ARCHIVE_ID,
                "copy_record_sha256": copy_record_sha,
                "payload_files": manifest,
                "payload_bytes": total,
                "source_retained": True,
                "destination_hashes_verified": True,
            }
        )
        if total + len(copy_record) + len(seal) > MAX_PRIVATE_ARCHIVE_BYTES:
            raise L20ContractError("private external sealed bundle exceeds its byte cap")
        _write_exclusive_at(staging_descriptor, "SEAL.json", seal)
        os.fsync(staging_descriptor)
        os.rename(
            staging_name,
            EXTERNAL_ARCHIVE_ID,
            src_dir_fd=archive_handle.descriptor,
            dst_dir_fd=archive_handle.descriptor,
        )
        os.fsync(archive_handle.descriptor)
        os.close(staging_descriptor)
        staging_descriptor = -1
        final_descriptor = os.open(
            EXTERNAL_ARCHIVE_ID,
            _directory_flags(),
            dir_fd=archive_handle.descriptor,
        )
        for entry in manifest:
            name = str(entry["name"])
            readback = _archive_read_regular_at(
                final_descriptor,
                name,
                max_bytes=MAX_PRIVATE_BINDING_BYTES,
            )
            if sha256_bytes(readback) != entry["source_sha256"]:
                raise L20ContractError("final private archive hash verification failed")
        if (
            sha256_bytes(
                _archive_read_regular_at(
                    final_descriptor,
                    EXTERNAL_COPY_RECORD_NAME,
                    max_bytes=65_536,
                )
            )
            != copy_record_sha
            or _archive_read_regular_at(
                final_descriptor,
                "SEAL.json",
                max_bytes=65_536,
            )
            != seal
        ):
            raise L20ContractError("final private archive record verification failed")
        _write_exclusive_fsync(source_handle.descriptor, PRIVATE_COPY_RECORD_NAME, copy_record)
        os.fsync(source_handle.descriptor)
        return replace(
            binding,
            external_archive_path=str(EXTERNAL_ARCHIVE_ROOT / EXTERNAL_ARCHIVE_ID),
            external_archive_seal_sha256=sha256_bytes(seal),
            external_copy_record_sha256=copy_record_sha,
        )
    except (OSError, InventoryArchiveError):
        raise L20ContractError("private archive filesystem action failed") from None
    finally:
        if final_descriptor >= 0:
            os.close(final_descriptor)
        if staging_descriptor >= 0:
            os.close(staging_descriptor)
        if archive_handle is not None:
            with suppress(OSError):
                archive_handle.close()
        if source_handle is not None:
            with suppress(OSError):
                source_handle.close()
        if external_handle is not None:
            with suppress(OSError):
                external_handle.close()


def load_private_binding(repository_root: Path) -> PrivateBindingSeal:
    """Revalidate the retained local source and finalized external private archive."""

    local_root = repository_root / PRIVATE_ROOT_RELATIVE
    local_descriptor = -1
    external_descriptor = -1
    try:
        local_descriptor = os.open(local_root, _directory_flags())
        decision = _read_regular_at(
            local_descriptor,
            PRIVATE_DECISION_NAME,
            max_bytes=16_384,
        )
        decision_seal_encoded = _read_regular_at(
            local_descriptor,
            PRIVATE_DECISION_SEAL_NAME,
            max_bytes=16_384,
        )
        parameters = _read_regular_at(
            local_descriptor,
            PRIVATE_PARAMETERS_NAME,
            max_bytes=MAX_PRIVATE_BINDING_BYTES,
        )
        parameters_seal_encoded = _read_regular_at(
            local_descriptor,
            PRIVATE_PARAMETERS_SEAL_NAME,
            max_bytes=16_384,
        )
        bundle_seal_encoded = _read_regular_at(
            local_descriptor,
            PRIVATE_BUNDLE_SEAL_NAME,
            max_bytes=32_768,
        )
        local_copy_record = _read_regular_at(
            local_descriptor,
            PRIVATE_COPY_RECORD_NAME,
            max_bytes=65_536,
        )
        decision_seal = _strict_json(decision_seal_encoded, context="private decision seal")
        parameters_seal = _strict_json(
            parameters_seal_encoded,
            context="private parameters seal",
        )
        if (
            decision_seal.get("artifact_sha256") != sha256_bytes(decision)
            or decision_seal.get("artifact_bytes") != len(decision)
            or parameters_seal.get("artifact_sha256") != sha256_bytes(parameters)
            or parameters_seal.get("artifact_bytes") != len(parameters)
            or parameters_seal.get("decision_sha256") != sha256_bytes(decision)
        ):
            raise L20ContractError("local private binding seal verification failed")
        decision_alias = _nonempty(
            decision_seal.get("decision_alias"),
            context="decision alias",
        )
        archive_path = EXTERNAL_ARCHIVE_ROOT / EXTERNAL_ARCHIVE_ID
        external_descriptor = os.open(archive_path, _directory_flags())
        external_copy_record = _read_regular_at(
            external_descriptor,
            EXTERNAL_COPY_RECORD_NAME,
            max_bytes=65_536,
        )
        external_seal = _read_regular_at(
            external_descriptor,
            "SEAL.json",
            max_bytes=65_536,
        )
        if external_copy_record != local_copy_record:
            raise L20ContractError("local and external private copy records differ")
        for name, encoded in (
            (PRIVATE_DECISION_NAME, decision),
            (PRIVATE_DECISION_SEAL_NAME, decision_seal_encoded),
            (PRIVATE_PARAMETERS_NAME, parameters),
            (PRIVATE_PARAMETERS_SEAL_NAME, parameters_seal_encoded),
            (PRIVATE_BUNDLE_SEAL_NAME, bundle_seal_encoded),
        ):
            if (
                _read_regular_at(
                    external_descriptor,
                    name,
                    max_bytes=MAX_PRIVATE_BINDING_BYTES,
                )
                != encoded
            ):
                raise L20ContractError("external private payload differs from local source")
        external_seal_document = _strict_json(
            external_seal,
            context="external private bundle seal",
        )
        if (
            external_seal_document.get("archive_id") != EXTERNAL_ARCHIVE_ID
            or external_seal_document.get("copy_record_sha256")
            != sha256_bytes(external_copy_record)
            or external_seal_document.get("source_retained") is not True
            or external_seal_document.get("destination_hashes_verified") is not True
        ):
            raise L20ContractError("external private bundle seal contract drifted")
        return PrivateBindingSeal(
            root=local_root,
            decision_alias=decision_alias,
            decision_sha256=sha256_bytes(decision),
            decision_seal_sha256=sha256_bytes(decision_seal_encoded),
            parameters_sha256=sha256_bytes(parameters),
            parameters_seal_sha256=sha256_bytes(parameters_seal_encoded),
            bundle_seal_sha256=sha256_bytes(bundle_seal_encoded),
            total_bytes=(
                len(decision)
                + len(decision_seal_encoded)
                + len(parameters)
                + len(parameters_seal_encoded)
                + len(bundle_seal_encoded)
            ),
            external_archive_path=str(archive_path),
            external_archive_seal_sha256=sha256_bytes(external_seal),
            external_copy_record_sha256=sha256_bytes(external_copy_record),
        )
    except OSError:
        raise L20ContractError("sealed private binding is unavailable") from None
    finally:
        if external_descriptor >= 0:
            os.close(external_descriptor)
        if local_descriptor >= 0:
            os.close(local_descriptor)


class GateL2Phase(StrEnum):
    PREFLIGHT = "preflight"
    GLOBAL_OUTCOME_UNKNOWN = "global-outcome-unknown"
    GLOBAL_STRICT = "global-strict"
    REGIONAL_CREATE_OUTCOME_UNKNOWN = "regional-create-outcome-unknown"
    REGIONAL_OWNED = "regional-owned"
    REGIONAL_STRICT = "regional-strict"
    LAUNCH_OUTCOME_UNKNOWN = "launch-outcome-unknown"
    INSTANCE_OWNED = "instance-owned"
    INSTANCE_ACTIVE = "instance-active"
    CHECKPOINT_PASSED = "checkpoint-passed"
    QUALIFICATION_COMPLETE = "qualification-complete"
    TERMINATION_REQUIRED = "termination-required"
    TERMINATING = "terminating"
    INSTANCE_TERMINAL = "instance-terminal"
    REGIONAL_DELETED = "regional-deleted"
    GLOBAL_RESTORED = "global-restored"
    CLOSED = "closed"
    INCIDENT = "incident"


class GateL2Event(StrEnum):
    PREFLIGHT_PASSED = "preflight-passed"
    GLOBAL_PATCH_SEND_STARTED = "global-patch-send-started"
    GLOBAL_REPLACEMENT_VERIFIED = "global-replacement-verified"
    REGIONAL_CREATE_SEND_STARTED = "regional-create-send-started"
    REGIONAL_ID_OBSERVED = "regional-id-observed"
    REGIONAL_RECOVERY_OBSERVED = "regional-recovery-observed"
    REGIONAL_RULESET_VERIFIED = "regional-ruleset-verified"
    LAUNCH_SEND_STARTED = "launch-send-started"
    INSTANCE_ID_OBSERVED = "instance-id-observed"
    AMBIGUITY_RECOVERY_OBSERVED = "ambiguity-recovery-observed"
    AMBIGUITY_RECOVERY_ZERO_OWNED = "ambiguity-recovery-zero-owned"
    ACTIVE_OBSERVED = "active-observed"
    ACTIVE_ERROR_OBSERVED = "active-error-observed"
    ACTIVE_POLL_TIMEOUT = "active-poll-timeout"
    CHECKPOINT_VALIDATED = "checkpoint-validated"
    QUALIFICATION_FINISHED = "qualification-finished"
    ABORT = "abort"
    TERMINATION_SENT = "termination-sent"
    TERMINAL_OBSERVED = "terminal-observed"
    REGIONAL_DELETE_VERIFIED = "regional-delete-verified"
    GLOBAL_RESTORE_VERIFIED = "global-restore-verified"
    ZERO_OWNED_INSTANCES_VERIFIED = "zero-owned-instances-verified"
    CLEANUP_FAILED = "cleanup-failed"


@dataclass(frozen=True, slots=True)
class GateL2State:
    phase: GateL2Phase = GateL2Phase.PREFLIGHT
    launch_requests: int = 0
    ambiguity_recovery_requests: int = 0
    regional_recovery_requests: int = 0
    owned_instance_id: str | None = field(default=None, repr=False)
    owned_regional_ruleset_id: str | None = field(default=None, repr=False)
    termination_requests: int = 0
    global_mutated: bool = False
    regional_created: bool = False
    instance_terminal: bool = False
    zero_owned_instances_proven: bool = False


def transition_gate_l2(
    state: GateL2State,
    event: GateL2Event,
    *,
    instance_id: str | None = None,
    ruleset_id: str | None = None,
    terminal_status: str | None = None,
) -> GateL2State:
    """Advance the fail-closed future lifecycle without performing any action."""

    if event is GateL2Event.CLEANUP_FAILED:
        return replace(state, phase=GateL2Phase.INCIDENT)
    if state.phase is GateL2Phase.PREFLIGHT and event is GateL2Event.PREFLIGHT_PASSED:
        return state
    if state.phase is GateL2Phase.PREFLIGHT and event is GateL2Event.GLOBAL_PATCH_SEND_STARTED:
        return replace(state, phase=GateL2Phase.GLOBAL_OUTCOME_UNKNOWN)
    if (
        state.phase is GateL2Phase.GLOBAL_OUTCOME_UNKNOWN
        and event is GateL2Event.GLOBAL_REPLACEMENT_VERIFIED
    ):
        return replace(state, phase=GateL2Phase.GLOBAL_STRICT, global_mutated=True)
    if (
        state.phase is GateL2Phase.GLOBAL_STRICT
        and event is GateL2Event.REGIONAL_CREATE_SEND_STARTED
    ):
        return replace(state, phase=GateL2Phase.REGIONAL_CREATE_OUTCOME_UNKNOWN)
    if state.phase is GateL2Phase.REGIONAL_CREATE_OUTCOME_UNKNOWN and event in {
        GateL2Event.REGIONAL_ID_OBSERVED,
        GateL2Event.REGIONAL_RECOVERY_OBSERVED,
    }:
        if not isinstance(ruleset_id, str) or not ruleset_id:
            raise L20ContractError("owned regional ruleset identity is absent")
        if (
            event is GateL2Event.REGIONAL_RECOVERY_OBSERVED
            and state.regional_recovery_requests != 0
        ):
            raise L20ContractError("regional create recovery cannot be replayed")
        return replace(
            state,
            phase=GateL2Phase.REGIONAL_OWNED,
            regional_recovery_requests=(
                1
                if event is GateL2Event.REGIONAL_RECOVERY_OBSERVED
                else state.regional_recovery_requests
            ),
            owned_regional_ruleset_id=ruleset_id,
            regional_created=True,
        )
    if state.phase is GateL2Phase.REGIONAL_OWNED and event is GateL2Event.REGIONAL_RULESET_VERIFIED:
        return replace(state, phase=GateL2Phase.REGIONAL_STRICT)
    if state.phase is GateL2Phase.REGIONAL_STRICT and event is GateL2Event.LAUNCH_SEND_STARTED:
        if state.launch_requests != 0:
            raise L20ContractError("launch request identity cannot be replayed")
        return replace(
            state,
            phase=GateL2Phase.LAUNCH_OUTCOME_UNKNOWN,
            launch_requests=1,
        )
    if state.phase is GateL2Phase.LAUNCH_OUTCOME_UNKNOWN and event in {
        GateL2Event.INSTANCE_ID_OBSERVED,
        GateL2Event.AMBIGUITY_RECOVERY_OBSERVED,
    }:
        if not isinstance(instance_id, str) or not instance_id:
            raise L20ContractError("owned instance identity is absent")
        if (
            event is GateL2Event.AMBIGUITY_RECOVERY_OBSERVED
            and state.ambiguity_recovery_requests != 0
        ):
            raise L20ContractError("launch ambiguity recovery cannot be replayed")
        return replace(
            state,
            phase=GateL2Phase.INSTANCE_OWNED,
            ambiguity_recovery_requests=(
                1
                if event is GateL2Event.AMBIGUITY_RECOVERY_OBSERVED
                else state.ambiguity_recovery_requests
            ),
            owned_instance_id=instance_id,
        )
    if (
        state.phase is GateL2Phase.LAUNCH_OUTCOME_UNKNOWN
        and event is GateL2Event.AMBIGUITY_RECOVERY_ZERO_OWNED
    ):
        if state.ambiguity_recovery_requests != 0:
            raise L20ContractError("launch ambiguity recovery cannot be replayed")
        return replace(
            state,
            phase=GateL2Phase.INSTANCE_TERMINAL,
            ambiguity_recovery_requests=1,
            instance_terminal=True,
            zero_owned_instances_proven=True,
        )
    if state.phase is GateL2Phase.INSTANCE_OWNED and event is GateL2Event.ACTIVE_OBSERVED:
        return replace(state, phase=GateL2Phase.INSTANCE_ACTIVE)
    if state.phase is GateL2Phase.INSTANCE_OWNED and event in {
        GateL2Event.ACTIVE_ERROR_OBSERVED,
        GateL2Event.ACTIVE_POLL_TIMEOUT,
    }:
        return replace(state, phase=GateL2Phase.TERMINATION_REQUIRED)
    if state.phase is GateL2Phase.INSTANCE_ACTIVE and event is GateL2Event.CHECKPOINT_VALIDATED:
        return replace(state, phase=GateL2Phase.CHECKPOINT_PASSED)
    if state.phase is GateL2Phase.CHECKPOINT_PASSED and event is GateL2Event.QUALIFICATION_FINISHED:
        return replace(state, phase=GateL2Phase.QUALIFICATION_COMPLETE)
    if event is GateL2Event.ABORT and state.phase in {
        GateL2Phase.GLOBAL_OUTCOME_UNKNOWN,
        GateL2Phase.REGIONAL_CREATE_OUTCOME_UNKNOWN,
        GateL2Phase.LAUNCH_OUTCOME_UNKNOWN,
    }:
        return replace(state, phase=GateL2Phase.INCIDENT)
    if event is GateL2Event.ABORT and state.global_mutated:
        if state.owned_instance_id is not None:
            return replace(state, phase=GateL2Phase.TERMINATION_REQUIRED)
        if state.regional_created:
            return replace(
                state,
                phase=GateL2Phase.INSTANCE_TERMINAL,
                instance_terminal=True,
            )
        return replace(state, phase=GateL2Phase.GLOBAL_STRICT)
    if (
        state.phase
        in {
            GateL2Phase.INSTANCE_OWNED,
            GateL2Phase.INSTANCE_ACTIVE,
            GateL2Phase.CHECKPOINT_PASSED,
            GateL2Phase.QUALIFICATION_COMPLETE,
        }
        and event is GateL2Event.TERMINATION_SENT
    ):
        if state.owned_instance_id is None or state.termination_requests != 0:
            raise L20ContractError("termination must target one owned identity exactly once")
        return replace(
            state,
            phase=GateL2Phase.TERMINATING,
            termination_requests=1,
        )
    if state.phase is GateL2Phase.TERMINATION_REQUIRED and event is GateL2Event.TERMINATION_SENT:
        if state.owned_instance_id is None or state.termination_requests != 0:
            raise L20ContractError("termination-required state lacks one owned identity")
        return replace(
            state,
            phase=GateL2Phase.TERMINATING,
            termination_requests=1,
        )
    if state.phase is GateL2Phase.TERMINATING and event is GateL2Event.TERMINAL_OBSERVED:
        if instance_id != state.owned_instance_id:
            raise L20ContractError("terminal evidence does not bind the owned instance")
        if terminal_status != "terminated":
            raise L20ContractError("provider terminal evidence is not exact terminated state")
        return replace(
            state,
            phase=GateL2Phase.INSTANCE_TERMINAL,
            instance_terminal=True,
        )
    if (
        state.phase in {GateL2Phase.GLOBAL_STRICT, GateL2Phase.INSTANCE_TERMINAL}
        and event is GateL2Event.REGIONAL_DELETE_VERIFIED
    ):
        if state.owned_instance_id is not None and not state.instance_terminal:
            raise L20ContractError("regional cleanup cannot precede instance termination")
        return replace(state, phase=GateL2Phase.REGIONAL_DELETED, regional_created=False)
    if state.phase is GateL2Phase.REGIONAL_DELETED and event is GateL2Event.GLOBAL_RESTORE_VERIFIED:
        if state.owned_instance_id is not None and not state.instance_terminal:
            raise L20ContractError("global restoration cannot precede instance termination")
        return replace(state, phase=GateL2Phase.GLOBAL_RESTORED, global_mutated=False)
    if (
        state.phase is GateL2Phase.GLOBAL_STRICT
        and event is GateL2Event.GLOBAL_RESTORE_VERIFIED
        and state.owned_instance_id is None
        and not state.regional_created
    ):
        return replace(state, phase=GateL2Phase.GLOBAL_RESTORED, global_mutated=False)
    if (
        state.phase is GateL2Phase.GLOBAL_RESTORED
        and event is GateL2Event.ZERO_OWNED_INSTANCES_VERIFIED
    ):
        return replace(state, phase=GateL2Phase.CLOSED, zero_owned_instances_proven=True)
    raise L20ContractError("Gate L2 lifecycle transition is unsafe")


def require_unique_agent_match(observed: Sequence[str], expected: str) -> str:
    """Return the sole matching agent-exposed public fingerprint."""

    matches = [value for value in observed if value == expected]
    if len(matches) != 1:
        raise L20ContractError("SSH agent does not expose exactly one approved identity")
    return matches[0]


def render_global_restore_body(
    sealed_original_response: Mapping[str, object],
) -> dict[str, object]:
    """Render exact rollback rules from the fresh sealed pre-mutation response.

    The historical redacted inventory is evidence for selection and drift checks, but
    it intentionally omits values such as rule descriptions. It cannot be the
    authoritative rollback payload.
    """

    data = _mapping(sealed_original_response.get("data"), context="global response data")
    rules = _sequence(data.get("rules"), context="fresh global firewall rules")
    if not 1 <= len(rules) <= 100:
        raise L20ContractError("fresh global firewall rules count is outside contract")
    rendered: list[dict[str, object]] = []
    allowed = {"protocol", "source_network", "port_range", "description"}
    required = {"protocol", "source_network", "description"}
    for value in rules:
        rule = _mapping(value, context="fresh global firewall rule")
        if not required.issubset(rule) or not set(rule).issubset(allowed):
            raise L20ContractError("fresh global firewall rule shape is not exact")
        if rule.get("protocol") not in {"tcp", "udp", "icmp", "all"}:
            raise L20ContractError("fresh global firewall protocol is unsupported")
        source = rule.get("source_network")
        description = rule.get("description")
        if not isinstance(source, str) or not source:
            raise L20ContractError("fresh global firewall source is absent")
        if not isinstance(description, str) or len(description) > 128:
            raise L20ContractError("fresh global firewall description is invalid")
        port_range = rule.get("port_range")
        if port_range is not None and (
            not isinstance(port_range, list)
            or len(port_range) != 2
            or any(type(port) is not int or not 1 <= port <= 65_535 for port in port_range)
        ):
            raise L20ContractError("fresh global firewall port range is invalid")
        rendered.append(dict(rule))
    return {"rules": rendered}


def render_launch_body(
    template: Mapping[str, object],
    *,
    owned_regional_ruleset_id: str,
    authorization_reference: str,
) -> dict[str, object]:
    """Substitute the two typed launch bindings and reject every other drift."""

    if _SAFE_ID.fullmatch(owned_regional_ruleset_id) is None:
        raise L20ContractError("owned regional ruleset ID is unsafe")
    if _SAFE_ID.fullmatch(authorization_reference) is None or authorization_reference.endswith(
        "-PENDING"
    ):
        raise L20ContractError("launch authorization identity is not active")
    expected_keys = {
        "region_name",
        "instance_type_name",
        "ssh_key_names",
        "file_system_names",
        "file_system_mounts",
        "name",
        "hostname",
        "image",
        "tags",
        "authorization_tag_runtime_binding",
        "firewall_rulesets_runtime_binding",
    }
    if set(template) != expected_keys:
        raise L20ContractError("launch template keys drifted")
    if (
        template.get("authorization_tag_runtime_binding") != "authorization_reference"
        or template.get("firewall_rulesets_runtime_binding") != "owned_regional_ruleset_id"
        or template.get("file_system_names") != []
        or template.get("file_system_mounts") != []
        or template.get("ssh_key_names") != ["fractal-lambda-codex"]
    ):
        raise L20ContractError("launch template security binding drifted")
    tags = [
        dict(_mapping(value, context="launch ownership tag"))
        for value in _sequence(template.get("tags"), context="launch ownership tags")
    ]
    if len(tags) != 5 or any(set(tag) != {"key", "value"} for tag in tags):
        raise L20ContractError("launch ownership tag set drifted")
    rendered = {
        key: json.loads(json.dumps(value))
        for key, value in template.items()
        if key not in {"authorization_tag_runtime_binding", "firewall_rulesets_runtime_binding"}
    }
    rendered["tags"] = [
        *tags,
        {"key": "giclab-authorization", "value": authorization_reference},
    ]
    rendered["firewall_rulesets"] = [{"id": owned_regional_ruleset_id}]
    return rendered


def render_terminate_body(owned_instance_id: str) -> dict[str, object]:
    """Render the only authorized termination target."""

    if _SAFE_ID.fullmatch(owned_instance_id) is None:
        raise L20ContractError("owned instance ID is unsafe")
    return {"instance_ids": [owned_instance_id]}


def resolve_owned_regional_ruleset_id(
    *,
    expected_name: str,
    expected_region: str,
    create_response: Mapping[str, object] | None = None,
    recovery_response: Mapping[str, object] | None = None,
) -> str | None:
    """Resolve one owned ruleset from either POST success or one recovery list GET."""

    if (create_response is None) == (recovery_response is None):
        raise L20ContractError("regional identity needs exactly one response source")
    if create_response is not None:
        data = _mapping(create_response.get("data"), context="regional create response data")
        value = _nonempty(data.get("id"), context="created regional ruleset ID")
        return value
    assert recovery_response is not None
    candidates = []
    for raw in _sequence(recovery_response.get("data"), context="regional recovery data"):
        item = _mapping(raw, context="regional recovery item")
        region = item.get("region")
        region_name = region.get("name") if isinstance(region, Mapping) else region
        if item.get("name") == expected_name and region_name == expected_region:
            candidates.append(_nonempty(item.get("id"), context="recovered regional ruleset ID"))
    if len(candidates) > 1:
        raise L20ContractError("regional create recovery matched multiple owned identities")
    return candidates[0] if candidates else None


def resolve_owned_instance_id(
    *,
    expected_name: str,
    expected_tags: Sequence[Mapping[str, object]],
    launch_response: Mapping[str, object] | None = None,
    recovery_response: Mapping[str, object] | None = None,
) -> str | None:
    """Resolve one launch identity without conflating POST and list response shapes."""

    if (launch_response is None) == (recovery_response is None):
        raise L20ContractError("instance identity needs exactly one response source")
    if launch_response is not None:
        data = _mapping(launch_response.get("data"), context="launch response data")
        values = _sequence(data.get("instance_ids"), context="launch instance IDs")
        if len(values) != 1:
            raise L20ContractError("launch response did not contain exactly one instance ID")
        return _nonempty(values[0], context="launched instance ID")
    assert recovery_response is not None
    expected_tag_set = {
        (_nonempty(tag.get("key"), context="expected tag key"), str(tag.get("value", "")))
        for tag in expected_tags
    }
    candidates: list[str] = []
    for raw in _sequence(recovery_response.get("data"), context="instance recovery data"):
        item = _mapping(raw, context="instance recovery item")
        observed_tags = {
            (
                _nonempty(_mapping(tag, context="instance tag").get("key"), context="tag key"),
                str(_mapping(tag, context="instance tag").get("value", "")),
            )
            for tag in _sequence(item.get("tags"), context="instance tags")
        }
        if item.get("name") == expected_name and expected_tag_set.issubset(observed_tags):
            candidates.append(_nonempty(item.get("id"), context="recovered instance ID"))
    if len(candidates) > 1:
        raise L20ContractError("launch recovery matched multiple owned instances")
    return candidates[0] if candidates else None


def resolve_owned_instance_active_ipv4(
    response: Mapping[str, object], *, owned_instance_id: str
) -> str:
    """Bind one active instance response to one exact public IPv4."""

    data = _mapping(response.get("data"), context="instance detail response")
    if data.get("id") != owned_instance_id or data.get("status") != "active":
        raise L20ContractError("active instance response identity or state drifted")
    return str(
        _public_ipv4_32(f"{_nonempty(data.get('ip'), context='instance IP')}/32")
    ).removesuffix("/32")


def validate_fresh_prelaunch_responses(
    repository_root: Path,
    *,
    responses: Mapping[str, Mapping[str, object]],
    private_parameters: Mapping[str, object],
) -> Mapping[str, object]:
    """Revalidate all seven account facts immediately before the first mutation."""

    schema_paths = {
        "instance-types": (
            "containers/sira-smoke/lambda/endpoint-schemas-v3/instance-types.schema.json"
        ),
        "images": "containers/sira-smoke/lambda/endpoint-schemas-v3/images.schema.json",
        "regions": "containers/sira-smoke/lambda/endpoint-schemas-v3/regions.schema.json",
        "ssh-keys": "containers/sira-smoke/lambda/endpoint-schemas-v3/ssh-keys.schema.json",
        "firewall-rulesets": (
            "containers/sira-smoke/lambda/endpoint-schemas-v3/firewall-rulesets.schema.json"
        ),
        "global-firewall-ruleset": (
            "containers/sira-smoke/lambda/endpoint-schemas-v3/global-firewall-ruleset.schema.json"
        ),
        "instances": "containers/sira-smoke/lambda/endpoint-schemas-v3/instances.schema.json",
    }
    if set(responses) != set(schema_paths):
        raise L20ContractError("fresh prelaunch response set is incomplete or expanded")
    for name, relative in schema_paths.items():
        _validate_schema(
            responses[name],
            repository_root=repository_root,
            schema_relative_path=relative,
        )
    selected = _mapping(private_parameters.get("selected_resource"), context="selected resource")
    owned = _mapping(private_parameters.get("owned_names"), context="owned names")
    instance_types = _mapping(responses["instance-types"].get("data"), context="instance types")
    type_row = _mapping(instance_types.get("gpu_1x_a10"), context="selected type row")
    type_identity = _mapping(type_row.get("instance_type"), context="selected instance type")
    specs = _mapping(type_identity.get("specs"), context="selected instance specs")
    capacity = [
        _mapping(value, context="capacity region").get("name")
        for value in _sequence(type_row.get("regions_with_capacity_available"), context="capacity")
    ]
    if (
        type_identity.get("name") != "gpu_1x_a10"
        or type_identity.get("price_cents_per_hour") != SELECTED_LIST_PRICE_CENTS_PER_HOUR
        or type_identity.get("architecture") != "x86_64"
        or specs.get("vcpus") != 30
        or specs.get("memory_gib") != 200
        or specs.get("storage_gib") != 1400
        or specs.get("gpus") != 1
        or "us-east-1" not in capacity
    ):
        raise L20ContractError("fresh selected type, price, specs, or capacity drifted")
    raw_image_id = selected.get("raw_image_id")
    image_matches = [
        _mapping(value, context="fresh image")
        for value in _sequence(responses["images"].get("data"), context="fresh images")
        if _mapping(value, context="fresh image").get("id") == raw_image_id
    ]
    if len(image_matches) != 1:
        raise L20ContractError("fresh selected image identity is absent or ambiguous")
    image = image_matches[0]
    region = _mapping(image.get("region"), context="fresh image region")
    if (
        image.get("family") != "gpu-base-22-04"
        or image.get("version") != "22.4.5-2141"
        or image.get("architecture") != "x86_64"
        or region.get("name") != "us-east-1"
    ):
        raise L20ContractError("fresh selected image metadata drifted")
    region_names = {
        _mapping(value, context="fresh region").get("name")
        for value in _sequence(responses["regions"].get("data"), context="fresh regions")
    }
    if "us-east-1" not in region_names:
        raise L20ContractError("fresh selected region is absent")
    ssh_matches = [
        _mapping(value, context="fresh SSH key")
        for value in _sequence(responses["ssh-keys"].get("data"), context="fresh SSH keys")
        if _mapping(value, context="fresh SSH key").get("id") == selected.get("raw_ssh_key_id")
        and _mapping(value, context="fresh SSH key").get("name") == "fractal-lambda-codex"
    ]
    if len(ssh_matches) != 1:
        raise L20ContractError("fresh selected SSH key identity drifted")
    if _sequence(responses["instances"].get("data"), context="fresh instances"):
        raise L20ContractError("fresh prelaunch state contains a running instance")
    owned_ruleset_name = owned.get("regional_ruleset_name")
    if any(
        _mapping(value, context="fresh ruleset").get("name") == owned_ruleset_name
        for value in _sequence(
            responses["firewall-rulesets"].get("data"),
            context="fresh firewall rulesets",
        )
    ):
        raise L20ContractError("fresh owned regional ruleset name already exists")
    fresh_global = responses["global-firewall-ruleset"]
    render_global_restore_body(fresh_global)
    historical = _mapping(
        private_parameters.get("original_global_firewall"),
        context="historical global baseline",
    )
    historical_rules = [
        dict(_mapping(value, context="historical firewall rule"))
        for value in _sequence(historical.get("rules"), context="historical firewall rules")
    ]
    fresh_rules = [
        {
            key: value
            for key, value in _mapping(raw, context="fresh global rule").items()
            if key in {"protocol", "source_network", "port_range"}
        }
        for raw in _sequence(
            _mapping(fresh_global.get("data"), context="fresh global data").get("rules"),
            context="fresh global rules",
        )
    ]
    if fresh_rules != historical_rules:
        raise L20ContractError("fresh global firewall differs from the sealed redacted baseline")
    return fresh_global


@dataclass(frozen=True, slots=True)
class CheckpointWaitBinding:
    path: Path = field(repr=False)
    challenge_nonce: str = field(repr=False)
    started_monotonic_ns: int
    started_wall_utc: datetime


def prepare_host_key_checkpoint_wait(
    *,
    path: Path,
    challenge_nonce: str,
    started_monotonic_ns: int,
    started_wall_utc: datetime,
) -> CheckpointWaitBinding:
    """Mint a wait binding only while the future checkpoint path is absent."""

    if not path.is_absolute() or ".." in path.parts or _NONCE.fullmatch(challenge_nonce) is None:
        raise L20ContractError("host-key checkpoint wait binding is unsafe")
    if started_monotonic_ns < 0 or started_wall_utc.tzinfo is None:
        raise L20ContractError("host-key checkpoint start time is invalid")
    current = Path(path.anchor)
    for component in path.parts[1:-1]:
        current /= component
        try:
            status = os.lstat(current)
        except OSError:
            raise L20ContractError("host-key checkpoint parent is unavailable") from None
        if not stat.S_ISDIR(status.st_mode) or stat.S_ISLNK(status.st_mode):
            raise L20ContractError("host-key checkpoint parent hierarchy is unsafe")
    try:
        os.lstat(path)
    except FileNotFoundError:
        pass
    except OSError:
        raise L20ContractError("host-key checkpoint absence check failed") from None
    else:
        raise L20ContractError("host-key checkpoint path already existed before the wait")
    return CheckpointWaitBinding(
        path=path,
        challenge_nonce=challenge_nonce,
        started_monotonic_ns=started_monotonic_ns,
        started_wall_utc=started_wall_utc.astimezone(UTC),
    )


def validate_host_key_checkpoint(
    repository_root: Path,
    *,
    wait_binding: CheckpointWaitBinding,
    expected_instance_id: str,
    observed_monotonic_ns: int,
    observed_wall_utc: datetime,
) -> dict[str, object]:
    """Validate a fresh private Jupyter fingerprint checkpoint by held file identity."""

    if observed_monotonic_ns < wait_binding.started_monotonic_ns:
        raise L20ContractError("checkpoint monotonic timestamps are reversed")
    elapsed = (observed_monotonic_ns - wait_binding.started_monotonic_ns) / 1_000_000_000
    if elapsed > MAX_HUMAN_CHECKPOINT_SECONDS:
        raise L20ContractError("host-key checkpoint arrived after its deadline")
    encoded = _read_regular_no_follow(
        wait_binding.path,
        max_bytes=16_384,
        required_mode=0o600,
    )
    document = _strict_json(encoded, context="host-key checkpoint")
    _validate_schema(
        document,
        repository_root=repository_root,
        schema_relative_path=HOST_KEY_CHECKPOINT_SCHEMA_PATH,
    )
    if (
        document.get("run_id") != RUN_ID
        or document.get("provider_instance_id") != expected_instance_id
        or document.get("checkpoint_challenge_nonce") != wait_binding.challenge_nonce
    ):
        raise L20ContractError("host-key checkpoint identity does not match the owned instance")
    if document.get("algorithm") != "ssh-ed25519":
        raise L20ContractError("host-key checkpoint algorithm is not ED25519")
    if observed_wall_utc.tzinfo is None:
        raise L20ContractError("checkpoint observation wall time is not timezone aware")
    try:
        documented = datetime.fromisoformat(
            str(document.get("observed_at_utc")).replace("Z", "+00:00")
        )
    except ValueError:
        raise L20ContractError("checkpoint wall timestamp is invalid") from None
    if not wait_binding.started_wall_utc <= documented <= observed_wall_utc.astimezone(UTC):
        raise L20ContractError("checkpoint timestamp is outside the minted wait window")
    return document


def _ssh_wire_string(blob: bytes, offset: int) -> tuple[bytes, int]:
    if offset + 4 > len(blob):
        raise L20ContractError("host-key wire encoding is truncated")
    length = int.from_bytes(blob[offset : offset + 4], "big")
    start = offset + 4
    end = start + length
    if length < 1 or end > len(blob):
        raise L20ContractError("host-key wire field is invalid")
    return blob[start:end], end


def ed25519_fingerprint(public_key_line: str) -> str:
    fields = public_key_line.strip().split()
    if len(fields) < 2 or fields[-2] != "ssh-ed25519":
        raise L20ContractError("keyscan output is not one ED25519 key")
    try:
        blob = base64.b64decode(fields[-1], validate=True)
    except (binascii.Error, ValueError):
        raise L20ContractError("keyscan ED25519 body is malformed") from None
    algorithm, offset = _ssh_wire_string(blob, 0)
    key_bytes, offset = _ssh_wire_string(blob, offset)
    if algorithm != b"ssh-ed25519" or len(key_bytes) != 32 or offset != len(blob):
        raise L20ContractError("keyscan ED25519 wire body is invalid")
    digest = base64.b64encode(hashlib.sha256(blob).digest()).decode().rstrip("=")
    return f"SHA256:{digest}"


def verified_known_hosts_line(
    *,
    instance_ipv4: str,
    keyscan_output: bytes,
    checkpoint_fingerprint: str,
) -> bytes:
    """Build a private known_hosts line only after independent fingerprint equality."""

    try:
        address = ipaddress.ip_address(instance_ipv4)
    except ValueError:
        raise L20ContractError("owned instance address is invalid") from None
    if not isinstance(address, ipaddress.IPv4Address) or not address.is_global:
        raise L20ContractError("owned instance address is not a public IPv4")
    try:
        lines = [line for line in keyscan_output.decode("ascii").splitlines() if line.strip()]
    except UnicodeDecodeError:
        raise L20ContractError("keyscan output is not ASCII") from None
    if len(lines) != 1:
        raise L20ContractError("keyscan did not return exactly one host key")
    fields = lines[0].split()
    if len(fields) != 3 or fields[0] not in {str(address), f"[{address}]:22"}:
        raise L20ContractError("keyscan host identity differs from the owned instance")
    observed = ed25519_fingerprint(lines[0])
    if observed != checkpoint_fingerprint:
        raise L20ContractError("keyscan fingerprint differs from the Jupyter checkpoint")
    return f"{address} {fields[1]} {fields[2]}\n".encode("ascii")


REMOTE_STATIC_COMMANDS: Final = (
    ("/usr/bin/uname", "-srmo"),
    ("/usr/bin/cat", "/etc/os-release"),
    ("/usr/bin/stat", "-fc", "%T", "/sys/fs/cgroup"),
    ("containerd", "--version"),
    ("runc", "--version"),
    ("/usr/bin/df", "-B1", "/"),
    ("systemctl", "is-active", "docker"),
    ("/bin/ps", "-eo", "pid,ppid,sid,pgid,stat,comm,args"),
    ("docker", "version", "--format", "{{json .}}"),
    ("docker", "info", "--format", "{{json .}}"),
    ("docker", "buildx", "version"),
    ("docker", "ps", "--no-trunc", "--format", "{{json .}}"),
    ("docker", "image", "ls", "--no-trunc", "--format", "{{json .}}"),
    ("docker", "network", "ls", "--no-trunc", "--format", "{{json .}}"),
    ("docker", "volume", "ls", "--format", "{{json .}}"),
)


def validate_remote_argv(remote_argv: Sequence[str]) -> None:
    """Reject every remote command outside the finite host/container contract."""

    argv = tuple(remote_argv)
    if argv in REMOTE_STATIC_COMMANDS:
        return
    if len(argv) == 3 and argv[:2] == ("/usr/bin/df", "-B1"):
        docker_root = Path(argv[2])
        if docker_root.is_absolute() and ".." not in docker_root.parts:
            return
    if argv in {
        ("docker", "pull", "--platform", "linux/amd64", BUSYBOX_REFERENCE),
        ("docker", "image", "inspect", BUSYBOX_REFERENCE),
    }:
        return
    if len(argv) >= 3 and argv[:2] == ("docker", "create"):
        try:
            name = argv[argv.index("--name") + 1]
            labels = {
                argv[index + 1].split("=", 1)[0]: argv[index + 1].split("=", 1)[1]
                for index, value in enumerate(argv[:-1])
                if value == "--label"
            }
            expected = render_container_create_argv(
                container_name=name,
                fixture_script=argv[-1],
                authorization_reference=labels["giclab.authorization"],
                repository_commit=labels["giclab.repository_commit"],
                provider_instance_id=labels["giclab.provider_instance_id"],
            )
        except (KeyError, IndexError, ValueError, L20ContractError):
            pass
        else:
            if argv == tuple(expected):
                return
    id_index = (
        2
        if len(argv) > 2
        and argv[:2]
        in {
            ("docker", "inspect"),
            ("docker", "start"),
            ("docker", "top"),
            ("docker", "logs"),
            ("docker", "rm"),
        }
        else len(argv) - 1
    )
    container_id = argv[id_index] if argv else ""
    if re.fullmatch(r"[a-f0-9]{64}", container_id) is not None:
        allowed_dynamic = {
            ("docker", "inspect", container_id),
            ("docker", "start", container_id),
            ("docker", "top", container_id, "-eo", "pid,ppid,sid,pgid,stat,comm,args"),
            ("docker", "stop", "--time", str(CONTAINER_STOP_SECONDS), container_id),
            ("docker", "kill", "--signal", "KILL", container_id),
            ("docker", "logs", "--timestamps", container_id),
            ("docker", "rm", container_id),
        }
        if argv in allowed_dynamic:
            return
    label_filter = f"label=giclab.run={RUN_ID}"
    if argv in {
        ("docker", "ps", "-a", "--no-trunc", "--filter", label_filter),
        ("docker", "network", "ls", "--no-trunc", "--filter", label_filter),
        ("docker", "volume", "ls", "--filter", label_filter),
    }:
        return
    raise L20ContractError("remote command is outside the exact qualification allowlist")


def render_ssh_argv(
    *,
    agent_socket: str,
    public_identity_file: str,
    known_hosts_file: str,
    instance_ipv4: str,
    remote_argv: Sequence[str],
) -> list[str]:
    """Render the exact agent-only, strict-host-key future SSH invocation."""

    if not agent_socket.startswith("/") or not public_identity_file.startswith("/"):
        raise L20ContractError("SSH private binding paths must be absolute")
    if not known_hosts_file.startswith("/") or not remote_argv:
        raise L20ContractError("SSH run-owned path or remote command is absent")
    try:
        address = ipaddress.ip_address(instance_ipv4)
    except ValueError:
        raise L20ContractError("SSH target is invalid") from None
    if not isinstance(address, ipaddress.IPv4Address) or not address.is_global:
        raise L20ContractError("SSH target is not a public IPv4")
    validate_remote_argv(remote_argv)
    return [
        "/usr/bin/ssh",
        "-F",
        "/dev/null",
        "-o",
        "BatchMode=yes",
        "-o",
        "IdentitiesOnly=yes",
        "-o",
        f"IdentityAgent={agent_socket}",
        "-o",
        f"IdentityFile={public_identity_file}",
        "-o",
        "StrictHostKeyChecking=yes",
        "-o",
        f"UserKnownHostsFile={known_hosts_file}",
        "-o",
        "GlobalKnownHostsFile=/dev/null",
        "-o",
        "ForwardAgent=no",
        "-o",
        "ClearAllForwardings=yes",
        "-o",
        "PermitLocalCommand=no",
        "-o",
        "UpdateHostKeys=no",
        "-o",
        "CheckHostIP=yes",
        "-o",
        "ConnectTimeout=10",
        "-o",
        "ServerAliveInterval=5",
        "-o",
        "ServerAliveCountMax=2",
        "-o",
        "LogLevel=ERROR",
        "-p",
        "22",
        f"ubuntu@{address}",
        *remote_argv,
    ]


def render_container_create_argv(
    *,
    container_name: str,
    fixture_script: str,
    authorization_reference: str,
    repository_commit: str,
    provider_instance_id: str,
) -> list[str]:
    """Render the immutable-image, no-network adversarial container create array."""

    if re.fullmatch(r"giclab-t07-l2-containment-[a-f0-9]{12}", container_name) is None:
        raise L20ContractError("containment container name is not run-owned")
    if sha256_bytes(fixture_script.encode()) != CONTAINMENT_FIXTURE_SHA256:
        raise L20ContractError("containment fixture bytes differ from the reviewed fixture")
    if (
        not authorization_reference
        or authorization_reference.endswith("-PENDING")
        or _SAFE_ID.fullmatch(authorization_reference) is None
    ):
        raise L20ContractError("containment authorization identity is not exact and active")
    if _COMMIT.fullmatch(repository_commit) is None:
        raise L20ContractError("containment repository commit is not immutable")
    if _SAFE_ID.fullmatch(provider_instance_id) is None:
        raise L20ContractError("containment provider instance identity is unsafe")
    return [
        "docker",
        "create",
        "--name",
        container_name,
        "--label",
        f"giclab.run={RUN_ID}",
        "--label",
        "giclab.gate=T07-L2",
        "--label",
        "giclab.experiment=EXP-0001",
        "--label",
        "giclab.profile=PLAN-EXP0001-SMOKE",
        "--label",
        f"giclab.plan={PLAN_ID}",
        "--label",
        f"giclab.authorization={authorization_reference}",
        "--label",
        f"giclab.repository_commit={repository_commit}",
        "--label",
        f"giclab.provider_instance_id={provider_instance_id}",
        "--label",
        f"giclab.image_digest={BUSYBOX_REFERENCE.split('@', maxsplit=1)[1]}",
        "--label",
        f"giclab.attempt={container_name}",
        "--init",
        "--network",
        "none",
        "--pid",
        "private",
        "--ipc",
        "private",
        "--cgroupns",
        "private",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges=true",
        "--read-only",
        "--tmpfs",
        f"/tmp:rw,nosuid,nodev,noexec,size={CONTAINER_TMPFS_BYTES}",
        "--shm-size",
        str(CONTAINER_SHM_BYTES),
        "--cpus",
        CONTAINER_CPU,
        "--memory",
        str(CONTAINER_MEMORY_BYTES),
        "--memory-swap",
        str(CONTAINER_MEMORY_BYTES),
        "--pids-limit",
        str(CONTAINER_PID_LIMIT),
        "--restart",
        "no",
        "--stop-timeout",
        str(CONTAINER_STOP_SECONDS),
        "--log-driver",
        "json-file",
        "--log-opt",
        "max-size=1048576",
        "--log-opt",
        "max-file=1",
        BUSYBOX_REFERENCE,
        "/bin/sh",
        "-c",
        fixture_script,
    ]


def exact_limits() -> dict[str, object]:
    """Return every numeric Gate L2 plan cap in one typed public mapping."""

    return {
        "provider_cost_cents": MAX_PROVIDER_COST_CENTS,
        "selected_one_hour_list_cost_cents": SELECTED_LIST_PRICE_CENTS_PER_HOUR,
        "provider_wall_seconds": MAX_PROVIDER_WALL_SECONDS,
        "human_host_key_checkpoint_seconds": MAX_HUMAN_CHECKPOINT_SECONDS,
        "read_only_prelaunch_requests": MAX_READ_ONLY_PRELAUNCH_CALLS,
        "firewall_mutation_requests": MAX_FIREWALL_MUTATION_CALLS,
        "firewall_verification_requests": MAX_FIREWALL_VERIFICATION_CALLS,
        "regional_create_recovery_requests": MAX_REGIONAL_CREATE_RECOVERY_CALLS,
        "launch_requests": MAX_LAUNCH_CALLS,
        "launch_ambiguity_recovery_requests": MAX_LAUNCH_RECOVERY_CALLS,
        "active_instance_polls": MAX_ACTIVE_POLLS,
        "termination_requests": MAX_TERMINATION_CALLS,
        "terminal_instance_polls": MAX_TERMINAL_POLLS,
        "final_zero_instance_requests": MAX_FINAL_ZERO_INSTANCE_CALLS,
        "provider_api_calls": MAX_PROVIDER_API_CALLS,
        "provider_request_spacing_seconds": MIN_PROVIDER_REQUEST_SPACING_SECONDS,
        "instance_poll_spacing_seconds": INSTANCE_POLL_SPACING_SECONDS,
        "automatic_provider_retries": AUTOMATIC_RETRIES,
        "automatic_mutation_retries": AUTOMATIC_RETRIES,
        "provider_response_bytes_per_call": MAX_PROVIDER_RESPONSE_BYTES_PER_CALL,
        "provider_response_bytes_aggregate": MAX_PROVIDER_RESPONSE_BYTES_AGGREGATE,
        "provider_ledger_bytes": MAX_PROVIDER_LEDGER_BYTES,
        "provider_ledger_events": MAX_PROVIDER_LEDGER_EVENTS,
        "provider_ledger_event_bytes": MAX_PROVIDER_LEDGER_EVENT_BYTES,
        "provider_request_body_bytes": MAX_PROVIDER_REQUEST_BODY_BYTES,
        "tcp_readiness_probes": MAX_TCP_READINESS_PROBES,
        "ssh_agent_inspection_calls": MAX_SSH_AGENT_INSPECTION_CALLS,
        "ssh_keyscan_calls": MAX_SSH_KEYSCAN_CALLS,
        "host_inspection_commands": MAX_HOST_INSPECTION_COMMANDS,
        "ssh_sessions": MAX_SSH_SESSIONS,
        "remote_commands": MAX_REMOTE_COMMANDS,
        "ssh_output_bytes_per_call": MAX_SSH_OUTPUT_BYTES_PER_CALL,
        "ssh_output_bytes_aggregate": MAX_SSH_OUTPUT_BYTES_AGGREGATE,
        "ssh_transfer_calls": MAX_SSH_TRANSFER_CALLS,
        "docker_calls": MAX_DOCKER_CALLS,
        "docker_output_bytes_per_call": MAX_DOCKER_OUTPUT_BYTES_PER_CALL,
        "docker_output_bytes_aggregate": MAX_DOCKER_OUTPUT_BYTES_AGGREGATE,
        "registry_metadata_calls_before_execution": MAX_REGISTRY_METADATA_CALLS_BEFORE_EXECUTION,
        "registry_response_bytes": MAX_REGISTRY_RESPONSE_BYTES,
        "docker_disk_delta_bytes": MAX_DOCKER_DISK_DELTA_BYTES,
        "minimum_root_free_bytes": MIN_ROOT_FREE_BYTES,
        "minimum_docker_root_free_bytes": MIN_DOCKER_ROOT_FREE_BYTES,
        "remote_evidence_bytes": MAX_REMOTE_EVIDENCE_BYTES,
        "evidence_transfer_bytes": MAX_TRANSFER_BYTES,
        "mac_active_evidence_bytes": MAX_MAC_ACTIVE_EVIDENCE_BYTES,
        "archive_bytes": MAX_ARCHIVE_BYTES,
        "archive_copy_calls": MAX_ARCHIVE_COPY_CALLS,
        "mac_active_incremental_bytes": MAX_LOCAL_INCREMENTAL_BYTES,
        "mac_prewrite_free_floor_bytes": MIN_LOCAL_PREWRITE_FREE_BYTES,
        "mac_retained_free_floor_bytes": MIN_LOCAL_RETAINED_FREE_BYTES,
        "external_container_capacity_bytes": EXTERNAL_CONTAINER_CAPACITY_BYTES,
        "external_retained_free_floor_bytes": EXTERNAL_RETAINED_FREE_FLOOR_BYTES,
        "external_precopy_free_floor_bytes": EXTERNAL_PRECOPY_FREE_FLOOR_BYTES,
        "private_binding_bytes": MAX_PRIVATE_BINDING_BYTES,
        "private_archive_bytes": MAX_PRIVATE_ARCHIVE_BYTES,
        "instance_count": 1,
        "persistent_filesystem_count": 0,
        "model_api_cost_cents": 0,
        "model_calls": 0,
        "model_tokens": 0,
        "automated_browser_actions": 0,
        "sira_executions": 0,
        "scientific_executions": 0,
        "container_count": 1,
        "container_cpu": CONTAINER_CPU,
        "container_memory_bytes": CONTAINER_MEMORY_BYTES,
        "container_pid_limit": CONTAINER_PID_LIMIT,
        "container_wall_seconds": CONTAINER_WALL_SECONDS,
        "container_output_bytes": CONTAINER_OUTPUT_BYTES,
        "container_tmpfs_bytes": CONTAINER_TMPFS_BYTES,
        "container_shm_bytes": CONTAINER_SHM_BYTES,
        "container_stop_seconds": CONTAINER_STOP_SECONDS,
        "human_console_checkpoint_sessions": 1,
    }


def provider_operations() -> list[dict[str, object]]:
    """Return the exact ordered provider operation classes and finite cardinalities."""

    operations: list[dict[str, object]] = [
        {
            "ordinal": 1,
            "id": "list-instance-types",
            "method": "GET",
            "path": "/api/v1/instance-types",
            "max_calls": 1,
        },
        {
            "ordinal": 2,
            "id": "list-images",
            "method": "GET",
            "path": "/api/v1/images",
            "max_calls": 1,
        },
        {
            "ordinal": 3,
            "id": "list-regions",
            "method": "GET",
            "path": "/api/v1/regions",
            "max_calls": 1,
        },
        {
            "ordinal": 4,
            "id": "list-ssh-keys",
            "method": "GET",
            "path": "/api/v1/ssh-keys",
            "max_calls": 1,
        },
        {
            "ordinal": 5,
            "id": "list-firewall-rulesets",
            "method": "GET",
            "path": "/api/v1/firewall-rulesets",
            "max_calls": 1,
        },
        {
            "ordinal": 6,
            "id": "get-global-firewall",
            "method": "GET",
            "path": "/api/v1/firewall-rulesets/global",
            "max_calls": 1,
        },
        {
            "ordinal": 7,
            "id": "list-instances",
            "method": "GET",
            "path": "/api/v1/instances",
            "max_calls": 1,
        },
        {
            "ordinal": 8,
            "id": "patch-global-strict",
            "method": "PATCH",
            "path": "/api/v1/firewall-rulesets/global",
            "max_calls": 1,
            "private_body": "strict_global_patch_body",
        },
        {
            "ordinal": 9,
            "id": "verify-global-strict",
            "method": "GET",
            "path": "/api/v1/firewall-rulesets/global",
            "max_calls": 1,
        },
        {
            "ordinal": 10,
            "id": "create-owned-regional-ruleset",
            "method": "POST",
            "path": "/api/v1/firewall-rulesets",
            "max_calls": 1,
            "private_body": "regional_create_body",
        },
        {
            "ordinal": 11,
            "id": "recover-owned-regional-ruleset-after-unknown-create",
            "method": "GET",
            "path": "/api/v1/firewall-rulesets",
            "max_calls": 1,
            "incident_only": True,
        },
        {
            "ordinal": 12,
            "id": "verify-owned-regional-ruleset",
            "method": "GET",
            "path": "/api/v1/firewall-rulesets/{owned_ruleset_id}",
            "max_calls": 1,
        },
        {
            "ordinal": 13,
            "id": "launch-instance",
            "method": "POST",
            "path": "/api/v1/instance-operations/launch",
            "max_calls": 1,
            "private_body": "launch_body_rendered",
        },
        {
            "ordinal": 14,
            "id": "poll-instance-active",
            "method": "GET",
            "path": "/api/v1/instances/{owned_instance_id}",
            "max_calls": MAX_ACTIVE_POLLS,
        },
        {
            "ordinal": 15,
            "id": "launch-ambiguity-recovery",
            "method": "GET",
            "path": "/api/v1/instances",
            "max_calls": 1,
            "incident_only": True,
        },
        {
            "ordinal": 16,
            "id": "terminate-owned-instance",
            "method": "POST",
            "path": "/api/v1/instance-operations/terminate",
            "max_calls": 1,
            "private_body": "terminate_body_rendered",
        },
        {
            "ordinal": 17,
            "id": "poll-instance-terminal",
            "method": "GET",
            "path": "/api/v1/instances/{owned_instance_id}",
            "max_calls": MAX_TERMINAL_POLLS,
        },
        {
            "ordinal": 18,
            "id": "delete-owned-regional-ruleset",
            "method": "DELETE",
            "path": "/api/v1/firewall-rulesets/{owned_ruleset_id}",
            "max_calls": 1,
        },
        {
            "ordinal": 19,
            "id": "verify-owned-regional-ruleset-absent",
            "method": "GET",
            "path": "/api/v1/firewall-rulesets/{owned_ruleset_id}",
            "max_calls": 1,
        },
        {
            "ordinal": 20,
            "id": "restore-global-firewall",
            "method": "PATCH",
            "path": "/api/v1/firewall-rulesets/global",
            "max_calls": 1,
            "private_body": "restore_global_patch_body_from_sealed_runtime_binding",
        },
        {
            "ordinal": 21,
            "id": "verify-global-restored",
            "method": "GET",
            "path": "/api/v1/firewall-rulesets/global",
            "max_calls": 1,
        },
        {
            "ordinal": 22,
            "id": "verify-zero-owned-instances",
            "method": "GET",
            "path": "/api/v1/instances",
            "max_calls": 1,
        },
    ]
    return [{**operation, "expected_status": 200} for operation in operations]


def _contains_null(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, Mapping):
        return any(_contains_null(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_null(item) for item in value)
    return False


def _assert_public_privacy(document: Mapping[str, object]) -> None:
    encoded = canonical_bytes(document).decode("utf-8")
    if any(pattern.search(encoded) for pattern in _PRIVATE_PUBLIC_PATTERNS):
        raise L20ContractError("public plan contains a private scalar or path")
    forbidden_keys = {
        "source_ipv4_cidr",
        "raw_image_id",
        "raw_ssh_key_id",
        "fingerprint",
        "local_public_identity_file",
        "agent_socket",
    }

    def walk(value: object) -> None:
        if isinstance(value, Mapping):
            if forbidden_keys.intersection(value):
                raise L20ContractError("public plan contains a forbidden private field")
            for item in value.values():
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(document)


def render_public_plan(
    repository_root: Path,
    *,
    implementation_commit: str,
    binding: PrivateBindingSeal,
    implementation_hashes: Mapping[str, str],
) -> dict[str, object]:
    """Render the complete executable-but-unauthorized public Gate L2 plan."""

    if _COMMIT.fullmatch(implementation_commit) is None:
        raise L20ContractError("reviewed implementation commit is invalid")
    if not implementation_hashes or any(
        _SHA256.fullmatch(value) is None for value in implementation_hashes.values()
    ):
        raise L20ContractError("implementation file hash binding is incomplete")
    fixture = _read_regular_no_follow(
        repository_root / CONTAINMENT_FIXTURE_PATH,
        max_bytes=16_384,
        require_owner=False,
    )
    if sha256_bytes(fixture) != CONTAINMENT_FIXTURE_SHA256:
        raise L20ContractError("containment fixture hash drifted")
    plan: dict[str, object] = {
        "schema_version": "0.1.0",
        "plan_id": PLAN_ID,
        "run_id": RUN_ID,
        "authorization_reference": AUTHORIZATION_PLACEHOLDER,
        "authorization_state": "pending-user-authorization",
        "executable_after_exact_authorization": True,
        "authorized": False,
        "branch": BRANCH,
        "reviewed_implementation_commit": implementation_commit,
        "provider": {
            "name": "lambda-on-demand-cloud",
            "api_base_url": API_BASE_URL,
            "transport": "python-stdlib-in-process-https-no-redirect",
            "secret_variable": "LAMBDA_API_KEY",
            "secret_channel": "approved-nonlogging-in-process-channel",
            "secret_retained_through_terminal_confirmation": True,
            "account_api_requests_authorized_now": 0,
            "request_renderer": "giclab.harness.lambda_l2_execution.render_provider_request",
            "request_executor": "giclab.harness.lambda_l2_execution.execute_observed_request",
            "request_ledger": "giclab.harness.lambda_l2_execution.FsyncL2ProviderLedger",
            "request_ledger_schema": PROVIDER_LEDGER_SCHEMA_PATH,
            "ledger_capacity_reserved_before_first_request": True,
            "raw_request_bodies_in_ledger": False,
        },
        "source_contracts": {
            "openapi": {
                "url": CURRENT_OPENAPI_URL,
                "version": CURRENT_OPENAPI_VERSION,
                "retrieved_at_utc": CURRENT_OPENAPI_RETRIEVED_AT_UTC,
                "bytes": CURRENT_OPENAPI_BYTES,
                "sha256": CURRENT_OPENAPI_SHA256,
                "prior_same_version_sha256": PRIOR_OPENAPI_SHA256,
                "same_version_byte_drift_recorded": True,
            },
            "public_observation_path": (
                "containers/sira-smoke/lambda/public-source-observations-l2-0.json"
            ),
            "implementation_file_sha256s": dict(sorted(implementation_hashes.items())),
        },
        "scientific_boundary": {
            "experiment_id": "EXP-0001",
            "profile_plan_id": "PLAN-EXP0001-SMOKE",
            "reactive_first": True,
            "simulative_second": True,
            "pair_id": "PAIR-EXP0001-SMOKE-0000",
            "model": "gpt-4o-2024-11-20",
            "reproduction_level": "directional-reproduction",
            "interpretation_allowed": False,
            "pilot_authorized": False,
            "training_allowed": False,
        },
        "public_selection": {
            "instance_type_name": "gpu_1x_a10",
            "region_name": "us-east-1",
            "image_alias": "img-0111",
            "image_family": "gpu-base-22-04",
            "image_version": "22.4.5-2141",
            "architecture": "x86_64",
            "price_cents_per_hour": SELECTED_LIST_PRICE_CENTS_PER_HOUR,
            "vcpus": 30,
            "memory_gib": 200,
            "root_storage_gib": 1400,
            "gpus": 1,
            "ssh_key_name": "fractal-lambda-codex",
            "ssh_access_mode": "preloaded-ssh-agent",
            "persistent_filesystem_count": 0,
        },
        "private_binding": binding.public_binding(),
        "runtime_bindings": [
            {
                "name": "original_global_rules_for_restore",
                "producer": "fresh-pre-mutation-global-firewall-response",
                "cardinality": 1,
                "replay_allowed": False,
            },
            {
                "name": "owned_ruleset_id",
                "producer": "create-owned-regional-ruleset",
                "cardinality": 1,
                "replay_allowed": False,
            },
            {
                "name": "owned_instance_id",
                "producer": "launch-instance-or-one-recovery-get",
                "cardinality": 1,
                "replay_allowed": False,
            },
            {
                "name": "owned_instance_public_ipv4",
                "producer": "active-instance-response",
                "cardinality": 1,
                "replay_allowed": False,
            },
            {
                "name": "approved_agent_socket",
                "producer": "local-agent-preflight",
                "cardinality": 1,
                "replay_allowed": False,
            },
            {
                "name": "jupyter_ed25519_fingerprint",
                "producer": "user-private-checkpoint",
                "cardinality": 1,
                "replay_allowed": False,
            },
        ],
        "provider_operations": provider_operations(),
        "firewall_transaction": {
            "global_before_regional_before_launch": True,
            "strict_rule_count": 1,
            "strict_protocol": "tcp",
            "strict_port_range": [22, 22],
            "strict_source_state": "private-parameter-seal",
            "per_instance_rules_additive_only": True,
            "original_response_sealed_before_first_mutation": True,
            "restore_body_source": "sealed-fresh-pre-mutation-response-data-rules",
            "redacted_inventory_is_restore_body": False,
            "instance_terminal_before_regional_delete": True,
            "regional_delete_before_global_restore": True,
            "termination_unconfirmed_action": (
                "preserve-strict-firewall-and-open-high-severity-incident"
            ),
            "restore_failure_action": (
                "preserve-safest-verified-state-and-open-high-severity-incident"
            ),
        },
        "launch_contract": {
            "launch_count": 1,
            "automatic_retry_count": 0,
            "exact_body_state": "private-template-plus-single-runtime-ruleset-id-binding",
            "one_ssh_key": True,
            "one_regional_ruleset": True,
            "file_system_names": [],
            "file_system_mounts": [],
            "user_data_present": False,
            "unknown_outcome_action": "one-read-only-owned-instance-recovery-get-no-replay",
            "zero-match_recovery_action": "prove-zero-owned-before-firewall-cleanup",
            "multiple-match_recovery_action": "preserve-strict-firewall-high-severity-incident",
        },
        "host_key_checkpoint": {
            "actor": "user",
            "method": "authenticated-lambda-console-jupyter-independent-ed25519-fingerprint",
            "command_argv": [
                "sudo",
                "ssh-keygen",
                "-lf",
                "/etc/ssh/ssh_host_ed25519_key.pub",
                "-E",
                "sha256",
            ],
            "private_checkpoint_schema": HOST_KEY_CHECKPOINT_SCHEMA_PATH,
            "path_must_be_absent_before_wait": True,
            "supervisor_minted_challenge_nonce_after_absence_check": True,
            "checkpoint_timestamp_must_be_inside_wait_window": True,
            "max_seconds": MAX_HUMAN_CHECKPOINT_SECONDS,
            "absent_or_invalid_action": "no-ssh-terminate-and-restore",
        },
        "ssh_contract": {
            "actor": "codex-after-authorization",
            "provider_username": "ubuntu",
            "agent_precondition": "exactly-one-sealed-fingerprint-match",
            "private_key_file_reads": 0,
            "private_key_exports": 0,
            "agent_forwarding": False,
            "keyscan_argv_template": [
                "/usr/bin/ssh-keyscan",
                "-T",
                "10",
                "-t",
                "ed25519",
                "{owned_instance_public_ipv4}",
            ],
            "strict_host_key_checking": True,
            "known_hosts": "fresh-run-owned-private-file",
            "identity_file": "sealed-matching-public-key-file",
            "identity_agent": "held-approved-agent-socket",
            "ssh_argv_renderer": "giclab.harness.lambda_l20_plan.render_ssh_argv",
            "remote_static_command_allowlist": [list(value) for value in REMOTE_STATIC_COMMANDS],
            "remote_dynamic_command_validator": (
                "giclab.harness.lambda_l20_plan.validate_remote_argv"
            ),
            "one-command-per-ssh-session": True,
            "stdout_transfer": (
                "bounded-in-process-stream-to-exclusive-fsync-local-evidence-record"
            ),
            "package_or_daemon_mutation_commands": [],
        },
        "containment_probe": {
            "image_reference": BUSYBOX_REFERENCE,
            "config_digest": BUSYBOX_CONFIG_DIGEST,
            "layer_digest": BUSYBOX_LAYER_DIGEST,
            "layer_bytes": 2_211_507,
            "platform": "linux/amd64",
            "fixture_path": CONTAINMENT_FIXTURE_PATH,
            "fixture_sha256": CONTAINMENT_FIXTURE_SHA256,
            "pull_argv": ["docker", "pull", "--platform", "linux/amd64", BUSYBOX_REFERENCE],
            "create_argv_renderer": "giclab.harness.lambda_l20_plan.render_container_create_argv",
            "lifecycle_arrays": [
                ["docker", "image", "inspect", BUSYBOX_REFERENCE],
                ["docker", "create", "{exact-rendered-private-array}"],
                ["docker", "inspect", "{immutable-container-id}"],
                ["docker", "start", "{immutable-container-id}"],
                [
                    "docker",
                    "top",
                    "{immutable-container-id}",
                    "-eo",
                    "pid,ppid,sid,pgid,stat,comm,args",
                ],
                ["docker", "stop", "--time", "1", "{immutable-container-id}"],
                ["docker", "kill", "--signal", "KILL", "{immutable-container-id}"],
                ["docker", "inspect", "{immutable-container-id}"],
                ["docker", "logs", "--timestamps", "{immutable-container-id}"],
                ["docker", "rm", "{immutable-container-id}"],
                [
                    "docker",
                    "ps",
                    "-a",
                    "--no-trunc",
                    "--filter",
                    f"label=giclab.run={RUN_ID}",
                ],
                [
                    "docker",
                    "network",
                    "ls",
                    "--no-trunc",
                    "--filter",
                    f"label=giclab.run={RUN_ID}",
                ],
                [
                    "docker",
                    "volume",
                    "ls",
                    "--filter",
                    f"label=giclab.run={RUN_ID}",
                ],
                ["/bin/ps", "-eo", "pid,ppid,sid,pgid,stat,comm,args"],
            ],
            "network": "none",
            "cap_drop_all": True,
            "no_new_privileges": True,
            "read_only_root": True,
            "restart_policy": "no",
            "term_to_kill_required": True,
            "wall_deadline_enforced_by": "provider-supervisor-monotonic-deadline",
            "output_cap_enforced_by": "bounded-ssh-stream-writer",
            "init_process": True,
            "ownership_labels_required": [
                "experiment",
                "profile",
                "gate",
                "plan",
                "run",
                "authorization",
                "repository_commit",
                "image_digest",
                "attempt",
                "provider_instance_id",
            ],
            "residual_owned_resources_required": 0,
            "residual_process_analyzer": (
                "reject-container-id-name-or-owned-cgroup-in-final-host-process-snapshot"
            ),
        },
        "network_allowlist": [
            {"host": "cloud.lambda.ai", "port": 443, "purpose": "provider-control"},
            {
                "host": "{owned_instance_public_ipv4}",
                "port": 22,
                "purpose": "ssh-and-evidence-transfer",
            },
            {"host": "auth.docker.io", "port": 443, "purpose": "official-image-token"},
            {
                "host": "registry-1.docker.io",
                "port": 443,
                "purpose": "official-image-manifest-config-layer",
            },
            {
                "host": "production.cloudflare.docker.com",
                "port": 443,
                "purpose": "registry-supplied-layer-redirect-only",
            },
        ],
        "evidence_and_cleanup": {
            "success_schema": HOST_EVIDENCE_SCHEMA_PATH,
            "incident_schema": INCIDENT_SCHEMA_PATH,
            "stream_writer": "giclab.harness.lambda_l2_evidence.GateL2EvidenceWriter",
            "archive_executor": "giclab.harness.lambda_l2_evidence.archive_to_approved_external",
            "archive_id": "RUN-T07-L2-LAMBDA-HOST-QUALIFICATION-0001-HOST-EVIDENCE",
            "remote_source_retained_until_local_hash_verification": True,
            "transfer_failure_does_not_delay_termination": True,
            "provider_api_termination_required": True,
            "required_provider_terminal_status": "terminated",
            "billing_ended_source_contract": True,
            "final_zero_owned_instances_get_required": True,
            "host_shutdown_is_termination": False,
            "local_source_retained": True,
            "external_archive_root": str(EXTERNAL_ARCHIVE_ROOT),
            "external_volume_uuid": "8478609D-FA37-4ED5-875D-47AE912B9151",
            "external_physical_store_uuid": "7904A6F1-F483-4ED7-9E34-BFECAB31C63E",
            "observed_container_capacity_bytes": EXTERNAL_CONTAINER_CAPACITY_BYTES,
            "retained_free_floor_bytes": EXTERNAL_RETAINED_FREE_FLOOR_BYTES,
            "required_precopy_free_bytes": EXTERNAL_PRECOPY_FREE_FLOOR_BYTES,
            "future_revalidation_formula": (
                "max(150_GiB,ceil(container_capacity_bytes/5))+archive_bytes"
            ),
            "held_no_follow_guard": True,
            "one_way_copy": True,
            "source_destination_sha256_verification": True,
            "atomic_finalization": True,
            "broad_prune_allowed": False,
        },
        "limits": exact_limits(),
        "actors": [
            {
                "step": "load-approved-private-key-into-macos-agent",
                "actor": "user",
                "authorized_now": False,
            },
            {
                "step": "authorize-exact-plan-and-clean-commit",
                "actor": "user",
                "authorized_now": False,
            },
            {
                "step": "run-preflight-and-provider-lifecycle",
                "actor": "codex",
                "authorized_now": False,
            },
            {
                "step": "obtain-jupyter-ed25519-fingerprint-and-write-private-checkpoint",
                "actor": "user",
                "authorized_now": False,
            },
            {
                "step": "ssh-host-and-containment-qualification",
                "actor": "codex",
                "authorized_now": False,
            },
            {"step": "terminate-restore-seal-and-stop", "actor": "codex", "authorized_now": False},
        ],
        "terminal_state": "ready-for-gate-l2-authorization",
        "next_gate": "Gate L2 exact user authorization only",
        "cloud_mutation_allowed_now": False,
        "paid_compute_allowed_now": False,
        "ssh_allowed_now": False,
        "container_allowed_now": False,
        "model_calls_allowed": False,
        "browser_automation_allowed": False,
        "sira_execution_allowed": False,
    }
    validate_public_plan(plan, repository_root=repository_root)
    return plan


def validate_public_plan(
    plan: Mapping[str, object],
    *,
    repository_root: Path,
) -> None:
    """Validate schema, privacy, exact limits, calls, and unauthorized state."""

    _validate_schema(
        plan,
        repository_root=repository_root,
        schema_relative_path=PLAN_SCHEMA_PATH,
    )
    if _contains_null(plan):
        raise L20ContractError("executable public plan contains a null value")
    if plan.get("plan_id") != PLAN_ID or plan.get("run_id") != RUN_ID:
        raise L20ContractError("public plan identity drifted")
    if (
        plan.get("authorized") is not False
        or plan.get("authorization_reference") != AUTHORIZATION_PLACEHOLDER
        or plan.get("cloud_mutation_allowed_now") is not False
        or plan.get("paid_compute_allowed_now") is not False
    ):
        raise L20ContractError("public plan prematurely grants execution authority")
    provider = _mapping(plan.get("provider"), context="plan provider")
    if provider != {
        "name": "lambda-on-demand-cloud",
        "api_base_url": API_BASE_URL,
        "transport": "python-stdlib-in-process-https-no-redirect",
        "secret_variable": "LAMBDA_API_KEY",
        "secret_channel": "approved-nonlogging-in-process-channel",
        "secret_retained_through_terminal_confirmation": True,
        "account_api_requests_authorized_now": 0,
        "request_renderer": "giclab.harness.lambda_l2_execution.render_provider_request",
        "request_executor": "giclab.harness.lambda_l2_execution.execute_observed_request",
        "request_ledger": "giclab.harness.lambda_l2_execution.FsyncL2ProviderLedger",
        "request_ledger_schema": PROVIDER_LEDGER_SCHEMA_PATH,
        "ledger_capacity_reserved_before_first_request": True,
        "raw_request_bodies_in_ledger": False,
    }:
        raise L20ContractError("provider transport or ledger contract drifted")
    scientific = _mapping(plan.get("scientific_boundary"), context="scientific boundary")
    if scientific != {
        "experiment_id": "EXP-0001",
        "profile_plan_id": "PLAN-EXP0001-SMOKE",
        "reactive_first": True,
        "simulative_second": True,
        "pair_id": "PAIR-EXP0001-SMOKE-0000",
        "model": "gpt-4o-2024-11-20",
        "reproduction_level": "directional-reproduction",
        "interpretation_allowed": False,
        "pilot_authorized": False,
        "training_allowed": False,
    }:
        raise L20ContractError("scientific boundary drifted")
    selection = _mapping(plan.get("public_selection"), context="public selection")
    expected_selection = {
        "instance_type_name": "gpu_1x_a10",
        "region_name": "us-east-1",
        "image_alias": "img-0111",
        "image_family": "gpu-base-22-04",
        "image_version": "22.4.5-2141",
        "architecture": "x86_64",
        "price_cents_per_hour": SELECTED_LIST_PRICE_CENTS_PER_HOUR,
        "vcpus": 30,
        "memory_gib": 200,
        "root_storage_gib": 1400,
        "gpus": 1,
        "ssh_key_name": "fractal-lambda-codex",
        "ssh_access_mode": "preloaded-ssh-agent",
        "persistent_filesystem_count": 0,
    }
    if selection != expected_selection:
        raise L20ContractError("public resource selection drifted")
    limits = _mapping(plan.get("limits"), context="plan limits")
    if dict(limits) != exact_limits():
        raise L20ContractError("public plan limits drifted")
    operations = [
        _mapping(value, context="provider operation")
        for value in _sequence(plan.get("provider_operations"), context="provider operations")
    ]
    if operations != provider_operations():
        raise L20ContractError("provider operation order or identity drifted")
    if (
        sum(_integer(value.get("max_calls"), context="provider call cap") for value in operations)
        != MAX_PROVIDER_API_CALLS
    ):
        raise L20ContractError("provider call-cap derivation does not equal aggregate")
    containment = _mapping(plan.get("containment_probe"), context="containment probe")
    if (
        containment.get("image_reference") != BUSYBOX_REFERENCE
        or containment.get("network") != "none"
        or containment.get("config_digest") != BUSYBOX_CONFIG_DIGEST
        or containment.get("layer_digest") != BUSYBOX_LAYER_DIGEST
        or containment.get("cap_drop_all") is not True
        or containment.get("no_new_privileges") is not True
        or containment.get("read_only_root") is not True
        or containment.get("restart_policy") != "no"
        or containment.get("term_to_kill_required") is not True
        or containment.get("init_process") is not True
        or containment.get("residual_owned_resources_required") != 0
    ):
        raise L20ContractError("containment image or network contract drifted")
    launch = _mapping(plan.get("launch_contract"), context="launch contract")
    if launch.get("launch_count") != 1 or launch.get("automatic_retry_count") != 0:
        raise L20ContractError("launch count or replay policy drifted")
    firewall = _mapping(plan.get("firewall_transaction"), context="firewall transaction")
    if (
        firewall.get("global_before_regional_before_launch") is not True
        or firewall.get("strict_rule_count") != 1
        or firewall.get("strict_protocol") != "tcp"
        or firewall.get("strict_port_range") != [22, 22]
        or firewall.get("original_response_sealed_before_first_mutation") is not True
        or firewall.get("restore_body_source") != "sealed-fresh-pre-mutation-response-data-rules"
        or firewall.get("redacted_inventory_is_restore_body") is not False
        or firewall.get("instance_terminal_before_regional_delete") is not True
        or firewall.get("regional_delete_before_global_restore") is not True
    ):
        raise L20ContractError("firewall transaction contract drifted")
    checkpoint = _mapping(plan.get("host_key_checkpoint"), context="host-key checkpoint")
    if (
        checkpoint.get("path_must_be_absent_before_wait") is not True
        or checkpoint.get("supervisor_minted_challenge_nonce_after_absence_check") is not True
        or checkpoint.get("checkpoint_timestamp_must_be_inside_wait_window") is not True
        or checkpoint.get("max_seconds") != MAX_HUMAN_CHECKPOINT_SECONDS
    ):
        raise L20ContractError("host-key checkpoint freshness contract drifted")
    ssh = _mapping(plan.get("ssh_contract"), context="SSH contract")
    if (
        ssh.get("private_key_file_reads") != 0
        or ssh.get("private_key_exports") != 0
        or ssh.get("agent_forwarding") is not False
        or ssh.get("one-command-per-ssh-session") is not True
        or ssh.get("remote_static_command_allowlist")
        != [list(value) for value in REMOTE_STATIC_COMMANDS]
        or ssh.get("package_or_daemon_mutation_commands") != []
    ):
        raise L20ContractError("SSH command or private-key contract drifted")
    evidence = _mapping(plan.get("evidence_and_cleanup"), context="evidence cleanup")
    if (
        evidence.get("success_schema") != HOST_EVIDENCE_SCHEMA_PATH
        or evidence.get("incident_schema") != INCIDENT_SCHEMA_PATH
        or evidence.get("source_destination_sha256_verification") is not True
        or evidence.get("atomic_finalization") is not True
        or evidence.get("local_source_retained") is not True
        or evidence.get("provider_api_termination_required") is not True
        or evidence.get("required_provider_terminal_status") != "terminated"
        or evidence.get("final_zero_owned_instances_get_required") is not True
        or evidence.get("broad_prune_allowed") is not False
        or evidence.get("retained_free_floor_bytes") != EXTERNAL_RETAINED_FREE_FLOOR_BYTES
        or evidence.get("required_precopy_free_bytes") != EXTERNAL_PRECOPY_FREE_FLOOR_BYTES
    ):
        raise L20ContractError("evidence, termination, or archive contract drifted")
    _assert_public_privacy(plan)


def schema_hashes(repository_root: Path) -> dict[str, str]:
    """Hash every new Gate L2.0 schema without interpreting private evidence."""

    result: dict[str, str] = {}
    for relative in (
        HUMAN_DECISION_SCHEMA_PATH,
        PRIVATE_PARAMETERS_SCHEMA_PATH,
        HOST_KEY_CHECKPOINT_SCHEMA_PATH,
        PLAN_SCHEMA_PATH,
        PROVIDER_LEDGER_SCHEMA_PATH,
        HOST_EVIDENCE_SCHEMA_PATH,
        INCIDENT_SCHEMA_PATH,
    ):
        encoded = _read_regular_no_follow(
            repository_root / relative,
            max_bytes=256 * 1024,
            require_owner=False,
        )
        result[relative] = sha256_bytes(encoded)
    return result
