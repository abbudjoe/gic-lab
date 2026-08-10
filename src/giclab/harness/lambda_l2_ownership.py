"""Private launch ownership and exact Lambda instance matching for T07 Gate L2.

This module is deliberately transport inert.  It derives a provider-visible marker
from private randomness and immutable bindings, classifies already supplied instance
documents, and never calls Lambda or reads a secret.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Final


class OwnershipContractError(ValueError):
    """An ownership marker or provider observation is outside the closed contract."""


MIN_MARKER_SEED_BYTES: Final = 20
GENERATED_MARKER_SEED_BYTES: Final = 32
MARKER_FRAGMENT_HEX_LENGTH: Final = 32
OWNERSHIP_TAG_KEY: Final = "giclab-owner"
PURPOSE_TAG_KEY: Final = "giclab-purpose"
PURPOSE_TAG_PREFIX: Final = "t07-host-qualification-"
DOCUMENTED_INSTANCE_STATUSES: Final = frozenset(
    {"booting", "active", "unhealthy", "terminated", "terminating", "preempted"}
)

_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_SAFE_REFERENCE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$")
_SAFE_PROVIDER_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$")
_HOSTNAME = re.compile(r"^[a-z0-9][0-9a-z-]{0,62}$")
_TAG_KEY = re.compile(r"^[a-z][a-z0-9-:]+$")


def canonical_bytes(value: object) -> bytes:
    """Encode one ownership-bound document deterministically."""

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


def _safe_reference(value: str, *, context: str) -> str:
    if _SAFE_REFERENCE.fullmatch(value) is None:
        raise OwnershipContractError(f"{context} is not one safe immutable reference")
    return value


def _sha256(value: str, *, context: str) -> str:
    if _SHA256.fullmatch(value) is None:
        raise OwnershipContractError(f"{context} is not a lowercase SHA-256")
    return value


@dataclass(frozen=True, slots=True)
class OwnershipBinding:
    """Immutable inputs domain-bound into a private single-use marker."""

    plan_id: str
    plan_sha256: str
    authorization_reference: str
    instance_type_name: str
    region_name: str
    image_identity_sha256: str
    ssh_key_identity_sha256: str
    regional_ruleset_identity_sha256: str
    human_decision_seal_sha256: str
    launch_recovery_decision_seal_sha256: str

    def __post_init__(self) -> None:
        for value, context in (
            (self.plan_id, "plan ID"),
            (self.authorization_reference, "authorization reference"),
            (self.instance_type_name, "instance type"),
            (self.region_name, "region"),
        ):
            _safe_reference(value, context=context)
        for value, context in (
            (self.plan_sha256, "plan hash"),
            (self.image_identity_sha256, "image identity hash"),
            (self.ssh_key_identity_sha256, "SSH-key identity hash"),
            (self.regional_ruleset_identity_sha256, "ruleset identity hash"),
            (self.human_decision_seal_sha256, "human-decision seal hash"),
            (
                self.launch_recovery_decision_seal_sha256,
                "launch-recovery decision seal hash",
            ),
        ):
            _sha256(value, context=context)

    def document(self) -> dict[str, str]:
        return {
            "authorization_reference": self.authorization_reference,
            "human_decision_seal_sha256": self.human_decision_seal_sha256,
            "image_identity_sha256": self.image_identity_sha256,
            "instance_type_name": self.instance_type_name,
            "launch_recovery_decision_seal_sha256": (self.launch_recovery_decision_seal_sha256),
            "plan_id": self.plan_id,
            "plan_sha256": self.plan_sha256,
            "region_name": self.region_name,
            "regional_ruleset_identity_sha256": self.regional_ruleset_identity_sha256,
            "ssh_key_identity_sha256": self.ssh_key_identity_sha256,
        }


@dataclass(frozen=True, slots=True)
class OwnedLaunchMarker:
    """Rendered provider fields plus private seed/binding evidence.

    ``seed`` is intentionally excluded from repr and from ``public_document``.
    """

    seed: bytes = field(repr=False)
    binding: OwnershipBinding
    fragment: str
    name: str
    hostname: str
    tags: tuple[tuple[str, str], ...]
    binding_sha256: str
    marker_sha256: str

    def provider_tags(self) -> list[dict[str, str]]:
        return [{"key": key, "value": value} for key, value in self.tags]

    def private_document(self) -> dict[str, object]:
        return {
            "schema_version": "0.1.0",
            "seed_hex": self.seed.hex(),
            "seed_bytes": len(self.seed),
            "binding": self.binding.document(),
            "binding_sha256": self.binding_sha256,
            "fragment": self.fragment,
            "name": self.name,
            "hostname": self.hostname,
            "tags": self.provider_tags(),
            "marker_sha256": self.marker_sha256,
            "single_use": True,
        }

    def public_document(self) -> dict[str, object]:
        return {
            "schema_version": "0.1.0",
            "binding_sha256": self.binding_sha256,
            "marker_sha256": self.marker_sha256,
            "fragment_length": len(self.fragment),
            "name_length": len(self.name),
            "hostname_length": len(self.hostname),
            "tag_keys": [key for key, _value in self.tags],
            "tag_value_lengths": {key: len(value) for key, value in self.tags},
            "random_seed_minimum_bits": MIN_MARKER_SEED_BYTES * 8,
            "single_use": True,
        }


def generate_marker_seed() -> bytes:
    """Generate the future private seed; callers must seal it outside Git."""

    return secrets.token_bytes(GENERATED_MARKER_SEED_BYTES)


def derive_owned_launch_marker(seed: bytes, binding: OwnershipBinding) -> OwnedLaunchMarker:
    """Derive exact Lambda-compatible provider fields from private randomness."""

    if not isinstance(seed, bytes) or len(seed) < MIN_MARKER_SEED_BYTES:
        raise OwnershipContractError("ownership seed contains fewer than 160 random bits")
    binding_bytes = canonical_bytes(binding.document())
    binding_sha256 = hashlib.sha256(binding_bytes).hexdigest()
    digest = hmac.new(
        seed,
        b"giclab:t07:lambda-owned-launch:v1\x00" + binding_bytes,
        hashlib.sha256,
    ).hexdigest()
    fragment = digest[:MARKER_FRAGMENT_HEX_LENGTH]
    name = f"t07-{fragment}"
    hostname = f"t07-{fragment}"
    tags = (
        (OWNERSHIP_TAG_KEY, fragment),
        (PURPOSE_TAG_KEY, f"{PURPOSE_TAG_PREFIX}{fragment}"),
    )
    if len(name) > 64 or _HOSTNAME.fullmatch(hostname) is None:
        raise OwnershipContractError("derived name or hostname violates Lambda constraints")
    if any(
        _TAG_KEY.fullmatch(key) is None or len(key) > 55 or not value or len(value) > 128
        for key, value in tags
    ):
        raise OwnershipContractError("derived tag violates Lambda constraints")
    marker_document = {
        "binding_sha256": binding_sha256,
        "fragment": fragment,
        "hostname": hostname,
        "name": name,
        "tags": [{"key": key, "value": value} for key, value in tags],
    }
    return OwnedLaunchMarker(
        seed=seed,
        binding=binding,
        fragment=fragment,
        name=name,
        hostname=hostname,
        tags=tags,
        binding_sha256=binding_sha256,
        marker_sha256=hashlib.sha256(canonical_bytes(marker_document)).hexdigest(),
    )


@dataclass(frozen=True, slots=True)
class ExpectedOwnedInstance:
    marker: OwnedLaunchMarker
    region_name: str
    instance_type_name: str
    ssh_key_names: tuple[str, ...]
    firewall_ruleset_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if len(self.ssh_key_names) != 1:
            raise OwnershipContractError("owned launch requires exactly one SSH-key name")
        if len(self.firewall_ruleset_ids) != 1:
            raise OwnershipContractError("owned launch requires exactly one ruleset ID")
        for value, context in (
            (self.region_name, "region"),
            (self.instance_type_name, "instance type"),
            (self.ssh_key_names[0], "SSH-key name"),
            (self.firewall_ruleset_ids[0], "ruleset ID"),
        ):
            if _SAFE_PROVIDER_ID.fullmatch(value) is None:
                raise OwnershipContractError(f"{context} is not one safe provider identity")


@dataclass(frozen=True, slots=True)
class InstanceObservation:
    instance_id: str
    name: str | None
    hostname: str | None
    tags: tuple[tuple[str, str], ...]
    region_name: str
    instance_type_name: str
    ssh_key_names: tuple[str, ...]
    firewall_ruleset_ids: tuple[str, ...] | None
    file_system_names: tuple[str, ...]
    file_system_mount_count: int
    status: str


def _required_mapping(value: object, *, context: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or any(not isinstance(key, str) for key in value):
        raise OwnershipContractError(f"{context} is not an object")
    return value


def _required_string(value: object, *, context: str) -> str:
    if not isinstance(value, str) or not value:
        raise OwnershipContractError(f"{context} is not a nonempty string")
    return value


def _string_array(value: object, *, context: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise OwnershipContractError(f"{context} is not a string array")
    return tuple(value)


def parse_instance_observation(document: Mapping[str, object]) -> InstanceObservation:
    """Parse only fields documented by Lambda's current ``Instance`` schema."""

    instance_id = _required_string(document.get("id"), context="instance ID")
    if _SAFE_PROVIDER_ID.fullmatch(instance_id) is None:
        raise OwnershipContractError("instance ID is not one safe provider identity")
    name_value = document.get("name")
    hostname_value = document.get("hostname")
    if name_value is not None and not isinstance(name_value, str):
        raise OwnershipContractError("instance name has an incompatible type")
    if hostname_value is not None and not isinstance(hostname_value, str):
        raise OwnershipContractError("instance hostname has an incompatible type")

    raw_tags = document.get("tags", [])
    if not isinstance(raw_tags, list):
        raise OwnershipContractError("instance tags are not an array")
    tags: list[tuple[str, str]] = []
    seen_tag_keys: set[str] = set()
    for raw_tag in raw_tags:
        tag = _required_mapping(raw_tag, context="instance tag")
        key = _required_string(tag.get("key"), context="instance tag key")
        value = _required_string(tag.get("value"), context="instance tag value")
        if key in seen_tag_keys:
            raise OwnershipContractError("instance contains a duplicate tag key")
        seen_tag_keys.add(key)
        tags.append((key, value))

    region = _required_mapping(document.get("region"), context="instance region")
    instance_type = _required_mapping(document.get("instance_type"), context="instance type")
    raw_rulesets = document.get("firewall_rulesets")
    ruleset_ids: tuple[str, ...] | None
    if raw_rulesets is None:
        ruleset_ids = None
    else:
        if not isinstance(raw_rulesets, list):
            raise OwnershipContractError("instance firewall rulesets are not an array")
        ruleset_ids = tuple(
            _required_string(
                _required_mapping(item, context="firewall ruleset entry").get("id"),
                context="firewall ruleset ID",
            )
            for item in raw_rulesets
        )

    raw_mounts = document.get("file_system_mounts", [])
    if not isinstance(raw_mounts, list):
        raise OwnershipContractError("instance filesystem mounts are not an array")
    status = _required_string(document.get("status"), context="instance status")
    if status not in DOCUMENTED_INSTANCE_STATUSES:
        raise OwnershipContractError("instance status is outside the documented enum")
    return InstanceObservation(
        instance_id=instance_id,
        name=name_value,
        hostname=hostname_value,
        tags=tuple(tags),
        region_name=_required_string(region.get("name"), context="instance region name"),
        instance_type_name=_required_string(
            instance_type.get("name"), context="instance type name"
        ),
        ssh_key_names=_string_array(document.get("ssh_key_names"), context="SSH-key names"),
        firewall_ruleset_ids=ruleset_ids,
        file_system_names=_string_array(
            document.get("file_system_names"), context="filesystem names"
        ),
        file_system_mount_count=len(raw_mounts),
        status=status,
    )


