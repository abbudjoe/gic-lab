"""Offline Gate L2.3 decision sealing and unauthorized plan contracts.

Importing this module is inert.  It has no credential, network, browser, SSH,
container, Jupyter, or cloud-mutation boundary.  The only concrete side effect is the
explicitly invoked local/private decision materialization and guarded one-way archive
copy used by Gate L2.3.
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import re
import runpy
import secrets
import stat
from collections.abc import Callable, Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from jsonschema import Draft202012Validator

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
from .lambda_inventory_plan_v3 import InventoryRunBindingV3, load_inventory_plan_v3
from .lambda_l2m_checkpoints import (
    USER_CHECKPOINT_TYPES,
    CheckpointContractError,
    validate_human_decision,
)
from .lambda_l2m_checkpoints import (
    ValidatedHumanDecision as CheckpointHumanDecision,
)
from .lambda_l2m_observer import (
    MAX_AGGREGATE_RESPONSE_BYTES,
    MAX_EXTERNAL_ARCHIVE_BYTES,
    MAX_LOCAL_PROCESS_CALLS,
    MAX_LOCAL_PROCESS_OUTPUT_BYTES,
    MAX_MAC_ACTIVE_EVIDENCE_BYTES,
    MAX_OBSERVER_EVENT_BYTES,
    MAX_OBSERVER_EVENTS,
    MAX_OBSERVER_GETS,
    MAX_OBSERVER_JOURNAL_BYTES,
    MAX_OBSERVER_WALL_SECONDS,
    MAX_PROVIDER_COST_CENTS,
    MAX_PROVIDER_WALL_SECONDS,
    MAX_QUALIFICATION_ARCHIVE_BYTES,
    MAX_QUALIFICATION_FILES,
    MAX_QUALIFICATION_UNPACKED_BYTES,
    MAX_RESPONSE_BYTES_PER_GET,
    MAX_USER_CHECKPOINT_SECONDS,
    MIN_REQUEST_SPACING_SECONDS,
    OBSERVER_PHASE_GET_LIMITS,
    RECOMMENDED_IMAGE_ALIAS,
    RECOMMENDED_IMAGE_VERSION,
    REQUIRED_IMAGE_FAMILY,
    SELECTED_ARCHITECTURE,
    SELECTED_INSTANCE_TYPE,
    SELECTED_REGION,
    SELECTED_SSH_KEY_NAME,
    exact_l2m_caps,
)
from .lambda_l13_security import (
    ALIAS_MAP_RELATIVE_ROOT,
    INVENTORY_SHA256,
    L13ContractError,
    project_image_identities,
    validate_l13_gate_l2_evidence,
)
from .lambda_l13_security import (
    AUTHORIZATION_REFERENCE as L1_AUTHORIZATION_REFERENCE,
)
from .lambda_l13_security import (
    AUTHORIZATION_SHA256 as L1_AUTHORIZATION_SHA256,
)
from .lambda_l13_security import (
    EXECUTION_COMMIT as L1_EXECUTION_COMMIT,
)
from .lambda_l13_security import (
    IMPLEMENTATION_COMMIT as L1_IMPLEMENTATION_COMMIT,
)
from .lambda_l13_security import (
    PLAN_SHA256 as L1_PLAN_SHA256,
)
from .lambda_l20_plan import (
    PRIVATE_DECISION_NAME as L20_PRIVATE_DECISION_NAME,
)
from .lambda_l20_plan import PRIVATE_PARAMETERS_NAME as L20_PRIVATE_PARAMETERS_NAME
from .lambda_l20_plan import (
    PRIVATE_ROOT_RELATIVE as L20_PRIVATE_ROOT_RELATIVE,
)
from .lambda_l20_plan import (
    load_private_binding as load_l20_private_binding,
)
from .sira_storage import APPROVED_MOUNT, VolumeObservation


class L23ContractError(ValueError):
    """A private decision, binding, seal, or public plan violated Gate L2.3."""


BRANCH: Final = "phase-1/sira-smoke-lambda"
STARTING_COMMIT: Final = "b71cbbc29f59da600d57b7f0ad28d14572b5fc62"
L22_IMPLEMENTATION_COMMIT: Final = "82670a862e73ae1404fecaec775232445fddcdd8"
PLAN_ID: Final = "PLAN-T07-GATE-L2M-MANUAL-CONSOLE-HOST-QUALIFICATION-V1"
RUN_ID: Final = "RUN-T07-L2M-MANUAL-CONSOLE-HOST-QUALIFICATION-0001"
AUTHORIZATION_PLACEHOLDER: Final = "AUTH-T07-GATE-L2M-MANUAL-CONSOLE-HOST-QUALIFICATION-V1-PENDING"
TERMINAL_DECISION: Final = "ready-for-manual-console-qualification-authorization"

DECISION_PATH: Final = Path.home() / ".config/gic-lab/t07/l2-manual-console-decisions.json"
DECISION_SCHEMA_RELATIVE: Final = Path("schemas/t07-lambda-l2m-human-decision.schema.json")
DECISION_SCHEMA_SHA256: Final = "7054b83d9aa56683b24ba3c1057ca6f9aeb9ae1ee38fc3d2f37179514d4f1d79"
PRIVATE_SEAL_SCHEMA_RELATIVE: Final = Path(
    "schemas/t07-lambda-l2m-private-decision-seal.schema.json"
)
PRIVATE_SEAL_SCHEMA_SHA256: Final = (
    "e4bc66c5759fe700e62ba2bb54dec1c509c68f7f63308170195c6454c607ca3f"
)
CHECKPOINT_SCHEMA_RELATIVE: Final = Path("schemas/t07-lambda-l2m-checkpoint.schema.json")
CHECKPOINT_SCHEMA_SHA256: Final = "a55f9023f8cc8f530acebe31bbe7b50c57d1e1a01b959ced38876e43e0f108ff"
OBSERVER_JOURNAL_SCHEMA_RELATIVE: Final = Path(
    "schemas/t07-lambda-l2m-observer-journal.schema.json"
)
HOST_EVIDENCE_SCHEMA_RELATIVE: Final = Path("schemas/t07-lambda-l2m-host-evidence.schema.json")
PLAN_RELATIVE: Final = Path(
    "containers/sira-smoke/lambda/manual-console/gate-l2m-host-qualification-plan-v1.json"
)
CHECKPOINT_TEMPLATE_ROOT_RELATIVE: Final = Path(
    "containers/sira-smoke/lambda/manual-console/checkpoints"
)
SUPERVISOR_BOOTSTRAP_RELATIVE: Final = Path(
    "containers/sira-smoke/lambda/manual-console/l23_supervisor_bootstrap.py"
)

PRIVATE_ROOT_RELATIVE: Final = Path("artifacts/t07/lambda/gate-l2m") / RUN_ID / "materialization-v1"
PRIVATE_DECISION_FILE: Final = "human-decision-original.json"
PRIVATE_PARAMETERS_FILE: Final = "private-parameters.json"
PRIVATE_DECISION_SEAL_FILE: Final = "PRIVATE_DECISION_SEAL.json"
PRIVATE_BUNDLE_SEAL_FILE: Final = "PRIVATE_BUNDLE_SEAL.json"
PRIVATE_COPY_RECORD_FILE: Final = "PRIVATE_ARCHIVE_COPY_RECORD.json"
EXTERNAL_COPY_RECORD_FILE: Final = "COPY_RECORD.json"
EXTERNAL_SEAL_FILE: Final = "SEAL.json"
EXTERNAL_ARCHIVE_ROOT: Final = APPROVED_MOUNT / "GIC-Lab/t07/sealed-artifacts"

INVENTORY_RELATIVE: Final = Path(
    "artifacts/t07/lambda/gate-l1/RUN-T07-L1-LAMBDA-INVENTORY-0003/inventory-redacted.json"
)
L1_PLAN_RELATIVE: Final = Path(
    "containers/sira-smoke/lambda/gate-l1-readonly-inventory-plan-v3.json"
)
L1A_PRIVATE_RELATIVE: Final = Path(
    "artifacts/t07/lambda/gate-l1a/"
    "RUN-T07-L1A-LAMBDA-SSH-KEY-FINGERPRINT-0001/private-evidence.json"
)

BUNDLE_ROOT_RELATIVE: Final = Path("containers/sira-smoke/lambda/manual-console")
BUNDLE_MANIFEST_RELATIVE: Final = BUNDLE_ROOT_RELATIVE / "manifest.json"
BUNDLE_MANIFEST_SHA256: Final = "dc9824649f97fab6cfd105b5fc0d0c6c1c5ff513fa25f70e0d517afa623cc261"
QUALIFICATION_DRIVER_SHA256: Final = (
    "ab9a3f8981d2e60ea5b57bb7cf63512f64cdb89f26d8183788aedc2dbe4b5050"
)

MAX_DECISION_BYTES: Final = 16_384
MAX_PRIVATE_PARAMETERS_BYTES: Final = 262_144
MAX_PRIVATE_SEAL_BYTES: Final = 65_536
MAX_PRIVATE_ARCHIVE_BYTES: Final = 1_048_576
MIN_LOCAL_PREWRITE_FREE_BYTES: Final = 8_725_200_896
MIN_LOCAL_RETAINED_FREE_BYTES: Final = 8_589_934_592
SELECTED_PRICE_CENTS_PER_HOUR: Final = 129
CHECKPOINT_COUNT: Final = len(USER_CHECKPOINT_TYPES)
PUBLIC_METADATA_RETRIEVED_AT_UTC: Final = "2026-08-11T06:15:19.646016Z"
PUBLIC_METADATA_MAX_AGE_SECONDS: Final = 86_400
PUBLIC_METADATA_PRELAUNCH_HEADROOM_SECONDS: Final = 3_600
PLAN_LATEST_SAFE_START_UTC: Final = "2026-08-12T05:15:19.646016Z"

MANUAL_STEP_CONTRACT: Final = (
    ("observer", "preflight_and_read_only_revalidation"),
    ("user", "launch_wizard_offeredness_check_no_launch"),
    ("observer", "seal_exact_original_global_firewall"),
    ("user", "replace_global_firewall_tcp22_private_32"),
    ("observer", "verify_exact_global_restriction"),
    ("user", "create_owned_regional_ruleset"),
    ("observer", "bind_and_verify_owned_regional_ruleset"),
    ("user", "select_exact_launch_configuration_no_launch"),
    ("observer", "arm_durable_launch_window"),
    ("user", "click_launch_exactly_once"),
    ("observer", "bind_exactly_one_instance_or_incident"),
    ("user", "open_cloud_ide_jupyter_for_bound_instance"),
    ("user", "upload_exact_qualification_bundle"),
    ("user", "run_hash_first_qualification_once"),
    ("user", "download_evidence_to_exact_inbound_root"),
    ("observer", "validate_archive_and_host_container_evidence"),
    ("user", "terminate_bound_or_incident_scope_instances"),
    ("observer", "verify_terminal_or_absent"),
    ("user", "delete_owned_regional_ruleset"),
    ("observer", "verify_owned_regional_ruleset_absent"),
    ("user", "restore_exact_original_global_firewall"),
    ("observer", "verify_exact_global_restoration"),
    ("observer", "seal_and_copy_evidence_one_way"),
)

_HEX64: Final = re.compile(r"^[a-f0-9]{64}$")
_SAFE_PRIVATE_ID: Final = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$")
_PLACEHOLDERS: Final = ("replace", "placeholder", "<private", "<64-", "todo", "changeme")
_PRIVATE_PUBLIC_PATTERNS: Final = (
    re.compile(r"/Users/"),
    re.compile(r"(?:^|[^0-9])(?:[0-9]{1,3}\.){3}[0-9]{1,3}/32(?:$|[^0-9])"),
    re.compile(r"SHA256:[A-Za-z0-9+/]{20,}"),
    re.compile(r"(?:/Users/[^/]+/\.ssh/|~/\.ssh/|SSH_AUTH_SOCK=)"),
    re.compile(r"(?:jupyter[_-]token|token=)", re.IGNORECASE),
)


def canonical_bytes(value: object) -> bytes:
    """Return the canonical newline-terminated JSON encoding for retained records."""

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


def canonical_decision_bytes(value: object) -> bytes:
    """Match the decision capability's canonical encoding exactly."""

    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _strict_json(encoded: bytes, *, context: str) -> dict[str, object]:
    def pairs(values: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in values:
            if key in result:
                raise L23ContractError(f"{context} contains a duplicate key")
            result[key] = value
        return result

    try:
        value = json.loads(encoded, object_pairs_hook=pairs)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise L23ContractError(f"{context} is not strict JSON") from None
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise L23ContractError(f"{context} must be an object")
    return value


def _mapping(value: object, *, context: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or any(not isinstance(key, str) for key in value):
        raise L23ContractError(f"{context} is not an object")
    return value


def _sequence(value: object, *, context: str) -> Sequence[object]:
    if not isinstance(value, list):
        raise L23ContractError(f"{context} is not an array")
    return value


def _nonempty(value: object, *, context: str) -> str:
    if not isinstance(value, str) or not value:
        raise L23ContractError(f"{context} is unavailable")
    return value


def _read_descriptor(descriptor: int, *, max_bytes: int) -> bytes:
    observed = os.fstat(descriptor)
    if not stat.S_ISREG(observed.st_mode) or observed.st_nlink != 1:
        raise L23ContractError("held input is not one regular file")
    output = bytearray()
    while True:
        chunk = os.read(descriptor, min(65_536, max_bytes + 1 - len(output)))
        if not chunk:
            break
        output.extend(chunk)
        if len(output) > max_bytes:
            raise L23ContractError("held input exceeds its byte cap")
    if len(output) != observed.st_size:
        raise L23ContractError("held input size changed during read")
    return bytes(output)


def _read_regular_no_follow(
    path: Path,
    *,
    max_bytes: int,
    require_owner: bool = True,
    required_mode: int | None = None,
) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        before = path.lstat()
        descriptor = os.open(path, flags)
    except OSError:
        raise L23ContractError("required retained input is unavailable") from None
    try:
        opened = os.fstat(descriptor)
        if (
            not stat.S_ISREG(before.st_mode)
            or stat.S_ISLNK(before.st_mode)
            or (before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino)
            or opened.st_nlink != 1
            or (require_owner and opened.st_uid != os.getuid())
            or (required_mode is not None and stat.S_IMODE(opened.st_mode) != required_mode)
        ):
            raise L23ContractError("required retained input identity is unsafe")
        return _read_descriptor(descriptor, max_bytes=max_bytes)
    finally:
        os.close(descriptor)


def _read_exact_private_decision(path: Path) -> bytes:
    """Traverse every absolute path component with O_NOFOLLOW and retain no path value."""

    if path != DECISION_PATH or not path.is_absolute():
        raise L23ContractError("private decision path differs from the fixed contract")
    descriptor = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in path.parts[1:-1]:
            child = os.open(
                part,
                os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0),
                dir_fd=descriptor,
            )
            os.close(descriptor)
            descriptor = child
        leaf = os.open(
            path.name,
            os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=descriptor,
        )
        try:
            observed = os.fstat(leaf)
            if (
                not stat.S_ISREG(observed.st_mode)
                or observed.st_uid != os.getuid()
                or stat.S_IMODE(observed.st_mode) != 0o600
                or observed.st_nlink != 1
                or not 0 < observed.st_size <= MAX_DECISION_BYTES
            ):
                raise L23ContractError("private decision identity, mode, or size is unsafe")
            return _read_descriptor(leaf, max_bytes=MAX_DECISION_BYTES)
        finally:
            os.close(leaf)
    except OSError:
        raise L23ContractError("private decision no-follow traversal failed") from None
    finally:
        os.close(descriptor)


def _load_schema(
    repository_root: Path, relative: Path, *, expected_sha256: str
) -> dict[str, object]:
    encoded = _read_regular_no_follow(
        repository_root / relative,
        max_bytes=MAX_PRIVATE_PARAMETERS_BYTES,
        require_owner=False,
    )
    if sha256_bytes(encoded) != expected_sha256:
        raise L23ContractError("bound schema identity drifted")
    schema = _strict_json(encoded, context="bound schema")
    Draft202012Validator.check_schema(schema)
    return schema


def _fresh_nonce(repository_root: Path, nonce: str) -> bool:
    """Reject reuse against the last sealed private L2 decision without exposing either."""

    load_l20_private_binding(repository_root)
    prior = _strict_json(
        _read_regular_no_follow(
            repository_root / L20_PRIVATE_ROOT_RELATIVE / L20_PRIVATE_DECISION_NAME,
            max_bytes=MAX_DECISION_BYTES,
        ),
        context="prior sealed decision",
    )
    return prior.get("decision_nonce") != nonce


@dataclass(frozen=True, slots=True)
class ValidatedPrivateDecision:
    encoded: bytes = field(repr=False)
    document: Mapping[str, object] = field(repr=False)
    capability: CheckpointHumanDecision = field(repr=False)
    decision_alias: str
    source_sha256: str
    canonical_sha256: str
    bytes: int


def load_private_decision(
    repository_root: Path,
    *,
    path: Path = DECISION_PATH,
) -> ValidatedPrivateDecision:
    """Validate the exact user file and return only an opaque public capability."""

    root = repository_root.resolve(strict=True)
    if root != repository_root.absolute():
        raise L23ContractError("repository root is not canonical")
    encoded = _read_exact_private_decision(path)
    document = _strict_json(encoded, context="private decision")
    schema = _load_schema(root, DECISION_SCHEMA_RELATIVE, expected_sha256=DECISION_SCHEMA_SHA256)
    try:
        capability = validate_human_decision(
            document,
            schema=schema,
            schema_path=root / DECISION_SCHEMA_RELATIVE,
        )
    except CheckpointContractError:
        raise L23ContractError("private decision failed the repository contract") from None
    for name, value in document.items():
        if name.startswith(("approve_", "attest_", "acknowledge_")) and value is not True:
            raise L23ContractError("private decision lacks an explicit required true value")
    expected: dict[str, object] = {
        "selected_image_alias": RECOMMENDED_IMAGE_ALIAS,
        "selected_image_version": RECOMMENDED_IMAGE_VERSION,
        "selected_ssh_key_name": SELECTED_SSH_KEY_NAME,
        "max_provider_cost_usd": 2.0,
        "max_provider_wall_seconds": MAX_PROVIDER_WALL_SECONDS,
        "max_user_checkpoint_seconds": MAX_USER_CHECKPOINT_SECONDS,
        "persistent_filesystem": None,
    }
    if any(document.get(name) != value for name, value in expected.items()):
        raise L23ContractError("private decision fixed values drifted")
    nonce = _nonempty(document.get("decision_nonce"), context="decision nonce")
    if _HEX64.fullmatch(nonce) is None or not _fresh_nonce(root, nonce):
        raise L23ContractError("private decision nonce is invalid or reused")
    if any(
        any(marker in value.lower() for marker in _PLACEHOLDERS)
        for value in document.values()
        if isinstance(value, str)
    ):
        raise L23ContractError("private decision contains a placeholder")
    source_sha256 = sha256_bytes(encoded)
    canonical_sha256 = sha256_bytes(canonical_decision_bytes(document))
    if canonical_sha256 != capability.decision_sha256:
        raise L23ContractError("private decision capability hash drifted")
    return ValidatedPrivateDecision(
        encoded,
        document,
        capability,
        capability.decision_alias,
        source_sha256,
        canonical_sha256,
        len(encoded),
    )


@dataclass(frozen=True, slots=True)
class PrivateMaterialization:
    document: Mapping[str, object] = field(repr=False)
    decision_alias: str
    marker_alias: str
    archive_alias: str
    raw_image_id_bound: bool
    raw_ssh_key_id_bound: bool
    unique_public_key_match_bound: bool
    global_firewall_bound: bool
    checkpoint_count: int


def _load_json(repository_root: Path, relative: Path, *, max_bytes: int) -> dict[str, object]:
    return _strict_json(
        _read_regular_no_follow(repository_root / relative, max_bytes=max_bytes),
        context="sealed input",
    )


def _validate_retained_gate_evidence(repository_root: Path) -> None:
    plan = load_inventory_plan_v3(
        repository_root / L1_PLAN_RELATIVE,
        expected_sha256=L1_PLAN_SHA256,
    )
    binding = InventoryRunBindingV3(
        run_id="RUN-T07-L1-LAMBDA-INVENTORY-0003",
        repository_commit=L1_EXECUTION_COMMIT,
        implementation_commit=L1_IMPLEMENTATION_COMMIT,
        authorization_reference=L1_AUTHORIZATION_REFERENCE,
        authorization_sha256=L1_AUTHORIZATION_SHA256,
    )
    try:
        evidence = validate_l13_gate_l2_evidence(
            repository_root,
            plan=plan,
            plan_sha256=L1_PLAN_SHA256,
            run_binding=binding,
        )
    except L13ContractError:
        raise L23ContractError("sealed Gate L1/L1A/L1.3 evidence failed revalidation") from None
    if evidence.inventory_sha256 != INVENTORY_SHA256:
        raise L23ContractError("sealed inventory binding drifted")
    load_l20_private_binding(repository_root)


def _random_hex(random_bytes: Callable[[int], bytes], byte_count: int) -> str:
    value = random_bytes(byte_count)
    if len(value) != byte_count:
        raise L23ContractError("random source returned the wrong byte count")
    return value.hex()


def resolve_private_parameters(
    repository_root: Path,
    decision: ValidatedPrivateDecision,
    *,
    random_bytes: Callable[[int], bytes] = secrets.token_bytes,
) -> PrivateMaterialization:
    """Resolve public aliases through sealed ignored evidence and mint private identities."""

    root = repository_root.resolve(strict=True)
    _validate_retained_gate_evidence(root)
    l20_parameters = _load_json(
        root,
        L20_PRIVATE_ROOT_RELATIVE / L20_PRIVATE_PARAMETERS_NAME,
        max_bytes=MAX_PRIVATE_PARAMETERS_BYTES,
    )
    l20_selected = _mapping(
        l20_parameters.get("selected_resource"), context="sealed L2.0 selected resource"
    )
    if (
        l20_selected.get("instance_type_name") != SELECTED_INSTANCE_TYPE
        or l20_selected.get("region_name") != SELECTED_REGION
        or l20_selected.get("ssh_key_name") != SELECTED_SSH_KEY_NAME
    ):
        raise L23ContractError("sealed human instance-type, region, or key decision drifted")
    inventory = _load_json(root, INVENTORY_RELATIVE, max_bytes=524_288)
    alias_map = _load_json(
        root,
        ALIAS_MAP_RELATIVE_ROOT / "image-id-alias-map.json",
        max_bytes=65_536,
    )
    l1a = _load_json(root, L1A_PRIVATE_RELATIVE, max_bytes=262_144)
    if _sequence(inventory.get("running_instances"), context="running instances"):
        raise L23ContractError("sealed inventory contains a running instance")

    image_rows = _sequence(inventory.get("images"), context="images")
    projection = project_image_identities(image_rows)
    aliases = [
        _mapping(value, context="image alias entry")
        for value in _sequence(alias_map.get("entries"), context="image alias entries")
    ]
    raw_image_ids = [
        _nonempty(value.get("raw_image_id"), context="raw image identity")
        for value in aliases
        if value.get("alias") == RECOMMENDED_IMAGE_ALIAS
    ]
    if len(raw_image_ids) != 1 or projection.alias_by_raw_id.get(raw_image_ids[0]) != (
        RECOMMENDED_IMAGE_ALIAS
    ):
        raise L23ContractError("selected image alias is not a unique sealed binding")
    raw_image_id = raw_image_ids[0]
    selected_images = [
        _mapping(value, context="selected image")
        for value in image_rows
        if _mapping(value, context="image").get("id") == raw_image_id
        and _mapping(_mapping(value, context="image").get("region"), context="image region").get(
            "name"
        )
        == SELECTED_REGION
    ]
    if len(selected_images) != 1 or any(
        selected_images[0].get(name) != expected
        for name, expected in {
            "family": REQUIRED_IMAGE_FAMILY,
            "version": RECOMMENDED_IMAGE_VERSION,
            "architecture": SELECTED_ARCHITECTURE,
        }.items()
    ):
        raise L23ContractError("selected raw image conflicts with the approved public tuple")

    instance_types = [
        _mapping(value, context="instance type")
        for value in _sequence(inventory.get("instance_types"), context="instance types")
        if _mapping(value, context="instance type").get("name") == SELECTED_INSTANCE_TYPE
    ]
    if len(instance_types) != 1:
        raise L23ContractError("selected instance type is not unique")
    selected_type = instance_types[0]
    capacity_regions = {
        _mapping(value, context="capacity region").get("name")
        for value in _sequence(selected_type.get("capacity_regions"), context="capacity regions")
    }
    if (
        selected_type.get("architecture") != SELECTED_ARCHITECTURE
        or selected_type.get("price_cents_per_hour") != SELECTED_PRICE_CENTS_PER_HOUR
        or SELECTED_REGION not in capacity_regions
    ):
        raise L23ContractError("selected instance type price/capacity/architecture drifted")

    account_matches = [
        _mapping(value, context="account key match")
        for value in _sequence(l1a.get("account_to_local_matches"), context="account key matches")
        if _mapping(value, context="account key match").get("account_key_name")
        == SELECTED_SSH_KEY_NAME
    ]
    if len(account_matches) != 1 or account_matches[0].get("match_status") != "unique_match":
        raise L23ContractError("selected SSH key lacks one sealed public-key match")
    raw_ssh_key_id = _nonempty(
        account_matches[0].get("raw_api_key_id"), context="raw provider key identity"
    )
    if _SAFE_PRIVATE_ID.fullmatch(raw_ssh_key_id) is None:
        raise L23ContractError("raw provider key identity is unsafe")
    local_aliases = _sequence(
        account_matches[0].get("matching_local_key_aliases"), context="local key aliases"
    )
    if len(local_aliases) != 1:
        raise L23ContractError("selected SSH key public match is not unique")
    local_alias = _nonempty(local_aliases[0], context="local public key alias")
    local_matches = [
        _mapping(value, context="local public key")
        for value in _sequence(l1a.get("local_public_keys"), context="local public keys")
        if _mapping(value, context="local public key").get("local_key_alias") == local_alias
    ]
    if (
        len(local_matches) != 1
        or local_matches[0].get("private_key_bytes_accessed") is not False
        or l1a.get("private_key_bytes_accessed") is not False
        or l1a.get("ssh_invoked") is not False
    ):
        raise L23ContractError("sealed SSH key evidence violates the public-only contract")
    inventory_keys = [
        _mapping(value, context="inventory SSH key")
        for value in _sequence(inventory.get("ssh_keys"), context="inventory SSH keys")
        if _mapping(value, context="inventory SSH key").get("name") == SELECTED_SSH_KEY_NAME
    ]
    if len(inventory_keys) != 1 or inventory_keys[0].get("id") != raw_ssh_key_id:
        raise L23ContractError("provider SSH key identity differs across sealed evidence")

    global_rows = [
        _mapping(value, context="global firewall")
        for value in _sequence(inventory.get("firewall_rulesets"), context="firewall rulesets")
        if _mapping(value, context="firewall ruleset").get("scope") == "global"
    ]
    regional_rows = [
        value
        for value in _sequence(inventory.get("firewall_rulesets"), context="firewall rulesets")
        if _mapping(value, context="firewall ruleset").get("scope") != "global"
    ]
    if len(global_rows) != 1 or regional_rows:
        raise L23ContractError("sealed firewall baseline is not one global and zero regional")
    original_rules = _sequence(global_rows[0].get("rules"), context="global firewall rules")
    if not original_rules:
        raise L23ContractError("sealed global firewall baseline is empty")

    source_ipv4 = _nonempty(decision.document.get("source_ipv4_cidr"), context="source network")
    try:
        network = ipaddress.ip_network(source_ipv4, strict=True)
    except ValueError:
        raise L23ContractError("private source network is invalid") from None
    if network.version != 4 or network.prefixlen != 32 or not network.network_address.is_global:
        raise L23ContractError("private source network is not one public IPv4 /32")

    ruleset_random_id = _random_hex(random_bytes, 20)
    manual_run_random_id = _random_hex(random_bytes, 32)
    decision_archive_random_id = _random_hex(random_bytes, 32)
    observer_archive_random_id = _random_hex(random_bytes, 32)
    minted_64_hex = {
        manual_run_random_id,
        decision_archive_random_id,
        observer_archive_random_id,
    }
    decision_nonce = _nonempty(decision.document.get("decision_nonce"), context="decision nonce")
    if len(minted_64_hex) != 3 or decision_nonce in minted_64_hex:
        raise L23ContractError("private random identity collision detected")
    private_ruleset_name = f"t07-l2m-{ruleset_random_id}"
    marker_alias = f"l2m-marker-{sha256_bytes(private_ruleset_name.encode())[:12]}"
    archive_alias = f"l2m-archive-{sha256_bytes(observer_archive_random_id.encode())[:12]}"
    decision_archive_id = f"{RUN_ID}-PRIVATE-{decision_archive_random_id[:16]}"
    observer_archive_id = f"{RUN_ID}-EVIDENCE-{observer_archive_random_id[:16]}"
    checkpoints: list[dict[str, object]] = []
    for ordinal, checkpoint_type in enumerate(USER_CHECKPOINT_TYPES, start=1):
        checkpoint_nonce = _random_hex(random_bytes, 32)
        if checkpoint_nonce in minted_64_hex or checkpoint_nonce == decision_nonce:
            raise L23ContractError("private checkpoint nonce collision detected")
        minted_64_hex.add(checkpoint_nonce)
        checkpoint_alias = sha256_bytes(f"{RUN_ID}:{checkpoint_type}:{checkpoint_nonce}".encode())[
            :12
        ].upper()
        checkpoints.append(
            {
                "ordinal": ordinal,
                "checkpoint_type": checkpoint_type,
                "checkpoint_id": f"CHECKPOINT-T07-L2M-{ordinal:02d}-{checkpoint_alias}",
                "checkpoint_nonce": checkpoint_nonce,
            }
        )

    strict_rule = {
        "description": "T07 L2M temporary qualification SSH",
        "port_range": [22, 22],
        "protocol": "tcp",
        "source_network": source_ipv4,
    }
    private_document: dict[str, object] = {
        "schema_version": "0.1.0",
        "plan_id": PLAN_ID,
        "run_id": RUN_ID,
        "manual_run_identity": manual_run_random_id,
        "decision_alias": decision.decision_alias,
        "decision_source_sha256": decision.source_sha256,
        "decision_canonical_sha256": decision.canonical_sha256,
        "selected_resource": {
            "instance_type": SELECTED_INSTANCE_TYPE,
            "region": SELECTED_REGION,
            "architecture": SELECTED_ARCHITECTURE,
            "image_alias": RECOMMENDED_IMAGE_ALIAS,
            "image_family": REQUIRED_IMAGE_FAMILY,
            "image_version": RECOMMENDED_IMAGE_VERSION,
            "raw_image_id": raw_image_id,
            "price_cents_per_hour": SELECTED_PRICE_CENTS_PER_HOUR,
            "ssh_key_name": SELECTED_SSH_KEY_NAME,
            "raw_ssh_key_id": raw_ssh_key_id,
            "local_public_key_alias": local_alias,
            "local_public_key_basename": local_matches[0].get("basename"),
            "local_public_identity_path": local_matches[0].get("exact_path"),
            "local_public_key_fingerprint": local_matches[0].get("fingerprint"),
        },
        "source_ipv4_cidr": source_ipv4,
        "strict_firewall_rule": strict_rule,
        "original_global_firewall": {
            "inventory_sha256": INVENTORY_SHA256,
            "rules": list(original_rules),
            "semantic_sha256": sha256_bytes(canonical_bytes(list(original_rules))),
        },
        "owned_regional_ruleset": {
            "name": private_ruleset_name,
            "marker_alias": marker_alias,
            "region": SELECTED_REGION,
            "rules": [strict_rule],
            "raw_id_runtime_binding": None,
        },
        "checkpoint_root_relative": str(
            Path("artifacts/t07/lambda/gate-l2m") / RUN_ID / "checkpoints"
        ),
        "checkpoint_consumption_ledger_relative": str(
            Path("artifacts/t07/lambda/gate-l2m") / RUN_ID / "checkpoint-consumption.jsonl"
        ),
        "checkpoint_bindings": checkpoints,
        "external_archive": {
            "decision_archive_identity": decision_archive_id,
            "observer_archive_identity": observer_archive_id,
            "archive_alias": archive_alias,
        },
        "limits": {
            "provider_cost_cents": MAX_PROVIDER_COST_CENTS,
            "provider_wall_seconds": MAX_PROVIDER_WALL_SECONDS,
            "observer_wall_seconds": MAX_OBSERVER_WALL_SECONDS,
            "user_checkpoint_seconds": MAX_USER_CHECKPOINT_SECONDS,
            "read_only_gets": MAX_OBSERVER_GETS,
            "persistent_filesystems": 0,
            "launch_clicks": 1,
            "normal_instances": 1,
        },
        "permissions": {
            "authorized": False,
            "cloud_mutation_allowed": False,
            "paid_compute_allowed": False,
            "prototype_execution_allowed": False,
            "ssh_allowed": False,
            "scientific_execution_allowed": False,
        },
    }
    encoded = canonical_bytes(private_document)
    if len(encoded) > MAX_PRIVATE_PARAMETERS_BYTES:
        raise L23ContractError("private parameters exceed their byte cap")
    return PrivateMaterialization(
        private_document,
        decision.decision_alias,
        marker_alias,
        archive_alias,
        True,
        True,
        True,
        True,
        len(checkpoints),
    )


def _directory_flags() -> int:
    return os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0)


