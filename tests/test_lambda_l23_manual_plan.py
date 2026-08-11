from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

import giclab.harness.lambda_l23_manual_plan as l23
from giclab.harness.lambda_l23_manual_plan import (
    AUTHORIZATION_PLACEHOLDER,
    CHECKPOINT_COUNT,
    PLAN_ID,
    RUN_ID,
    L23ContractError,
    PrivateBindingSeal,
    archive_private_binding,
    load_private_decision,
    render_public_plan,
    resolve_private_parameters,
    validate_execution_storage_preflight,
    validate_public_plan,
    write_private_binding,
)
from giclab.harness.sira_storage import (
    APPROVED_MOUNT,
    APPROVED_PHYSICAL_STORE_UUID,
    APPROVED_VOLUME_UUID,
    SYSTEM_CAPACITY_BYTES,
    SYSTEM_DATA_MOUNT,
    SYSTEM_DATA_VOLUME_UUID,
    VolumeObservation,
)

ROOT = Path(__file__).resolve().parents[1]


def decision_document(*, nonce: str = "9" * 64, cidr: str = "8.8.4.4/32") -> dict[str, object]:
    template = json.loads(
        (
            ROOT / "containers/sira-smoke/lambda/manual-console/"
            "T07_L2M_HUMAN_DECISION_TEMPLATE.json"
        ).read_bytes()
    )
    template.update(
        {
            "decision_id": "T07-L2M-GATE-L23-TEST",
            "decision_nonce": nonce,
            "source_ipv4_cidr": cidr,
            "notes": "synthetic nonsecret fixture",
        }
    )
    for key in tuple(template):
        if key.startswith(("approve_", "attest_", "acknowledge_")):
            template[key] = True
    return template


def write_decision(path: Path, document: dict[str, object]) -> None:
    path.write_bytes(l23.canonical_bytes(document))
    path.chmod(0o600)


def load_fixture_decision(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    document: dict[str, object] | None = None,
) -> l23.ValidatedPrivateDecision:
    tmp_path.mkdir(parents=True, exist_ok=True)
    path = tmp_path / "decision.json"
    write_decision(path, decision_document() if document is None else document)
    monkeypatch.setattr(l23, "DECISION_PATH", path)
    monkeypatch.setattr(l23, "_fresh_nonce", lambda _root, _nonce: True)
    return load_private_decision(ROOT, path=path)


def private_seal(tmp_path: Path) -> PrivateBindingSeal:
    return PrivateBindingSeal(
        root=tmp_path,
        decision_alias="l2m-decision-0123456789ab",
        decision_source_sha256="1" * 64,
        decision_canonical_sha256="2" * 64,
        decision_seal_sha256="3" * 64,
        private_parameters_sha256="4" * 64,
        bundle_seal_sha256="5" * 64,
        marker_alias="l2m-marker-0123456789ab",
        archive_alias="l2m-archive-0123456789ab",
        external_archive_id="PRIVATE-ARCHIVE-FIXTURE",
        external_seal_sha256="6" * 64,
        external_copy_record_sha256="7" * 64,
    )


def materialization_inputs() -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    inventory = {
        "running_instances": [],
        "images": [
            {
                "id": "raw-image-private",
                "family": "lambda-stack-22-04",
                "version": "22.4.5-2141",
                "architecture": "x86_64",
                "region": {"name": "us-east-1"},
            }
        ],
        "instance_types": [
            {
                "name": "gpu_1x_a10",
                "architecture": "x86_64",
                "price_cents_per_hour": 129,
                "capacity_regions": [{"name": "us-east-1"}],
            }
        ],
        "ssh_keys": [{"id": "raw-key-private", "name": "fractal-lambda-codex"}],
        "firewall_rulesets": [
            {
                "id": "global-private",
                "scope": "global",
                "rules": [
                    {
                        "protocol": "tcp",
                        "port_range": [443, 443],
                        "source_network": "0.0.0.0/0",
                        "description": "synthetic baseline",
                    }
                ],
            }
        ],
    }
    alias_map = {"entries": [{"alias": "img-0032", "raw_image_id": "raw-image-private"}]}
    l1a = {
        "account_to_local_matches": [
            {
                "account_key_name": "fractal-lambda-codex",
                "raw_api_key_id": "raw-key-private",
                "match_status": "unique_match",
                "matching_local_key_aliases": ["local-key-0001"],
            }
        ],
        "local_public_keys": [
            {
                "local_key_alias": "local-key-0001",
                "basename": "fixture.pub",
                "exact_path": "/synthetic/private/path/fixture.pub",
                "fingerprint": "SHA256:SYNTHETICNONSECRET",
                "private_key_bytes_accessed": False,
            }
        ],
        "private_key_bytes_accessed": False,
        "ssh_invoked": False,
    }
    return inventory, alias_map, l1a