class OwnershipMatch(StrEnum):
    NONE = "none"
    PARTIAL_MARKER = "partial_marker"
    CONFLICTING_DETAILS = "conflicting_details"
    FULL = "full"


def classify_owned_instance(
    observation: InstanceObservation, expected: ExpectedOwnedInstance
) -> OwnershipMatch:
    """Classify one instance without treating IP address or image as ownership."""

    observed_tags = dict(observation.tags)
    expected_tags = dict(expected.marker.tags)
    signals = (
        observation.name == expected.marker.name,
        observation.hostname == expected.marker.hostname,
        observed_tags.get(OWNERSHIP_TAG_KEY) == expected_tags[OWNERSHIP_TAG_KEY],
        observed_tags.get(PURPOSE_TAG_KEY) == expected_tags[PURPOSE_TAG_KEY],
    )
    if not any(signals):
        return OwnershipMatch.NONE
    if not all(signals):
        return OwnershipMatch.PARTIAL_MARKER
    binding_matches = (
        observation.region_name == expected.region_name
        and observation.instance_type_name == expected.instance_type_name
        and observation.ssh_key_names == expected.ssh_key_names
        and observation.firewall_ruleset_ids == expected.firewall_ruleset_ids
        and observation.file_system_names == ()
        and observation.file_system_mount_count == 0
        and observation.status in DOCUMENTED_INSTANCE_STATUSES
    )
    return OwnershipMatch.FULL if binding_matches else OwnershipMatch.CONFLICTING_DETAILS


