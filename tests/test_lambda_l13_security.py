from __future__ import annotations

import ast
import base64
import hashlib
import json
import stat
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest
from harness_test_support import materialize_git_tree, materialize_worktree_files

from giclab.harness.lambda_inventory_plan_v3 import (
    InventoryRunBindingV3,
    load_inventory_plan_v3,
)
from giclab.harness.lambda_l13_security import (
    COPY_RECORD_SHA256,
    INVENTORY_SHA256,
    LEDGER_SHA256,
    PLAN_SHA256,
    PUBLIC_IPV4_PLACEHOLDER,
    SCHEMA_EXTENSION_REPORT_SHA256,
    SEAL_SHA256,
    AccountSSHKeyMaterial,
    FirewallInstanceIdentity,
    FirewallInstanceTerminalEvidence,
    FirewallPreconditionsEvidence,
    FirewallReplacementEvent,
    FirewallReplacementPhase,
    FirewallReplacementState,
    FirewallRulesSnapshot,
    L13ContractError,
    LocalPublicKey,
    _retained_absolute_path_matches,
    build_resource_candidate_matrix,
    capture_firewall_rules_snapshot,
    firewall_assessment_document,
    host_key_trust_decision_document,
    inspect_local_public_keys,
    project_image_identities,
    ssh_key_match_document,
    strict_firewall_replacement_request,
    transition_firewall_replacement,
    validate_alias_map_evidence,
    validate_l13_gate_l2_evidence,
    validate_supplemental_l2_decision_evidence,
    verify_bound_run_bytes,
    write_sealed_alias_map,
    write_sealed_firewall_snapshot,
)
from giclab.validation import validate_instance

ROOT = Path(__file__).resolve().parents[1]


def _image(
    raw_id: str,
    *,
    region: str = "us-test-1",
    name: str = "Synthetic image",
    family: str = "gpu-base-22-04",
    version: str = "synthetic-v1",
    architecture: str = "x86_64",
) -> dict[str, object]:
    return {
        "id": raw_id,
        "name": name,
        "family": family,
        "version": version,
        "architecture": architecture,
        "region": {"name": region},
    }


def _offer(
    name: str,
    *,
    regions: tuple[str, ...] = ("us-test-1",),
    architecture: str = "x86_64",
    price: int = 100,
    vcpus: int = 8,
    memory_gib: int = 16,
    storage_gib: int = 100,
    gpus: int = 1,
) -> dict[str, object]:
    return {
        "name": name,
        "architecture": architecture,
        "price_cents_per_hour": price,
        "specs": {
            "vcpus": vcpus,
            "memory_gib": memory_gib,
            "storage_gib": storage_gib,
            "gpus": gpus,
        },
        "capacity_regions": [{"name": region} for region in regions],
    }


def _inventory(
    *,
    offers: list[dict[str, object]] | None = None,
    firewall_rules: list[dict[str, object]] | None = None,
    running_instances: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return {
        "instance_types": offers or [_offer("gpu_1x_synthetic")],
        "firewall_rulesets": [
            {
                "id": "global",
                "name": "Synthetic global",
                "scope": "global",
                "region_name": None,
                "ssh_only": True,
                "rules": firewall_rules
                or [
                    {
                        "protocol": "tcp",
                        "port_range": [22, 22],
                        "source_network": "8.8.8.8/32",
                        "description": "Synthetic SSH",
                    }
                ],
            }
        ],
        "running_instances": running_instances or [],
    }


def _public_key(blob: bytes, *, algorithm: str = "ssh-ed25519") -> str:
    def wire(value: bytes) -> bytes:
        return len(value).to_bytes(4, "big") + value

    material = hashlib.sha256(blob).digest()
    if algorithm == "ssh-ed25519":
        encoded = wire(algorithm.encode()) + wire(material)
    elif algorithm == "ssh-rsa":
        encoded = wire(algorithm.encode()) + wire(b"\x01\x00\x01") + wire(material * 8)
    else:
        raise AssertionError("unsupported synthetic public-key algorithm")
    return f"{algorithm} {base64.b64encode(encoded).decode()} synthetic-comment"


def _canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
        + b"\n"
    )


def _prepare_alias_root(tmp_path: Path) -> Path:
    (tmp_path / ".gitignore").write_text("artifacts/\n")
    return tmp_path / "artifacts/t07/lambda/gate-l1-3/RUN-T07-L1-LAMBDA-INVENTORY-0003"


def _firewall_response(rules: list[dict[str, object]]) -> bytes:
    return _canonical_bytes({"data": {"id": "global", "name": "Synthetic global", "rules": rules}})


def _strict_firewall_rules(source: str = "8.8.8.8/32") -> list[dict[str, object]]:
    return [
        {
            "description": "T07 temporary qualification SSH",
            "port_range": [22, 22],
            "protocol": "tcp",
            "source_network": source,
        }
    ]


def _write_firewall_evidence(
    tmp_path: Path,
    snapshot: FirewallRulesSnapshot,
    *,
    ordinal: int,
):
    ignore = tmp_path / ".gitignore"
    if not ignore.exists():
        ignore.write_text("artifacts/\n")
    run_id = f"RUN-T07-L2-LAMBDA-QUALIFICATION-{ordinal:04d}"
    evidence_root = tmp_path / "artifacts/t07/lambda/gate-l2" / run_id / "firewall-snapshot"
    return write_sealed_firewall_snapshot(
        evidence_root,
        repository_root=tmp_path,
        run_id=run_id,
        snapshot=snapshot,
    )


def test_distinct_raw_ids_survive_naive_redaction_collision_as_distinct_aliases() -> None:
    rows = [
        _image("raw-image-alpha", name="same", family="same"),
        _image("raw-image-beta", name="same", family="same"),
    ]
    projection = project_image_identities(rows)
    assert len(projection.images) == 2
    assert len({item.alias for item in projection.images}) == 2
    assert projection.family_name_groups_with_distinct_ids == 1