def resolve_fixture_materialization(
    monkeypatch: pytest.MonkeyPatch,
    decision: l23.ValidatedPrivateDecision,
) -> l23.PrivateMaterialization:
    inventory, alias_map, l1a = materialization_inputs()
    monkeypatch.setattr(l23, "_validate_retained_gate_evidence", lambda _root: None)

    def load(_root: Path, relative: Path, *, max_bytes: int) -> dict[str, object]:
        del max_bytes
        if relative == l23.L20_PRIVATE_ROOT_RELATIVE / l23.L20_PRIVATE_PARAMETERS_NAME:
            return {
                "selected_resource": {
                    "instance_type_name": "gpu_1x_a10",
                    "region_name": "us-east-1",
                    "ssh_key_name": "fractal-lambda-codex",
                }
            }
        if relative == l23.INVENTORY_RELATIVE:
            return inventory
        if relative == l23.ALIAS_MAP_RELATIVE_ROOT / "image-id-alias-map.json":
            return alias_map
        if relative == l23.L1A_PRIVATE_RELATIVE:
            return l1a
        raise AssertionError(relative)

    counter = 1

    def random_bytes(count: int) -> bytes:
        nonlocal counter
        result = bytes([counter]) * count
        counter += 1
        return result

    monkeypatch.setattr(l23, "_load_json", load)
    monkeypatch.setattr(
        l23,
        "project_image_identities",
        lambda _rows: SimpleNamespace(alias_by_raw_id={"raw-image-private": "img-0032"}),
    )
    return resolve_private_parameters(ROOT, decision, random_bytes=random_bytes)


def external_observation(*, free_bytes: int = 800_000_000_000) -> VolumeObservation:
    return VolumeObservation(
        APPROVED_MOUNT,
        "apfs",
        True,
        APPROVED_VOLUME_UUID,
        APPROVED_PHYSICAL_STORE_UUID,
        1_000_000_000_000,
        free_bytes,
        False,
        True,
        True,
        True,
        "disk-fixture-external",
        "Thunderbolt",
        "IODeviceTree:/fixture/UTDM",
    )


def system_observation(*, free_bytes: int = 20_000_000_000) -> VolumeObservation:
    return VolumeObservation(
        SYSTEM_DATA_MOUNT,
        "apfs",
        True,
        SYSTEM_DATA_VOLUME_UUID,
        None,
        SYSTEM_CAPACITY_BYTES,
        free_bytes,
        True,
        True,
        True,
        True,
        "disk-fixture-system",
    )


def test_private_decision_exact_mode_schema_nonce_and_public_cidr(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    loaded = load_fixture_decision(monkeypatch, tmp_path)
    assert loaded.decision_alias.startswith("l2m-decision-")
    assert loaded.source_sha256 == hashlib.sha256(loaded.encoded).hexdigest()

    path = tmp_path / "decision.json"
    path.chmod(0o644)
    with pytest.raises(L23ContractError, match="identity, mode"):
        load_private_decision(ROOT, path=path)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("approve_manual_console_launch_exactly_once", False),
        ("selected_image_alias", "img-0111"),
        ("persistent_filesystem", "fixture"),
        ("max_provider_cost_usd", 2.01),
        ("source_ipv4_cidr", "10.0.0.1/32"),
        ("decision_nonce", "0" * 63),
    ],
)
def test_private_decision_rejects_incomplete_or_drifting_values(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    field: str,
    value: object,
) -> None:
    document = decision_document()
    document[field] = value
    with pytest.raises(L23ContractError):
        load_fixture_decision(monkeypatch, tmp_path, document=document)