class DiscoveryKind(StrEnum):
    ZERO_MATCHES = "owned_instance_not_yet_visible"
    ONE_FULL_MATCH = "owned_instance_discovered"
    MULTIPLE_FULL_MATCHES = "provider_duplicate_owned_instances"
    PARTIAL_MARKER = "ownership_collision_or_drift"
    CONFLICTING_DETAILS = "owned_instance_conflicting_details"


@dataclass(frozen=True, slots=True)
class DiscoveryResult:
    kind: DiscoveryKind
    full_match_ids: tuple[str, ...] = field(default=(), repr=False)
    partial_match_count: int = 0
    conflicting_detail_count: int = 0


def classify_discovery(
    documents: Sequence[Mapping[str, object]], expected: ExpectedOwnedInstance
) -> DiscoveryResult:
    """Classify one bounded list response without selecting an unsafe candidate."""

    full_ids: list[str] = []
    partial = 0
    conflicting = 0
    for document in documents:
        observation = parse_instance_observation(document)
        classification = classify_owned_instance(observation, expected)
        if classification is OwnershipMatch.FULL:
            full_ids.append(observation.instance_id)
        elif classification is OwnershipMatch.PARTIAL_MARKER:
            partial += 1
        elif classification is OwnershipMatch.CONFLICTING_DETAILS:
            conflicting += 1
    if conflicting:
        kind = DiscoveryKind.CONFLICTING_DETAILS
    elif partial:
        kind = DiscoveryKind.PARTIAL_MARKER
    elif len(full_ids) > 1:
        kind = DiscoveryKind.MULTIPLE_FULL_MATCHES
    elif len(full_ids) == 1:
        kind = DiscoveryKind.ONE_FULL_MATCH
    else:
        kind = DiscoveryKind.ZERO_MATCHES
    return DiscoveryResult(kind, tuple(full_ids), partial, conflicting)


