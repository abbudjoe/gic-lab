"""Offline Gate L1.3 resource-identity and Gate L2 security controls.

This module is deliberately network inert. It consumes an already sealed, redacted
Lambda inventory, projects provider image IDs to inventory-local opaque aliases,
derives the fixed Gate L0 candidate matrix, inspects public SSH key files only, and
models firewall/host-key decisions that remain human gated.

The historical Gate L1 V3 plan-bound implementation stays byte-frozen. This
supplemental verifier repairs post-run typed consumption without rewriting the V3
plan, run ledger, inventory, archive, or seal.
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
from collections import Counter, defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from enum import StrEnum
from pathlib import Path
from typing import Final

from .lambda_archive import _open_directory_no_symlinks, _read_regular_at
from .lambda_archive_v3 import (
    ARCHIVE_ACTION_ID_V3,
    COPY_RECORD_NAME,
    EXTERNAL_RECORD_FIELDS,
    INVENTORY_ARCHIVE_NAME,
    LEDGER_ARCHIVE_NAME,
    LOCAL_RECORD_FIELDS,
    SEAL_NAME,
    _strict_object,
    _validate_inventory_request_provenance,
)
from .lambda_cloud import (
    FIREWALL_UNENFORCED_REGIONS,
    MAX_PRICE_CENTS_PER_HOUR,
    MAX_PROVIDER_COMPUTE_CENTS,
    MAX_QUALIFICATION_WALL_SECONDS,
    QUALIFICATION_IMAGE_FAMILY,
    LambdaCloudContractError,
    qualification_list_price_cap_cents,
)
from .lambda_cloud_v3 import schema_extension_report_bytes
from .lambda_inventory_plan_v3 import (
    InventoryRunBindingV3,
    ReadOnlyInventoryPlanV3,
    inventory_ledger_contract_document_v3,
    inventory_limits_document_v3,
    verify_inventory_implementation_v3,
    verify_repository_commit_ancestry_v3,
)
from .lambda_request_ledger_v3 import (
    load_request_ledger_validator,
    validate_request_ledger_bytes,
)
from .sira_storage import (
    APPROVED_MOUNT,
    APPROVED_PHYSICAL_STORE_UUID,
    APPROVED_VOLUME_UUID,
)

RUN_ID: Final = "RUN-T07-L1-LAMBDA-INVENTORY-0003"
INVENTORY_SHA256: Final = "022835438165e7e6e70dc992d6904f4e8b9448dc933d1d4c3e39ebdcc8914933"
LEDGER_SHA256: Final = "1f94068bdb1d1d2af0075d50c1a0c06eb1c077d4128f90bdc16fd571fa6af707"
SEAL_SHA256: Final = "3347b8d03d0f937111de92ef79286c7fbcb02027f652f35ba42ac337cf8f7bd5"
COPY_RECORD_SHA256: Final = "76d8511282962cb6fdc4f72a63eaf41e7e63239acb9fa38e030f51057cb8a0e7"
LOCAL_COPY_RECORD_SHA256: Final = "65068ff4884880ac8e6568652c0aba089e39c8fea621c4544e4da46edd01a5a8"
PLAN_SHA256: Final = "b5ec82aaa84882a7c3269ebdb695a6c694f891d66d367c05f82eaf9797515331"
EXECUTION_COMMIT: Final = "42f74481e5a500cacb4973c6b29da4c3470679fe"
IMPLEMENTATION_COMMIT: Final = "718c75c694b3033fa7ef2ed5e7c4696fd8c389f3"
AUTHORIZATION_REFERENCE: Final = "AUTH-T07-GATE-L1-LAMBDA-INPROCESS-V4-2026-08-10"
AUTHORIZATION_SHA256: Final = "7246784915f376d503bab7b63acfc8d48e9c82993be394aa22dacd036a4c7195"
POSTRUN_ADJUDICATION_SHA256: Final = (
    "23ae723811cb15b2cbc1229592d507624c9107851fc883d9ce023464301631d0"
)
SCHEMA_EXTENSION_REPORT_SHA256: Final = (
    "20f035039e633e5ef81c544f439b8fac6dc08ee4dafce1eacd2646df0e3a9263"
)
SCHEMA_EXTENSION_REPORT_BYTES: Final = 1_863
OPENAPI_VERSION: Final = "1.10.0"
OPENAPI_SHA256: Final = "365488015cf79fda38e1268f44a9e2d4af4fe2794ad3c6878c78a7e1f98caded"
IMAGE_ALIAS_PATTERN: Final = re.compile(r"^img-[0-9]{4}$")
IMAGE_REQUIRED_FIELDS: Final = frozenset(
    {"id", "name", "family", "version", "architecture", "region"}
)
IMAGE_INTRINSIC_FIELDS: Final = ("name", "family", "version", "architecture")
MAX_PUBLIC_KEY_BYTES: Final = 64 * 1024
MAX_ALIAS_MAP_BYTES: Final = 64 * 1024
MAX_ALIAS_MAP_SEAL_BYTES: Final = 4 * 1024
MAX_FIREWALL_EVIDENCE_BYTES: Final = 64 * 1024
MAX_FIREWALL_SEAL_BYTES: Final = 4 * 1024
PUBLIC_IPV4_PLACEHOLDER: Final = "<USER_APPROVED_PUBLIC_IPV4/32>"
ALIAS_MAP_RELATIVE_ROOT: Final = Path(
    "artifacts/t07/lambda/gate-l1-3/RUN-T07-L1-LAMBDA-INVENTORY-0003"
)
FIREWALL_SNAPSHOT_RUN_PATTERN: Final = re.compile(r"^RUN-T07-L2-LAMBDA-QUALIFICATION-[0-9]{4}$")


class L13ContractError(LambdaCloudContractError):
    """An offline Gate L1.3 evidence or decision contract is unsafe."""


class ImageDefectClassification(StrEnum):
    VERIFIER_KEY_BUG = "verifier_key_bug"
    EXACT_DUPLICATE_ROWS = "exact_duplicate_api_rows"
    REDACTION_COLLISION = "distinct_raw_ids_collapsed_to_same_redacted_placeholder"
    CONFLICTING_METADATA = "same_raw_id_conflicting_metadata"
    FAMILY_NAME_NOT_ID = "duplicate_family_name_not_duplicate_id"


class SSHMatchState(StrEnum):
    UNIQUE_MATCH = "unique_match"
    NO_MATCH = "no_match"
    MULTIPLE_MATCHES = "multiple_matches"
    EVIDENCE_UNAVAILABLE = "evidence_unavailable"


class FirewallSourceScope(StrEnum):
    ANY_IPV4 = "any-ipv4"
    SINGLE_IPV4 = "single-ipv4"
    RESTRICTED_CIDR = "restricted-cidr"


class FirewallDescriptionClass(StrEnum):
    SSH = "ssh"
    HTTP = "http"
    HTTPS = "https"
    ICMP = "icmp"
    ALL_PROTOCOL = "all-protocol"
    CUSTOM_NETWORK = "custom-network"


class FirewallReplacementPhase(StrEnum):
    PRECONDITIONS_PENDING = "preconditions-pending"
    PRECONDITIONS_VERIFIED = "preconditions-verified"
    ORIGINAL_SNAPSHOT_SEALED = "original-snapshot-sealed"
    REPLACEMENT_PENDING = "replacement-pending"
    STRICT_REPLACEMENT_VERIFIED = "strict-replacement-verified"
    INSTANCE_ACTIVE = "instance-active"
    INSTANCE_TERMINATION_REQUIRED = "instance-termination-required"
    RESTORE_REQUIRED = "restore-required"
    RESTORE_PENDING = "restore-pending"
    CLOSED = "closed"
    INCIDENT = "incident"


class FirewallReplacementEvent(StrEnum):
    PRECONDITIONS_VERIFIED = "preconditions-verified"
    ORIGINAL_SNAPSHOT_SEALED = "original-snapshot-sealed"
    REPLACEMENT_REQUESTED = "replacement-requested"
    REPLACEMENT_VERIFIED = "replacement-verified"
    INSTANCE_LAUNCHED = "instance-launched"
    QUALIFICATION_FINISHED = "qualification-finished"
    INSTANCE_TERMINATED = "instance-terminated"
    FAILURE_AFTER_MUTATION = "failure-after-mutation"
    RESTORE_REQUESTED = "restore-requested"
    RESTORE_VERIFIED = "restore-verified"
    RESTORE_FAILED = "restore-failed"


@dataclass(frozen=True, slots=True)
class ImageAvailability:
    region_name: str
    multiplicity: int
    source_indices: tuple[int, ...]

    def public_document(self) -> dict[str, object]:
        return {
            "region_name": self.region_name,
            "multiplicity": self.multiplicity,
            "source_indices": list(self.source_indices),
        }


@dataclass(frozen=True, slots=True)
class ProjectedImage:
    alias: str
    name: str
    family: str
    version: str
    architecture: str
    availability: tuple[ImageAvailability, ...]

    def public_document(self) -> dict[str, object]:
        return {
            "alias": self.alias,
            "name": self.name,
            "family": self.family,
            "version": self.version,
            "architecture": self.architecture,
            "availability": [item.public_document() for item in self.availability],
        }


@dataclass(frozen=True, slots=True)
class ImageProjection:
    images: tuple[ProjectedImage, ...]
    alias_by_raw_id: Mapping[str, str]
    raw_row_count: int
    unique_raw_id_count: int
    region_availability_group_count: int
    exact_duplicate_group_count: int
    exact_duplicate_extra_rows: int
    family_name_groups_with_distinct_ids: int

    def public_images(self) -> list[dict[str, object]]:
        return [image.public_document() for image in self.images]


@dataclass(frozen=True, slots=True)
class AliasMapSeal:
    map_path: Path
    map_bytes: int
    map_sha256: str
    seal_path: Path
    seal_bytes: int
    seal_sha256: str
    alias_count: int

    def public_document(self, *, repository_root: Path) -> dict[str, object]:
        return {
            "state": "ignored-sealed-local-evidence",
            "path": str(self.map_path.relative_to(repository_root)),
            "bytes": self.map_bytes,
            "sha256": self.map_sha256,
            "seal_path": str(self.seal_path.relative_to(repository_root)),
            "seal_bytes": self.seal_bytes,
            "seal_sha256": self.seal_sha256,
            "alias_count": self.alias_count,
            "raw_ids_committed": False,
            "raw_id_hashes_committed": False,
        }


@dataclass(frozen=True, slots=True)
class GateL2EvidenceValidationL13:
    """Authoritative, non-authorizing result for the immutable Gate L1 evidence."""

    evidence_valid: bool
    decision_state: str
    historical_selection_state: str
    qualifying_candidate_count: int
    inventory_sha256: str
    ledger_sha256: str
    archive_seal_sha256: str
    external_copy_record_sha256: str
    local_copy_record_sha256: str
    extension_report_sha256: str
    alias_map_sha256: str
    alias_map_seal_sha256: str


@dataclass(frozen=True, slots=True)
class FirewallPreconditionsEvidence:
    """Fresh account-wide and human preconditions for a future global mutation."""

    running_instance_count_account_wide: int
    workspace_dependency_attested: bool
    approved_public_ipv4_cidr: str = field(repr=False)
    observation_sha256: str


@dataclass(frozen=True, slots=True)
class FirewallRulesSnapshot:
    """Exact response bytes plus a normalized rules identity."""

    response_bytes: bytes = field(repr=False)
    response_sha256: str
    normalized_rules_bytes: bytes = field(repr=False)
    normalized_rules_sha256: str
    rule_count: int


@dataclass(frozen=True, slots=True)
class SealedFirewallRulesSnapshot:
    """Durable readback identity for the exact pre-mutation snapshot seal."""

    repository_root: Path = field(repr=False)
    run_id: str
    snapshot: FirewallRulesSnapshot = field(repr=False)
    snapshot_artifact_relative_path: str
    snapshot_artifact_bytes: int
    snapshot_artifact_sha256: str
    snapshot_post_fsync_readback_sha256: str
    seal_relative_path: str
    seal_bytes: int
    seal_sha256: str
    post_fsync_readback_sha256: str
    directory_fsync_completed: bool


@dataclass(frozen=True, slots=True)
class FirewallReplacementRequest:
    """Exact strict PATCH body, retained privately."""

    request_body_bytes: bytes = field(repr=False)
    request_body_sha256: str
    approved_public_ipv4_cidr: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class FirewallInstanceIdentity:
    instance_id: str = field(repr=False)
    launch_evidence_sha256: str


@dataclass(frozen=True, slots=True)
class FirewallInstanceTerminalEvidence:
    instance_id: str = field(repr=False)
    terminal_state: str
    terminal_evidence_sha256: str


@dataclass(frozen=True, slots=True)
class FirewallReplacementState:
    """Typed future lifecycle; no method in this module performs a mutation."""

    phase: FirewallReplacementPhase = FirewallReplacementPhase.PRECONDITIONS_PENDING
    preconditions: FirewallPreconditionsEvidence | None = field(default=None, repr=False)
    original_snapshot: SealedFirewallRulesSnapshot | None = field(default=None, repr=False)
    replacement_request: FirewallReplacementRequest | None = field(default=None, repr=False)
    replacement_observation: FirewallRulesSnapshot | None = field(default=None, repr=False)
    instance: FirewallInstanceIdentity | None = field(default=None, repr=False)
    terminal_instance: FirewallInstanceTerminalEvidence | None = field(default=None, repr=False)


@dataclass(frozen=True, slots=True)
class LocalPublicKey:
    display_path: str
    algorithm: str
    fingerprint: str
    mode: str
    owner_class: str
    same_stem_private_file_present: bool

    def public_document(self) -> dict[str, object]:
        return {
            "path": self.display_path,
            "algorithm": self.algorithm,
            "fingerprint": self.fingerprint,
            "mode": self.mode,
            "owner_class": self.owner_class,
            "same_stem_private_file_present": self.same_stem_private_file_present,
            "private_key_bytes_accessed": False,
        }


@dataclass(frozen=True, slots=True)
class AccountSSHKeyMaterial:
    name: str
    public_key: str | None


@dataclass(frozen=True, slots=True)
class SanitizedFirewallRule:
    ordinal: int
    protocol: str
    port_range: tuple[int, int] | None
    source_scope_class: FirewallSourceScope
    source_is_public_ipv4: bool
    description_classification: FirewallDescriptionClass
    is_ssh_rule: bool
    is_non_ssh_exposure: bool

    def public_document(self) -> dict[str, object]:
        return {
            "ordinal": self.ordinal,
            "protocol": self.protocol,
            "port_range": list(self.port_range) if self.port_range is not None else None,
            "source_scope_class": self.source_scope_class.value,
            "description_classification": self.description_classification.value,
            "is_ssh_rule": self.is_ssh_rule,
            "is_non_ssh_exposure": self.is_non_ssh_exposure,
        }


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _mapping(value: object, *, context: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or any(not isinstance(key, str) for key in value):
        raise L13ContractError(f"{context} must be an object")
    return value


def _sequence(value: object, *, context: str) -> Sequence[object]:
    if not isinstance(value, list):
        raise L13ContractError(f"{context} must be an array")
    return value


def _string(value: object, *, context: str) -> str:
    if not isinstance(value, str) or not value:
        raise L13ContractError(f"{context} must be a nonempty string")
    return value


def _integer(value: object, *, context: str) -> int:
    if type(value) is not int or value < 0:
        raise L13ContractError(f"{context} must be a nonnegative integer")
    return value


def project_image_identities(raw_rows: Sequence[object]) -> ImageProjection:
    """Project official ``Image.id`` values to stable inventory-local aliases.

    Aliases are assigned by sorted raw-ID order, so their order preserves the frozen
    Gate L0 final tie-break without publishing an ID or an ID-derived hash. Region is
    modeled as an availability relation. All other official required image fields are
    intrinsic and must be identical for every occurrence of one raw ID.
    """

    grouped: dict[str, list[tuple[int, Mapping[str, object]]]] = defaultdict(list)
    for index, raw in enumerate(raw_rows, start=1):
        row = _mapping(raw, context="image row")
        if not IMAGE_REQUIRED_FIELDS.issubset(row):
            raise L13ContractError("image row is missing an official required field")
        raw_id = _string(row.get("id"), context="image ID")
        grouped[raw_id].append((index, row))
    if not grouped:
        raise L13ContractError("image inventory is empty")

    alias_by_raw_id = {
        raw_id: f"img-{ordinal:04d}" for ordinal, raw_id in enumerate(sorted(grouped), start=1)
    }
    projected: list[ProjectedImage] = []
    region_availability_groups = 0
    exact_duplicate_groups = 0
    exact_duplicate_extra_rows = 0
    family_name_ids: dict[tuple[str, str], set[str]] = defaultdict(set)

    for raw_id in sorted(grouped):
        entries = grouped[raw_id]
        intrinsic_values: set[tuple[str, str, str, str]] = set()
        availability_indices: dict[str, list[int]] = defaultdict(list)
        for source_index, row in entries:
            intrinsic = (
                _string(row.get("name"), context="image name"),
                _string(row.get("family"), context="image family"),
                _string(row.get("version"), context="image version"),
                _string(row.get("architecture"), context="image architecture"),
            )
            intrinsic_values.add(intrinsic)
            region = _mapping(row.get("region"), context="image region")
            region_name = _string(region.get("name"), context="image region name")
            availability_indices[region_name].append(source_index)
        if len(intrinsic_values) != 1:
            raise L13ContractError("one official image ID has conflicting intrinsic metadata")
        name, family, version, architecture = next(iter(intrinsic_values))
        family_name_ids[(family, name)].add(raw_id)
        if len(availability_indices) > 1:
            region_availability_groups += 1
        availability: list[ImageAvailability] = []
        for region_name in sorted(availability_indices):
            indices = tuple(availability_indices[region_name])
            if len(indices) > 1:
                exact_duplicate_groups += 1
                exact_duplicate_extra_rows += len(indices) - 1
            availability.append(
                ImageAvailability(
                    region_name=region_name,
                    multiplicity=len(indices),
                    source_indices=indices,
                )
            )
        projected.append(
            ProjectedImage(
                alias=alias_by_raw_id[raw_id],
                name=name,
                family=family,
                version=version,
                architecture=architecture,
                availability=tuple(availability),
            )
        )

    return ImageProjection(
        images=tuple(projected),
        alias_by_raw_id=alias_by_raw_id,
        raw_row_count=len(raw_rows),
        unique_raw_id_count=len(grouped),
        region_availability_group_count=region_availability_groups,
        exact_duplicate_group_count=exact_duplicate_groups,
        exact_duplicate_extra_rows=exact_duplicate_extra_rows,
        family_name_groups_with_distinct_ids=sum(
            1 for raw_ids in family_name_ids.values() if len(raw_ids) > 1
        ),
    )


def image_identity_adjudication_document(
    projection: ImageProjection,
    *,
    alias_map_seal: AliasMapSeal,
    repository_root: Path,
) -> dict[str, object]:
    """Build the public structural adjudication without raw IDs or their hashes."""

    multiplicities = Counter(
        sum(item.multiplicity for item in image.availability) for image in projection.images
    )
    return {
        "schema_version": "0.1.0",
        "run_id": RUN_ID,
        "source_inventory_sha256": INVENTORY_SHA256,
        "raw_images_response_state": "not-retained",
        "defect_classification": ImageDefectClassification.VERIFIER_KEY_BUG.value,
        "official_uniqueness_key": "Image.id",
        "official_availability_field": "Image.region",
        "intrinsic_identity_fields": list(IMAGE_INTRINSIC_FIELDS),
        "raw_row_count": projection.raw_row_count,
        "unique_raw_id_count": projection.unique_raw_id_count,
        "alias_count": len(projection.images),
        "multiplicity_distribution": {
            str(key): value for key, value in sorted(multiplicities.items())
        },
        "region_availability_group_count": projection.region_availability_group_count,
        "exact_duplicate_group_count": projection.exact_duplicate_group_count,
        "exact_duplicate_extra_rows": projection.exact_duplicate_extra_rows,
        "conflicting_intrinsic_metadata_count": 0,
        "family_name_groups_with_distinct_ids": (projection.family_name_groups_with_distinct_ids),
        "row_field_names": [
            "architecture",
            "family",
            "id",
            "name",
            "region",
            "version",
        ],
        "row_field_types": {
            "architecture": "string",
            "family": "string",
            "id": "string",
            "name": "string",
            "region": "object",
            "version": "string",
        },
        "privacy": {
            "raw_ids_retained_in_public_record": False,
            "raw_id_hashes_retained_in_public_record": False,
            "reversible_aliases_retained_in_public_record": False,
            "unknown_sensitive_scalars_retained": False,
        },
        "private_alias_map": alias_map_seal.public_document(repository_root=repository_root),
    }


def _directory_open_flags() -> int:
    flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    return flags


def _write_exclusive_fsync_at(directory_descriptor: int, name: str, encoded: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(name, flags, 0o600, dir_fd=directory_descriptor)
    try:
        view = memoryview(encoded)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise OSError("short evidence write")
            view = view[written:]
        os.fchmod(descriptor, 0o400)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _create_held_directory_chain(
    repository_root: Path,
    relative_path: Path,
) -> int:
    """Create one exact repository-contained path through held no-follow handles."""

    descriptor = os.open(repository_root, _directory_open_flags())
    try:
        parts = relative_path.parts
        for index, part in enumerate(parts):
            if part in {"", ".", ".."} or "/" in part:
                raise L13ContractError("alias evidence path contains an unsafe component")
            final = index == len(parts) - 1
            created = False
            try:
                os.mkdir(part, 0o700, dir_fd=descriptor)
                created = True
            except FileExistsError:
                if final:
                    raise
            next_descriptor = os.open(
                part,
                _directory_open_flags(),
                dir_fd=descriptor,
            )
            try:
                opened = os.fstat(next_descriptor)
                if not stat.S_ISDIR(opened.st_mode):
                    raise L13ContractError("evidence ancestor is not a directory")
                if created:
                    os.fsync(descriptor)
            except Exception:
                os.close(next_descriptor)
                raise
            os.close(descriptor)
            descriptor = next_descriptor
        return descriptor
    except Exception:
        os.close(descriptor)
        raise


def write_sealed_alias_map(
    evidence_root: Path,
    *,
    repository_root: Path,
    projection: ImageProjection,
    inventory_sha256: str,
) -> AliasMapSeal:
    """Write the raw-ID map once under the exact ignored, held-descriptor root."""

    if inventory_sha256 != INVENTORY_SHA256:
        raise L13ContractError("alias map source inventory hash drifted")
    root = repository_root.resolve(strict=True)
    if root != repository_root.absolute():
        raise L13ContractError("alias evidence repository root is unsafe")
    expected_root = root / ALIAS_MAP_RELATIVE_ROOT
    if evidence_root.absolute() != expected_root:
        raise L13ContractError("alias evidence path escaped its exact run root")
    root_descriptor = os.open(root, _directory_open_flags())
    try:
        ignored = _read_regular_at(root_descriptor, ".gitignore", max_bytes=64 * 1024)
    except OSError:
        raise L13ContractError("alias evidence ignore policy is unavailable") from None
    finally:
        os.close(root_descriptor)
    if b"artifacts/" not in {line.strip() for line in ignored.splitlines()}:
        raise L13ContractError("alias evidence root is not excluded from Git")

    map_path = evidence_root / "image-id-alias-map.json"
    seal_path = evidence_root / "IMAGE_ALIAS_MAP_SEAL.json"
    map_document = {
        "schema_version": "0.1.0",
        "run_id": RUN_ID,
        "source_inventory_sha256": inventory_sha256,
        "entries": [
            {"raw_image_id": raw_id, "alias": projection.alias_by_raw_id[raw_id]}
            for raw_id in sorted(projection.alias_by_raw_id)
        ],
    }
    map_encoded = _canonical(map_document) + b"\n"
    if len(map_encoded) > MAX_ALIAS_MAP_BYTES:
        raise L13ContractError("alias map exceeds its byte cap")
    map_sha256 = hashlib.sha256(map_encoded).hexdigest()
    seal_document = {
        "schema_version": "0.1.0",
        "run_id": RUN_ID,
        "source_inventory_sha256": inventory_sha256,
        "map_path": map_path.name,
        "map_bytes": len(map_encoded),
        "map_sha256": map_sha256,
        "alias_count": len(projection.alias_by_raw_id),
        "raw_ids_in_seal": False,
    }
    seal_encoded = _canonical(seal_document) + b"\n"
    if len(seal_encoded) > MAX_ALIAS_MAP_SEAL_BYTES:
        raise L13ContractError("alias map seal exceeds its byte cap")
    directory_descriptor = _create_held_directory_chain(root, ALIAS_MAP_RELATIVE_ROOT)
    try:
        _write_exclusive_fsync_at(
            directory_descriptor,
            map_path.name,
            map_encoded,
        )
        _write_exclusive_fsync_at(
            directory_descriptor,
            seal_path.name,
            seal_encoded,
        )
        os.fsync(directory_descriptor)
    finally:
        os.close(directory_descriptor)
    return AliasMapSeal(
        map_path=map_path,
        map_bytes=len(map_encoded),
        map_sha256=map_sha256,
        seal_path=seal_path,
        seal_bytes=len(seal_encoded),
        seal_sha256=hashlib.sha256(seal_encoded).hexdigest(),
        alias_count=len(projection.alias_by_raw_id),
    )


def build_resource_candidate_matrix(
    inventory: Mapping[str, object],
    projection: ImageProjection,
) -> dict[str, object]:
    """Apply the frozen Gate L0 resource policy without selecting a candidate."""

    images_by_region: dict[str, list[ProjectedImage]] = defaultdict(list)
    for image in projection.images:
        if image.architecture != "x86_64" or image.family != QUALIFICATION_IMAGE_FAMILY:
            continue
        for availability in image.availability:
            images_by_region[availability.region_name].append(image)
    for images in images_by_region.values():
        images.sort(key=lambda image: image.alias)

    candidates: list[dict[str, object]] = []
    near_misses: list[dict[str, object]] = []
    raw_offers = _sequence(inventory.get("instance_types"), context="instance types")
    for raw_offer in sorted(
        raw_offers,
        key=lambda value: _string(
            _mapping(value, context="instance type").get("name"),
            context="instance type name",
        ),
    ):
        offer = _mapping(raw_offer, context="instance type")
        name = _string(offer.get("name"), context="instance type name")
        architecture = _string(offer.get("architecture"), context="instance architecture")
        price = _integer(offer.get("price_cents_per_hour"), context="instance price")
        specs = _mapping(offer.get("specs"), context="instance specs")
        vcpus = _integer(specs.get("vcpus"), context="instance vcpus")
        memory_gib = _integer(specs.get("memory_gib"), context="instance memory")
        storage_gib = _integer(specs.get("storage_gib"), context="instance storage")
        gpus = _integer(specs.get("gpus"), context="instance GPUs")
        regions = [
            _string(
                _mapping(item, context="capacity region").get("name"),
                context="capacity region name",
            )
            for item in _sequence(offer.get("capacity_regions"), context="capacity regions")
        ]
        reasons: list[str] = []
        if architecture != "x86_64":
            reasons.append("architecture-not-x86_64")
        if vcpus < 8:
            reasons.append("vcpus-below-8")
        if memory_gib < 16:
            reasons.append("memory-below-16-gib")
        if storage_gib < 100:
            reasons.append("root-storage-below-100-gib")
        if price > MAX_PRICE_CENTS_PER_HOUR:
            reasons.append("price-over-150-cents-per-hour")
        if gpus > 1:
            reasons.append("multi-gpu-excluded")
        if not regions:
            reasons.append("currently-unavailable")
        if reasons:
            near_misses.append(
                {
                    "instance_type_name": name,
                    "region_name": None,
                    "price_cents_per_hour": price,
                    "reasons": reasons,
                }
            )
            continue
        for region_name in sorted(regions):
            if region_name in FIREWALL_UNENFORCED_REGIONS:
                near_misses.append(
                    {
                        "instance_type_name": name,
                        "region_name": region_name,
                        "price_cents_per_hour": price,
                        "reasons": ["firewall-exception-region-not-auto-selectable"],
                    }
                )
                continue
            compatible = images_by_region.get(region_name, [])
            if not compatible:
                near_misses.append(
                    {
                        "instance_type_name": name,
                        "region_name": region_name,
                        "price_cents_per_hour": price,
                        "reasons": ["no-compatible-approved-image"],
                    }
                )
                continue
            for image in compatible:
                candidates.append(
                    {
                        "instance_type_name": name,
                        "region_name": region_name,
                        "image_alias": image.alias,
                        "image_family": image.family,
                        "image_version": image.version,
                        "architecture": architecture,
                        "price_cents_per_hour": price,
                        "vcpus": vcpus,
                        "memory_gib": memory_gib,
                        "storage_gib": storage_gib,
                        "gpus": gpus,
                        "persistent_filesystem": False,
                        "observed_available": True,
                        "provider_docker_path_support": "documented-gpu-base-22-04",
                        "qualification_list_price_cap_cents": (
                            qualification_list_price_cap_cents(
                                price, MAX_QUALIFICATION_WALL_SECONDS
                            )
                        ),
                    }
                )
    candidates.sort(
        key=lambda item: (
            item["price_cents_per_hour"],
            item["instance_type_name"],
            item["region_name"],
            item["image_alias"],
        )
    )
    near_misses.sort(
        key=lambda item: (
            item["price_cents_per_hour"],
            item["instance_type_name"],
            item["region_name"] or "",
        )
    )
    return {
        "schema_version": "0.1.0",
        "run_id": RUN_ID,
        "source_inventory_sha256": INVENTORY_SHA256,
        "policy": {
            "architecture": "x86_64",
            "minimum_vcpus": 8,
            "minimum_memory_gib": 16,
            "minimum_root_storage_gib": 100,
            "maximum_gpus": 1,
            "maximum_price_cents_per_hour": MAX_PRICE_CENTS_PER_HOUR,
            "persistent_filesystem": False,
            "required_image_family": QUALIFICATION_IMAGE_FAMILY,
            "ranking": [
                "price_cents_per_hour",
                "instance_type_name",
                "region_name",
                "image_alias",
            ],
            "provider_compute_hard_cap_cents": MAX_PROVIDER_COMPUTE_CENTS,
            "qualification_wall_seconds": MAX_QUALIFICATION_WALL_SECONDS,
        },
        "qualifying_candidates": candidates,
        "top_three": candidates[:3],
        "near_misses": near_misses,
        "candidate_selected": False,
        "fresh_price_and_availability_revalidation_required": True,
        "us_south_1_automatically_selectable": False,
    }


def _ssh_wire_string(blob: bytes, offset: int) -> tuple[bytes, int]:
    if offset + 4 > len(blob):
        raise L13ContractError("public key wire encoding is truncated")
    length = int.from_bytes(blob[offset : offset + 4], "big")
    start = offset + 4
    end = start + length
    if length < 1 or end > len(blob):
        raise L13ContractError("public key wire field is invalid")
    return blob[start:end], end


def _public_key_fingerprint(public_key: str) -> tuple[str, str]:
    fields = public_key.strip().split()
    if len(fields) < 2 or fields[0] not in {"ssh-ed25519", "ssh-rsa"}:
        raise L13ContractError("public key is malformed")
    try:
        blob = base64.b64decode(fields[1], validate=True)
    except (binascii.Error, ValueError):
        raise L13ContractError("public key encoding is malformed") from None
    if not blob:
        raise L13ContractError("public key blob is empty")
    embedded_type, offset = _ssh_wire_string(blob, 0)
    try:
        embedded_algorithm = embedded_type.decode("ascii")
    except UnicodeDecodeError:
        raise L13ContractError("public key embedded algorithm is invalid") from None
    if embedded_algorithm != fields[0]:
        raise L13ContractError("public key text and wire algorithms differ")
    if embedded_algorithm == "ssh-ed25519":
        key_bytes, offset = _ssh_wire_string(blob, offset)
        if len(key_bytes) != 32:
            raise L13ContractError("Ed25519 public key length is invalid")
    else:
        exponent, offset = _ssh_wire_string(blob, offset)
        modulus, offset = _ssh_wire_string(blob, offset)
        if not exponent or not modulus:
            raise L13ContractError("RSA public key fields are invalid")
    if offset != len(blob):
        raise L13ContractError("public key wire encoding has trailing bytes")
    fingerprint = base64.b64encode(hashlib.sha256(blob).digest()).decode().rstrip("=")
    return fields[0], f"SHA256:{fingerprint}"


def inspect_local_public_keys(
    ssh_root: Path,
    *,
    _pre_open_hook: Callable[[str], None] | None = None,
) -> tuple[LocalPublicKey, ...]:
    """Inspect held-dirfd ``*.pub`` files and private-file metadata only."""

    flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        root_descriptor = os.open(ssh_root, flags)
    except OSError:
        raise L13ContractError("SSH public-key directory is missing or unsafe") from None
    records: list[LocalPublicKey] = []
    try:
        for name in sorted(item for item in os.listdir(root_descriptor) if item.endswith(".pub")):
            try:
                metadata = os.stat(name, dir_fd=root_descriptor, follow_symlinks=False)
            except OSError:
                raise L13ContractError("public key metadata is unavailable") from None
            if (
                stat.S_ISLNK(metadata.st_mode)
                or not stat.S_ISREG(metadata.st_mode)
                or metadata.st_nlink != 1
            ):
                raise L13ContractError("public key path must be a single-link regular file")
            if _pre_open_hook is not None:
                _pre_open_hook(name)
            file_flags = os.O_RDONLY
            if hasattr(os, "O_NOFOLLOW"):
                file_flags |= os.O_NOFOLLOW
            try:
                descriptor = os.open(name, file_flags, dir_fd=root_descriptor)
            except OSError:
                raise L13ContractError("public key open rejected path drift") from None
            try:
                opened = os.fstat(descriptor)
                if (
                    not stat.S_ISREG(opened.st_mode)
                    or opened.st_nlink != 1
                    or (opened.st_dev, opened.st_ino) != (metadata.st_dev, metadata.st_ino)
                ):
                    raise L13ContractError("public key identity changed before open")
                chunks: list[bytes] = []
                total = 0
                while True:
                    chunk = os.read(
                        descriptor,
                        min(8192, MAX_PUBLIC_KEY_BYTES + 1 - total),
                    )
                    if not chunk:
                        break
                    chunks.append(chunk)
                    total += len(chunk)
                    if total > MAX_PUBLIC_KEY_BYTES:
                        raise L13ContractError("public key file exceeds its byte cap")
                encoded = b"".join(chunks)
            finally:
                os.close(descriptor)
            try:
                public_key = encoded.decode("utf-8")
            except UnicodeDecodeError:
                raise L13ContractError("public key file is not UTF-8") from None
            algorithm, fingerprint = _public_key_fingerprint(public_key)
            private_name = name.removesuffix(".pub")
            try:
                private_metadata = os.stat(
                    private_name,
                    dir_fd=root_descriptor,
                    follow_symlinks=False,
                )
            except FileNotFoundError:
                private_present = False
            except OSError:
                raise L13ContractError("private-key metadata inspection failed") from None
            else:
                private_present = stat.S_ISREG(private_metadata.st_mode)
            records.append(
                LocalPublicKey(
                    display_path=f"~/.ssh/{name}",
                    algorithm=algorithm,
                    fingerprint=fingerprint,
                    mode=f"{stat.S_IMODE(opened.st_mode):04o}",
                    owner_class=(
                        "current-user" if opened.st_uid == os.getuid() else "different-user"
                    ),
                    same_stem_private_file_present=private_present,
                )
            )
    finally:
        os.close(root_descriptor)
    return tuple(records)


def ssh_key_match_document(
    account_keys: Sequence[AccountSSHKeyMaterial],
    local_keys: Sequence[LocalPublicKey],
) -> dict[str, object]:
    """Match public fingerprints without retaining provider public-key bodies."""

    rows: list[dict[str, object]] = []
    approvable: list[tuple[str, LocalPublicKey]] = []
    for account in account_keys:
        if account.public_key is None:
            state = SSHMatchState.EVIDENCE_UNAVAILABLE
            matches: list[LocalPublicKey] = []
        else:
            _, fingerprint = _public_key_fingerprint(account.public_key)
            matches = [item for item in local_keys if item.fingerprint == fingerprint]
            if len(matches) == 1:
                state = SSHMatchState.UNIQUE_MATCH
                if matches[0].same_stem_private_file_present:
                    approvable.append((account.name, matches[0]))
            elif matches:
                state = SSHMatchState.MULTIPLE_MATCHES
            else:
                state = SSHMatchState.NO_MATCH
        rows.append(
            {
                "lambda_key_name": account.name,
                "match_state": state.value,
                "matching_local_public_key_path": (
                    matches[0].display_path if len(matches) == 1 else None
                ),
                "matching_fingerprint": matches[0].fingerprint if len(matches) == 1 else None,
                "same_stem_private_file_present": (
                    matches[0].same_stem_private_file_present if len(matches) == 1 else None
                ),
                "private_key_bytes_accessed": False,
                "account_public_key_retained": False,
            }
        )
    recommendation = approvable[0][0] if len(approvable) == 1 else None
    return {
        "schema_version": "0.1.0",
        "run_id": RUN_ID,
        "source_inventory_sha256": INVENTORY_SHA256,
        "local_public_keys": [item.public_document() for item in local_keys],
        "account_key_matches": rows,
        "recommended_lambda_key_name": recommendation,
        "selection_state": (
            "unique-match-awaiting-user-approval" if recommendation is not None else "blocked"
        ),
        "private_key_bytes_accessed": False,
        "ssh_agent_used": False,
        "ssh_invoked": False,
    }


def _firewall_source_scope(value: str) -> tuple[FirewallSourceScope, bool]:
    try:
        network = ipaddress.ip_network(value, strict=False)
    except ValueError:
        raise L13ContractError("firewall source network is invalid") from None
    if not isinstance(network, ipaddress.IPv4Network):
        raise L13ContractError("firewall source must be IPv4")
    if network.prefixlen == 0:
        scope = FirewallSourceScope.ANY_IPV4
    elif network.prefixlen == 32:
        scope = FirewallSourceScope.SINGLE_IPV4
    else:
        scope = FirewallSourceScope.RESTRICTED_CIDR
    return scope, network.network_address.is_global


def _description_class(
    protocol: str, port_range: tuple[int, int] | None
) -> FirewallDescriptionClass:
    if protocol == "tcp" and port_range == (22, 22):
        return FirewallDescriptionClass.SSH
    if protocol == "tcp" and port_range == (80, 80):
        return FirewallDescriptionClass.HTTP
    if protocol == "tcp" and port_range == (443, 443):
        return FirewallDescriptionClass.HTTPS
    if protocol == "icmp":
        return FirewallDescriptionClass.ICMP
    if protocol == "all":
        return FirewallDescriptionClass.ALL_PROTOCOL
    return FirewallDescriptionClass.CUSTOM_NETWORK


def firewall_assessment_document(
    inventory: Mapping[str, object],
    *,
    approved_public_ipv4_cidr: str | None = None,
) -> dict[str, object]:
    """Return a source-IP-free assessment of the effective global firewall."""

    approved_network = (
        None
        if approved_public_ipv4_cidr is None
        else _approved_public_ipv4(approved_public_ipv4_cidr)
    )

    rulesets = [
        _mapping(item, context="firewall ruleset")
        for item in _sequence(inventory.get("firewall_rulesets"), context="firewall rulesets")
    ]
    global_rulesets = [item for item in rulesets if item.get("scope") == "global"]
    regional_rulesets = [item for item in rulesets if item.get("scope") == "regional"]
    if len(global_rulesets) != 1:
        raise L13ContractError("exactly one global firewall ruleset is required")
    strict_regional_present = any(
        bool(regional_rules := _sequence(item.get("rules"), context="regional rules"))
        and all(
            _mapping(rule, context="regional rule").get("protocol") == "tcp"
            and _mapping(rule, context="regional rule").get("port_range") == [22, 22]
            for rule in regional_rules
        )
        for item in regional_rulesets
    )
    sanitized: list[SanitizedFirewallRule] = []
    strict_source_matches_approval = False
    for ordinal, raw in enumerate(
        _sequence(global_rulesets[0].get("rules"), context="global firewall rules"),
        start=1,
    ):
        rule = _mapping(raw, context="global firewall rule")
        protocol = _string(rule.get("protocol"), context="firewall protocol")
        raw_range = rule.get("port_range")
        if raw_range is None:
            port_range = None
        else:
            values = _sequence(raw_range, context="firewall port range")
            if len(values) != 2:
                raise L13ContractError("firewall port range must contain two values")
            port_range = (
                _integer(values[0], context="firewall port"),
                _integer(values[1], context="firewall port"),
            )
        source_value = _string(rule.get("source_network"), context="firewall source")
        source_scope, source_is_public = _firewall_source_scope(source_value)
        strict_source_matches_approval = (
            approved_network is not None
            and ipaddress.ip_network(source_value, strict=False) == approved_network
        )
        is_ssh = protocol == "tcp" and port_range == (22, 22)
        sanitized.append(
            SanitizedFirewallRule(
                ordinal=ordinal,
                protocol=protocol,
                port_range=port_range,
                source_scope_class=source_scope,
                source_is_public_ipv4=source_is_public,
                description_classification=_description_class(protocol, port_range),
                is_ssh_rule=is_ssh,
                is_non_ssh_exposure=not is_ssh,
            )
        )
    strict = (
        len(sanitized) == 1
        and sanitized[0].is_ssh_rule
        and sanitized[0].source_scope_class is FirewallSourceScope.SINGLE_IPV4
        and sanitized[0].source_is_public_ipv4
        and strict_source_matches_approval
    )
    running_count = len(_sequence(inventory.get("running_instances"), context="running instances"))
    return {
        "schema_version": "0.1.0",
        "run_id": RUN_ID,
        "source_inventory_sha256": INVENTORY_SHA256,
        "global_rule_count": len(sanitized),
        "rules": [item.public_document() for item in sanitized],
        "strict_qualification_firewall": strict,
        "per_instance_ruleset_alone_is_sufficient": False,
        "global_and_per_instance_rules_are_additive": True,
        "regional_ruleset_count_observed": len(regional_rulesets),
        "strict_regional_ruleset_present": strict_regional_present,
        "regional_ruleset_is_additive_only": True,
        "regional_ruleset_requirement_state": (
            "present" if strict_regional_present else "missing-separate-decision-required"
        ),
        "running_instance_count_observed": running_count,
        "no_running_instance_precondition_met": running_count == 0,
        "preferred_option": "temporary-global-rule-replacement",
        "preferred_option_state": "blocked-human-attestation-and-public-ip",
        "public_ipv4_placeholder": PUBLIC_IPV4_PLACEHOLDER,
        "other_workspace_dependency_attestation_required": True,
        "us_south_1_automatically_selectable": False,
        "source_network_values_retained": False,
        "free_form_descriptions_retained": False,
        "options": [
            "temporary-global-rule-replacement",
            "user-permanent-global-cleanup",
            "no-launch",
        ],
    }


def _require_sha256(value: str, *, context: str) -> None:
    if re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise L13ContractError(f"{context} hash is invalid")


def _approved_public_ipv4(value: str) -> ipaddress.IPv4Network:
    try:
        network = ipaddress.ip_network(value, strict=True)
    except ValueError:
        raise L13ContractError("approved public IPv4 must be a canonical public /32") from None
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
        raise L13ContractError("approved public IPv4 must be a canonical public /32")
    return network


def _validated_firewall_rules(response_bytes: bytes) -> tuple[bytes, int]:
    if not response_bytes or len(response_bytes) > MAX_FIREWALL_EVIDENCE_BYTES:
        raise L13ContractError("firewall snapshot exceeds its byte contract")
    response = _strict_object(response_bytes, context="global firewall response")
    data = _mapping(response.get("data"), context="global firewall response data")
    if data.get("id") != "global":
        raise L13ContractError("global firewall response identity drifted")
    _string(data.get("name"), context="global firewall name")
    rules = _sequence(data.get("rules"), context="global firewall rules")
    for raw_rule in rules:
        rule = _mapping(raw_rule, context="global firewall rule")
        protocol = _string(rule.get("protocol"), context="global firewall protocol")
        if protocol not in {"tcp", "udp", "icmp", "all"}:
            raise L13ContractError("global firewall protocol is unsupported")
        _string(rule.get("source_network"), context="global firewall source")
        description = rule.get("description")
        if not isinstance(description, str):
            raise L13ContractError("global firewall description has the wrong type")
        raw_range = rule.get("port_range")
        if raw_range is not None:
            values = _sequence(raw_range, context="global firewall port range")
            if len(values) != 2:
                raise L13ContractError("global firewall port range is invalid")
            start = _integer(values[0], context="global firewall port")
            end = _integer(values[1], context="global firewall port")
            if not 1 <= start <= end <= 65_535:
                raise L13ContractError("global firewall port range is invalid")
    return _canonical(list(rules)), len(rules)


def capture_firewall_rules_snapshot(response_bytes: bytes) -> FirewallRulesSnapshot:
    """Schema-check and hash one exact future GET response without exposing it."""

    normalized, rule_count = _validated_firewall_rules(response_bytes)
    return FirewallRulesSnapshot(
        response_bytes=response_bytes,
        response_sha256=hashlib.sha256(response_bytes).hexdigest(),
        normalized_rules_bytes=normalized,
        normalized_rules_sha256=hashlib.sha256(normalized).hexdigest(),
        rule_count=rule_count,
    )


def firewall_snapshot_seal_bytes(
    snapshot: FirewallRulesSnapshot,
    *,
    run_id: str,
    snapshot_artifact_relative_path: str,
    seal_relative_path: str,
) -> bytes:
    """Render a seal binding the exact private raw snapshot artifact."""

    _validate_snapshot(snapshot)
    if FIREWALL_SNAPSHOT_RUN_PATTERN.fullmatch(run_id) is None:
        raise L13ContractError("firewall snapshot run identity is invalid")
    relative_root = Path("artifacts/t07/lambda/gate-l2") / run_id / "firewall-snapshot"
    snapshot_relative = Path(snapshot_artifact_relative_path)
    seal_relative = Path(seal_relative_path)
    if (
        snapshot_relative != relative_root / "original-global-firewall-response.json"
        or seal_relative != relative_root / "ORIGINAL_GLOBAL_FIREWALL_SEAL.json"
    ):
        raise L13ContractError("firewall snapshot artifact path is unsafe")
    return (
        _canonical(
            {
                "schema_version": "0.1.0",
                "run_id": run_id,
                "snapshot_artifact_relative_path": snapshot_artifact_relative_path,
                "snapshot_artifact_bytes": len(snapshot.response_bytes),
                "snapshot_artifact_sha256": snapshot.response_sha256,
                "seal_relative_path": seal_relative_path,
                "normalized_rules_bytes": len(snapshot.normalized_rules_bytes),
                "normalized_rules_sha256": snapshot.normalized_rules_sha256,
                "rule_count": snapshot.rule_count,
            }
        )
        + b"\n"
    )


def write_sealed_firewall_snapshot(
    evidence_root: Path,
    *,
    repository_root: Path,
    run_id: str,
    snapshot: FirewallRulesSnapshot,
) -> SealedFirewallRulesSnapshot:
    """Persist exact private snapshot bytes and their seal through held descriptors."""

    _validate_snapshot(snapshot)
    root = repository_root.resolve(strict=True)
    if root != repository_root.absolute():
        raise L13ContractError("firewall evidence repository root is unsafe")
    if FIREWALL_SNAPSHOT_RUN_PATTERN.fullmatch(run_id) is None:
        raise L13ContractError("firewall snapshot run identity is invalid")
    relative_root = Path("artifacts/t07/lambda/gate-l2") / run_id / "firewall-snapshot"
    if evidence_root.absolute() != root / relative_root:
        raise L13ContractError("firewall snapshot path escaped its exact run root")
    root_descriptor = os.open(root, _directory_open_flags())
    try:
        ignored = _read_regular_at(root_descriptor, ".gitignore", max_bytes=64 * 1024)
    except OSError:
        raise L13ContractError("firewall evidence ignore policy is unavailable") from None
    finally:
        os.close(root_descriptor)
    if b"artifacts/" not in {line.strip() for line in ignored.splitlines()}:
        raise L13ContractError("firewall evidence root is not excluded from Git")
    if len(snapshot.response_bytes) > MAX_FIREWALL_EVIDENCE_BYTES:
        raise L13ContractError("firewall snapshot exceeds its byte cap")
    snapshot_relative = relative_root / "original-global-firewall-response.json"
    seal_relative = relative_root / "ORIGINAL_GLOBAL_FIREWALL_SEAL.json"
    seal_encoded = firewall_snapshot_seal_bytes(
        snapshot,
        run_id=run_id,
        snapshot_artifact_relative_path=str(snapshot_relative),
        seal_relative_path=str(seal_relative),
    )
    if len(seal_encoded) > MAX_FIREWALL_SEAL_BYTES:
        raise L13ContractError("firewall snapshot seal exceeds its byte cap")
    directory_descriptor = _create_held_directory_chain(root, relative_root)
    try:
        _write_exclusive_fsync_at(
            directory_descriptor,
            snapshot_relative.name,
            snapshot.response_bytes,
        )
        _write_exclusive_fsync_at(
            directory_descriptor,
            seal_relative.name,
            seal_encoded,
        )
        os.fsync(directory_descriptor)
        snapshot_readback = _read_regular_at(
            directory_descriptor,
            snapshot_relative.name,
            max_bytes=MAX_FIREWALL_EVIDENCE_BYTES,
        )
        seal_readback = _read_regular_at(
            directory_descriptor,
            seal_relative.name,
            max_bytes=MAX_FIREWALL_SEAL_BYTES,
        )
    finally:
        os.close(directory_descriptor)
    if snapshot_readback != snapshot.response_bytes or seal_readback != seal_encoded:
        raise L13ContractError("firewall snapshot post-fsync readback drifted")
    seal_digest = hashlib.sha256(seal_readback).hexdigest()
    snapshot_digest = hashlib.sha256(snapshot_readback).hexdigest()
    return SealedFirewallRulesSnapshot(
        repository_root=root,
        run_id=run_id,
        snapshot=snapshot,
        snapshot_artifact_relative_path=str(snapshot_relative),
        snapshot_artifact_bytes=len(snapshot_readback),
        snapshot_artifact_sha256=snapshot_digest,
        snapshot_post_fsync_readback_sha256=snapshot_digest,
        seal_relative_path=str(seal_relative),
        seal_bytes=len(seal_readback),
        seal_sha256=seal_digest,
        post_fsync_readback_sha256=seal_digest,
        directory_fsync_completed=True,
    )


def strict_firewall_replacement_request(
    approved_public_ipv4_cidr: str,
) -> FirewallReplacementRequest:
    """Construct the sole permitted future global replacement body."""

    approved = str(_approved_public_ipv4(approved_public_ipv4_cidr))
    body = _canonical(
        {
            "rules": [
                {
                    "description": "T07 temporary qualification SSH",
                    "port_range": [22, 22],
                    "protocol": "tcp",
                    "source_network": approved,
                }
            ]
        }
    )
    return FirewallReplacementRequest(
        request_body_bytes=body,
        request_body_sha256=hashlib.sha256(body).hexdigest(),
        approved_public_ipv4_cidr=approved,
    )


def _validate_snapshot(evidence: FirewallRulesSnapshot) -> None:
    expected = capture_firewall_rules_snapshot(evidence.response_bytes)
    if evidence != expected:
        raise L13ContractError("firewall snapshot evidence was tampered")


def _validate_sealed_snapshot(evidence: SealedFirewallRulesSnapshot) -> None:
    root = evidence.repository_root.resolve(strict=True)
    if root != evidence.repository_root.absolute():
        raise L13ContractError("firewall snapshot repository root is unsafe")
    expected = firewall_snapshot_seal_bytes(
        evidence.snapshot,
        run_id=evidence.run_id,
        snapshot_artifact_relative_path=evidence.snapshot_artifact_relative_path,
        seal_relative_path=evidence.seal_relative_path,
    )
    snapshot_readback = _read_bound_regular(
        root / evidence.snapshot_artifact_relative_path,
        maximum_bytes=MAX_FIREWALL_EVIDENCE_BYTES,
    )
    seal_readback = _read_bound_regular(
        root / evidence.seal_relative_path,
        maximum_bytes=MAX_FIREWALL_SEAL_BYTES,
    )
    snapshot_digest = hashlib.sha256(snapshot_readback).hexdigest()
    seal_digest = hashlib.sha256(seal_readback).hexdigest()
    if (
        snapshot_readback != evidence.snapshot.response_bytes
        or evidence.snapshot_artifact_bytes != len(snapshot_readback)
        or evidence.snapshot_artifact_sha256 != snapshot_digest
        or evidence.snapshot_post_fsync_readback_sha256 != snapshot_digest
        or seal_readback != expected
        or evidence.seal_bytes != len(seal_readback)
        or evidence.seal_sha256 != seal_digest
        or evidence.post_fsync_readback_sha256 != seal_digest
        or not evidence.directory_fsync_completed
    ):
        raise L13ContractError("firewall snapshot artifact or seal evidence was tampered")


def _validate_replacement_request(evidence: FirewallReplacementRequest) -> None:
    expected = strict_firewall_replacement_request(evidence.approved_public_ipv4_cidr)
    if evidence != expected:
        raise L13ContractError("firewall replacement request was tampered")


def transition_firewall_replacement(
    state: FirewallReplacementState,
    event: FirewallReplacementEvent,
    *,
    evidence: (
        FirewallPreconditionsEvidence
        | FirewallRulesSnapshot
        | SealedFirewallRulesSnapshot
        | FirewallReplacementRequest
        | FirewallInstanceIdentity
        | FirewallInstanceTerminalEvidence
        | None
    ) = None,
) -> FirewallReplacementState:
    """Advance a future evidence-bound lifecycle; this performs no provider action."""

    phase = state.phase
    if (
        phase is FirewallReplacementPhase.PRECONDITIONS_PENDING
        and event is FirewallReplacementEvent.PRECONDITIONS_VERIFIED
        and isinstance(evidence, FirewallPreconditionsEvidence)
    ):
        if (
            evidence.running_instance_count_account_wide != 0
            or not evidence.workspace_dependency_attested
        ):
            raise L13ContractError("global firewall preconditions are not satisfied")
        _approved_public_ipv4(evidence.approved_public_ipv4_cidr)
        _require_sha256(evidence.observation_sha256, context="firewall observation")
        return replace(
            state,
            phase=FirewallReplacementPhase.PRECONDITIONS_VERIFIED,
            preconditions=evidence,
        )
    if (
        phase is FirewallReplacementPhase.PRECONDITIONS_VERIFIED
        and event is FirewallReplacementEvent.ORIGINAL_SNAPSHOT_SEALED
        and isinstance(evidence, SealedFirewallRulesSnapshot)
    ):
        _validate_sealed_snapshot(evidence)
        return replace(
            state,
            phase=FirewallReplacementPhase.ORIGINAL_SNAPSHOT_SEALED,
            original_snapshot=evidence,
        )
    if (
        phase is FirewallReplacementPhase.ORIGINAL_SNAPSHOT_SEALED
        and event is FirewallReplacementEvent.REPLACEMENT_REQUESTED
        and isinstance(evidence, FirewallReplacementRequest)
        and state.preconditions is not None
        and state.original_snapshot is not None
    ):
        _validate_sealed_snapshot(state.original_snapshot)
        _validate_replacement_request(evidence)
        if evidence.approved_public_ipv4_cidr != state.preconditions.approved_public_ipv4_cidr:
            raise L13ContractError("firewall replacement source does not match approval")
        return replace(
            state,
            phase=FirewallReplacementPhase.REPLACEMENT_PENDING,
            replacement_request=evidence,
        )
    if (
        phase is FirewallReplacementPhase.REPLACEMENT_PENDING
        and event is FirewallReplacementEvent.REPLACEMENT_VERIFIED
        and isinstance(evidence, FirewallRulesSnapshot)
        and state.replacement_request is not None
    ):
        _validate_snapshot(evidence)
        request = _strict_object(
            state.replacement_request.request_body_bytes,
            context="strict firewall request",
        )
        if evidence.normalized_rules_bytes != _canonical(
            _sequence(request.get("rules"), context="strict firewall request rules")
        ):
            raise L13ContractError("observed firewall does not equal strict replacement")
        return replace(
            state,
            phase=FirewallReplacementPhase.STRICT_REPLACEMENT_VERIFIED,
            replacement_observation=evidence,
        )
    if (
        phase is FirewallReplacementPhase.STRICT_REPLACEMENT_VERIFIED
        and event is FirewallReplacementEvent.INSTANCE_LAUNCHED
        and isinstance(evidence, FirewallInstanceIdentity)
    ):
        _string(evidence.instance_id, context="qualification instance identity")
        _require_sha256(evidence.launch_evidence_sha256, context="instance launch evidence")
        return replace(
            state,
            phase=FirewallReplacementPhase.INSTANCE_ACTIVE,
            instance=evidence,
        )
    if phase is FirewallReplacementPhase.INSTANCE_ACTIVE and event in {
        FirewallReplacementEvent.QUALIFICATION_FINISHED,
        FirewallReplacementEvent.FAILURE_AFTER_MUTATION,
    }:
        return replace(
            state,
            phase=FirewallReplacementPhase.INSTANCE_TERMINATION_REQUIRED,
        )
    if (
        phase is FirewallReplacementPhase.INSTANCE_TERMINATION_REQUIRED
        and event is FirewallReplacementEvent.INSTANCE_TERMINATED
        and isinstance(evidence, FirewallInstanceTerminalEvidence)
        and state.instance is not None
    ):
        if evidence.instance_id != state.instance.instance_id or evidence.terminal_state not in {
            "terminated",
            "deleted",
        }:
            raise L13ContractError("terminal evidence does not close the launched instance")
        _require_sha256(
            evidence.terminal_evidence_sha256,
            context="instance terminal evidence",
        )
        return replace(
            state,
            phase=FirewallReplacementPhase.RESTORE_REQUIRED,
            terminal_instance=evidence,
        )
    if (
        phase
        in {
            FirewallReplacementPhase.REPLACEMENT_PENDING,
            FirewallReplacementPhase.STRICT_REPLACEMENT_VERIFIED,
        }
        and event is FirewallReplacementEvent.FAILURE_AFTER_MUTATION
    ):
        return replace(state, phase=FirewallReplacementPhase.RESTORE_REQUIRED)
    if (
        phase is FirewallReplacementPhase.RESTORE_REQUIRED
        and event is FirewallReplacementEvent.RESTORE_REQUESTED
        and state.original_snapshot is not None
        and (state.instance is None or state.terminal_instance is not None)
    ):
        _validate_sealed_snapshot(state.original_snapshot)
        return replace(state, phase=FirewallReplacementPhase.RESTORE_PENDING)
    if (
        phase is FirewallReplacementPhase.RESTORE_PENDING
        and event is FirewallReplacementEvent.RESTORE_VERIFIED
        and isinstance(evidence, FirewallRulesSnapshot)
        and state.original_snapshot is not None
    ):
        _validate_sealed_snapshot(state.original_snapshot)
        _validate_snapshot(evidence)
        if (
            evidence.normalized_rules_bytes
            != state.original_snapshot.snapshot.normalized_rules_bytes
        ):
            raise L13ContractError("restored firewall does not equal original rules")
        return replace(state, phase=FirewallReplacementPhase.CLOSED)
    if (
        phase is FirewallReplacementPhase.RESTORE_PENDING
        and event is FirewallReplacementEvent.RESTORE_FAILED
    ):
        return replace(state, phase=FirewallReplacementPhase.INCIDENT)
    raise L13ContractError("firewall replacement lifecycle transition is unsafe")


def host_key_trust_decision_document() -> dict[str, object]:
    return {
        "schema_version": "0.1.0",
        "preferred_option": "independent-console-fingerprint-verification",
        "preferred_option_user_action": (
            "After a separately authorized launch, obtain the ED25519 host-key fingerprint "
            "inside the authenticated Lambda console or Jupyter terminal and return it for "
            "comparison before first SSH login."
        ),
        "strict_host_key_checking_required": True,
        "fresh_run_owned_known_hosts_required": True,
        "ssh_keyscan_authorized": False,
        "tofu_option_state": "blocked-explicit-governance-relaxation-required",
        "no_ssh_no_launch_available": True,
        "private_host_key_in_cloud_init_allowed": False,
        "decision_state": "awaiting-user-approval",
    }


def validate_supplemental_l2_decision_evidence(
    inventory: Mapping[str, object],
    *,
    projection: ImageProjection,
    candidate_matrix: Mapping[str, object],
) -> None:
    """Recompute alias/candidate semantics and reject ambiguous public evidence."""

    aliases = [image.alias for image in projection.images]
    if len(aliases) != len(set(aliases)) or any(
        IMAGE_ALIAS_PATTERN.fullmatch(alias) is None for alias in aliases
    ):
        raise L13ContractError("image aliases are ambiguous")
    encoded_public = _canonical(projection.public_images())
    if any(raw_id.encode() in encoded_public for raw_id in projection.alias_by_raw_id):
        raise L13ContractError("raw image ID reached public projection")
    expected = build_resource_candidate_matrix(inventory, projection)
    if candidate_matrix != expected:
        raise L13ContractError("resource candidate matrix drifted")
    candidate_aliases = {
        _string(
            _mapping(item, context="candidate").get("image_alias"),
            context="candidate image alias",
        )
        for item in _sequence(
            candidate_matrix.get("qualifying_candidates"), context="qualifying candidates"
        )
    }
    if not candidate_aliases.issubset(set(aliases)):
        raise L13ContractError("candidate references an unknown image alias")


def verify_bound_run_bytes(
    *,
    inventory_bytes: bytes,
    ledger_bytes: bytes,
    external_inventory_bytes: bytes,
    external_ledger_bytes: bytes,
    seal_bytes: bytes,
    copy_record_bytes: bytes,
    extension_report_bytes: bytes,
) -> None:
    """Verify immutable run-0003 byte identities without inspecting secret material."""

    expected = (
        (inventory_bytes, INVENTORY_SHA256),
        (ledger_bytes, LEDGER_SHA256),
        (seal_bytes, SEAL_SHA256),
        (copy_record_bytes, COPY_RECORD_SHA256),
        (extension_report_bytes, SCHEMA_EXTENSION_REPORT_SHA256),
    )
    if any(hashlib.sha256(encoded).hexdigest() != digest for encoded, digest in expected):
        raise L13ContractError("bound run-0003 evidence hash drifted")
    if inventory_bytes != external_inventory_bytes or ledger_bytes != external_ledger_bytes:
        raise L13ContractError("bound run-0003 source/archive bytes differ")


def _read_bound_regular(path: Path, *, maximum_bytes: int) -> bytes:
    try:
        parent_descriptor = _open_directory_no_symlinks(path.parent)
        try:
            return _read_regular_at(
                parent_descriptor,
                path.name,
                max_bytes=maximum_bytes,
            )
        finally:
            os.close(parent_descriptor)
    except OSError:
        raise L13ContractError("bound Gate L1 evidence is missing or unsafe") from None


def validate_alias_map_evidence(
    repository_root: Path,
    *,
    projection: ImageProjection,
    public_record: Mapping[str, object],
) -> AliasMapSeal:
    """Bind the private provider-ID map exactly to its public aliases and seal."""

    root = repository_root.resolve(strict=True)
    if root != repository_root.absolute():
        raise L13ContractError("alias map repository root is unsafe")
    map_path = root / ALIAS_MAP_RELATIVE_ROOT / "image-id-alias-map.json"
    seal_path = root / ALIAS_MAP_RELATIVE_ROOT / "IMAGE_ALIAS_MAP_SEAL.json"
    expected_public = {
        "state": "ignored-sealed-local-evidence",
        "path": str(ALIAS_MAP_RELATIVE_ROOT / map_path.name),
        "bytes": public_record.get("bytes"),
        "sha256": public_record.get("sha256"),
        "seal_path": str(ALIAS_MAP_RELATIVE_ROOT / seal_path.name),
        "seal_bytes": public_record.get("seal_bytes"),
        "seal_sha256": public_record.get("seal_sha256"),
        "alias_count": len(projection.alias_by_raw_id),
        "raw_ids_committed": False,
        "raw_id_hashes_committed": False,
    }
    if dict(public_record) != expected_public:
        raise L13ContractError("alias map public binding drifted")
    map_encoded = _read_bound_regular(map_path, maximum_bytes=MAX_ALIAS_MAP_BYTES)
    seal_encoded = _read_bound_regular(seal_path, maximum_bytes=MAX_ALIAS_MAP_SEAL_BYTES)
    if (
        len(map_encoded) != public_record.get("bytes")
        or hashlib.sha256(map_encoded).hexdigest() != public_record.get("sha256")
        or len(seal_encoded) != public_record.get("seal_bytes")
        or hashlib.sha256(seal_encoded).hexdigest() != public_record.get("seal_sha256")
    ):
        raise L13ContractError("alias map byte identity drifted")
    map_document = _strict_object(map_encoded, context="private image alias map")
    seal_document = _strict_object(seal_encoded, context="private image alias seal")
    expected_entries = [
        {"raw_image_id": raw_id, "alias": projection.alias_by_raw_id[raw_id]}
        for raw_id in sorted(projection.alias_by_raw_id)
    ]
    if map_document != {
        "schema_version": "0.1.0",
        "run_id": RUN_ID,
        "source_inventory_sha256": INVENTORY_SHA256,
        "entries": expected_entries,
    }:
        raise L13ContractError("alias map semantic binding drifted")
    map_sha256 = hashlib.sha256(map_encoded).hexdigest()
    if seal_document != {
        "schema_version": "0.1.0",
        "run_id": RUN_ID,
        "source_inventory_sha256": INVENTORY_SHA256,
        "map_path": map_path.name,
        "map_bytes": len(map_encoded),
        "map_sha256": map_sha256,
        "alias_count": len(expected_entries),
        "raw_ids_in_seal": False,
    }:
        raise L13ContractError("alias map seal binding drifted")
    return AliasMapSeal(
        map_path=map_path,
        map_bytes=len(map_encoded),
        map_sha256=map_sha256,
        seal_path=seal_path,
        seal_bytes=len(seal_encoded),
        seal_sha256=hashlib.sha256(seal_encoded).hexdigest(),
        alias_count=len(expected_entries),
    )


def validate_l13_gate_l2_evidence(
    repository_root: Path,
    *,
    plan: ReadOnlyInventoryPlanV3,
    plan_sha256: str,
    run_binding: InventoryRunBindingV3,
    ancestry_verifier: Callable[..., None] = verify_repository_commit_ancestry_v3,
) -> GateL2EvidenceValidationL13:
    """Authoritatively consume the complete sealed run through the L1.3 repair.

    The V3 execution implementation and evidence stay byte-frozen.  This versioned
    post-run consumer repeats their provenance, ledger, archive, and storage checks,
    replacing only the defective global-uniqueness interpretation of ``Image.id``
    with the official identity-plus-regional-availability projection.
    """

    from giclab.validation import validate_instance

    root = repository_root.resolve(strict=True)
    if root != repository_root.absolute():
        raise L13ContractError("Gate L1.3 repository root is unsafe")
    if (
        plan_sha256 != PLAN_SHA256
        or plan.implementation_commit != IMPLEMENTATION_COMMIT
        or run_binding.run_id != RUN_ID
        or run_binding.repository_commit != EXECUTION_COMMIT
        or run_binding.implementation_commit != IMPLEMENTATION_COMMIT
        or run_binding.authorization_reference != AUTHORIZATION_REFERENCE
        or run_binding.authorization_sha256 != AUTHORIZATION_SHA256
    ):
        raise L13ContractError("Gate L1.3 plan or run binding drifted")
    try:
        ancestry_verifier(
            root,
            implementation_commit=IMPLEMENTATION_COMMIT,
            execution_commit=EXECUTION_COMMIT,
        )
        verify_inventory_implementation_v3(root, plan)
    except Exception:
        raise L13ContractError("Gate L1.3 implementation binding failed") from None

    inventory_path = root / plan.output_relative_path
    ledger_path = root / plan.ledger_relative_path
    local_record_path = root / plan.copy_record_relative_path
    inventory_encoded = _read_bound_regular(
        inventory_path,
        maximum_bytes=plan.max_retained_output_bytes,
    )
    ledger_encoded = _read_bound_regular(
        ledger_path,
        maximum_bytes=plan.limits.max_bytes,
    )
    local_record_encoded = _read_bound_regular(
        local_record_path,
        maximum_bytes=plan.max_local_record_bytes,
    )

    archive_path = Path(plan.archive_root) / RUN_ID
    external_inventory = _read_bound_regular(
        archive_path / INVENTORY_ARCHIVE_NAME,
        maximum_bytes=plan.max_retained_output_bytes,
    )
    external_ledger = _read_bound_regular(
        archive_path / LEDGER_ARCHIVE_NAME,
        maximum_bytes=plan.limits.max_bytes,
    )
    external_record_encoded = _read_bound_regular(
        archive_path / COPY_RECORD_NAME,
        maximum_bytes=plan.max_local_record_bytes,
    )
    seal_encoded = _read_bound_regular(
        archive_path / SEAL_NAME,
        maximum_bytes=plan.max_local_record_bytes,
    )
    inventory = _strict_object(inventory_encoded, context="Gate L1.3 inventory")
    extension_binding = _mapping(
        inventory.get("schema_extension_report"),
        context="schema extension binding",
    )
    extension_report = _mapping(
        extension_binding.get("report"),
        context="schema extension report",
    )
    try:
        extension_encoded = schema_extension_report_bytes(extension_report)
    except LambdaCloudContractError:
        raise L13ContractError("Gate L1.3 extension report is invalid") from None
    if (
        len(extension_encoded) != SCHEMA_EXTENSION_REPORT_BYTES
        or hashlib.sha256(extension_encoded).hexdigest() != SCHEMA_EXTENSION_REPORT_SHA256
    ):
        raise L13ContractError("Gate L1.3 extension report byte identity drifted")
    verify_bound_run_bytes(
        inventory_bytes=inventory_encoded,
        ledger_bytes=ledger_encoded,
        external_inventory_bytes=external_inventory,
        external_ledger_bytes=external_ledger,
        seal_bytes=seal_encoded,
        copy_record_bytes=external_record_encoded,
        extension_report_bytes=extension_encoded,
    )
    if hashlib.sha256(local_record_encoded).hexdigest() != LOCAL_COPY_RECORD_SHA256:
        raise L13ContractError("Gate L1.3 local copy record hash drifted")

    validator = load_request_ledger_validator(root, plan)
    try:
        events = validate_request_ledger_bytes(
            ledger_encoded,
            plan=plan,
            run_binding=run_binding,
            validator=validator,
            require_terminal_success=True,
        )
    except LambdaCloudContractError:
        raise L13ContractError("Gate L1.3 terminal request ledger is invalid") from None
    if (
        len(events) != 44
        or any(event["event_type"] == "request_outcome_unknown_after_send" for event in events)
        or sum(event["event_type"] == "response_validation_passed" for event in events) != 7
    ):
        raise L13ContractError("Gate L1.3 request outcome provenance drifted")

    if validate_instance(inventory, root / plan.inventory_schema_relative_path):
        raise L13ContractError("Gate L1.3 inventory schema validation failed")
    expected_run_identity = {
        "run_id": RUN_ID,
        "attempt": plan.attempt,
        "experiment_id": "EXP-0001",
        "profile_plan_id": "PLAN-EXP0001-SMOKE",
        "gate": "T07-L1",
        "branch": "phase-1/sira-smoke-lambda",
        "implementation_commit": IMPLEMENTATION_COMMIT,
        "repository_commit": EXECUTION_COMMIT,
    }
    if (
        inventory.get("inventory_plan") != {"plan_id": plan.plan_id, "sha256": PLAN_SHA256}
        or inventory.get("run_identity") != expected_run_identity
        or inventory.get("authorization_binding")
        != {
            "authorization_reference": AUTHORIZATION_REFERENCE,
            "authorization_sha256": AUTHORIZATION_SHA256,
            "authorized": True,
        }
        or inventory.get("request_ledger") != inventory_ledger_contract_document_v3(plan)
        or inventory.get("limits") != inventory_limits_document_v3(plan)
    ):
        raise L13ContractError("Gate L1.3 inventory provenance binding drifted")
    try:
        _validate_inventory_request_provenance(
            inventory,
            plan=plan,
            ledger_events=events,
        )
    except Exception:
        raise L13ContractError("Gate L1.3 ordered request provenance drifted") from None

    projection = project_image_identities(_sequence(inventory.get("images"), context="images"))
    candidate_matrix = build_resource_candidate_matrix(inventory, projection)
    validate_supplemental_l2_decision_evidence(
        inventory,
        projection=projection,
        candidate_matrix=candidate_matrix,
    )
    historical_selection = inventory.get("selection")
    if historical_selection != {
        "state": "blocked",
        "reason_code": "global-firewall-not-ssh-only",
        "ssh_key_binding": None,
        "firewall_ruleset_binding": None,
    }:
        raise L13ContractError("Gate L1.3 historical selection provenance drifted")
    if _sequence(inventory.get("running_instances"), context="running instances"):
        raise L13ContractError("Gate L1.3 requires zero running instances account-wide")
    raw_keys = _sequence(inventory.get("ssh_keys"), context="SSH keys")
    if len(raw_keys) != 3 or any(
        set(_mapping(item, context="SSH key")) != {"id", "name"} for item in raw_keys
    ):
        raise L13ContractError("Gate L1.3 SSH public-key evidence state drifted")

    adjudication_path = root / "docs/harness/evidence/T07_RUN_0003_POSTRUN_ADJUDICATION.json"
    adjudication_encoded = _read_bound_regular(
        adjudication_path,
        maximum_bytes=256 * 1024,
    )
    if hashlib.sha256(adjudication_encoded).hexdigest() != POSTRUN_ADJUDICATION_SHA256:
        raise L13ContractError("Gate L1.3 public adjudication hash drifted")
    adjudication = _strict_object(
        adjudication_encoded,
        context="Gate L1.3 post-run adjudication",
    )
    if (
        adjudication.get("decision_state") != "inventory-evidence-insufficient"
        or adjudication.get("resource_candidate_matrix") != candidate_matrix
        or adjudication.get("firewall_assessment") != firewall_assessment_document(inventory)
    ):
        raise L13ContractError("Gate L1.3 public adjudication semantics drifted")
    image_adjudication = _mapping(
        adjudication.get("image_identity_adjudication"),
        context="image identity adjudication",
    )
    alias_record = _mapping(
        image_adjudication.get("private_alias_map"),
        context="private alias map binding",
    )
    alias_seal = validate_alias_map_evidence(
        root,
        projection=projection,
        public_record=alias_record,
    )
    if image_adjudication != image_identity_adjudication_document(
        projection,
        alias_map_seal=alias_seal,
        repository_root=root,
    ):
        raise L13ContractError("Gate L1.3 image adjudication semantics drifted")
    ssh_document = _mapping(
        adjudication.get("ssh_key_match"),
        context="SSH key match adjudication",
    )
    account_key_names = [
        _string(
            _mapping(item, context="SSH key").get("name"),
            context="SSH key name",
        )
        for item in raw_keys
    ]
    expected_account_matches = [
        {
            "lambda_key_name": name,
            "match_state": SSHMatchState.EVIDENCE_UNAVAILABLE.value,
            "matching_local_public_key_path": None,
            "matching_fingerprint": None,
            "same_stem_private_file_present": None,
            "private_key_bytes_accessed": False,
            "account_public_key_retained": False,
        }
        for name in account_key_names
    ]
    if (
        ssh_document.get("schema_version") != "0.1.0"
        or ssh_document.get("run_id") != RUN_ID
        or ssh_document.get("source_inventory_sha256") != INVENTORY_SHA256
        or ssh_document.get("account_key_matches") != expected_account_matches
        or ssh_document.get("recommended_lambda_key_name") is not None
        or ssh_document.get("selection_state") != "blocked"
        or ssh_document.get("private_key_bytes_accessed") is not False
        or ssh_document.get("ssh_agent_used") is not False
        or ssh_document.get("ssh_invoked") is not False
    ):
        raise L13ContractError("Gate L1.3 SSH-key adjudication semantics drifted")
    expected_authorization = {
        "cloud_mutation_authorized": False,
        "gate_l2_authorized": False,
        "paid_compute_authorized": False,
    }
    expected_prohibited = {
        "account_requests": 0,
        "browser_actions": 0,
        "cloud_mutations": 0,
        "container_runs": 0,
        "model_api_calls": 0,
        "private_key_byte_reads": 0,
        "public_ip_requests": 0,
        "scientific_executions": 0,
        "sira_executions": 0,
        "ssh_operations": 0,
    }
    expected_gap = {
        "account_request_authorized": False,
        "code": "account-ssh-public-key-material-not-retained",
        "fact": (
            "The sealed run-0003 inventory retains account key names but not account "
            "public-key material, so local/account fingerprint equivalence cannot be "
            "established."
        ),
        "minimum_resolution": (
            "A new reviewed and separately authorized minimal read-only evidence plan, "
            "or user-provided independently verified account public-key fingerprints, "
            "must supply matchable account public-key evidence."
        ),
    }
    expected_source = {
        "external_copy_record_sha256": COPY_RECORD_SHA256,
        "external_seal_sha256": SEAL_SHA256,
        "inventory": {
            "bytes": len(inventory_encoded),
            "path": plan.output_relative_path,
            "sha256": INVENTORY_SHA256,
        },
        "schema_extension_report": {
            "bytes": len(extension_encoded),
            "location": "inventory-redacted.json#/schema_extension_report/report",
            "sha256": SCHEMA_EXTENSION_REPORT_SHA256,
        },
        "request_ledger": {
            "bytes": len(ledger_encoded),
            "events": len(events),
            "path": plan.ledger_relative_path,
            "sha256": LEDGER_SHA256,
        },
        "running_instances_observed": 0,
        "seven_http_200_schema_valid_outcomes": True,
        "source_destination_equal": True,
    }
    if (
        set(adjudication)
        != {
            "authorization",
            "blocking_evidence_gap",
            "decision_state",
            "firewall_assessment",
            "gate",
            "host_key_trust_decision",
            "image_identity_adjudication",
            "prohibited_operations_observed",
            "resource_candidate_matrix",
            "run_id",
            "schema_version",
            "source_evidence",
            "ssh_key_match",
        }
        or adjudication.get("authorization") != expected_authorization
        or adjudication.get("prohibited_operations_observed") != expected_prohibited
        or adjudication.get("blocking_evidence_gap") != expected_gap
        or adjudication.get("source_evidence") != expected_source
        or adjudication.get("host_key_trust_decision") != host_key_trust_decision_document()
        or adjudication.get("gate") != "T07-L1.3"
        or adjudication.get("run_id") != RUN_ID
        or adjudication.get("schema_version") != "0.1.0"
    ):
        raise L13ContractError("Gate L1.3 authorization or safety semantics drifted")
    for document_field, schema in (
        (
            "image_identity_adjudication",
            "schemas/t07-lambda-image-identity-adjudication.schema.json",
        ),
        (
            "resource_candidate_matrix",
            "schemas/t07-lambda-resource-candidate-matrix.schema.json",
        ),
        ("firewall_assessment", "schemas/t07-lambda-firewall-assessment.schema.json"),
        ("ssh_key_match", "schemas/t07-lambda-ssh-key-match.schema.json"),
    ):
        raw_document = adjudication.get(document_field)
        if not isinstance(raw_document, Mapping) or validate_instance(raw_document, root / schema):
            raise L13ContractError("Gate L1.3 public adjudication schema drifted")

    external_record = _strict_object(
        external_record_encoded,
        context="Gate L1.3 external copy record",
    )
    seal = _strict_object(seal_encoded, context="Gate L1.3 external seal")
    local_record = _strict_object(
        local_record_encoded,
        context="Gate L1.3 local copy record",
    )
    if set(external_record) != EXTERNAL_RECORD_FIELDS or set(local_record) != LOCAL_RECORD_FIELDS:
        raise L13ContractError("Gate L1.3 copy-record field set drifted")
    inventory_sha256 = hashlib.sha256(inventory_encoded).hexdigest()
    ledger_sha256 = hashlib.sha256(ledger_encoded).hexdigest()
    external_record_sha256 = hashlib.sha256(external_record_encoded).hexdigest()
    seal_sha256 = hashlib.sha256(seal_encoded).hexdigest()
    expected_files = [
        {
            "path": INVENTORY_ARCHIVE_NAME,
            "bytes": len(inventory_encoded),
            "sha256": inventory_sha256,
        },
        {
            "path": LEDGER_ARCHIVE_NAME,
            "bytes": len(ledger_encoded),
            "sha256": ledger_sha256,
        },
        {
            "path": COPY_RECORD_NAME,
            "bytes": len(external_record_encoded),
            "sha256": external_record_sha256,
        },
    ]
    if seal != {
        "schema_version": "0.3.0",
        "run_id": RUN_ID,
        "terminal_ledger_validated": True,
        "files": expected_files,
    }:
        raise L13ContractError("Gate L1.3 external seal binding drifted")
    common = {
        "plan_id": plan.plan_id,
        "plan_sha256": PLAN_SHA256,
        "run_id": RUN_ID,
        "implementation_commit": IMPLEMENTATION_COMMIT,
        "repository_commit": EXECUTION_COMMIT,
        "authorization_reference": AUTHORIZATION_REFERENCE,
        "authorization_sha256": AUTHORIZATION_SHA256,
    }
    if any(external_record.get(key) != value for key, value in common.items()) or any(
        local_record.get(key) != value for key, value in common.items()
    ):
        raise L13ContractError("Gate L1.3 archive identity binding drifted")
    if (
        external_record.get("schema_version") != "0.3.0"
        or local_record.get("schema_version") != "0.3.0"
        or external_record.get("action_id") != ARCHIVE_ACTION_ID_V3
        or local_record.get("action_id") != ARCHIVE_ACTION_ID_V3
        or external_record.get("source_inventory_path") != str(inventory_path)
        or external_record.get("source_inventory_sha256") != INVENTORY_SHA256
        or external_record.get("source_inventory_bytes") != len(inventory_encoded)
        or external_record.get("source_ledger_path") != str(ledger_path)
        or external_record.get("source_ledger_sha256") != LEDGER_SHA256
        or external_record.get("source_ledger_bytes") != len(ledger_encoded)
        or external_record.get("source_ledger_events") != len(events)
        or external_record.get("destination_path") != str(archive_path)
        or external_record.get("terminal_ledger_validated") is not True
        or external_record.get("source_retained") is not True
        or external_record.get("held_descriptor_guard") is not True
        or external_record.get("atomic_finalization") is not True
        or external_record.get("fsync_required") is not True
        or external_record.get("no_internal_fallback") is not True
        or external_record.get("external_mount") != str(APPROVED_MOUNT)
        or external_record.get("external_volume_uuid") != APPROVED_VOLUME_UUID
        or external_record.get("external_physical_store_uuid") != APPROVED_PHYSICAL_STORE_UUID
    ):
        raise L13ContractError("Gate L1.3 external archive evidence drifted")
    if (
        local_record.get("source_inventory_path") != str(inventory_path)
        or local_record.get("source_inventory_sha256") != INVENTORY_SHA256
        or local_record.get("source_inventory_bytes") != len(inventory_encoded)
        or local_record.get("source_ledger_path") != str(ledger_path)
        or local_record.get("source_ledger_sha256") != LEDGER_SHA256
        or local_record.get("source_ledger_bytes") != len(ledger_encoded)
        or local_record.get("source_ledger_events") != len(events)
        or local_record.get("destination_path") != str(archive_path)
        or local_record.get("destination_inventory_sha256") != INVENTORY_SHA256
        or local_record.get("destination_ledger_sha256") != LEDGER_SHA256
        or local_record.get("destination_copy_record_sha256") != COPY_RECORD_SHA256
        or local_record.get("destination_seal_sha256") != SEAL_SHA256
        or local_record.get("external_volume_uuid") != APPROVED_VOLUME_UUID
        or local_record.get("external_physical_store_uuid") != APPROVED_PHYSICAL_STORE_UUID
        or local_record.get("terminal_ledger_validated") is not True
        or local_record.get("held_descriptor_guard") is not True
        or local_record.get("source_destination_sha256_equal") is not True
        or local_record.get("source_retained_until_independent_verification") is not True
    ):
        raise L13ContractError("Gate L1.3 local archive evidence drifted")
    external_floor = _integer(
        external_record.get("external_retained_floor_bytes"),
        context="external retained floor",
    )
    if (
        _integer(
            external_record.get("external_precopy_floor_bytes"),
            context="external precopy floor",
        )
        != external_floor + plan.max_archive_bytes
        or _integer(
            external_record.get("external_precopy_free_bytes"),
            context="external precopy free bytes",
        )
        < external_floor + plan.max_archive_bytes
        or _integer(
            local_record.get("external_postcopy_free_bytes"),
            context="external postcopy free bytes",
        )
        < external_floor
        or local_record.get("external_retained_floor_bytes") != external_floor
        or local_record.get("system_retained_floor_bytes") != plan.local_retained_floor_bytes
        or _integer(
            local_record.get("system_postcopy_free_bytes"),
            context="system postcopy free bytes",
        )
        < plan.local_retained_floor_bytes
    ):
        raise L13ContractError("Gate L1.3 storage floor evidence drifted")

    return GateL2EvidenceValidationL13(
        evidence_valid=True,
        decision_state="inventory-evidence-insufficient",
        historical_selection_state="blocked",
        qualifying_candidate_count=len(
            _sequence(
                candidate_matrix.get("qualifying_candidates"),
                context="qualifying candidates",
            )
        ),
        inventory_sha256=inventory_sha256,
        ledger_sha256=ledger_sha256,
        archive_seal_sha256=seal_sha256,
        external_copy_record_sha256=external_record_sha256,
        local_copy_record_sha256=hashlib.sha256(local_record_encoded).hexdigest(),
        extension_report_sha256=hashlib.sha256(extension_encoded).hexdigest(),
        alias_map_sha256=alias_seal.map_sha256,
        alias_map_seal_sha256=alias_seal.seal_sha256,
    )
