from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from giclab.harness.lambda_l2_ownership import (
    DiscoveryKind,
    ExpectedOwnedInstance,
    OwnershipBinding,
    OwnershipContractError,
    OwnershipMatch,
    classify_discovery,
    classify_owned_instance,
    derive_owned_launch_marker,
    parse_instance_observation,
    public_instance_projection,
    require_prelaunch_zero_match,
    revalidate_owned_instance_detail,
)

ROOT = Path(__file__).resolve().parents[1]


def binding(**changes: str) -> OwnershipBinding:
    values = {
        "plan_id": "PLAN-T07-GATE-L2-LAMBDA-HOST-QUALIFICATION-V2",
        "plan_sha256": "1" * 64,
        "authorization_reference": "AUTH-T07-GATE-L2-TEST-0001",
        "instance_type_name": "gpu_1x_a10",
        "region_name": "us-east-1",
        "image_identity_sha256": "2" * 64,
        "ssh_key_identity_sha256": "3" * 64,
        "regional_ruleset_identity_sha256": "4" * 64,
        "human_decision_seal_sha256": "5" * 64,
        "launch_recovery_decision_seal_sha256": "6" * 64,
    }
    values.update(changes)
    return OwnershipBinding(**values)


def expected() -> ExpectedOwnedInstance:
    marker = derive_owned_launch_marker(bytes(range(32)), binding())
    return ExpectedOwnedInstance(
        marker,
        "us-east-1",
        "gpu_1x_a10",
        ("fractal-lambda-codex",),
        ("ruleset-test",),
    )


def instance(
    *,
    instance_id: str = "instance-test",
    name: str | None = None,
    hostname: str | None = None,
    tags: list[dict[str, str]] | None = None,
    region: str = "us-east-1",
    instance_type: str = "gpu_1x_a10",
    ssh_keys: list[str] | None = None,
    rulesets: list[str] | None = None,
    file_system_names: list[str] | None = None,
    file_system_mounts: list[dict[str, str]] | None = None,
    status: str = "booting",
) -> dict[str, object]:
    contract = expected()
    document: dict[str, object] = {
        "id": instance_id,
        "name": contract.marker.name if name is None else name,
        "hostname": contract.marker.hostname if hostname is None else hostname,
        "tags": contract.marker.provider_tags() if tags is None else tags,
        "region": {"name": region},
        "instance_type": {"name": instance_type},
        "ssh_key_names": ["fractal-lambda-codex"] if ssh_keys is None else ssh_keys,
        "firewall_rulesets": [
            {"id": value} for value in (["ruleset-test"] if rulesets is None else rulesets)
        ],
        "file_system_names": [] if file_system_names is None else file_system_names,
        "actions": {},
        "status": status,
    }
    if file_system_mounts is not None:
        document["file_system_mounts"] = file_system_mounts
    return document


def test_marker_rejects_fewer_than_160_seed_bits() -> None:
    with pytest.raises(OwnershipContractError):
        derive_owned_launch_marker(b"short", binding())


def test_marker_is_deterministic_but_every_bound_identity_changes_it() -> None:
    seed = bytes(range(32))
    first = derive_owned_launch_marker(seed, binding())
    same = derive_owned_launch_marker(seed, binding())
    changed = derive_owned_launch_marker(
        seed,
        binding(launch_recovery_decision_seal_sha256="7" * 64),
    )
    assert first == same
    assert first.fragment != changed.fragment


def test_marker_private_schema_passes_and_public_projection_excludes_seed() -> None:
    marker = expected().marker
    schema = json.loads((ROOT / "schemas/t07-lambda-owned-launch-marker.schema.json").read_text())
    assert not list(Draft202012Validator(schema).iter_errors(marker.private_document()))
    public = marker.public_document()
    encoded = json.dumps(public, sort_keys=True)
    assert "seed_hex" not in public
    assert marker.seed.hex() not in encoded
    assert marker.fragment not in encoded


def test_marker_provider_fields_satisfy_exact_limits() -> None:
    marker = expected().marker
    assert len(marker.fragment) == 32
    assert len(marker.name) <= 64
    assert len(marker.hostname) <= 63
    assert [item[0] for item in marker.tags] == ["giclab-owner", "giclab-purpose"]
    assert all(len(key) <= 55 and len(value) <= 128 for key, value in marker.tags)