def test_exact_duplicate_row_collapses_with_multiplicity_and_source_indices() -> None:
    projection = project_image_identities([_image("raw-image-alpha"), _image("raw-image-alpha")])
    image = projection.images[0]
    assert len(image.availability) == 1
    assert image.availability[0].multiplicity == 2
    assert image.availability[0].source_indices == (1, 2)
    assert projection.exact_duplicate_group_count == 1
    assert projection.exact_duplicate_extra_rows == 1


def test_same_raw_id_with_conflicting_intrinsic_metadata_hard_fails() -> None:
    with pytest.raises(L13ContractError, match="conflicting intrinsic metadata"):
        project_image_identities(
            [
                _image("raw-image-alpha", family="gpu-base-22-04"),
                _image("raw-image-alpha", family="another-family"),
            ]
        )


def test_same_raw_id_across_regions_is_one_identity_with_availability_set() -> None:
    projection = project_image_identities(
        [
            _image("raw-image-alpha", region="us-east-1"),
            _image("raw-image-alpha", region="us-west-1"),
        ]
    )
    assert len(projection.images) == 1
    assert [item.region_name for item in projection.images[0].availability] == [
        "us-east-1",
        "us-west-1",
    ]
    assert projection.region_availability_group_count == 1


def test_duplicate_family_name_with_different_ids_remains_distinct() -> None:
    projection = project_image_identities([_image("raw-image-alpha"), _image("raw-image-beta")])
    assert projection.unique_raw_id_count == 2
    assert len(projection.images) == 2
    assert projection.family_name_groups_with_distinct_ids == 1


def test_aliases_and_public_projection_contain_no_raw_id_or_raw_id_hash() -> None:
    raw_ids = ("raw-image-alpha", "raw-image-beta")
    projection = project_image_identities([_image(value) for value in raw_ids])
    encoded = json.dumps(projection.public_images(), sort_keys=True).encode()
    for raw_id in raw_ids:
        assert raw_id.encode() not in encoded
        assert hashlib.sha256(raw_id.encode()).hexdigest().encode() not in encoded
    assert [item.alias for item in projection.images] == ["img-0001", "img-0002"]


def test_raw_alias_map_is_exclusive_ignored_style_sealed_evidence(tmp_path: Path) -> None:
    projection = project_image_identities([_image("raw-image-alpha")])
    root = _prepare_alias_root(tmp_path)
    seal = write_sealed_alias_map(
        root,
        repository_root=tmp_path,
        projection=projection,
        inventory_sha256=INVENTORY_SHA256,
    )
    assert stat.S_IMODE(seal.map_path.stat().st_mode) == 0o400
    assert stat.S_IMODE(seal.seal_path.stat().st_mode) == 0o400
    assert seal.map_sha256 == hashlib.sha256(seal.map_path.read_bytes()).hexdigest()
    assert b"raw-image-alpha" in seal.map_path.read_bytes()
    assert b"raw-image-alpha" not in seal.seal_path.read_bytes()
    with pytest.raises(FileExistsError):
        write_sealed_alias_map(
            root,
            repository_root=tmp_path,
            projection=projection,
            inventory_sha256=INVENTORY_SHA256,
        )


def test_alias_writer_rejects_path_escape_and_symlink_ancestor(tmp_path: Path) -> None:
    projection = project_image_identities([_image("raw-image-alpha")])
    (tmp_path / ".gitignore").write_text("artifacts/\n")
    with pytest.raises(L13ContractError, match="escaped"):
        write_sealed_alias_map(
            tmp_path / "somewhere-else",
            repository_root=tmp_path,
            projection=projection,
            inventory_sha256=INVENTORY_SHA256,
        )
    outside = tmp_path / "outside"
    outside.mkdir()
    (tmp_path / "artifacts").symlink_to(outside, target_is_directory=True)
    with pytest.raises(OSError):
        write_sealed_alias_map(
            _prepare_alias_root(tmp_path),
            repository_root=tmp_path,
            projection=projection,
            inventory_sha256=INVENTORY_SHA256,
        )


def test_alias_writer_reserves_reader_capacity_before_creating_run_root(tmp_path: Path) -> None:
    root = _prepare_alias_root(tmp_path)
    projection = project_image_identities(
        [_image(f"synthetic-raw-image-{index:05d}") for index in range(2_000)]
    )
    with pytest.raises(L13ContractError, match="byte cap"):
        write_sealed_alias_map(
            root,
            repository_root=tmp_path,
            projection=projection,
            inventory_sha256=INVENTORY_SHA256,
        )
    assert not root.exists()


def _rewrite_alias_evidence(
    root: Path,
    entries: list[dict[str, str]],
) -> dict[str, object]:
    map_path = root / "image-id-alias-map.json"
    seal_path = root / "IMAGE_ALIAS_MAP_SEAL.json"
    map_document = {
        "schema_version": "0.1.0",
        "run_id": "RUN-T07-L1-LAMBDA-INVENTORY-0003",
        "source_inventory_sha256": INVENTORY_SHA256,
        "entries": entries,
    }
    map_encoded = _canonical_bytes(map_document)
    map_sha256 = hashlib.sha256(map_encoded).hexdigest()
    seal_document = {
        "schema_version": "0.1.0",
        "run_id": "RUN-T07-L1-LAMBDA-INVENTORY-0003",
        "source_inventory_sha256": INVENTORY_SHA256,
        "map_path": map_path.name,
        "map_bytes": len(map_encoded),
        "map_sha256": map_sha256,
        "alias_count": 1,
        "raw_ids_in_seal": False,
    }
    seal_encoded = _canonical_bytes(seal_document)
    for path, encoded in ((map_path, map_encoded), (seal_path, seal_encoded)):
        path.chmod(0o600)
        path.write_bytes(encoded)
        path.chmod(0o400)
    return {
        "state": "ignored-sealed-local-evidence",
        "path": str(path := root.relative_to(root.parents[4]) / map_path.name),
        "bytes": len(map_encoded),
        "sha256": map_sha256,
        "seal_path": str(path.parent / seal_path.name),
        "seal_bytes": len(seal_encoded),
        "seal_sha256": hashlib.sha256(seal_encoded).hexdigest(),
        "alias_count": 1,
        "raw_ids_committed": False,
        "raw_id_hashes_committed": False,
    }