def _create_private_root(repository_root: Path) -> int:
    descriptor = os.open(repository_root, _directory_flags())
    try:
        for index, part in enumerate(PRIVATE_ROOT_RELATIVE.parts):
            final = index == len(PRIVATE_ROOT_RELATIVE.parts) - 1
            try:
                os.mkdir(part, 0o700, dir_fd=descriptor)
                os.fsync(descriptor)
            except FileExistsError:
                if final:
                    raise L23ContractError(
                        "fresh private materialization root already exists"
                    ) from None
            child = os.open(part, _directory_flags(), dir_fd=descriptor)
            observed = os.fstat(child)
            if (
                not stat.S_ISDIR(observed.st_mode)
                or observed.st_uid != os.getuid()
                or stat.S_IMODE(observed.st_mode) & 0o077
            ):
                os.close(child)
                raise L23ContractError("private materialization hierarchy is unsafe")
            os.close(descriptor)
            descriptor = child
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _write_private_at(directory_fd: int, name: str, encoded: bytes) -> None:
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
                raise L23ContractError("private evidence write made no progress")
            view = view[written:]
        os.fsync(descriptor)
        os.fchmod(descriptor, 0o400)
    finally:
        os.close(descriptor)


@dataclass(frozen=True, slots=True)
class PrivateBindingSeal:
    root: Path = field(repr=False)
    decision_alias: str
    decision_source_sha256: str
    decision_canonical_sha256: str
    decision_seal_sha256: str
    private_parameters_sha256: str
    bundle_seal_sha256: str
    marker_alias: str
    archive_alias: str
    external_archive_id: str = field(repr=False)
    external_seal_sha256: str = ""
    external_copy_record_sha256: str = ""

    def public_binding(self) -> dict[str, object]:
        if (
            _HEX64.fullmatch(self.external_seal_sha256) is None
            or _HEX64.fullmatch(self.external_copy_record_sha256) is None
        ):
            raise L23ContractError("private binding lacks verified external evidence")
        return {
            "state": "ignored-sealed-local-and-external-evidence",
            "decision_alias": self.decision_alias,
            "decision_source_sha256": self.decision_source_sha256,
            "decision_canonical_sha256": self.decision_canonical_sha256,
            "decision_seal_sha256": self.decision_seal_sha256,
            "private_parameters_sha256": self.private_parameters_sha256,
            "bundle_seal_sha256": self.bundle_seal_sha256,
            "marker_alias": self.marker_alias,
            "archive_alias": self.archive_alias,
            "external_seal_sha256": self.external_seal_sha256,
            "external_copy_record_sha256": self.external_copy_record_sha256,
            "source_retained": True,
            "destination_hashes_verified": True,
            "private_values_in_public_plan": False,
        }