def test_private_decision_symlink_is_rejected(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    target = tmp_path / "target.json"
    write_decision(target, decision_document())
    alias = tmp_path / "decision.json"
    alias.symlink_to(target)
    monkeypatch.setattr(l23, "DECISION_PATH", alias)
    with pytest.raises(L23ContractError, match="no-follow"):
        load_private_decision(ROOT, path=alias)


def test_private_resolution_binds_exact_resources_and_unique_identities(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    decision = load_fixture_decision(monkeypatch, tmp_path)
    materialized = resolve_fixture_materialization(monkeypatch, decision)
    assert materialized.checkpoint_count == CHECKPOINT_COUNT == 13
    parameters = materialized.document
    selected = parameters["selected_resource"]
    assert isinstance(selected, dict)
    assert selected["image_alias"] == "img-0032"
    assert selected["instance_type"] == "gpu_1x_a10"
    assert selected["region"] == "us-east-1"
    assert selected["ssh_key_name"] == "fractal-lambda-codex"
    checkpoints = parameters["checkpoint_bindings"]
    assert isinstance(checkpoints, list)
    nonces = {str(item["checkpoint_nonce"]) for item in checkpoints}
    assert len(nonces) == CHECKPOINT_COUNT
    assert all(len(value) == 64 for value in nonces)
    assert all(
        re.fullmatch(r"CHECKPOINT-T07-L2M-[A-Z0-9_-]{3,64}", str(item["checkpoint_id"]))
        for item in checkpoints
    )


def test_random_identity_collision_fails_closed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    decision = load_fixture_decision(monkeypatch, tmp_path)
    inventory, alias_map, l1a = materialization_inputs()
    monkeypatch.setattr(l23, "_validate_retained_gate_evidence", lambda _root: None)
    monkeypatch.setattr(
        l23,
        "_load_json",
        lambda _root, relative, max_bytes: (
            {
                "selected_resource": {
                    "instance_type_name": "gpu_1x_a10",
                    "region_name": "us-east-1",
                    "ssh_key_name": "fractal-lambda-codex",
                }
            }
            if relative == l23.L20_PRIVATE_ROOT_RELATIVE / l23.L20_PRIVATE_PARAMETERS_NAME
            else inventory
            if relative == l23.INVENTORY_RELATIVE
            else alias_map
            if relative == l23.ALIAS_MAP_RELATIVE_ROOT / "image-id-alias-map.json"
            else l1a
        ),
    )
    monkeypatch.setattr(
        l23,
        "project_image_identities",
        lambda _rows: SimpleNamespace(alias_by_raw_id={"raw-image-private": "img-0032"}),
    )
    with pytest.raises(L23ContractError, match="collision"):
        resolve_private_parameters(ROOT, decision, random_bytes=lambda count: b"x" * count)


def test_public_plan_is_exactly_unauthorized_ordered_and_private_safe(tmp_path: Path) -> None:
    plan = render_public_plan(
        ROOT,
        reviewed_implementation_commit="a" * 40,
        binding=private_seal(tmp_path),
    )
    validate_public_plan(plan, repository_root=ROOT)
    assert plan["plan_id"] == PLAN_ID and plan["run_id"] == RUN_ID
    authorization = plan["authorization"]
    assert isinstance(authorization, dict)
    assert authorization == {
        "authorized": False,
        "authorization_reference": AUTHORIZATION_PLACEHOLDER,
        "cloud_mutation_allowed": False,
        "paid_compute_allowed": False,
        "prototype_execution_allowed": False,
        "scientific_interpretation_allowed": False,
    }
    steps = plan["steps"]
    assert isinstance(steps, list)
    assert [step["ordinal"] for step in steps] == list(range(1, 24))
    assert steps[1]["action"] == "launch_wizard_offeredness_check_no_launch"
    caps = plan["caps"]
    assert isinstance(caps, dict)
    assert caps["read_only_lambda_gets"] == 44
    assert caps["launch_clicks"] == 1
    assert caps["automated_cloud_mutations"] == 0
    assert caps["ssh_operations"] == caps["model_calls"] == caps["sira_executions"] == 0
    expected_cap_subset = {
        "private_observation_files": 44,
        "private_observation_bytes_per_file": 1_048_576,
        "private_observation_aggregate_bytes": 16_777_216,
        "observer_active_seconds": 6_000,
        "observer_prelaunch_seconds": 1_200,
        "observer_post_provider_cleanup_seconds": 1_200,
        "observer_archive_seconds": 300,
        "observer_request_seconds": 60,
        "normal_termination_click_seconds": 1_800,
        "launch_to_active_seconds": 600,
        "cloud_ide_availability_seconds": 600,
        "qualification_command_seconds": 300,
        "evidence_download_validation_seconds": 300,
        "termination_verification_seconds": 600,
        "firewall_cleanup_seconds": 300,
        "incident_headroom_seconds": 900,
        "docker_calls": 32,
        "docker_ordinary_work_calls": 22,
        "docker_cleanup_reserved_calls": 10,
        "docker_call_output_bytes": 1_048_576,
        "docker_output_bytes": 8_388_608,
        "docker_ordinary_output_bytes": 7_340_032,
        "docker_cleanup_reserved_output_bytes": 1_048_576,
        "docker_work_wall_seconds": 270,
        "docker_total_wall_seconds": 300,
        "fixture_wall_seconds": 30,
        "qualification_containers": 1,
        "create_outcome_poll_observations": 5,
        "create_outcome_stable_absence_observations": 3,
        "create_outcome_poll_interval_seconds": 1,
        "remote_source_bytes_per_evidence_set": 16_777_216,
        "remote_archive_bytes_per_evidence_set": 16_777_216,
        "remote_source_retained_bytes": 34_603_008,
        "remote_archive_retained_bytes": 33_554_432,
        "remote_aggregate_retained_bytes": 68_157_440,
        "local_source_evidence_bytes": 41_943_040,
        "local_sealed_evidence_bytes": 41_943_040,
        "busybox_layer_bytes": 2_211_507,
        "container_cpu_millis": 1_000,
        "container_memory_bytes": 536_870_912,
        "container_memory_swap_bytes": 536_870_912,
        "container_pids_limit": 64,
        "container_tmpfs_mounts": 2,
        "container_tmpfs_bytes_each": 16_777_216,
        "container_shm_bytes": 16_777_216,
        "container_log_max_bytes": 1_048_576,
        "container_log_max_files": 1,
        "container_network_mode": "none",
    }
    assert {name: caps[name] for name in expected_cap_subset} == expected_cap_subset
    encoded = l23.canonical_bytes(plan)
    for private_value in (
        "8.8.4.4/32",
        "raw-image-private",
        "raw-key-private",
        "/synthetic/private/path",
    ):
        assert private_value.encode() not in encoded


def test_materialized_public_plan_identity_is_exact_and_unauthorized() -> None:
    encoded = (ROOT / l23.PLAN_RELATIVE).read_bytes()
    assert len(encoded) == 21_638
    assert hashlib.sha256(encoded).hexdigest() == (
        "670564fad25cc079439d35dfbb2aecb960f3f48093e5ce05b9dd973a9d87e754"
    )
    plan = json.loads(encoded)
    validate_public_plan(plan, repository_root=ROOT)
    assert plan["implementation_binding"]["reviewed_implementation_commit"] == (
        "e2b0cb93bba03599f128621f537c2f6255bae2c8"
    )
    assert plan["authorization"] == {
        "authorization_reference": AUTHORIZATION_PLACEHOLDER,
        "authorized": False,
        "cloud_mutation_allowed": False,
        "paid_compute_allowed": False,
        "prototype_execution_allowed": False,
        "scientific_interpretation_allowed": False,
    }


def test_public_plan_rejects_authority_or_order_drift(tmp_path: Path) -> None:
    plan = render_public_plan(
        ROOT,
        reviewed_implementation_commit="a" * 40,
        binding=private_seal(tmp_path),
    )
    authorization = plan["authorization"]
    assert isinstance(authorization, dict)
    authorization["authorized"] = True
    with pytest.raises(L23ContractError, match="authority"):
        validate_public_plan(plan, repository_root=ROOT)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda plan: plan.__setitem__("unexpected", True), "identity"),
        (
            lambda plan: plan["implementation_binding"]["artifacts"][0].__setitem__(
                "sha256", "0" * 64
            ),
            "artifact binding",
        ),
        (
            lambda plan: plan["qualification_bootstrap_argv"].append("--unreviewed"),
            "hash-first",
        ),
        (
            lambda plan: plan["incident_rules"].__setitem__("unreviewed_rule", True),
            "incident contract",
        ),
    ],
)
def test_public_plan_rejects_structural_or_argument_drift(
    tmp_path: Path,
    mutation: object,
    message: str,
) -> None:
    plan = render_public_plan(
        ROOT,
        reviewed_implementation_commit="a" * 40,
        binding=private_seal(tmp_path),
    )
    assert callable(mutation)
    mutation(plan)
    with pytest.raises(L23ContractError, match=message):
        validate_public_plan(plan, repository_root=ROOT)