def test_alias_loader_binds_exact_map_to_projection_and_rejects_missing_or_symlink(
    tmp_path: Path,
) -> None:
    projection = project_image_identities([_image("raw-image-alpha")])
    root = _prepare_alias_root(tmp_path)
    seal = write_sealed_alias_map(
        root,
        repository_root=tmp_path,
        projection=projection,
        inventory_sha256=INVENTORY_SHA256,
    )
    public = seal.public_document(repository_root=tmp_path)
    assert (
        validate_alias_map_evidence(
            tmp_path,
            projection=projection,
            public_record=public,
        ).map_sha256
        == seal.map_sha256
    )
    map_path = seal.map_path
    map_path.chmod(0o600)
    map_path.unlink()
    with pytest.raises(L13ContractError, match="missing or unsafe"):
        validate_alias_map_evidence(
            tmp_path,
            projection=projection,
            public_record=public,
        )
    outside = tmp_path / "outside-map"
    outside.write_text("{}")
    map_path.symlink_to(outside)
    with pytest.raises(L13ContractError, match="missing or unsafe"):
        validate_alias_map_evidence(
            tmp_path,
            projection=projection,
            public_record=public,
        )


@pytest.mark.parametrize(
    "entries",
    [
        [
            {"raw_image_id": "raw-image-alpha", "alias": "img-0001"},
            {"raw_image_id": "raw-image-alpha", "alias": "img-0001"},
        ],
        [{"raw_image_id": "raw-image-alpha", "alias": "img-9999"}],
    ],
)
def test_alias_loader_rejects_hash_recorded_duplicate_or_wrong_mapping(
    tmp_path: Path,
    entries: list[dict[str, str]],
) -> None:
    projection = project_image_identities([_image("raw-image-alpha")])
    root = _prepare_alias_root(tmp_path)
    write_sealed_alias_map(
        root,
        repository_root=tmp_path,
        projection=projection,
        inventory_sha256=INVENTORY_SHA256,
    )
    public = _rewrite_alias_evidence(root, entries)
    with pytest.raises(L13ContractError, match="semantic binding"):
        validate_alias_map_evidence(
            tmp_path,
            projection=projection,
            public_record=public,
        )


def test_typed_supplemental_verifier_passes_valid_aliases_and_rejects_ambiguity() -> None:
    projection = project_image_identities([_image("raw-image-alpha")])
    inventory = _inventory()
    matrix = build_resource_candidate_matrix(inventory, projection)
    validate_supplemental_l2_decision_evidence(
        inventory,
        projection=projection,
        candidate_matrix=matrix,
    )
    drifted = deepcopy(matrix)
    drifted["qualifying_candidates"][0]["image_alias"] = "img-9999"
    with pytest.raises(L13ContractError, match="matrix drifted"):
        validate_supplemental_l2_decision_evidence(
            inventory,
            projection=projection,
            candidate_matrix=drifted,
        )


def test_candidate_selection_obeys_thresholds_price_order_and_image_compatibility() -> None:
    projection = project_image_identities(
        [
            _image("raw-image-beta", region="us-test-1"),
            _image("raw-image-alpha", region="us-test-1"),
            _image("raw-image-other", region="other-1"),
        ]
    )
    inventory = _inventory(
        offers=[
            _offer("gpu_1x_expensive", price=151),
            _offer("gpu_1x_second", price=120),
            _offer("gpu_1x_first", price=100),
            _offer("gpu_1x_unavailable", price=69, regions=()),
            _offer("gpu_2x_disallowed", price=90, gpus=2),
            _offer("gpu_1x_wrong_region", price=80, regions=("missing-1",)),
        ]
    )
    matrix = build_resource_candidate_matrix(inventory, projection)
    candidates = matrix["qualifying_candidates"]
    assert [item["instance_type_name"] for item in candidates[:2]] == [
        "gpu_1x_first",
        "gpu_1x_first",
    ]
    assert [item["image_alias"] for item in candidates[:2]] == [
        "img-0001",
        "img-0002",
    ]
    reasons = {item["instance_type_name"]: item["reasons"] for item in matrix["near_misses"]}
    assert "price-over-150-cents-per-hour" in reasons["gpu_1x_expensive"]
    assert "currently-unavailable" in reasons["gpu_1x_unavailable"]
    assert "multi-gpu-excluded" in reasons["gpu_2x_disallowed"]
    assert "no-compatible-approved-image" in reasons["gpu_1x_wrong_region"]
    assert matrix["candidate_selected"] is False
    assert matrix["fresh_price_and_availability_revalidation_required"] is True


def test_us_south_1_is_never_automatically_eligible() -> None:
    projection = project_image_identities([_image("raw-image-alpha", region="us-south-1")])
    matrix = build_resource_candidate_matrix(
        _inventory(offers=[_offer("gpu_1x_synthetic", regions=("us-south-1",))]),
        projection,
    )
    assert matrix["qualifying_candidates"] == []
    assert matrix["near_misses"][0]["reasons"] == ["firewall-exception-region-not-auto-selectable"]


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"architecture": "arm64"}, "architecture-not-x86_64"),
        ({"vcpus": 7}, "vcpus-below-8"),
        ({"memory_gib": 15}, "memory-below-16-gib"),
        ({"storage_gib": 99}, "root-storage-below-100-gib"),
        ({"price": 151}, "price-over-150-cents-per-hour"),
        ({"gpus": 2}, "multi-gpu-excluded"),
    ],
)
def test_candidate_policy_rejects_each_independent_boundary(
    overrides: dict[str, object],
    reason: str,
) -> None:
    projection = project_image_identities([_image("raw-image-alpha")])
    offer = _offer("boundary-failure", **overrides)  # type: ignore[arg-type]
    matrix = build_resource_candidate_matrix(_inventory(offers=[offer]), projection)
    assert matrix["qualifying_candidates"] == []
    assert reason in matrix["near_misses"][0]["reasons"]