@dataclass(frozen=True, slots=True)
class LoadedPrivateBinding:
    seal: PrivateBindingSeal
    parameters: Mapping[str, object] = field(repr=False)
    decision: Mapping[str, object] = field(repr=False)


@dataclass(frozen=True, slots=True)
class ExecutionStoragePreflight:
    """Public-safe proof that the future run has one fresh, approved storage target."""

    external_identity_validated: bool
    external_archive_identity_fresh: bool
    system_prewrite_floor_validated: bool
    internal_fallback: bool = False


def load_private_binding(repository_root: Path) -> LoadedPrivateBinding:
    """Revalidate every local and external private byte before a future observer run."""

    root = repository_root.resolve(strict=True)
    local_root = root / PRIVATE_ROOT_RELATIVE
    local = _HeldDirectory.open(local_root)
    external: _HeldDirectory | None = None
    try:
        local_identity = os.fstat(local.descriptor)
        if local_identity.st_uid != os.getuid() or stat.S_IMODE(local_identity.st_mode) & 0o077:
            raise L23ContractError("retained private materialization root is not private")
        decision_encoded = _read_regular_at(
            local.descriptor, PRIVATE_DECISION_FILE, max_bytes=MAX_DECISION_BYTES
        )
        parameters_encoded = _read_regular_at(
            local.descriptor,
            PRIVATE_PARAMETERS_FILE,
            max_bytes=MAX_PRIVATE_PARAMETERS_BYTES,
        )
        decision_seal_encoded = _read_regular_at(
            local.descriptor,
            PRIVATE_DECISION_SEAL_FILE,
            max_bytes=MAX_PRIVATE_SEAL_BYTES,
        )
        bundle_seal_encoded = _read_regular_at(
            local.descriptor,
            PRIVATE_BUNDLE_SEAL_FILE,
            max_bytes=MAX_PRIVATE_SEAL_BYTES,
        )
        local_copy = _read_regular_at(
            local.descriptor,
            PRIVATE_COPY_RECORD_FILE,
            max_bytes=MAX_PRIVATE_SEAL_BYTES,
        )
        decision = _strict_json(decision_encoded, context="sealed private decision")
        parameters = _strict_json(parameters_encoded, context="sealed private parameters")
        decision_seal = _strict_json(decision_seal_encoded, context="sealed private decision seal")
        bundle_seal = _strict_json(bundle_seal_encoded, context="sealed private bundle seal")
        schema = _load_schema(
            root,
            PRIVATE_SEAL_SCHEMA_RELATIVE,
            expected_sha256=PRIVATE_SEAL_SCHEMA_SHA256,
        )
        if list(Draft202012Validator(schema).iter_errors(decision_seal)):
            raise L23ContractError("retained private decision seal failed its schema")
        if (
            decision_seal.get("decision_source_sha256") != sha256_bytes(decision_encoded)
            or decision_seal.get("decision_source_bytes") != len(decision_encoded)
            or decision_seal.get("decision_canonical_sha256")
            != sha256_bytes(canonical_decision_bytes(decision))
            or decision_seal.get("private_parameters_sha256") != sha256_bytes(parameters_encoded)
            or decision_seal.get("private_parameters_bytes") != len(parameters_encoded)
        ):
            raise L23ContractError("retained private decision or parameter identity drifted")
        expected_members = {
            PRIVATE_DECISION_FILE: decision_encoded,
            PRIVATE_PARAMETERS_FILE: parameters_encoded,
            PRIVATE_DECISION_SEAL_FILE: decision_seal_encoded,
        }
        sealed_members = {
            _nonempty(
                _mapping(value, context="bundle member").get("name"), context="member"
            ): _mapping(value, context="bundle member")
            for value in _sequence(bundle_seal.get("files"), context="bundle members")
        }
        if set(sealed_members) != set(expected_members) or any(
            sealed_members[name].get("bytes") != len(encoded)
            or sealed_members[name].get("sha256") != sha256_bytes(encoded)
            for name, encoded in expected_members.items()
        ):
            raise L23ContractError("retained private bundle seal drifted")
        archive = _mapping(parameters.get("external_archive"), context="private archive")
        archive_identity = _nonempty(
            archive.get("decision_archive_identity"),
            context="private decision archive identity",
        )
        archive_alias = _nonempty(archive.get("archive_alias"), context="archive alias")
        marker = _mapping(parameters.get("owned_regional_ruleset"), context="private ruleset")
        marker_alias = _nonempty(marker.get("marker_alias"), context="marker alias")
        external_path = EXTERNAL_ARCHIVE_ROOT / archive_identity
        external = _HeldDirectory.open(external_path)
        external_identity = os.fstat(external.descriptor)
        if (
            external_identity.st_uid != os.getuid()
            or stat.S_IMODE(external_identity.st_mode) & 0o077
        ):
            raise L23ContractError("retained external private archive is not private")
        for name, encoded in {
            **expected_members,
            PRIVATE_BUNDLE_SEAL_FILE: bundle_seal_encoded,
        }.items():
            if (
                _read_regular_at(
                    external.descriptor,
                    name,
                    max_bytes=MAX_PRIVATE_PARAMETERS_BYTES,
                )
                != encoded
            ):
                raise L23ContractError("external private archive payload drifted")
        external_copy = _read_regular_at(
            external.descriptor,
            EXTERNAL_COPY_RECORD_FILE,
            max_bytes=MAX_PRIVATE_SEAL_BYTES,
        )
        external_seal = _read_regular_at(
            external.descriptor,
            EXTERNAL_SEAL_FILE,
            max_bytes=MAX_PRIVATE_SEAL_BYTES,
        )
        if external_copy != local_copy:
            raise L23ContractError("local and external private copy records differ")
        external_seal_document = _strict_json(
            external_seal, context="external private archive seal"
        )
        if (
            external_seal_document.get("copy_record_sha256") != sha256_bytes(external_copy)
            or external_seal_document.get("source_retained") is not True
            or external_seal_document.get("destination_hashes_verified") is not True
            or external_seal_document.get("internal_fallback") is not False
        ):
            raise L23ContractError("external private archive seal drifted")
        retained = PrivateBindingSeal(
            local_root,
            _nonempty(decision_seal.get("decision_alias"), context="decision alias"),
            sha256_bytes(decision_encoded),
            sha256_bytes(canonical_decision_bytes(decision)),
            sha256_bytes(decision_seal_encoded),
            sha256_bytes(parameters_encoded),
            sha256_bytes(bundle_seal_encoded),
            marker_alias,
            archive_alias,
            archive_identity,
            sha256_bytes(external_seal),
            sha256_bytes(external_copy),
        )
        if retained.public_binding()["decision_alias"] != parameters.get("decision_alias"):
            raise L23ContractError("private decision alias differs across sealed records")
        return LoadedPrivateBinding(retained, parameters, decision)
    finally:
        if external is not None:
            external.close()
        local.close()