def require_prelaunch_zero_match(result: DiscoveryResult) -> None:
    """Require zero complete or partial marker evidence before the only launch send."""

    if result.kind is not DiscoveryKind.ZERO_MATCHES:
        raise OwnershipContractError("prelaunch marker collision or prior use is present")


def revalidate_owned_instance_detail(
    document: Mapping[str, object],
    *,
    expected_instance_id: str,
    expected: ExpectedOwnedInstance,
) -> InstanceObservation:
    """Bind one exact ID only after the detail response repeats the full conjunction."""

    observation = parse_instance_observation(document)
    if observation.instance_id != expected_instance_id:
        raise OwnershipContractError("instance detail ID differs from the candidate ID")
    if classify_owned_instance(observation, expected) is not OwnershipMatch.FULL:
        raise OwnershipContractError("instance detail does not revalidate full ownership")
    return observation


def public_instance_projection(observation: InstanceObservation) -> dict[str, object]:
    """Return an alias-only public projection; raw provider IDs and addresses are absent."""

    return {
        "instance_alias": (
            "owned-instance-"
            + hashlib.sha256(observation.instance_id.encode("utf-8")).hexdigest()[:12]
        ),
        "status": observation.status,
        "region_name": observation.region_name,
        "instance_type_name": observation.instance_type_name,
        "ssh_key_count": len(observation.ssh_key_names),
        "firewall_ruleset_count": (
            0 if observation.firewall_ruleset_ids is None else len(observation.firewall_ruleset_ids)
        ),
        "file_system_count": len(observation.file_system_names),
        "file_system_mount_count": observation.file_system_mount_count,
        "full_marker_observed": True,
        "image_observable_in_instance_schema": False,
    }