def test_candidate_exact_thresholds_and_full_tie_break_are_eligible() -> None:
    projection = project_image_identities(
        [
            _image("raw-image-beta", region="us-east-1"),
            _image("raw-image-alpha", region="us-east-1"),
            _image("raw-image-alpha", region="us-west-1"),
            _image("raw-image-alpha", region="us-south-1"),
        ]
    )
    inventory = _inventory(
        offers=[
            _offer(
                "type-b",
                price=150,
                vcpus=8,
                memory_gib=16,
                storage_gib=100,
                regions=("us-west-1", "us-east-1", "us-south-1"),
            ),
            _offer(
                "type-a",
                price=150,
                vcpus=8,
                memory_gib=16,
                storage_gib=100,
                regions=("us-west-1", "us-east-1"),
            ),
        ]
    )
    matrix = build_resource_candidate_matrix(inventory, projection)
    candidates = matrix["qualifying_candidates"]
    assert [
        (
            row["price_cents_per_hour"],
            row["instance_type_name"],
            row["region_name"],
            row["image_alias"],
        )
        for row in candidates
    ] == sorted(
        (
            row["price_cents_per_hour"],
            row["instance_type_name"],
            row["region_name"],
            row["image_alias"],
        )
        for row in candidates
    )
    assert matrix["top_three"] == candidates[:3]
    assert any(
        row["region_name"] == "us-south-1"
        and row["reasons"] == ["firewall-exception-region-not-auto-selectable"]
        for row in matrix["near_misses"]
    )


def test_public_key_fingerprint_unique_match_and_no_private_read(tmp_path: Path) -> None:
    ssh_root = tmp_path / ".ssh"
    ssh_root.mkdir()
    public_path = ssh_root / "dedicated.pub"
    private_path = ssh_root / "dedicated"
    public_value = _public_key(b"public-blob-one")
    public_path.write_text(public_value)
    private_path.write_text("PRIVATE-CANARY-MUST-NOT-BE-OPENED")
    private_path.chmod(0o000)

    local = inspect_local_public_keys(ssh_root)
    assert local[0].same_stem_private_file_present
    document = ssh_key_match_document(
        [AccountSSHKeyMaterial("dedicated-account-key", public_value)],
        local,
    )
    assert document["recommended_lambda_key_name"] == "dedicated-account-key"
    assert document["account_key_matches"][0]["match_state"] == "unique_match"
    assert "PRIVATE-CANARY" not in json.dumps(document)
    assert document["private_key_bytes_accessed"] is False


def test_public_key_inspection_rejects_symlink_and_lstat_open_swap(tmp_path: Path) -> None:
    ssh_root = tmp_path / ".ssh"
    ssh_root.mkdir()
    outside = tmp_path / "outside.pub"
    outside.write_text(_public_key(b"outside"))
    (ssh_root / "direct.pub").symlink_to(outside)
    with pytest.raises(L13ContractError, match="single-link regular file"):
        inspect_local_public_keys(ssh_root)
    (ssh_root / "direct.pub").unlink()
    target = ssh_root / "swap.pub"
    target.write_text(_public_key(b"before-swap"))

    def swap(name: str) -> None:
        assert name == "swap.pub"
        target.unlink()
        target.symlink_to(outside)

    with pytest.raises(L13ContractError, match="rejected path drift"):
        inspect_local_public_keys(ssh_root, _pre_open_hook=swap)


@pytest.mark.parametrize("failure", ["algorithm-mismatch", "trailing-wire-bytes"])
def test_public_key_parser_rejects_malformed_wire_encoding(
    tmp_path: Path,
    failure: str,
) -> None:
    ssh_root = tmp_path / ".ssh"
    ssh_root.mkdir()
    valid = _public_key(b"valid")
    algorithm, encoded, _ = valid.split()
    blob = base64.b64decode(encoded)
    if failure == "algorithm-mismatch":
        text = f"ssh-rsa {encoded} synthetic"
    else:
        text = f"{algorithm} {base64.b64encode(blob + b'x').decode()} synthetic"
    (ssh_root / "bad.pub").write_text(text)
    with pytest.raises(L13ContractError):
        inspect_local_public_keys(ssh_root)


def test_ssh_zero_multiple_and_unavailable_matches_stay_blocked(tmp_path: Path) -> None:
    ssh_root = tmp_path / ".ssh"
    ssh_root.mkdir()
    (ssh_root / "one.pub").write_text(_public_key(b"same-public-blob"))
    (ssh_root / "two.pub").write_text(_public_key(b"same-public-blob"))
    local = inspect_local_public_keys(ssh_root)
    document = ssh_key_match_document(
        [
            AccountSSHKeyMaterial("multiple", _public_key(b"same-public-blob")),
            AccountSSHKeyMaterial("zero", _public_key(b"different-public-blob")),
            AccountSSHKeyMaterial("missing-evidence", None),
        ],
        local,
    )
    states = {row["lambda_key_name"]: row["match_state"] for row in document["account_key_matches"]}
    assert states == {
        "multiple": "multiple_matches",
        "zero": "no_match",
        "missing-evidence": "evidence_unavailable",
    }
    assert document["recommended_lambda_key_name"] is None
    assert document["selection_state"] == "blocked"


def test_global_firewall_is_sanitized_and_non_ssh_exposure_blocks_strictness() -> None:
    document = firewall_assessment_document(
        _inventory(
            firewall_rules=[
                {
                    "protocol": "tcp",
                    "port_range": [22, 22],
                    "source_network": "8.8.8.8/32",
                    "description": "free-form value must not survive",
                },
                {
                    "protocol": "udp",
                    "port_range": [5000, 5000],
                    "source_network": "0.0.0.0/0",
                    "description": "another free-form value",
                },
            ]
        )
    )
    assert document["strict_qualification_firewall"] is False
    assert document["per_instance_ruleset_alone_is_sufficient"] is False
    assert document["global_and_per_instance_rules_are_additive"] is True
    assert document["regional_ruleset_count_observed"] == 0
    assert document["strict_regional_ruleset_present"] is False
    assert document["regional_ruleset_is_additive_only"] is True
    assert document["regional_ruleset_requirement_state"] == ("missing-separate-decision-required")
    assert document["rules"][0]["source_scope_class"] == "single-ipv4"
    assert document["rules"][1]["source_scope_class"] == "any-ipv4"
    assert document["rules"][1]["is_non_ssh_exposure"] is True
    assert "source_is_public_ipv4" not in document["rules"][0]
    encoded = json.dumps(document)
    assert "8.8.8.8" not in encoded
    assert "0.0.0.0" not in encoded
    assert "free-form value" not in encoded