def validate_execution_storage_preflight(
    repository_root: Path,
    private: LoadedPrivateBinding,
    *,
    volume_observer: Callable[[], tuple[VolumeObservation, VolumeObservation]] | None = None,
) -> ExecutionStoragePreflight:
    """Revalidate the UTDM identity/floors and one fresh observer archive identity.

    This check is deliberately performed before a future credential read.  The final
    copy implementation repeats the observation while holding no-follow descriptors;
    this preflight is not treated as authority for a later archive write.
    """

    root = repository_root.resolve(strict=True)
    if private.seal.root.parent.parent.parent.parent.parent != root / "artifacts":
        raise L23ContractError("private binding is not rooted in the repository artifact tree")
    observer = DiskutilVolumeObserver() if volume_observer is None else volume_observer
    archive_handle: _HeldDirectory | None = None
    try:
        external, system = observer()
        _validate_external(external, incremental_bytes=MAX_EXTERNAL_ARCHIVE_BYTES)
        _validate_system(system, floor_bytes=MIN_LOCAL_PREWRITE_FREE_BYTES)
        archive_handle = _HeldDirectory.open(EXTERNAL_ARCHIVE_ROOT)
        archive_handle.revalidate()
        archive = _mapping(private.parameters.get("external_archive"), context="private archive")
        archive_identity = _nonempty(
            archive.get("observer_archive_identity"), context="observer archive identity"
        )
        staging_identity = f".{archive_identity}.partial"
        for name in (archive_identity, staging_identity):
            try:
                os.stat(name, dir_fd=archive_handle.descriptor, follow_symlinks=False)
            except FileNotFoundError:
                continue
            raise L23ContractError("fresh observer archive identity already exists")
        archive_handle.revalidate()
        return ExecutionStoragePreflight(True, True, True)
    except InventoryArchiveError:
        raise L23ContractError("manual execution storage preflight failed") from None
    finally:
        if archive_handle is not None:
            with suppress(OSError):
                archive_handle.close()