def test_public_plan_contains_no_absolute_user_home_or_private_binding_name(
    tmp_path: Path,
) -> None:
    plan = render_public_plan(
        ROOT,
        reviewed_implementation_commit="a" * 40,
        binding=private_seal(tmp_path),
    )
    encoded = l23.canonical_bytes(plan)
    assert b"/Users/" not in encoded
    assert b"raw_image_id" not in encoded
    assert b"raw_ssh_key_id" not in encoded
    assert b"source_ipv4_cidr" not in encoded


def test_checkpoint_templates_and_schema_hashes_are_exact() -> None:
    assert hashlib.sha256((ROOT / l23.CHECKPOINT_SCHEMA_RELATIVE).read_bytes()).hexdigest() == (
        "a55f9023f8cc8f530acebe31bbe7b50c57d1e1a01b959ced38876e43e0f108ff"
    )
    assert hashlib.sha256((ROOT / l23.PRIVATE_SEAL_SCHEMA_RELATIVE).read_bytes()).hexdigest() == (
        l23.PRIVATE_SEAL_SCHEMA_SHA256
    )
    templates = sorted(
        path
        for path in (ROOT / l23.CHECKPOINT_TEMPLATE_ROOT_RELATIVE).glob("*.json")
        if path.is_file()
    )
    assert len(templates) == CHECKPOINT_COUNT == 13
    assert "launch_wizard_image_offered" in templates[0].name
    assert "qualification_bundle_uploaded" in templates[6].name
    assert not any("instance_bound" in path.name for path in templates)
    assert not any("instance_terminal_verified" in path.name for path in templates)