def test_exact_single_public_ipv4_ssh_rule_requires_exact_user_approval() -> None:
    assert firewall_assessment_document(_inventory())["strict_qualification_firewall"] is False
    document = firewall_assessment_document(_inventory(), approved_public_ipv4_cidr="8.8.8.8/32")
    assert document["strict_qualification_firewall"] is True
    assert document["public_ipv4_placeholder"] == PUBLIC_IPV4_PLACEHOLDER
    with pytest.raises(L13ContractError, match="canonical public /32"):
        firewall_assessment_document(_inventory(), approved_public_ipv4_cidr="192.0.2.1/32")
    with pytest.raises(L13ContractError, match="canonical public /32"):
        firewall_assessment_document(_inventory(), approved_public_ipv4_cidr="224.0.0.1/32")


def test_no_running_instance_precondition_is_explicit() -> None:
    clear = firewall_assessment_document(_inventory())
    occupied = firewall_assessment_document(
        _inventory(running_instances=[{"id": "synthetic-running"}])
    )
    assert clear["no_running_instance_precondition_met"] is True
    assert occupied["no_running_instance_precondition_met"] is False


def test_temporary_global_replacement_restores_or_enters_incident(tmp_path: Path) -> None:
    original = capture_firewall_rules_snapshot(
        _firewall_response(
            [
                {
                    "description": "Original SSH",
                    "port_range": [22, 22],
                    "protocol": "tcp",
                    "source_network": "8.8.4.4/32",
                },
                {
                    "description": "Original custom",
                    "port_range": [8210, 8210],
                    "protocol": "tcp",
                    "source_network": "8.8.4.4/32",
                },
            ]
        )
    )
    replacement = strict_firewall_replacement_request("8.8.8.8/32")
    sealed_original = _write_firewall_evidence(tmp_path, original, ordinal=1)
    raw_snapshot_path = tmp_path / sealed_original.snapshot_artifact_relative_path
    raw_seal_path = tmp_path / sealed_original.seal_relative_path
    assert raw_snapshot_path.read_bytes() == original.response_bytes
    assert stat.S_IMODE(raw_snapshot_path.stat().st_mode) == 0o400
    assert stat.S_IMODE(raw_seal_path.stat().st_mode) == 0o400
    assert sealed_original.directory_fsync_completed is True
    observed_strict = capture_firewall_rules_snapshot(_firewall_response(_strict_firewall_rules()))
    state = transition_firewall_replacement(
        FirewallReplacementState(),
        FirewallReplacementEvent.PRECONDITIONS_VERIFIED,
        evidence=FirewallPreconditionsEvidence(
            running_instance_count_account_wide=0,
            workspace_dependency_attested=True,
            approved_public_ipv4_cidr="8.8.8.8/32",
            observation_sha256="1" * 64,
        ),
    )
    state = transition_firewall_replacement(
        state,
        FirewallReplacementEvent.ORIGINAL_SNAPSHOT_SEALED,
        evidence=sealed_original,
    )
    state = transition_firewall_replacement(
        state,
        FirewallReplacementEvent.REPLACEMENT_REQUESTED,
        evidence=replacement,
    )
    state = transition_firewall_replacement(
        state,
        FirewallReplacementEvent.REPLACEMENT_VERIFIED,
        evidence=observed_strict,
    )
    state = transition_firewall_replacement(
        state,
        FirewallReplacementEvent.INSTANCE_LAUNCHED,
        evidence=FirewallInstanceIdentity(
            instance_id="synthetic-instance",
            launch_evidence_sha256="2" * 64,
        ),
    )
    state = transition_firewall_replacement(
        state,
        FirewallReplacementEvent.QUALIFICATION_FINISHED,
    )
    assert state.phase is FirewallReplacementPhase.INSTANCE_TERMINATION_REQUIRED
    with pytest.raises(L13ContractError, match="transition is unsafe"):
        transition_firewall_replacement(
            state,
            FirewallReplacementEvent.RESTORE_REQUESTED,
        )
    with pytest.raises(L13ContractError, match="does not close"):
        transition_firewall_replacement(
            state,
            FirewallReplacementEvent.INSTANCE_TERMINATED,
            evidence=FirewallInstanceTerminalEvidence(
                instance_id="wrong-instance",
                terminal_state="terminated",
                terminal_evidence_sha256="3" * 64,
            ),
        )
    state = transition_firewall_replacement(
        state,
        FirewallReplacementEvent.INSTANCE_TERMINATED,
        evidence=FirewallInstanceTerminalEvidence(
            instance_id="synthetic-instance",
            terminal_state="terminated",
            terminal_evidence_sha256="3" * 64,
        ),
    )
    state = transition_firewall_replacement(
        state,
        FirewallReplacementEvent.RESTORE_REQUESTED,
    )
    assert state.phase is FirewallReplacementPhase.RESTORE_PENDING
    with pytest.raises(L13ContractError, match="does not equal original"):
        transition_firewall_replacement(
            state,
            FirewallReplacementEvent.RESTORE_VERIFIED,
            evidence=observed_strict,
        )
    closed = transition_firewall_replacement(
        state,
        FirewallReplacementEvent.RESTORE_VERIFIED,
        evidence=capture_firewall_rules_snapshot(original.response_bytes),
    )
    assert closed.phase is FirewallReplacementPhase.CLOSED
    incident = transition_firewall_replacement(
        state,
        FirewallReplacementEvent.RESTORE_FAILED,
    )
    assert incident.phase is FirewallReplacementPhase.INCIDENT