def test_prelaunch_zero_match_passes_only_for_no_marker_signal() -> None:
    unrelated = instance(name="unrelated", hostname="unrelated", tags=[])
    result = classify_discovery([unrelated], expected())
    require_prelaunch_zero_match(result)
    assert result.kind is DiscoveryKind.ZERO_MATCHES
    with pytest.raises(OwnershipContractError):
        require_prelaunch_zero_match(classify_discovery([instance()], expected()))


def test_exact_full_match_requires_complete_conjunction() -> None:
    observation = parse_instance_observation(instance())
    assert classify_owned_instance(observation, expected()) is OwnershipMatch.FULL


def test_partial_marker_is_not_owned_and_stops_prelaunch() -> None:
    contract = expected()
    partial = instance(
        hostname="unrelated",
        tags=[contract.marker.provider_tags()[0]],
    )
    result = classify_discovery([partial], contract)
    assert result.kind is DiscoveryKind.PARTIAL_MARKER
    assert result.full_match_ids == ()
    with pytest.raises(OwnershipContractError):
        require_prelaunch_zero_match(result)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("region", "us-west-1"),
        ("instance_type", "gpu_2x_a10"),
        ("ssh_keys", ["another-key"]),
        ("rulesets", ["another-ruleset"]),
        ("file_system_names", ["forbidden-filesystem"]),
    ],
)
def test_complete_marker_with_conflicting_bound_detail_is_hard_failure(
    field: str, value: object
) -> None:
    kwargs = {field: value}
    result = classify_discovery([instance(**kwargs)], expected())  # type: ignore[arg-type]
    assert result.kind is DiscoveryKind.CONFLICTING_DETAILS
    assert result.full_match_ids == ()


def test_missing_optional_ruleset_field_cannot_be_full_match() -> None:
    document = instance()
    del document["firewall_rulesets"]
    observation = parse_instance_observation(document)
    assert classify_owned_instance(observation, expected()) is OwnershipMatch.CONFLICTING_DETAILS


def test_duplicate_provider_tag_keys_are_rejected() -> None:
    tag = expected().marker.provider_tags()[0]
    with pytest.raises(OwnershipContractError):
        parse_instance_observation(instance(tags=[tag, tag]))


def test_multiple_full_matches_are_never_silently_selected() -> None:
    result = classify_discovery(
        [instance(instance_id="instance-one"), instance(instance_id="instance-two")],
        expected(),
    )
    assert result.kind is DiscoveryKind.MULTIPLE_FULL_MATCHES
    assert result.full_match_ids == ("instance-one", "instance-two")


def test_detail_revalidation_requires_exact_candidate_id() -> None:
    with pytest.raises(OwnershipContractError):
        revalidate_owned_instance_detail(
            instance(instance_id="instance-one"),
            expected_instance_id="instance-two",
            expected=expected(),
        )


def test_detail_revalidation_does_not_falsely_require_image_field() -> None:
    document = instance()
    assert "image" not in document
    observation = revalidate_owned_instance_detail(
        document,
        expected_instance_id="instance-test",
        expected=expected(),
    )
    assert observation.instance_id == "instance-test"


def test_undocumented_status_is_rejected() -> None:
    with pytest.raises(OwnershipContractError):
        parse_instance_observation(instance(status="mystery"))


def test_public_projection_excludes_raw_id_ip_tags_and_key_name() -> None:
    document = instance()
    document["ip"] = "203.0.113.10"
    observation = parse_instance_observation(document)
    projected = public_instance_projection(observation)
    encoded = json.dumps(projected, sort_keys=True)
    for forbidden in (
        "instance-test",
        "203.0.113.10",
        "fractal-lambda-codex",
        expected().marker.fragment,
    ):
        assert forbidden not in encoded
    assert projected["image_observable_in_instance_schema"] is False


def test_expected_contract_rejects_multiple_ssh_keys_or_rulesets() -> None:
    contract = expected()
    with pytest.raises(OwnershipContractError):
        replace(contract, ssh_key_names=("key-one", "key-two"))
    with pytest.raises(OwnershipContractError):
        replace(contract, firewall_ruleset_ids=())