def test_execution_storage_preflight_checks_fresh_external_identity(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    repository = tmp_path / "repo"
    private_root = repository / "artifacts/t07/lambda/gate-l2m" / RUN_ID / "materialization-v1"
    private_root.mkdir(parents=True)
    external_root = tmp_path / "external"
    external_root.mkdir()
    monkeypatch.setattr(l23, "EXTERNAL_ARCHIVE_ROOT", external_root)
    seal = replace(private_seal(private_root), root=private_root)
    private = l23.LoadedPrivateBinding(
        seal,
        {"external_archive": {"observer_archive_identity": "OBSERVER-ARCHIVE-FIXTURE"}},
        {},
    )
    result = validate_execution_storage_preflight(
        repository,
        private,
        volume_observer=lambda: (external_observation(), system_observation()),
    )
    assert result.external_identity_validated
    assert result.external_archive_identity_fresh
    assert result.system_prewrite_floor_validated
    assert result.internal_fallback is False

    (external_root / "OBSERVER-ARCHIVE-FIXTURE").mkdir()
    with pytest.raises(L23ContractError, match="already exists"):
        validate_execution_storage_preflight(
            repository,
            private,
            volume_observer=lambda: (external_observation(), system_observation()),
        )


def test_write_private_binding_is_exclusive_and_schema_valid(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    repository = tmp_path / "repo"
    (repository / "schemas").mkdir(parents=True)
    (repository / ".gitignore").write_text("artifacts/\n", encoding="utf-8")
    for relative in (l23.DECISION_SCHEMA_RELATIVE, l23.PRIVATE_SEAL_SCHEMA_RELATIVE):
        destination = repository / relative
        destination.write_bytes((ROOT / relative).read_bytes())
    decision = load_fixture_decision(monkeypatch, tmp_path / "decision-source")
    materialized = resolve_fixture_materialization(monkeypatch, decision)
    binding = write_private_binding(
        repository,
        decision=decision,
        materialization=materialized,
    )
    assert binding.root.is_dir()
    assert all(
        oct(path.stat().st_mode & 0o777) == "0o400"
        for path in binding.root.iterdir()
        if path.is_file()
    )
    with pytest.raises(L23ContractError, match="already exists"):
        write_private_binding(
            repository,
            decision=decision,
            materialization=materialized,
        )


def test_private_binding_archive_copy_verifies_every_destination_hash(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    repository = tmp_path / "repo"
    (repository / "schemas").mkdir(parents=True)
    (repository / ".gitignore").write_text("artifacts/\n", encoding="utf-8")
    for relative in (l23.DECISION_SCHEMA_RELATIVE, l23.PRIVATE_SEAL_SCHEMA_RELATIVE):
        destination = repository / relative
        destination.write_bytes((ROOT / relative).read_bytes())
    decision = load_fixture_decision(monkeypatch, tmp_path / "decision-source")
    materialized = resolve_fixture_materialization(monkeypatch, decision)
    binding = write_private_binding(
        repository,
        decision=decision,
        materialization=materialized,
    )

    external_mount = tmp_path / "external-volume"
    archive_root = external_mount / "GIC-Lab/t07/sealed-artifacts"
    external_mount.mkdir()
    real_held = l23._HeldDirectory

    class FakeHeld:
        def __init__(self, path: Path, *, source: bool) -> None:
            self.path = path
            self.descriptor = os.open(
                path,
                os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0),
            )
            observed = os.fstat(self.descriptor)
            self.device = observed.st_dev + int(source)
            self.inode = observed.st_ino
            self.closed = False

        @classmethod
        def open(cls, path: Path) -> FakeHeld:
            return cls(path, source=path == binding.root)

        def revalidate(self) -> None:
            assert not self.closed

        def close(self) -> None:
            if not self.closed:
                os.close(self.descriptor)
                self.closed = True

    def open_archive_root(external: object, requested: Path) -> object:
        del external
        assert requested == archive_root
        archive_root.mkdir(parents=True, exist_ok=True)
        return real_held.open(archive_root)

    monkeypatch.setattr(l23, "APPROVED_MOUNT", external_mount)
    monkeypatch.setattr(l23, "EXTERNAL_ARCHIVE_ROOT", archive_root)
    monkeypatch.setattr(l23, "_HeldDirectory", FakeHeld)
    monkeypatch.setattr(l23, "_open_or_create_archive_root", open_archive_root)
    monkeypatch.setattr(
        l23,
        "DiskutilVolumeObserver",
        lambda: lambda: (external_observation(), system_observation()),
    )
    archived = archive_private_binding(binding)
    assert archived.external_seal_sha256
    assert archived.external_copy_record_sha256
    final = archive_root / binding.external_archive_id
    copy_record = json.loads((final / l23.EXTERNAL_COPY_RECORD_FILE).read_bytes())
    assert copy_record["source_retained"] is True
    assert copy_record["internal_fallback"] is False
    assert all(row["source_sha256"] == row["destination_sha256"] for row in copy_record["files"])
    assert (binding.root / l23.PRIVATE_COPY_RECORD_FILE).read_bytes() == (
        final / l23.EXTERNAL_COPY_RECORD_FILE
    ).read_bytes()


def test_modules_have_no_shell_http_mutation_or_secret_file_reader() -> None:
    combined = (ROOT / "src/giclab/harness/lambda_l23_manual_plan.py").read_text() + (
        ROOT / "src/giclab/harness/lambda_l23_manual_supervisor.py"
    ).read_text()
    assert "curl" not in combined and "wget" not in combined
    assert "requests." not in combined and "urllib" not in combined
    assert 'os.environ.get("SIRA_API_KEY")' not in combined
    assert 'os.environ.get("OPENAI_API_KEY")' not in combined
    assert all(
        token not in combined for token in ('method="POST"', 'method="PATCH"', 'method="DELETE"')
    )