def test_launch_before_strict_verification_and_relaunch_before_restore_are_rejected() -> None:
    with pytest.raises(L13ContractError, match="transition is unsafe"):
        transition_firewall_replacement(
            FirewallReplacementState(phase=FirewallReplacementPhase.PRECONDITIONS_VERIFIED),
            FirewallReplacementEvent.REPLACEMENT_REQUESTED,
        )
    with pytest.raises(L13ContractError, match="transition is unsafe"):
        transition_firewall_replacement(
            FirewallReplacementState(phase=FirewallReplacementPhase.REPLACEMENT_PENDING),
            FirewallReplacementEvent.INSTANCE_LAUNCHED,
        )
    with pytest.raises(L13ContractError, match="transition is unsafe"):
        transition_firewall_replacement(
            FirewallReplacementState(phase=FirewallReplacementPhase.RESTORE_REQUIRED),
            FirewallReplacementEvent.INSTANCE_LAUNCHED,
        )


def test_raw_snapshot_is_revalidated_immediately_before_first_mutation(
    tmp_path: Path,
) -> None:
    state = transition_firewall_replacement(
        FirewallReplacementState(),
        FirewallReplacementEvent.PRECONDITIONS_VERIFIED,
        evidence=FirewallPreconditionsEvidence(
            running_instance_count_account_wide=0,
            workspace_dependency_attested=True,
            approved_public_ipv4_cidr="8.8.8.8/32",
            observation_sha256="6" * 64,
        ),
    )
    snapshot = capture_firewall_rules_snapshot(
        _firewall_response(_strict_firewall_rules("8.8.4.4/32"))
    )
    sealed = _write_firewall_evidence(tmp_path, snapshot, ordinal=6)
    state = transition_firewall_replacement(
        state,
        FirewallReplacementEvent.ORIGINAL_SNAPSHOT_SEALED,
        evidence=sealed,
    )
    (tmp_path / sealed.snapshot_artifact_relative_path).unlink()
    with pytest.raises(L13ContractError, match="missing or unsafe"):
        transition_firewall_replacement(
            state,
            FirewallReplacementEvent.REPLACEMENT_REQUESTED,
            evidence=strict_firewall_replacement_request("8.8.8.8/32"),
        )


def test_firewall_state_rejects_tampered_evidence_and_nonzero_account_state(
    tmp_path: Path,
) -> None:
    preconditions = FirewallPreconditionsEvidence(
        running_instance_count_account_wide=0,
        workspace_dependency_attested=True,
        approved_public_ipv4_cidr="8.8.8.8/32",
        observation_sha256="4" * 64,
    )
    with pytest.raises(L13ContractError, match="preconditions"):
        transition_firewall_replacement(
            FirewallReplacementState(),
            FirewallReplacementEvent.PRECONDITIONS_VERIFIED,
            evidence=replace(preconditions, running_instance_count_account_wide=1),
        )
    state = transition_firewall_replacement(
        FirewallReplacementState(),
        FirewallReplacementEvent.PRECONDITIONS_VERIFIED,
        evidence=preconditions,
    )
    snapshot = capture_firewall_rules_snapshot(
        _firewall_response(_strict_firewall_rules("8.8.4.4/32"))
    )
    with pytest.raises(L13ContractError, match="escaped"):
        write_sealed_firewall_snapshot(
            tmp_path / "outside-firewall-evidence",
            repository_root=tmp_path,
            run_id="RUN-T07-L2-LAMBDA-QUALIFICATION-0002",
            snapshot=snapshot,
        )
    sealed = _write_firewall_evidence(tmp_path, snapshot, ordinal=2)
    seal_only = _write_firewall_evidence(tmp_path, snapshot, ordinal=3)
    (tmp_path / seal_only.snapshot_artifact_relative_path).unlink()
    with pytest.raises(L13ContractError, match="missing or unsafe"):
        transition_firewall_replacement(
            state,
            FirewallReplacementEvent.ORIGINAL_SNAPSHOT_SEALED,
            evidence=seal_only,
        )
    tampered_snapshot = _write_firewall_evidence(tmp_path, snapshot, ordinal=4)
    raw_path = tmp_path / tampered_snapshot.snapshot_artifact_relative_path
    raw_path.chmod(0o600)
    raw_path.write_bytes(snapshot.response_bytes + b" ")
    raw_path.chmod(0o400)
    with pytest.raises(L13ContractError, match="tampered"):
        transition_firewall_replacement(
            state,
            FirewallReplacementEvent.ORIGINAL_SNAPSHOT_SEALED,
            evidence=tampered_snapshot,
        )
    tampered_seal = _write_firewall_evidence(tmp_path, snapshot, ordinal=5)
    seal_path = tmp_path / tampered_seal.seal_relative_path
    seal_path.chmod(0o600)
    seal_path.write_bytes(seal_path.read_bytes() + b" ")
    seal_path.chmod(0o400)
    with pytest.raises(L13ContractError, match="tampered"):
        transition_firewall_replacement(
            state,
            FirewallReplacementEvent.ORIGINAL_SNAPSHOT_SEALED,
            evidence=tampered_seal,
        )
    with pytest.raises(L13ContractError, match="tampered"):
        transition_firewall_replacement(
            state,
            FirewallReplacementEvent.ORIGINAL_SNAPSHOT_SEALED,
            evidence=replace(sealed, seal_sha256="0" * 64),
        )
    state = transition_firewall_replacement(
        state,
        FirewallReplacementEvent.ORIGINAL_SNAPSHOT_SEALED,
        evidence=sealed,
    )
    request = strict_firewall_replacement_request("8.8.8.8/32")
    with pytest.raises(L13ContractError, match="tampered"):
        transition_firewall_replacement(
            state,
            FirewallReplacementEvent.REPLACEMENT_REQUESTED,
            evidence=replace(request, request_body_sha256="0" * 64),
        )
    state = transition_firewall_replacement(
        state,
        FirewallReplacementEvent.REPLACEMENT_REQUESTED,
        evidence=request,
    )
    with pytest.raises(L13ContractError, match="does not equal"):
        transition_firewall_replacement(
            state,
            FirewallReplacementEvent.REPLACEMENT_VERIFIED,
            evidence=capture_firewall_rules_snapshot(
                _firewall_response(_strict_firewall_rules("8.8.4.4/32"))
            ),
        )