def write_private_binding(
    repository_root: Path,
    *,
    decision: ValidatedPrivateDecision,
    materialization: PrivateMaterialization,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> PrivateBindingSeal:
    """Exclusively retain the original decision, private bindings, and public-safe seals."""

    root = repository_root.resolve(strict=True)
    ignored = _read_regular_no_follow(root / ".gitignore", max_bytes=65_536, require_owner=False)
    if b"artifacts/" not in {line.strip() for line in ignored.splitlines()}:
        raise L23ContractError("private artifact root is not ignored by Git")
    parameters = canonical_bytes(materialization.document)
    external = _mapping(materialization.document.get("external_archive"), context="archive")
    archive_identity = _nonempty(
        external.get("decision_archive_identity"),
        context="private decision archive identity",
    )
    sealed_at = now().astimezone(UTC).isoformat().replace("+00:00", "Z")
    seal_document: dict[str, object] = {
        "schema_version": "0.1.0",
        "plan_id": PLAN_ID,
        "run_id": RUN_ID,
        "decision_alias": decision.decision_alias,
        "decision_source_bytes": decision.bytes,
        "decision_source_sha256": decision.source_sha256,
        "decision_canonical_sha256": decision.canonical_sha256,
        "decision_schema_sha256": DECISION_SCHEMA_SHA256,
        "decision_validated": True,
        "nonce_fresh": True,
        "selected_public_resources": {
            "instance_type": SELECTED_INSTANCE_TYPE,
            "region": SELECTED_REGION,
            "image_alias": RECOMMENDED_IMAGE_ALIAS,
            "image_family": REQUIRED_IMAGE_FAMILY,
            "image_version": RECOMMENDED_IMAGE_VERSION,
            "architecture": SELECTED_ARCHITECTURE,
            "ssh_key_name": SELECTED_SSH_KEY_NAME,
            "persistent_filesystem_count": 0,
        },
        "private_bindings": {
            "raw_image_id": materialization.raw_image_id_bound,
            "raw_ssh_key_id": materialization.raw_ssh_key_id_bound,
            "unique_public_key_match": materialization.unique_public_key_match_bound,
            "source_ipv4_cidr": True,
            "original_global_firewall": materialization.global_firewall_bound,
            "regional_ruleset_marker": True,
            "manual_run_identity": True,
            "checkpoint_identities": materialization.checkpoint_count == CHECKPOINT_COUNT,
            "archive_identity": True,
        },
        "private_parameters_bytes": len(parameters),
        "private_parameters_sha256": sha256_bytes(parameters),
        "private_values_publicly_retained": False,
        "source_retained": True,
        "sealed_at_utc": sealed_at,
    }
    schema = _load_schema(
        root,
        PRIVATE_SEAL_SCHEMA_RELATIVE,
        expected_sha256=PRIVATE_SEAL_SCHEMA_SHA256,
    )
    if list(Draft202012Validator(schema).iter_errors(seal_document)):
        raise L23ContractError("private decision seal failed its schema")
    decision_seal = canonical_bytes(seal_document)
    members = {
        PRIVATE_DECISION_FILE: decision.encoded,
        PRIVATE_PARAMETERS_FILE: parameters,
        PRIVATE_DECISION_SEAL_FILE: decision_seal,
    }
    bundle_seal = canonical_bytes(
        {
            "schema_version": "0.1.0",
            "plan_id": PLAN_ID,
            "run_id": RUN_ID,
            "archive_alias": materialization.archive_alias,
            "files": [
                {"name": name, "bytes": len(encoded), "sha256": sha256_bytes(encoded)}
                for name, encoded in sorted(members.items())
            ],
            "source_retained": True,
            "private_values_publicly_retained": False,
        }
    )
    members[PRIVATE_BUNDLE_SEAL_FILE] = bundle_seal
    if sum(len(value) for value in members.values()) > MAX_PRIVATE_ARCHIVE_BYTES:
        raise L23ContractError("private materialization exceeds its retained byte cap")
    descriptor = _create_private_root(root)
    try:
        for name, encoded in members.items():
            _write_private_at(descriptor, name, encoded)
        os.fsync(descriptor)
        for name, encoded in members.items():
            if (
                _read_regular_at(descriptor, name, max_bytes=MAX_PRIVATE_PARAMETERS_BYTES)
                != encoded
            ):
                raise L23ContractError("private materialization readback drifted")
    finally:
        os.close(descriptor)
    return PrivateBindingSeal(
        root / PRIVATE_ROOT_RELATIVE,
        decision.decision_alias,
        decision.source_sha256,
        decision.canonical_sha256,
        sha256_bytes(decision_seal),
        sha256_bytes(parameters),
        sha256_bytes(bundle_seal),
        materialization.marker_alias,
        materialization.archive_alias,
        archive_identity,
    )


def archive_private_binding(binding: PrivateBindingSeal) -> PrivateBindingSeal:
    """Copy the sealed private materialization through the reviewed UTDM guard."""

    if binding.root != binding.root.resolve(strict=True):
        raise L23ContractError("private materialization root is not canonical")
    observer = DiskutilVolumeObserver()
    try:
        external_before, system_before = observer()
        _validate_external(external_before, incremental_bytes=MAX_PRIVATE_ARCHIVE_BYTES)
        _validate_system(system_before, floor_bytes=MIN_LOCAL_PREWRITE_FREE_BYTES)
    except InventoryArchiveError:
        raise L23ContractError("private archive storage preflight failed") from None

    external_handle: _HeldDirectory | None = None
    archive_handle: _HeldDirectory | None = None
    source_handle: _HeldDirectory | None = None
    staging_descriptor = -1
    final_descriptor = -1
    try:
        external_handle = _HeldDirectory.open(APPROVED_MOUNT)
        archive_handle = _open_or_create_archive_root(external_handle, EXTERNAL_ARCHIVE_ROOT)
        source_handle = _HeldDirectory.open(binding.root)
        if source_handle.device == external_handle.device:
            raise L23ContractError("private archive source and destination share a volume")
        external_after, system_after = observer()
        if not _same_identity(external_before, external_after) or not _same_identity(
            system_before, system_after
        ):
            raise L23ContractError("archive volume identity changed before write")
        _validate_external(external_after, incremental_bytes=MAX_PRIVATE_ARCHIVE_BYTES)
        _validate_system(system_after, floor_bytes=MIN_LOCAL_PREWRITE_FREE_BYTES)
        for held in (external_handle, archive_handle, source_handle):
            held.revalidate()

        staging_name = f".{binding.external_archive_id}.partial"
        for name in (binding.external_archive_id, staging_name):
            try:
                os.stat(name, dir_fd=archive_handle.descriptor, follow_symlinks=False)
            except FileNotFoundError:
                continue
            raise L23ContractError("fresh external private archive identity already exists")
        os.mkdir(staging_name, 0o700, dir_fd=archive_handle.descriptor)
        os.fsync(archive_handle.descriptor)
        staging_descriptor = os.open(
            staging_name, _directory_flags(), dir_fd=archive_handle.descriptor
        )
        if os.fstat(staging_descriptor).st_dev != archive_handle.device:
            raise L23ContractError("private archive staging escaped the approved volume")

        names = (
            PRIVATE_DECISION_FILE,
            PRIVATE_PARAMETERS_FILE,
            PRIVATE_DECISION_SEAL_FILE,
            PRIVATE_BUNDLE_SEAL_FILE,
        )
        manifest: list[dict[str, object]] = []
        payload_total = 0
        for name in names:
            encoded = _read_regular_at(
                source_handle.descriptor,
                name,
                max_bytes=MAX_PRIVATE_PARAMETERS_BYTES,
            )
            payload_total += len(encoded)
            _write_exclusive_at(staging_descriptor, name, encoded)
            copied = _read_regular_at(
                staging_descriptor,
                name,
                max_bytes=MAX_PRIVATE_PARAMETERS_BYTES,
            )
            if copied != encoded:
                raise L23ContractError("private archive destination verification failed")
            manifest.append(
                {
                    "name": name,
                    "bytes": len(encoded),
                    "source_sha256": sha256_bytes(encoded),
                    "destination_sha256": sha256_bytes(copied),
                }
            )
        copy_record = canonical_bytes(
            {
                "schema_version": "0.1.0",
                "plan_id": PLAN_ID,
                "run_id": RUN_ID,
                "archive_alias": binding.archive_alias,
                "destination_volume_uuid": "8478609D-FA37-4ED5-875D-47AE912B9151",
                "destination_physical_store_uuid": ("7904A6F1-F483-4ED7-9E34-BFECAB31C63E"),
                "held_no_follow_descriptors": True,
                "internal_fallback": False,
                "source_retained": True,
                "atomic_finalization": True,
                "files": manifest,
            }
        )
        copy_record_sha256 = sha256_bytes(copy_record)
        external_seal = canonical_bytes(
            {
                "schema_version": "0.1.0",
                "plan_id": PLAN_ID,
                "run_id": RUN_ID,
                "archive_alias": binding.archive_alias,
                "copy_record_sha256": copy_record_sha256,
                "payload_files": manifest,
                "payload_bytes": payload_total,
                "source_retained": True,
                "destination_hashes_verified": True,
                "internal_fallback": False,
            }
        )
        if payload_total + len(copy_record) + len(external_seal) > MAX_PRIVATE_ARCHIVE_BYTES:
            raise L23ContractError("private external archive exceeds its byte cap")
        _write_exclusive_at(staging_descriptor, EXTERNAL_COPY_RECORD_FILE, copy_record)
        _write_exclusive_at(staging_descriptor, EXTERNAL_SEAL_FILE, external_seal)
        os.fsync(staging_descriptor)
        os.rename(
            staging_name,
            binding.external_archive_id,
            src_dir_fd=archive_handle.descriptor,
            dst_dir_fd=archive_handle.descriptor,
        )
        os.fsync(archive_handle.descriptor)
        os.close(staging_descriptor)
        staging_descriptor = -1
        final_descriptor = os.open(
            binding.external_archive_id,
            _directory_flags(),
            dir_fd=archive_handle.descriptor,
        )
        for entry in manifest:
            name = str(entry["name"])
            if (
                sha256_bytes(
                    _read_regular_at(final_descriptor, name, max_bytes=MAX_PRIVATE_PARAMETERS_BYTES)
                )
                != entry["source_sha256"]
            ):
                raise L23ContractError("final private archive payload drifted")
        if (
            _read_regular_at(final_descriptor, EXTERNAL_COPY_RECORD_FILE, max_bytes=65_536)
            != copy_record
            or _read_regular_at(final_descriptor, EXTERNAL_SEAL_FILE, max_bytes=65_536)
            != external_seal
        ):
            raise L23ContractError("final private archive control record drifted")
        _write_private_at(source_handle.descriptor, PRIVATE_COPY_RECORD_FILE, copy_record)
        os.fsync(source_handle.descriptor)
        external_final, system_final = observer()
        if not _same_identity(external_before, external_final) or not _same_identity(
            system_before, system_final
        ):
            raise L23ContractError("archive volume identity changed after finalization")
        _validate_external(external_final, incremental_bytes=0)
        _validate_system(system_final, floor_bytes=MIN_LOCAL_RETAINED_FREE_BYTES)
        return replace(
            binding,
            external_seal_sha256=sha256_bytes(external_seal),
            external_copy_record_sha256=copy_record_sha256,
        )
    except (OSError, InventoryArchiveError):
        raise L23ContractError("private archive filesystem action failed") from None
    finally:
        if final_descriptor >= 0:
            os.close(final_descriptor)
        if staging_descriptor >= 0:
            os.close(staging_descriptor)
        for optional_handle in (source_handle, archive_handle, external_handle):
            if optional_handle is not None:
                with suppress(OSError):
                    optional_handle.close()


def observer_caps() -> dict[str, object]:
    """Return the reviewed L2.2 caps with exact per-phase GET partitioning."""

    return {
        "read_only_lambda_gets": MAX_OBSERVER_GETS,
        "minimum_request_spacing_seconds": MIN_REQUEST_SPACING_SECONDS,
        "response_bytes_per_get": MAX_RESPONSE_BYTES_PER_GET,
        "aggregate_response_bytes": MAX_AGGREGATE_RESPONSE_BYTES,
        "observer_events": MAX_OBSERVER_EVENTS,
        "observer_event_bytes": MAX_OBSERVER_EVENT_BYTES,
        "observer_journal_bytes": MAX_OBSERVER_JOURNAL_BYTES,
        "observer_total_wall_seconds": MAX_OBSERVER_WALL_SECONDS,
        "provider_hard_wall_seconds": MAX_PROVIDER_WALL_SECONDS,
        "provider_cost_cents": MAX_PROVIDER_COST_CENTS,
        "observer_phase_get_limits": {
            phase.value: count for phase, count in OBSERVER_PHASE_GET_LIMITS.items()
        },
    }


def _qualification_runtime_caps(repository_root: Path) -> dict[str, object]:
    """Read the exact inert bundle constants instead of duplicating prose-only caps."""

    bundle_root = repository_root / BUNDLE_ROOT_RELATIVE
    driver = runpy.run_path(str(bundle_root / "qualification_driver.py"))
    inspector = runpy.run_path(str(bundle_root / "docker_inspector.py"))
    budget_type = inspector.get("CommandBudget")
    fields = getattr(budget_type, "__dataclass_fields__", None)
    if not isinstance(fields, dict):
        raise L23ContractError("qualification Docker budget contract is unavailable")

    def default(name: str) -> int:
        field = fields.get(name)
        value = getattr(field, "default", None)
        if not isinstance(value, int):
            raise L23ContractError("qualification Docker budget cap is unavailable")
        return value

    create = driver.get("create_arguments")
    if not callable(create):
        raise L23ContractError("qualification create renderer is unavailable")
    arguments = create(
        name="t07-l2m-0000000000000000",
        fixture=Path("/private/t07/adversarial-containment.sh"),
        run_id=RUN_ID,
        marker_alias="l2m-marker-000000000000",
    )

    def option(name: str) -> str:
        try:
            index = arguments.index(name)
            value = arguments[index + 1]
        except (IndexError, ValueError):
            raise L23ContractError("qualification container cap is unavailable") from None
        if not isinstance(value, str):
            raise L23ContractError("qualification container cap is unavailable")
        return value

    tmpfs_sizes = []
    for index, value in enumerate(arguments):
        if value == "--tmpfs" and index + 1 < len(arguments):
            specification = arguments[index + 1]
            match = re.search(r"(?:^|,)size=([0-9]+)(?:,|$)", specification)
            if match is None:
                raise L23ContractError("qualification tmpfs cap is unavailable")
            tmpfs_sizes.append(int(match.group(1)))
    if len(tmpfs_sizes) != 2 or len(set(tmpfs_sizes)) != 1:
        raise L23ContractError("qualification tmpfs cap drifted")

    log_options: dict[str, str] = {}
    for index, value in enumerate(arguments):
        if value == "--log-opt" and index + 1 < len(arguments):
            key, separator, setting = arguments[index + 1].partition("=")
            if separator != "=" or not key or not setting or key in log_options:
                raise L23ContractError("qualification log cap is unavailable")
            log_options[key] = setting
    if log_options != {"max-size": "1m", "max-file": "1"}:
        raise L23ContractError("qualification log cap drifted")
    max_call_output = inspector.get("MAX_CALL_OUTPUT")
    if not isinstance(max_call_output, int):
        raise L23ContractError("qualification per-call output cap is unavailable")
    driver_caps = {
        name: driver.get(name)
        for name in (
            "WORK_WALL_SECONDS",
            "TOTAL_WALL_SECONDS",
            "FIXTURE_WALL_SECONDS",
            "CREATE_OUTCOME_POLL_OBSERVATIONS",
            "CREATE_OUTCOME_STABLE_ABSENCE_OBSERVATIONS",
            "CREATE_OUTCOME_POLL_INTERVAL_SECONDS",
        )
    }
    if any(not isinstance(value, int) for value in driver_caps.values()):
        raise L23ContractError("qualification driver cap is unavailable")
    docker_calls = default("max_calls")
    cleanup_calls = default("cleanup_reserved_calls")
    docker_output_bytes = default("max_output_bytes")
    cleanup_output_bytes = default("cleanup_reserved_output_bytes")
    return {
        "docker_calls": docker_calls,
        "docker_ordinary_work_calls": docker_calls - cleanup_calls,
        "docker_call_output_bytes": max_call_output,
        "docker_output_bytes": docker_output_bytes,
        "docker_ordinary_output_bytes": docker_output_bytes - cleanup_output_bytes,
        "docker_cleanup_reserved_calls": cleanup_calls,
        "docker_cleanup_reserved_output_bytes": cleanup_output_bytes,
        "docker_work_wall_seconds": driver_caps["WORK_WALL_SECONDS"],
        "docker_total_wall_seconds": driver_caps["TOTAL_WALL_SECONDS"],
        "fixture_wall_seconds": driver_caps["FIXTURE_WALL_SECONDS"],
        "qualification_containers": 1,
        "create_outcome_poll_observations": driver_caps["CREATE_OUTCOME_POLL_OBSERVATIONS"],
        "create_outcome_stable_absence_observations": driver_caps[
            "CREATE_OUTCOME_STABLE_ABSENCE_OBSERVATIONS"
        ],
        "create_outcome_poll_interval_seconds": driver_caps["CREATE_OUTCOME_POLL_INTERVAL_SECONDS"],
        "container_cpu_millis": round(float(option("--cpus")) * 1_000),
        "container_memory_bytes": int(option("--memory")),
        "container_memory_swap_bytes": int(option("--memory-swap")),
        "container_pids_limit": int(option("--pids-limit")),
        "container_tmpfs_mounts": len(tmpfs_sizes),
        "container_tmpfs_bytes_each": tmpfs_sizes[0],
        "container_shm_bytes": int(option("--shm-size")),
        "container_log_max_bytes": int(log_options["max-size"].removesuffix("m")) * 1_048_576,
        "container_log_max_files": int(log_options["max-file"]),
        "container_network_mode": option("--network"),
    }


def _public_plan_caps(repository_root: Path) -> dict[str, object]:
    """Return the complete L2.2 cap surface bound by the executable public plan."""

    source = exact_l2m_caps()
    caps: dict[str, object] = {
        "read_only_lambda_gets": MAX_OBSERVER_GETS,
        "minimum_request_spacing_seconds": MIN_REQUEST_SPACING_SECONDS,
        "response_bytes_per_get": MAX_RESPONSE_BYTES_PER_GET,
        "aggregate_response_bytes": MAX_AGGREGATE_RESPONSE_BYTES,
        "private_observation_files": source["private_observation_files"],
        "private_observation_bytes_per_file": source["private_observation_bytes_per_file"],
        "private_observation_aggregate_bytes": source["private_observation_aggregate_bytes"],
        "observer_events": MAX_OBSERVER_EVENTS,
        "observer_event_bytes": MAX_OBSERVER_EVENT_BYTES,
        "observer_journal_bytes": MAX_OBSERVER_JOURNAL_BYTES,
        "observer_total_wall_seconds": MAX_OBSERVER_WALL_SECONDS,
        "observer_active_seconds": source["observer_active_seconds"],
        "observer_prelaunch_seconds": source["observer_prelaunch_seconds"],
        "observer_post_provider_cleanup_seconds": source["observer_post_provider_cleanup_seconds"],
        "observer_archive_seconds": source["observer_archive_seconds"],
        "observer_request_seconds": source["observer_request_seconds"],
        "provider_hard_wall_seconds": MAX_PROVIDER_WALL_SECONDS,
        "provider_cost_usd": MAX_PROVIDER_COST_CENTS / 100,
        "normal_termination_click_seconds": source["normal_termination_click_seconds"],
        "launch_to_active_seconds": source["launch_to_active_seconds"],
        "cloud_ide_availability_seconds": source["cloud_ide_availability_seconds"],
        "qualification_command_seconds": source["qualification_command_seconds"],
        "evidence_download_validation_seconds": source["evidence_download_validation_seconds"],
        "termination_verification_seconds": source["termination_verification_seconds"],
        "firewall_cleanup_seconds": source["firewall_cleanup_seconds"],
        "incident_headroom_seconds": source["incident_headroom_seconds"],
        "normal_modeled_list_cost_cents": source["normal_modeled_list_cost_cents"],
        "hard_wall_modeled_list_cost_cents": source["hard_wall_modeled_list_cost_cents"],
        "checkpoint_window_seconds": MAX_USER_CHECKPOINT_SECONDS,
        "launch_clicks": 1,
        "normal_instance_count": 1,
        "persistent_filesystem_count": 0,
        "automated_cloud_mutations": 0,
        "automatic_retries": 0,
        "pagination_requests": 0,
        "redirect_follows": 0,
        "ssh_operations": 0,
        "model_calls": 0,
        "model_tokens": 0,
        "browser_automation_actions": 0,
        "sira_executions": 0,
        "local_process_calls": MAX_LOCAL_PROCESS_CALLS,
        "local_process_output_bytes": MAX_LOCAL_PROCESS_OUTPUT_BYTES,
        "qualification_archive_bytes": MAX_QUALIFICATION_ARCHIVE_BYTES,
        "qualification_unpacked_bytes": MAX_QUALIFICATION_UNPACKED_BYTES,
        "qualification_files": MAX_QUALIFICATION_FILES,
        "remote_source_bytes_per_evidence_set": source["remote_source_bytes_per_evidence_set"],
        "remote_archive_bytes_per_evidence_set": source["remote_archive_bytes_per_evidence_set"],
        "remote_source_retained_bytes": source["remote_source_retained_bytes"],
        "remote_archive_retained_bytes": source["remote_archive_retained_bytes"],
        "remote_aggregate_retained_bytes": source["remote_aggregate_retained_bytes"],
        "local_source_evidence_bytes": source["local_source_evidence_bytes"],
        "local_sealed_evidence_bytes": source["local_sealed_evidence_bytes"],
        "mac_active_evidence_bytes": MAX_MAC_ACTIVE_EVIDENCE_BYTES,
        "external_archive_bytes": MAX_EXTERNAL_ARCHIVE_BYTES,
        "busybox_layer_bytes": source["busybox_layer_bytes"],
        "phase_get_limits": {
            phase.value: count for phase, count in OBSERVER_PHASE_GET_LIMITS.items()
        },
    }
    caps.update(_qualification_runtime_caps(repository_root))
    return caps


def qualification_bootstrap_template(repository_root: Path) -> list[str]:
    """Return the exact hash-first argv shape with private/runtime values unresolved."""

    path = repository_root / "containers/sira-smoke/lambda/manual-console/qualification_driver.py"
    namespace = runpy.run_path(str(path))
    renderer = namespace.get("qualification_bootstrap_arguments")
    if not callable(renderer):
        raise L23ContractError("qualification bootstrap renderer is unavailable")
    arguments = [
        "--run-id",
        RUN_ID,
        "--decision-alias",
        "<PRIVATE-DECISION-ALIAS>",
        "--marker-alias",
        "<PRIVATE-MARKER-ALIAS>",
        "--instance-binding-sha256",
        "<PRIVATE-INSTANCE-BINDING-SHA256>",
        "--authorization-reference",
        "<FRESH-AUTHORIZATION-REFERENCE>",
        "--authorization-sha256",
        "<FRESH-AUTHORIZATION-SHA256>",
        "--bundle-manifest-sha256",
        BUNDLE_MANIFEST_SHA256,
        "--output-dir",
        "/home/ubuntu/t07-l2m-output-0001",
    ]
    rendered = renderer(
        python_executable="/usr/bin/python3",
        driver_path=Path("/home/ubuntu/t07-l2m-bundle/qualification_driver.py"),
        expected_driver_sha256=QUALIFICATION_DRIVER_SHA256,
        driver_arguments=arguments,
    )
    if not isinstance(rendered, list) or any(not isinstance(value, str) for value in rendered):
        raise L23ContractError("qualification bootstrap renderer returned an unsafe value")
    return rendered


def _hash_artifacts(repository_root: Path, paths: Sequence[Path]) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for relative in paths:
        encoded = _read_regular_no_follow(
            repository_root / relative,
            max_bytes=4_194_304,
            require_owner=False,
        )
        result.append(
            {"path": str(relative), "bytes": len(encoded), "sha256": sha256_bytes(encoded)}
        )
    return result


def _implementation_artifact_paths() -> tuple[Path, ...]:
    return (
        Path("src/giclab/harness/lambda_l23_manual_plan.py"),
        Path("src/giclab/harness/lambda_l23_manual_supervisor.py"),
        Path("src/giclab/harness/lambda_l2m_checkpoints.py"),
        Path("src/giclab/harness/lambda_l2m_observer.py"),
        SUPERVISOR_BOOTSTRAP_RELATIVE,
        DECISION_SCHEMA_RELATIVE,
        PRIVATE_SEAL_SCHEMA_RELATIVE,
        CHECKPOINT_SCHEMA_RELATIVE,
        OBSERVER_JOURNAL_SCHEMA_RELATIVE,
        HOST_EVIDENCE_SCHEMA_RELATIVE,
        BUNDLE_MANIFEST_RELATIVE,
        BUNDLE_ROOT_RELATIVE / "qualification_driver.py",
        BUNDLE_ROOT_RELATIVE / "host_facts.py",
        BUNDLE_ROOT_RELATIVE / "docker_inspector.py",
        BUNDLE_ROOT_RELATIVE / "evidence_packager.py",
        BUNDLE_ROOT_RELATIVE / "adversarial-containment.sh",
        BUNDLE_ROOT_RELATIVE / "public-source-observations-l2-2.json",
        CHECKPOINT_TEMPLATE_ROOT_RELATIVE / "README.md",
        *(
            CHECKPOINT_TEMPLATE_ROOT_RELATIVE / f"{ordinal:02d}-{kind}.json"
            for ordinal, kind in enumerate(USER_CHECKPOINT_TYPES, start=1)
        ),
    )


def render_public_plan(
    repository_root: Path,
    *,
    reviewed_implementation_commit: str,
    binding: PrivateBindingSeal,
) -> dict[str, object]:
    """Render the exact public-safe plan.  It remains structurally unauthorized."""

    if not re.fullmatch(r"[a-f0-9]{40}", reviewed_implementation_commit):
        raise L23ContractError("reviewed implementation commit is invalid")
    public_binding = binding.public_binding()
    steps: list[dict[str, object]] = [
        {"ordinal": ordinal, "actor": actor, "action": action}
        for ordinal, (actor, action) in enumerate(MANUAL_STEP_CONTRACT, start=1)
    ]
    checkpoint_files = [
        str(CHECKPOINT_TEMPLATE_ROOT_RELATIVE / f"{ordinal:02d}-{kind}.json")
        for ordinal, kind in enumerate(USER_CHECKPOINT_TYPES, start=1)
    ]
    plan: dict[str, object] = {
        "schema_version": "0.1.0",
        "plan_id": PLAN_ID,
        "run_id": RUN_ID,
        "terminal_decision": TERMINAL_DECISION,
        "authorization": {
            "authorized": False,
            "authorization_reference": AUTHORIZATION_PLACEHOLDER,
            "cloud_mutation_allowed": False,
            "paid_compute_allowed": False,
            "prototype_execution_allowed": False,
            "scientific_interpretation_allowed": False,
        },
        "implementation_binding": {
            "branch": BRANCH,
            "starting_commit": STARTING_COMMIT,
            "l2_2_implementation_commit": L22_IMPLEMENTATION_COMMIT,
            "reviewed_implementation_commit": reviewed_implementation_commit,
            "required_execution_commit": "<EXACT-FINAL-CLEAN-GATE-L2-3-HANDOFF-COMMIT>",
            "artifacts": _hash_artifacts(repository_root, _implementation_artifact_paths()),
        },
        "private_binding": public_binding,
        "provider": {
            "name": "Lambda On-Demand Cloud",
            "api_base_url": "https://cloud.lambda.ai",
            "observer_transport": (
                "giclab.harness.lambda_l2m_observer.LambdaHttpsL2MObserverTransport"
            ),
            "observer_operations": "GET-only",
            "user_console_mutations_only": True,
        },
        "selected_resources": {
            "instance_type": SELECTED_INSTANCE_TYPE,
            "region": SELECTED_REGION,
            "architecture": SELECTED_ARCHITECTURE,
            "image_alias": RECOMMENDED_IMAGE_ALIAS,
            "image_family": REQUIRED_IMAGE_FAMILY,
            "image_version": RECOMMENDED_IMAGE_VERSION,
            "ssh_key_name": SELECTED_SSH_KEY_NAME,
            "ssh_use": False,
            "persistent_filesystem_count": 0,
            "launch_wizard_offeredness_required": True,
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
            "gate_scope": "infrastructure-qualification-only",
        },
        "temporal_contract": {
            "public_metadata_retrieved_at_utc": PUBLIC_METADATA_RETRIEVED_AT_UTC,
            "public_metadata_max_age_seconds": PUBLIC_METADATA_MAX_AGE_SECONDS,
            "prelaunch_and_jupyter_headroom_seconds": (PUBLIC_METADATA_PRELAUNCH_HEADROOM_SECONDS),
            "latest_safe_supervisor_start_utc": PLAN_LATEST_SAFE_START_UTC,
            "expired_plan_requires_new_bundle_plan_and_authorization": True,
        },
        "actors": {
            "user": "console mutations and Jupyter interaction",
            "observer": "read-only Lambda GETs and local validation/sealing",
            "host-bundle": "one deterministic qualification command inside Jupyter",
        },
        "steps": steps,
        "checkpoints": {
            "schema_path": str(CHECKPOINT_SCHEMA_RELATIVE),
            "schema_sha256": CHECKPOINT_SCHEMA_SHA256,
            "count": CHECKPOINT_COUNT,
            "maximum_bytes_each": 16_384,
            "window_seconds": MAX_USER_CHECKPOINT_SECONDS,
            "consumption_ledger_bytes": 262_144,
            "single_use": True,
            "private_nonce_bound": True,
            "templates": checkpoint_files,
        },
        "observer_working_directory_contract": (
            "run with cwd equal to the canonical clean repository root"
        ),
        "observer_invocation": [
            ".venv/bin/python",
            "-I",
            str(SUPERVISOR_BOOTSTRAP_RELATIVE),
            "--repository-root",
            ".",
            "--plan",
            str(PLAN_RELATIVE),
            "--plan-sha256",
            "<EXACT-PLAN-SHA256-FROM-FRESH-AUTHORIZATION>",
            "--expected-commit",
            "<EXACT-FINAL-CLEAN-GATE-L2-3-HANDOFF-COMMIT>",
            "--authorization-reference",
            "<FRESH-AUTHORIZATION-REFERENCE>",
            "--authorization-sha256",
            "<FRESH-AUTHORIZATION-SHA256>",
        ],
        "qualification_bootstrap_argv": qualification_bootstrap_template(repository_root),
        "caps": _public_plan_caps(repository_root),
        "storage": {
            "local_active_root": str(Path("artifacts/t07/lambda/gate-l2m") / RUN_ID),
            "local_inbound_root": str(Path("artifacts/t07/lambda/gate-l2m") / RUN_ID / "inbound"),
            "external_archive_root": str(EXTERNAL_ARCHIVE_ROOT),
            "external_volume_uuid": "8478609D-FA37-4ED5-875D-47AE912B9151",
            "external_physical_store_uuid": "7904A6F1-F483-4ED7-9E34-BFECAB31C63E",
            "held_no_follow_descriptors": True,
            "one_way_copy": True,
            "source_retained": True,
            "internal_fallback": False,
            "mac_prewrite_free_floor_bytes": MIN_LOCAL_PREWRITE_FREE_BYTES,
            "mac_retained_free_floor_bytes": MIN_LOCAL_RETAINED_FREE_BYTES,
            "private_archive_cap_bytes": MAX_PRIVATE_ARCHIVE_BYTES,
        },
        "incident_rules": {
            "no_workload_on_zero_multiple_or_drift": True,
            "no_second_launch_click": True,
            "terminate_all_incident_scope_instances": True,
            "terminal_before_ruleset_delete": True,
            "terminal_and_ruleset_absent_before_global_restore": True,
            "cloud_ide_failure_opens_no_ports_and_uses_no_ssh": True,
            "qualification_or_evidence_failure_never_reruns": True,
            "control_plane_outage_preserves_strict_firewall": True,
            "observer_restart_burns_run_identity": True,
            "archive_unavailable_preserves_local_source": True,
        },
    }
    validate_public_plan(plan, repository_root=repository_root)
    return plan


def validate_public_plan(
    plan: Mapping[str, object],
    *,
    repository_root: Path,
) -> None:
    """Fail closed on authority, sequence, cap, actor, or public-privacy drift."""

    repository_root = repository_root.resolve(strict=True)
    expected_top_level = {
        "schema_version",
        "plan_id",
        "run_id",
        "terminal_decision",
        "authorization",
        "implementation_binding",
        "private_binding",
        "provider",
        "selected_resources",
        "scientific_lock",
        "temporal_contract",
        "actors",
        "steps",
        "checkpoints",
        "observer_working_directory_contract",
        "observer_invocation",
        "qualification_bootstrap_argv",
        "caps",
        "storage",
        "incident_rules",
    }
    if (
        set(plan) != expected_top_level
        or plan.get("schema_version") != "0.1.0"
        or plan.get("plan_id") != PLAN_ID
        or plan.get("run_id") != RUN_ID
        or plan.get("terminal_decision") != TERMINAL_DECISION
    ):
        raise L23ContractError("public plan identity drifted")
    authorization = _mapping(plan.get("authorization"), context="plan authorization")
    if authorization != {
        "authorized": False,
        "authorization_reference": AUTHORIZATION_PLACEHOLDER,
        "cloud_mutation_allowed": False,
        "paid_compute_allowed": False,
        "prototype_execution_allowed": False,
        "scientific_interpretation_allowed": False,
    }:
        raise L23ContractError("public plan authority is not exactly false and pending")
    implementation = _mapping(plan.get("implementation_binding"), context="implementation binding")
    reviewed_commit = implementation.get("reviewed_implementation_commit")
    if (
        set(implementation)
        != {
            "branch",
            "starting_commit",
            "l2_2_implementation_commit",
            "reviewed_implementation_commit",
            "required_execution_commit",
            "artifacts",
        }
        or implementation.get("branch") != BRANCH
        or implementation.get("starting_commit") != STARTING_COMMIT
        or implementation.get("l2_2_implementation_commit") != L22_IMPLEMENTATION_COMMIT
        or not isinstance(reviewed_commit, str)
        or re.fullmatch(r"[a-f0-9]{40}", reviewed_commit) is None
        or implementation.get("required_execution_commit")
        != "<EXACT-FINAL-CLEAN-GATE-L2-3-HANDOFF-COMMIT>"
    ):
        raise L23ContractError("public plan implementation binding drifted")
    artifacts = [
        _mapping(value, context="implementation artifact")
        for value in _sequence(implementation.get("artifacts"), context="implementation artifacts")
    ]
    expected_artifacts = _hash_artifacts(repository_root, _implementation_artifact_paths())
    if [dict(value) for value in artifacts] != expected_artifacts:
        raise L23ContractError("public plan implementation artifact binding drifted")
    private_binding = _mapping(plan.get("private_binding"), context="private binding")
    private_hash_fields = {
        "decision_source_sha256",
        "decision_canonical_sha256",
        "decision_seal_sha256",
        "private_parameters_sha256",
        "bundle_seal_sha256",
        "external_seal_sha256",
        "external_copy_record_sha256",
    }
    if (
        set(private_binding)
        != {
            "state",
            "decision_alias",
            *private_hash_fields,
            "marker_alias",
            "archive_alias",
            "source_retained",
            "destination_hashes_verified",
            "private_values_in_public_plan",
        }
        or private_binding.get("state") != "ignored-sealed-local-and-external-evidence"
        or not isinstance(private_binding.get("decision_alias"), str)
        or re.fullmatch(r"l2m-decision-[a-f0-9]{12}", str(private_binding["decision_alias"]))
        is None
        or not isinstance(private_binding.get("marker_alias"), str)
        or re.fullmatch(r"l2m-marker-[a-f0-9]{12}", str(private_binding["marker_alias"])) is None
        or not isinstance(private_binding.get("archive_alias"), str)
        or re.fullmatch(r"l2m-archive-[a-f0-9]{12}", str(private_binding["archive_alias"])) is None
        or any(
            not isinstance(private_binding.get(name), str)
            or _HEX64.fullmatch(str(private_binding[name])) is None
            for name in private_hash_fields
        )
        or private_binding.get("source_retained") is not True
        or private_binding.get("destination_hashes_verified") is not True
        or private_binding.get("private_values_in_public_plan") is not False
    ):
        raise L23ContractError("public plan private seal binding drifted")
    steps = [
        _mapping(value, context="manual plan step")
        for value in _sequence(plan.get("steps"), context="steps")
    ]
    expected_steps = [
        {"ordinal": ordinal, "actor": actor, "action": action}
        for ordinal, (actor, action) in enumerate(MANUAL_STEP_CONTRACT, start=1)
    ]
    if [dict(value) for value in steps] != expected_steps:
        raise L23ContractError("manual plan does not contain the exact 23-step order")
    provider = _mapping(plan.get("provider"), context="provider")
    if provider != {
        "name": "Lambda On-Demand Cloud",
        "api_base_url": "https://cloud.lambda.ai",
        "observer_transport": (
            "giclab.harness.lambda_l2m_observer.LambdaHttpsL2MObserverTransport"
        ),
        "observer_operations": "GET-only",
        "user_console_mutations_only": True,
    }:
        raise L23ContractError("manual plan provider or actor boundary drifted")
    selected = _mapping(plan.get("selected_resources"), context="selected resources")
    if selected != {
        "instance_type": SELECTED_INSTANCE_TYPE,
        "region": SELECTED_REGION,
        "architecture": SELECTED_ARCHITECTURE,
        "image_alias": RECOMMENDED_IMAGE_ALIAS,
        "image_family": REQUIRED_IMAGE_FAMILY,
        "image_version": RECOMMENDED_IMAGE_VERSION,
        "ssh_key_name": SELECTED_SSH_KEY_NAME,
        "ssh_use": False,
        "persistent_filesystem_count": 0,
        "launch_wizard_offeredness_required": True,
    }:
        raise L23ContractError("manual plan selected resource contract drifted")
    scientific = _mapping(plan.get("scientific_lock"), context="scientific lock")
    if scientific != {
        "experiment": "EXP-0001",
        "profile": "PLAN-EXP0001-SMOKE",
        "condition_order": ["SIRA-REACTIVE", "SIRA-SIMULATIVE"],
        "pair": "PAIR-EXP0001-SMOKE-0000",
        "model": "gpt-4o-2024-11-20",
        "reproduction_level": "directional reproduction",
        "interpretation_allowed": False,
        "pilot_authorized": False,
        "training": False,
        "gate_scope": "infrastructure-qualification-only",
    }:
        raise L23ContractError("manual plan scientific lock drifted")
    if _mapping(plan.get("temporal_contract"), context="temporal contract") != {
        "public_metadata_retrieved_at_utc": PUBLIC_METADATA_RETRIEVED_AT_UTC,
        "public_metadata_max_age_seconds": PUBLIC_METADATA_MAX_AGE_SECONDS,
        "prelaunch_and_jupyter_headroom_seconds": PUBLIC_METADATA_PRELAUNCH_HEADROOM_SECONDS,
        "latest_safe_supervisor_start_utc": PLAN_LATEST_SAFE_START_UTC,
        "expired_plan_requires_new_bundle_plan_and_authorization": True,
    }:
        raise L23ContractError("manual plan temporal contract drifted")
    actors = _mapping(plan.get("actors"), context="actors")
    if actors != {
        "user": "console mutations and Jupyter interaction",
        "observer": "read-only Lambda GETs and local validation/sealing",
        "host-bundle": "one deterministic qualification command inside Jupyter",
    }:
        raise L23ContractError("manual plan actor responsibilities drifted")
    caps = _mapping(plan.get("caps"), context="plan caps")
    if dict(caps) != _public_plan_caps(repository_root):
        raise L23ContractError("manual plan cap drifted")
    checkpoints = _mapping(plan.get("checkpoints"), context="checkpoints")
    if (
        set(checkpoints)
        != {
            "schema_path",
            "schema_sha256",
            "count",
            "maximum_bytes_each",
            "window_seconds",
            "consumption_ledger_bytes",
            "single_use",
            "private_nonce_bound",
            "templates",
        }
        or checkpoints.get("schema_path") != str(CHECKPOINT_SCHEMA_RELATIVE)
        or checkpoints.get("schema_sha256") != CHECKPOINT_SCHEMA_SHA256
        or checkpoints.get("count") != CHECKPOINT_COUNT
        or checkpoints.get("maximum_bytes_each") != 16_384
        or checkpoints.get("window_seconds") != MAX_USER_CHECKPOINT_SECONDS
        or checkpoints.get("consumption_ledger_bytes") != 262_144
        or checkpoints.get("single_use") is not True
        or checkpoints.get("private_nonce_bound") is not True
        or checkpoints.get("templates")
        != [
            str(CHECKPOINT_TEMPLATE_ROOT_RELATIVE / f"{ordinal:02d}-{kind}.json")
            for ordinal, kind in enumerate(USER_CHECKPOINT_TYPES, start=1)
        ]
    ):
        raise L23ContractError("manual plan checkpoint contract drifted")
    storage = _mapping(plan.get("storage"), context="storage")
    if (
        set(storage)
        != {
            "local_active_root",
            "local_inbound_root",
            "external_archive_root",
            "external_volume_uuid",
            "external_physical_store_uuid",
            "held_no_follow_descriptors",
            "one_way_copy",
            "source_retained",
            "internal_fallback",
            "mac_prewrite_free_floor_bytes",
            "mac_retained_free_floor_bytes",
            "private_archive_cap_bytes",
        }
        or storage.get("local_active_root") != str(Path("artifacts/t07/lambda/gate-l2m") / RUN_ID)
        or storage.get("local_inbound_root")
        != str(Path("artifacts/t07/lambda/gate-l2m") / RUN_ID / "inbound")
        or storage.get("external_archive_root") != str(EXTERNAL_ARCHIVE_ROOT)
        or storage.get("external_volume_uuid") != "8478609D-FA37-4ED5-875D-47AE912B9151"
        or storage.get("external_physical_store_uuid") != "7904A6F1-F483-4ED7-9E34-BFECAB31C63E"
        or storage.get("held_no_follow_descriptors") is not True
        or storage.get("one_way_copy") is not True
        or storage.get("source_retained") is not True
        or storage.get("internal_fallback") is not False
        or storage.get("mac_prewrite_free_floor_bytes") != MIN_LOCAL_PREWRITE_FREE_BYTES
        or storage.get("mac_retained_free_floor_bytes") != MIN_LOCAL_RETAINED_FREE_BYTES
        or storage.get("private_archive_cap_bytes") != MAX_PRIVATE_ARCHIVE_BYTES
    ):
        raise L23ContractError("manual plan storage contract drifted")
    incident = _mapping(plan.get("incident_rules"), context="incident rules")
    if incident != {
        "no_workload_on_zero_multiple_or_drift": True,
        "no_second_launch_click": True,
        "terminate_all_incident_scope_instances": True,
        "terminal_before_ruleset_delete": True,
        "terminal_and_ruleset_absent_before_global_restore": True,
        "cloud_ide_failure_opens_no_ports_and_uses_no_ssh": True,
        "qualification_or_evidence_failure_never_reruns": True,
        "control_plane_outage_preserves_strict_firewall": True,
        "observer_restart_burns_run_identity": True,
        "archive_unavailable_preserves_local_source": True,
    }:
        raise L23ContractError("manual plan incident contract drifted")
    invocation = [
        _nonempty(value, context="observer invocation argument")
        for value in _sequence(plan.get("observer_invocation"), context="observer invocation")
    ]
    if plan.get(
        "observer_working_directory_contract"
    ) != "run with cwd equal to the canonical clean repository root" or invocation != [
        ".venv/bin/python",
        "-I",
        str(SUPERVISOR_BOOTSTRAP_RELATIVE),
        "--repository-root",
        ".",
        "--plan",
        str(PLAN_RELATIVE),
        "--plan-sha256",
        "<EXACT-PLAN-SHA256-FROM-FRESH-AUTHORIZATION>",
        "--expected-commit",
        "<EXACT-FINAL-CLEAN-GATE-L2-3-HANDOFF-COMMIT>",
        "--authorization-reference",
        "<FRESH-AUTHORIZATION-REFERENCE>",
        "--authorization-sha256",
        "<FRESH-AUTHORIZATION-SHA256>",
    ]:
        raise L23ContractError("manual plan observer invocation drifted")
    qualification = [
        _nonempty(value, context="qualification bootstrap argument")
        for value in _sequence(
            plan.get("qualification_bootstrap_argv"), context="qualification bootstrap argv"
        )
    ]
    if qualification != qualification_bootstrap_template(repository_root):
        raise L23ContractError("manual plan qualification bootstrap is not hash-first")
    public = canonical_bytes(plan).decode()
    if any(pattern.search(public) for pattern in _PRIVATE_PUBLIC_PATTERNS):
        raise L23ContractError("public plan contains a prohibited private value shape")
    if any(value in public for value in ("raw_image_id", "raw_ssh_key_id", "source_ipv4_cidr")):
        raise L23ContractError("public plan names a prohibited private binding field")