def test_host_key_independent_channel_remains_user_gated() -> None:
    document = host_key_trust_decision_document()
    assert document["preferred_option"] == "independent-console-fingerprint-verification"
    assert document["strict_host_key_checking_required"] is True
    assert document["ssh_keyscan_authorized"] is False
    assert document["tofu_option_state"].startswith("blocked-")
    assert document["decision_state"] == "awaiting-user-approval"


def test_bound_run_verifier_rejects_any_hash_or_archive_drift() -> None:
    inventory = b"inventory"
    ledger = b"ledger"
    seal = b"seal"
    copy_record = b"copy"
    # The real constants intentionally make synthetic bytes fail.
    assert all(
        len(value) == 64
        for value in (INVENTORY_SHA256, LEDGER_SHA256, SEAL_SHA256, COPY_RECORD_SHA256)
    )
    with pytest.raises(L13ContractError, match="hash drifted"):
        verify_bound_run_bytes(
            inventory_bytes=inventory,
            ledger_bytes=ledger,
            external_inventory_bytes=inventory,
            external_ledger_bytes=ledger,
            seal_bytes=seal,
            copy_record_bytes=copy_record,
            extension_report_bytes=b"extension",
        )


def test_retained_source_path_binding_is_portable_but_suffix_exact() -> None:
    relative = "artifacts/t07/lambda/run/inventory-redacted.json"
    assert _retained_absolute_path_matches(
        "/historical/worktree/gic-lab/" + relative,
        relative,
    )
    assert not _retained_absolute_path_matches("relative/path", relative)
    assert not _retained_absolute_path_matches(
        "/historical/worktree/gic-lab/artifacts/t07/lambda/run/other.json",
        relative,
    )
    assert not _retained_absolute_path_matches(
        "/historical/worktree/../gic-lab/" + relative,
        relative,
    )


def test_required_l13_schemas_accept_local_contract_documents(tmp_path: Path) -> None:
    projection = project_image_identities([_image("raw-image-alpha")])
    evidence_root = _prepare_alias_root(tmp_path)
    seal = write_sealed_alias_map(
        evidence_root,
        repository_root=tmp_path,
        projection=projection,
        inventory_sha256=INVENTORY_SHA256,
    )
    # Give the public path the repository shape required by the schema.
    from giclab.harness.lambda_l13_security import image_identity_adjudication_document

    adjudication = image_identity_adjudication_document(
        projection,
        alias_map_seal=seal,
        repository_root=tmp_path,
    )
    matrix = build_resource_candidate_matrix(_inventory(), projection)
    firewall = firewall_assessment_document(_inventory())
    ssh = ssh_key_match_document([AccountSSHKeyMaterial("account-key", None)], ())
    documents = (
        (adjudication, "t07-lambda-image-identity-adjudication.schema.json"),
        (matrix, "t07-lambda-resource-candidate-matrix.schema.json"),
        (firewall, "t07-lambda-firewall-assessment.schema.json"),
        (ssh, "t07-lambda-ssh-key-match.schema.json"),
    )
    for document, schema in documents:
        assert validate_instance(document, ROOT / "schemas" / schema) == []


def test_authoritative_l13_consumer_accepts_exact_real_sealed_run(tmp_path: Path) -> None:
    external = Path(
        "/Volumes/Macintosh HD - Data/GIC-Lab/t07/sealed-artifacts/RUN-T07-L1-LAMBDA-INVENTORY-0003"
    )
    if not external.is_dir():
        pytest.skip("approved external run-0003 archive is unavailable on this host")
    plan = load_inventory_plan_v3(
        ROOT / "containers/sira-smoke/lambda/gate-l1-readonly-inventory-plan-v3.json",
        expected_sha256=PLAN_SHA256,
    )
    binding = InventoryRunBindingV3(
        run_id="RUN-T07-L1-LAMBDA-INVENTORY-0003",
        repository_commit="42f74481e5a500cacb4973c6b29da4c3470679fe",
        implementation_commit="718c75c694b3033fa7ef2ed5e7c4696fd8c389f3",
        authorization_reference="AUTH-T07-GATE-L1-LAMBDA-INPROCESS-V4-2026-08-10",
        authorization_sha256=("7246784915f376d503bab7b63acfc8d48e9c82993be394aa22dacd036a4c7195"),
    )
    historical_root = materialize_git_tree(ROOT, binding.repository_commit, tmp_path / "frozen-run")
    materialize_worktree_files(
        ROOT,
        (
            plan.output_relative_path,
            plan.ledger_relative_path,
            plan.copy_record_relative_path,
            "docs/harness/evidence/T07_RUN_0003_POSTRUN_ADJUDICATION.json",
            "artifacts/t07/lambda/gate-l1-3/RUN-T07-L1-LAMBDA-INVENTORY-0003/image-id-alias-map.json",
            "artifacts/t07/lambda/gate-l1-3/RUN-T07-L1-LAMBDA-INVENTORY-0003/IMAGE_ALIAS_MAP_SEAL.json",
            "schemas/t07-lambda-image-identity-adjudication.schema.json",
            "schemas/t07-lambda-resource-candidate-matrix.schema.json",
            "schemas/t07-lambda-firewall-assessment.schema.json",
            "schemas/t07-lambda-ssh-key-match.schema.json",
        ),
        historical_root,
    )
    result = validate_l13_gate_l2_evidence(
        historical_root,
        plan=plan,
        plan_sha256=PLAN_SHA256,
        run_binding=binding,
        ancestry_verifier=lambda *args, **kwargs: None,
    )
    assert result.evidence_valid is True
    assert result.decision_state == "inventory-evidence-insufficient"
    assert result.qualifying_candidate_count == 6
    assert result.extension_report_sha256 == SCHEMA_EXTENSION_REPORT_SHA256
    assert result.alias_map_sha256 == (
        "9f37b9412110cc7433d5339cf4d8b1eadc92743eaa32db6bf8e4c59024a79d5f"
    )
    assert result.alias_map_seal_sha256 == (
        "ed3fb1ef3323f2b37150204ef060250e4f9510bbeb976d18d2fd1b8d9894c0b5"
    )


def test_l13_control_plane_contains_no_network_or_ssh_execution_primitive() -> None:
    source = (ROOT / "src/giclab/harness/lambda_l13_security.py").read_text()
    tree = ast.parse(source)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.add(node.module)
    forbidden_modules = {"urllib", "requests", "http", "socket", "subprocess", "paramiko"}
    assert not any(name.split(".", 1)[0] in forbidden_modules for name in imported)
    assert "ssh-keyscan" not in source
    assert "ssh-keygen" not in source


def test_committed_postrun_evidence_is_schema_valid_and_stays_blocked() -> None:
    path = ROOT / "docs/harness/evidence/T07_RUN_0003_POSTRUN_ADJUDICATION.json"
    encoded = path.read_bytes()
    assert hashlib.sha256(encoded).hexdigest() == (
        "23ae723811cb15b2cbc1229592d507624c9107851fc883d9ce023464301631d0"
    )
    assert b"SHA256:" not in encoded
    assert b"/.ssh/" not in encoded
    evidence = json.loads(encoded)
    assert evidence["decision_state"] == "inventory-evidence-insufficient"
    assert evidence["authorization"] == {
        "cloud_mutation_authorized": False,
        "gate_l2_authorized": False,
        "paid_compute_authorized": False,
    }
    assert evidence["blocking_evidence_gap"]["code"] == (
        "account-ssh-public-key-material-not-retained"
    )
    documents = (
        (
            evidence["image_identity_adjudication"],
            "t07-lambda-image-identity-adjudication.schema.json",
        ),
        (
            evidence["resource_candidate_matrix"],
            "t07-lambda-resource-candidate-matrix.schema.json",
        ),
        (
            evidence["firewall_assessment"],
            "t07-lambda-firewall-assessment.schema.json",
        ),
        (evidence["ssh_key_match"], "t07-lambda-ssh-key-match.schema.json"),
    )
    for document, schema in documents:
        assert validate_instance(document, ROOT / "schemas" / schema) == []
    assert len(evidence["resource_candidate_matrix"]["qualifying_candidates"]) == 6
    assert all(
        row["match_state"] == "evidence_unavailable"
        for row in evidence["ssh_key_match"]["account_key_matches"]
    )
    assert evidence["ssh_key_match"]["local_public_keys"] == []
    inventory = json.loads(
        (
            ROOT
            / "artifacts/t07/lambda/gate-l1"
            / "RUN-T07-L1-LAMBDA-INVENTORY-0003/inventory-redacted.json"
        ).read_text()
    )
    projection = project_image_identities(inventory["images"])
    assert evidence["resource_candidate_matrix"] == build_resource_candidate_matrix(
        inventory, projection
    )
    assert evidence["firewall_assessment"] == firewall_assessment_document(inventory)
    private = evidence["image_identity_adjudication"]["private_alias_map"]
    assert hashlib.sha256((ROOT / private["path"]).read_bytes()).hexdigest() == private["sha256"]
    assert (
        hashlib.sha256((ROOT / private["seal_path"]).read_bytes()).hexdigest()
        == (private["seal_sha256"])
    )


def test_public_source_observation_is_bounded_and_unauthenticated() -> None:
    observation = json.loads(
        (ROOT / "containers/sira-smoke/lambda/public-security-observation-l1-3.json").read_text()
    )
    assert observation["account_request_count"] == 0
    assert observation["openapi"]["declared_api_version"] == "1.10.0"
    assert observation["openapi"]["sha256"] == (
        "365488015cf79fda38e1268f44a9e2d4af4fe2794ad3c6878c78a7e1f98caded"
    )
    assert observation["firewall_documentation"]["source_facts"] == {
        "global_rules_apply_workspace_wide": True,
        "per_instance_rules_are_additive_to_global_rules": True,
        "per_instance_ruleset_change_after_launch_supported": False,
        "single_public_ipv4_32_supported": True,
        "us_south_1_has_distinct_firewall_behavior": True,
    }
    assert set(observation["prohibited_observations"].values()) == {False}


def test_private_alias_map_contract_is_ignored_and_never_committed() -> None:
    evidence = json.loads(
        (ROOT / "docs/harness/evidence/T07_RUN_0003_POSTRUN_ADJUDICATION.json").read_text()
    )
    private = evidence["image_identity_adjudication"]["private_alias_map"]
    assert private["path"].startswith("artifacts/")
    assert private["seal_path"].startswith("artifacts/")
    assert private["raw_ids_committed"] is False
    assert private["raw_id_hashes_committed"] is False
    assert "artifacts/" in (ROOT / ".gitignore").read_text().splitlines()


def test_public_documents_do_not_contain_synthetic_sensitive_scalars() -> None:
    raw_image_id = "private-provider-image-id"
    source_network = "8.8.4.4/32"
    public_key_body = _public_key(b"sensitive-public-key-body")
    projection = project_image_identities([_image(raw_image_id)])
    inventory = _inventory(
        firewall_rules=[
            {
                "protocol": "tcp",
                "port_range": [22, 22],
                "source_network": source_network,
                "description": "private provider description",
            }
        ]
    )
    local = LocalPublicKey(
        display_path="~/.ssh/synthetic.pub",
        algorithm="ssh-ed25519",
        fingerprint="SHA256:syntheticFingerprint",
        mode="0644",
        owner_class="current-user",
        same_stem_private_file_present=True,
    )
    public = json.dumps(
        {
            "images": projection.public_images(),
            "firewall": firewall_assessment_document(inventory),
            "ssh": ssh_key_match_document(
                [AccountSSHKeyMaterial("synthetic-account-key", public_key_body)],
                [local],
            ),
        },
        sort_keys=True,
    )
    assert raw_image_id not in public
    assert source_network not in public
    assert public_key_body not in public
    assert "private provider description" not in public
