from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import re
import shutil
import subprocess
import sys
import tarfile
import time
import zipfile
from collections.abc import Callable, Mapping
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import ModuleType
from typing import cast

import pytest

import giclab.harness.t07_bounded_supervisor as supervisor
from giclab.harness import lambda_archive
from giclab.harness import t07_bounded_smoke as contract
from giclab.harness.lambda_firewall_baseline import canonicalize_firewall_rules
from giclab.harness.sira_storage import (
    APPROVED_EXTERNAL_CAPACITY_BYTES,
    APPROVED_MOUNT,
    APPROVED_PHYSICAL_STORE_UUID,
    APPROVED_VOLUME_UUID,
    SYSTEM_CAPACITY_BYTES,
    SYSTEM_DATA_MOUNT,
    SYSTEM_DATA_VOLUME_UUID,
    VolumeObservation,
)
from giclab.validation import ROOT

NOW = datetime(2026, 8, 11, 20, 0, 0, tzinfo=UTC)
AFTER_NOW = NOW + timedelta(seconds=1)
COMMIT = "1" * 40
AUTHORIZATION_REFERENCE = "AUTH-T07-BOUNDED-SIRA-SMOKE-V2-TEST-0001"
PUBLIC_KEY = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIAABAgMEBQYHCAkKCwwNDg8QERITFBUWFxgZGhscHR4f"
JSON_SECRET_CANARY = "PUBLIC_DUMMY_OPAQUE_JUPYTER_CANARY_0123456789"


def _runtime_plan() -> dict[str, object]:
    conditions: list[dict[str, object]] = []
    for condition in contract.CONDITION_ORDER:
        conditions.append(
            {
                "condition": condition,
                "run_id": contract.RUN_IDS[condition],
                "container_create_argv_template": list(contract.container_create_argv(condition)),
                "inner_argv_template": list(contract.condition_inner_argv(condition)),
                "api_cost_usd": 2.0,
                "model_tokens": 200_000,
                "model_call_attempts": contract.MODEL_CALL_CAPS[condition],
                "browser_actions": 1,
                "wall_seconds": 120,
                "output_bytes": 104_857_600,
            }
        )
    contract_path = ROOT / "src/giclab/harness/t07_bounded_smoke.py"
    contract_encoded = contract_path.read_bytes()
    return {
        "implementation": {
            "artifacts": [
                {
                    "path": "src/giclab/harness/t07_bounded_smoke.py",
                    "bytes": len(contract_encoded),
                    "sha256": hashlib.sha256(contract_encoded).hexdigest(),
                }
            ]
        },
        "preflights": {
            "browser": {
                "container_create_argv_template": list(contract.browser_preflight_create_argv())
            },
            "model": {
                "container_create_argv_template": list(contract.model_preflight_create_argv())
            },
        },
        "limits": dict(contract.LIMITS),
        "conditions": conditions,
        "container_lifecycle": contract.lifecycle_argv_templates(),
        "storage": {"remote_active_root": "/home/ubuntu/t07-bounded-output-0002"},
        "lambda": {
            "image_alias": contract.SELECTED_IMAGE_ALIAS,
            "image_family": contract.SELECTED_IMAGE_FAMILY,
            "image_version": contract.SELECTED_IMAGE_VERSION,
        },
        "source_and_runtime": {
            "base_image": contract.BASE_IMAGE_INDEX,
            "base_image_index_digest": contract.BASE_IMAGE_INDEX_DIGEST,
            "base_image_amd64_manifest": contract.BASE_IMAGE_AMD64_MANIFEST,
            "base_image_amd64_config": contract.BASE_IMAGE_AMD64_CONFIG,
            "upstream_commit": contract.UPSTREAM_COMMIT,
            "upstream_tree": contract.UPSTREAM_TREE,
            "uv_lock_sha256": contract.UPSTREAM_LOCK_SHA256,
            "routing_patch_sha256": contract.ROUTING_PATCH_SHA256,
            "runtime_adaptation_sha256": contract.RUNTIME_ADAPTATION_SHA256,
            "routing_sha256": contract.ROUTING_SHA256,
            "playwright": contract.PLAYWRIGHT_VERSION,
            "chromium_revision": contract.CHROMIUM_REVISION,
            "chromium_version": contract.CHROMIUM_VERSION,
            "platform": "linux/amd64",
        },
    }


def _load_remote_bootstrap() -> ModuleType:
    path = ROOT / "containers/sira-smoke/bounded/bootstrap.py"
    spec = importlib.util.spec_from_file_location("test_t07_remote_bootstrap", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_local_bootstrap() -> ModuleType:
    path = ROOT / "containers/sira-smoke/bounded/local_supervisor_bootstrap.py"
    spec = importlib.util.spec_from_file_location("test_t07_local_bootstrap", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class FakeTransport:
    def __init__(self, documents: Mapping[str, object]) -> None:
        self.documents = documents
        self.paths: list[str] = []

    def fetch(
        self,
        path: str,
        *,
        credential: str,
        timeout_seconds: float,
        max_response_bytes: int,
    ) -> supervisor.HttpResponse:
        assert credential == "public-dummy-lambda-canary-never-retained"
        assert timeout_seconds == 60
        encoded = supervisor.canonical_json_bytes(self.documents[path])
        assert len(encoded) <= max_response_bytes
        self.paths.append(path)
        return supervisor.HttpResponse(200, "application/json", encoded, 5)


def _rule(description: str, source: str = "203.0.113.7/32") -> dict[str, object]:
    return {
        "protocol": "tcp",
        "port_range": [22, 22],
        "source_network": source,
        "description": description,
    }


def _region() -> dict[str, object]:
    return {"name": "us-east-1", "description": "synthetic local fixture"}


def _instance_type() -> dict[str, object]:
    return {
        "name": "gpu_1x_a10",
        "description": "synthetic local fixture",
        "gpu_description": "one A10",
        "price_cents_per_hour": 129,
        "specs": {"vcpus": 30, "memory_gib": 200, "storage_gib": 1400, "gpus": 1},
        "architecture": "x86_64",
    }


def _actions() -> dict[str, object]:
    return {
        name: {"available": True}
        for name in ("migrate", "rebuild", "restart", "cold_reboot", "terminate")
    }


def _instance(status: str, ruleset_id: str) -> dict[str, object]:
    return {
        "id": "synthetic-instance-private",
        "status": status,
        "ssh_key_names": ["fractal-lambda-codex"],
        "file_system_names": [],
        "region": _region(),
        "instance_type": _instance_type(),
        "actions": _actions(),
        "firewall_rulesets": [{"id": ruleset_id}],
        "jupyter_token": JSON_SECRET_CANARY,
        "jupyter_url": "https://example.invalid/lab?token=" + JSON_SECRET_CANARY,
        "unknown_secret_material": JSON_SECRET_CANARY,
    }


def _external_observation(mount: Path = APPROVED_MOUNT) -> VolumeObservation:
    return VolumeObservation(
        mount_path=mount,
        filesystem="apfs",
        writable=True,
        volume_uuid=APPROVED_VOLUME_UUID,
        physical_store_uuid=APPROVED_PHYSICAL_STORE_UUID,
        total_bytes=APPROVED_EXTERNAL_CAPACITY_BYTES,
        free_bytes=800_000_000_000,
        internal=False,
        owners_enabled=False,
        encrypted=True,
        unlocked=True,
        device_identifier="disk99s1",
        bus_protocol="Thunderbolt",
        device_tree_path="IOService:/synthetic/AppleThunderbolt/UTDM",
    )


def _system_observation() -> VolumeObservation:
    return VolumeObservation(
        mount_path=SYSTEM_DATA_MOUNT,
        filesystem="apfs",
        writable=True,
        volume_uuid=SYSTEM_DATA_VOLUME_UUID,
        physical_store_uuid=None,
        total_bytes=SYSTEM_CAPACITY_BYTES,
        free_bytes=20_000_000_000,
        internal=True,
        owners_enabled=True,
        encrypted=True,
        unlocked=True,
        device_identifier="disk3s1",
    )


def _copy_schemas(root: Path) -> None:
    for relative in (
        supervisor.AUTHORIZATION_SCHEMA_RELATIVE,
        supervisor.PRIVATE_BINDING_SCHEMA_RELATIVE,
        supervisor.LEDGER_SCHEMA_RELATIVE,
        supervisor.EVIDENCE_SCHEMA_RELATIVE,
    ):
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, destination)
    shutil.copytree(ROOT / supervisor.ENDPOINT_SCHEMA_ROOT, root / supervisor.ENDPOINT_SCHEMA_ROOT)


def _private_binding_fixture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Callable[[], tuple[VolumeObservation, VolumeObservation]], Path]:
    """Create synthetic protected inputs and a fake held-descriptor volume topology."""

    from giclab.harness import sira_storage

    _copy_schemas(tmp_path)
    baseline_rules = [_rule("synthetic sealed baseline", source="198.51.100.0/24")]
    baseline_sha256 = supervisor._firewall_semantic_sha256(baseline_rules)
    restoration = {"rules": baseline_rules}
    restoration_encoded = supervisor.canonical_json_bytes(restoration)
    restoration_sha256 = supervisor.sha256_bytes(restoration_encoded)
    source = {
        "schema_version": "0.1.0",
        "decision_alias": "synthetic-private-decision",
        "decision_canonical_sha256": "3" * 64,
        "source_ipv4_cidr": "203.0.113.7/32",
        "strict_firewall_rule": _rule("historical strict fixture"),
        "owned_regional_ruleset": {
            "name": "t07-l2m-" + "a" * 40,
            "rules": [_rule("historical owned fixture")],
        },
        "selected_resource": {
            "instance_type": "gpu_1x_a10",
            "region": "us-east-1",
            "architecture": "x86_64",
            "image_alias": "img-0032",
            "image_family": "lambda-stack-22-04",
            "image_version": "22.4.5-2141",
            "raw_image_id": "synthetic-image-private",
            "ssh_key_name": "fractal-lambda-codex",
            "raw_ssh_key_id": "synthetic-key-private",
            "local_public_key_fingerprint": supervisor._fingerprint(PUBLIC_KEY),
            "price_cents_per_hour": 129,
        },
    }
    source_encoded = supervisor.canonical_json_bytes(source)
    source_sha256 = supervisor.sha256_bytes(source_encoded)
    decision_seal = {
        "private_parameters_sha256": source_sha256,
        "decision_alias": source["decision_alias"],
        "decision_canonical_sha256": source["decision_canonical_sha256"],
        "decision_validated": True,
        "source_retained": True,
    }
    baseline = {
        "baseline_alias": supervisor.BASELINE_ALIAS,
        "canonical_semantic_sha256": baseline_sha256,
        "canonicalization_version": supervisor.CANONICALIZER_VERSION,
        "response_parser_version": supervisor.PARSER_VERSION,
        "restoration_payload_sha256": restoration_sha256,
    }
    baseline_seal = {
        "baseline_alias": supervisor.BASELINE_ALIAS,
        "canonical_semantic_sha256": baseline_sha256,
        "restoration_payload_alias": supervisor.RESTORATION_ALIAS,
        "restoration_payload_sha256": restoration_sha256,
        "original_capture_unchanged": True,
        "source_retained": True,
    }
    inputs = {
        supervisor.HISTORICAL_SOURCE_PARAMETERS_RELATIVE: source_encoded,
        supervisor.HISTORICAL_DECISION_SEAL_RELATIVE: supervisor.canonical_json_bytes(
            decision_seal
        ),
        supervisor.AUTHORITATIVE_BASELINE_RELATIVE: supervisor.canonical_json_bytes(baseline),
        supervisor.AUTHORITATIVE_BASELINE_SEAL_RELATIVE: supervisor.canonical_json_bytes(
            baseline_seal
        ),
        supervisor.AUTHORITATIVE_RESTORATION_RELATIVE: restoration_encoded,
    }
    for relative, encoded in inputs.items():
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        path.write_bytes(encoded)
        path.chmod(0o600)
    monkeypatch.setattr(supervisor, "HISTORICAL_SOURCE_PARAMETERS_SHA256", source_sha256)
    monkeypatch.setattr(supervisor, "BASELINE_SEMANTIC_SHA256", baseline_sha256)
    monkeypatch.setattr(supervisor, "RESTORATION_SHA256", restoration_sha256)
    schema_path = tmp_path / supervisor.PRIVATE_BINDING_SCHEMA_RELATIVE
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    schema["properties"]["baseline"]["properties"]["semantic_sha256"] = {"const": baseline_sha256}
    schema["properties"]["baseline"]["properties"]["restoration_payload_sha256"] = {
        "const": restoration_sha256
    }
    schema_path.write_bytes(supervisor.canonical_json_bytes(schema))

    external = tmp_path / "external"
    system = tmp_path / "system"
    external.mkdir()
    system.mkdir()
    external_parent = external / "GIC-Lab/t07/sealed-artifacts"
    monkeypatch.setattr(supervisor, "EXTERNAL_MOUNT", external)
    monkeypatch.setattr(supervisor, "EXTERNAL_PARENT", external_parent)
    monkeypatch.setattr(lambda_archive, "APPROVED_MOUNT", external)
    monkeypatch.setattr(sira_storage, "SYSTEM_DATA_MOUNT", system)

    held_type = lambda_archive._HeldDirectory
    original_open = held_type.open.__func__

    def fake_open(
        cls: type[lambda_archive._HeldDirectory], path: Path
    ) -> lambda_archive._HeldDirectory:
        handle = original_open(cls, path)
        if path in {tmp_path, system}:
            handle.device += 1
        return handle

    monkeypatch.setattr(held_type, "open", classmethod(fake_open))
    monkeypatch.setattr(held_type, "revalidate", lambda self: None)

    external_observation = _external_observation(external)
    system_observation = VolumeObservation(
        mount_path=system,
        filesystem="apfs",
        writable=True,
        volume_uuid=SYSTEM_DATA_VOLUME_UUID,
        physical_store_uuid=None,
        total_bytes=SYSTEM_CAPACITY_BYTES,
        free_bytes=20_000_000_000,
        internal=True,
        owners_enabled=True,
        encrypted=True,
        unlocked=True,
        device_identifier="disk3s1",
    )

    def observer() -> tuple[VolumeObservation, VolumeObservation]:
        return external_observation, system_observation

    return observer, external_parent


def _sealed_private_binding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[
    supervisor.SealedPrivateBinding, Callable[[], tuple[VolumeObservation, VolumeObservation]], Path
]:
    observer, external_parent = _private_binding_fixture(tmp_path, monkeypatch)
    sealed = supervisor.seal_private_security_binding(
        tmp_path,
        volume_observer=observer,
        random_bytes=lambda count: bytes(range(count)),
    )
    monkeypatch.setattr(supervisor, "PRIVATE_BINDING_ALIAS", sealed.binding_alias)
    monkeypatch.setattr(supervisor, "PRIVATE_BINDING_SHA256", sealed.binding_sha256)
    return sealed, observer, external_parent


def _materialize(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[dict[str, object], str, str]:
    sealed, observer, _ = _sealed_private_binding(tmp_path, monkeypatch)
    private = json.loads(sealed.local_path.read_text(encoding="utf-8"))
    baseline = cast(dict[str, object], private["baseline"])
    baseline_sha256 = cast(str, baseline["semantic_sha256"])
    monkeypatch.setattr(supervisor, "verify_repository_identity", lambda *_: None)
    monkeypatch.setattr(supervisor, "_validate_base_authority", lambda *_: None)
    plan = _runtime_plan()
    plan_sha256 = "2" * 64
    summary = supervisor.materialize_authority(
        tmp_path,
        plan=plan,
        plan_sha256=plan_sha256,
        expected_commit=COMMIT,
        authorization_reference=AUTHORIZATION_REFERENCE,
        private_security_binding_path=sealed.local_path,
        private_security_binding_sha256=sealed.binding_sha256,
        private_security_binding_seal_sha256=sealed.local_seal_sha256,
        volume_observer=observer,
        utc_now=lambda: NOW,
    )
    upload_root = tmp_path / supervisor.UPLOAD_ROOT_RELATIVE
    upload_root.mkdir(parents=True)
    upload_archive = b"public reviewed repository archive\n"
    upload_bootstrap = b"# public reviewed bootstrap\n"
    (upload_root / supervisor.UPLOAD_ARCHIVE_NAME).write_bytes(upload_archive)
    (upload_root / supervisor.UPLOAD_BOOTSTRAP_NAME).write_bytes(upload_bootstrap)
    upload_identity = {
        "archive_path": (
            supervisor.UPLOAD_ROOT_RELATIVE / supervisor.UPLOAD_ARCHIVE_NAME
        ).as_posix(),
        "archive_bytes": len(upload_archive),
        "archive_sha256": hashlib.sha256(upload_archive).hexdigest(),
        "bundle_manifest_sha256": "8" * 64,
        "bootstrap_path": (
            supervisor.UPLOAD_ROOT_RELATIVE / supervisor.UPLOAD_BOOTSTRAP_NAME
        ).as_posix(),
        "bootstrap_bytes": len(upload_bootstrap),
        "bootstrap_sha256": hashlib.sha256(upload_bootstrap).hexdigest(),
    }
    monkeypatch.setattr(
        supervisor,
        "_load_upload_bundle_identity",
        lambda *args, **kwargs: dict(upload_identity),
    )
    (tmp_path / supervisor.UPLOAD_IDENTITY_RELATIVE).write_bytes(
        supervisor.canonical_json_bytes(upload_identity)
    )
    return summary, plan_sha256, baseline_sha256


def _materialized_private(tmp_path: Path) -> dict[str, object]:
    return json.loads((tmp_path / supervisor.PRIVATE_BINDING_RELATIVE).read_text(encoding="utf-8"))


def test_bounded_baseline_hash_matches_authoritative_canonicalizer() -> None:
    rules = [
        _rule("synthetic TCP baseline", source="198.51.100.0/24"),
        {
            "protocol": "icmp",
            "source_network": "203.0.113.0/24",
            "description": "synthetic ICMP baseline",
        },
    ]
    assert supervisor._firewall_semantic_sha256(rules) == (
        canonicalize_firewall_rules(rules).semantic_sha256
    )


def test_private_binding_builder_uses_fresh_domain_separated_identities(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _private_binding_fixture(tmp_path, monkeypatch)
    first, first_encoded, first_sha256 = supervisor.build_private_security_binding(
        tmp_path, random_bytes=lambda count: bytes(range(count))
    )
    second, _, _ = supervisor.build_private_security_binding(
        tmp_path, random_bytes=lambda count: bytes(reversed(range(count)))
    )
    assert first_sha256 == hashlib.sha256(first_encoded).hexdigest()
    assert first["schema_version"] == "0.3.0"
    assert first["binding_alias"] != second["binding_alias"]
    assert first["owned_ruleset_name"] != second["owned_ruleset_name"]
    assert first["private_locator"] != second["private_locator"]
    assert first["private_locator"] not in {
        str(first["binding_nonce"]),
        str(first["binding_alias"]).rsplit("-", 1)[-1],
        str(first["owned_ruleset_name"]).rsplit("-", 1)[-1],
    }
    assert cast(dict[str, object], first["stale_source"])["reusable"] is False


@pytest.mark.parametrize("drift", ("source_hash", "baseline_version", "restoration_hash"))
def test_private_binding_builder_rejects_stale_input_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, drift: str
) -> None:
    _private_binding_fixture(tmp_path, monkeypatch)
    if drift == "source_hash":
        target = tmp_path / supervisor.HISTORICAL_SOURCE_PARAMETERS_RELATIVE
        target.write_bytes(target.read_bytes() + b" ")
    elif drift == "baseline_version":
        target = tmp_path / supervisor.AUTHORITATIVE_BASELINE_RELATIVE
        document = json.loads(target.read_text(encoding="utf-8"))
        document["canonicalization_version"] = "stale-canonicalizer"
        target.write_bytes(supervisor.canonical_json_bytes(document))
    else:
        target = tmp_path / supervisor.AUTHORITATIVE_RESTORATION_RELATIVE
        target.write_bytes(target.read_bytes() + b" ")
    with pytest.raises(supervisor.BoundedSupervisorError):
        supervisor.build_private_security_binding(
            tmp_path, random_bytes=lambda count: bytes(range(count))
        )


def test_private_binding_builder_rejects_symlinked_protected_input(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _private_binding_fixture(tmp_path, monkeypatch)
    target = tmp_path / supervisor.HISTORICAL_SOURCE_PARAMETERS_RELATIVE
    replacement = target.with_name("synthetic-source-copy.json")
    replacement.write_bytes(target.read_bytes())
    target.unlink()
    target.symlink_to(replacement)
    with pytest.raises(supervisor.BoundedSupervisorError):
        supervisor.build_private_security_binding(
            tmp_path, random_bytes=lambda count: bytes(range(count))
        )


def test_private_binding_seal_is_private_atomic_and_fully_verifiable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sealed, observer, external_parent = _sealed_private_binding(tmp_path, monkeypatch)
    private = json.loads(sealed.local_path.read_text(encoding="utf-8"))
    locator = cast(str, private["private_locator"])
    external_directory = external_parent / f"t07-private-binding-{locator}"
    assert sealed.local_path.parent.name == locator
    assert sealed.binding_alias not in str(sealed.local_path)
    assert sealed.binding_sha256 not in str(sealed.local_path)
    assert sealed.binding_alias not in external_directory.name
    assert sealed.binding_sha256 not in external_directory.name
    assert sealed.local_path.stat().st_mode & 0o777 == 0o600
    assert (
        sealed.local_path.parent / supervisor.PRIVATE_BINDING_LOCAL_SEAL_FILENAME
    ).stat().st_mode & 0o777 == 0o600
    assert external_directory.stat().st_mode & 0o777 == 0o500
    assert not list(external_parent.glob("*.staging"))
    verified, encoded, _, _ = supervisor._verify_presealed_private_security_binding(
        tmp_path,
        binding_path=sealed.local_path,
        binding_sha256=sealed.binding_sha256,
        local_seal_sha256=sealed.local_seal_sha256,
        volume_observer=observer,
    )
    assert verified["binding_alias"] == sealed.binding_alias
    assert hashlib.sha256(encoded).hexdigest() == sealed.binding_sha256
    assert sealed.source_retained and sealed.source_destination_sha256_equal


def test_private_binding_seal_rejects_existing_local_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sealed, observer, _ = _sealed_private_binding(tmp_path, monkeypatch)
    with pytest.raises(supervisor.BoundedSupervisorError, match="not fresh"):
        supervisor.seal_private_security_binding(
            tmp_path,
            volume_observer=observer,
            random_bytes=lambda count: bytes(range(count)),
        )
    assert sealed.local_path.is_file()


def test_private_binding_seal_preserves_preexisting_external_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    observer, external_parent = _private_binding_fixture(tmp_path, monkeypatch)
    document, _, _ = supervisor.build_private_security_binding(
        tmp_path, random_bytes=lambda count: bytes(range(count))
    )
    locator = cast(str, document["private_locator"])
    external_parent.mkdir(parents=True)
    preexisting = external_parent / f"t07-private-binding-{locator}"
    preexisting.mkdir()
    with pytest.raises(supervisor.BoundedSupervisorError):
        supervisor.seal_private_security_binding(
            tmp_path,
            volume_observer=observer,
            random_bytes=lambda count: bytes(range(count)),
        )
    assert preexisting.is_dir()
    assert not (tmp_path / supervisor.PRIVATE_BINDING_LOCAL_PARENT_RELATIVE / locator).exists()


@pytest.mark.parametrize("failure_stage", ("before_rename", "after_rename"))
def test_private_binding_seal_cleans_only_owned_incomplete_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure_stage: str,
) -> None:
    observer, external_parent = _private_binding_fixture(tmp_path, monkeypatch)
    document, _, _ = supervisor.build_private_security_binding(
        tmp_path, random_bytes=lambda count: bytes(range(count))
    )
    locator = cast(str, document["private_locator"])
    if failure_stage == "before_rename":
        original = lambda_archive._write_exclusive_at

        def fail_copy_record(directory_fd: int, name: str, encoded: bytes) -> None:
            if name == supervisor.PRIVATE_BINDING_COPY_RECORD_FILENAME:
                raise lambda_archive.InventoryArchiveError("synthetic write failure")
            original(directory_fd, name, encoded)

        monkeypatch.setattr(lambda_archive, "_write_exclusive_at", fail_copy_record)
        failing_observer = observer
    else:
        calls = 0

        def failing_observer() -> tuple[VolumeObservation, VolumeObservation]:
            nonlocal calls
            calls += 1
            external, system = observer()
            if calls == 2:
                external = replace(external, free_bytes=0)
            return external, system

    with pytest.raises(supervisor.BoundedSupervisorError, match="seal transaction failed"):
        supervisor.seal_private_security_binding(
            tmp_path,
            volume_observer=failing_observer,
            random_bytes=lambda count: bytes(range(count)),
        )
    local = tmp_path / supervisor.PRIVATE_BINDING_LOCAL_PARENT_RELATIVE / locator
    assert not local.exists()
    assert not (external_parent / f"t07-private-binding-{locator}").exists()
    assert not (external_parent / f".t07-private-binding-{locator}.staging").exists()


@pytest.mark.parametrize(
    "drift",
    (
        "local_copy_only",
        "external_copy_only",
        "missing_local_seal",
        "tampered_local_seal",
        "tampered_external_copy",
    ),
)
def test_materialization_requires_complete_local_and_external_preseal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    drift: str,
) -> None:
    sealed, observer, external_parent = _sealed_private_binding(tmp_path, monkeypatch)
    private = json.loads(sealed.local_path.read_text(encoding="utf-8"))
    locator = cast(str, private["private_locator"])
    external_directory = external_parent / f"t07-private-binding-{locator}"
    local_seal = sealed.local_path.parent / supervisor.PRIVATE_BINDING_LOCAL_SEAL_FILENAME
    if drift == "local_copy_only":
        external_directory.chmod(0o700)
        shutil.rmtree(external_directory)
    elif drift == "external_copy_only":
        sealed.local_path.unlink()
    elif drift == "missing_local_seal":
        local_seal.unlink()
    elif drift == "tampered_local_seal":
        local_seal.write_bytes(local_seal.read_bytes() + b" ")
    else:
        external_directory.chmod(0o700)
        external_binding = external_directory / supervisor.PRIVATE_BINDING_FILENAME
        external_binding.chmod(0o600)
        external_binding.write_bytes(external_binding.read_bytes() + b" ")
        external_binding.chmod(0o400)
        external_directory.chmod(0o500)
    monkeypatch.setattr(supervisor, "verify_repository_identity", lambda *_: None)
    monkeypatch.setattr(supervisor, "_validate_base_authority", lambda *_: None)
    with pytest.raises(supervisor.BoundedSupervisorError):
        supervisor.materialize_authority(
            tmp_path,
            plan=_runtime_plan(),
            plan_sha256="2" * 64,
            expected_commit=COMMIT,
            authorization_reference=AUTHORIZATION_REFERENCE,
            private_security_binding_path=sealed.local_path,
            private_security_binding_sha256=sealed.binding_sha256,
            private_security_binding_seal_sha256=sealed.local_seal_sha256,
            volume_observer=observer,
            utc_now=lambda: NOW,
        )
    assert not (tmp_path / supervisor.RUN_ROOT_RELATIVE).exists()


@pytest.mark.parametrize(
    ("field_path", "replacement"),
    (
        (("owned_ruleset_name",), "t07-l2m-" + "a" * 40),
        (("owned_ruleset_name",), "giclab-t07-bounded-" + "a" * 11),
        (("owned_ruleset_name",), "giclab-t07-bounded-" + "G" * 12),
        (("baseline", "semantic_sha256"), "4" * 64),
        (("baseline", "canonicalizer_version"), "wrong-canonicalizer"),
        (("baseline", "parser_version"), "wrong-parser"),
    ),
)
def test_private_binding_rejects_stale_or_malformed_security_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field_path: tuple[str, ...],
    replacement: str,
) -> None:
    _materialize(tmp_path, monkeypatch)
    private = _materialized_private(tmp_path)
    target: dict[str, object] = private
    for component in field_path[:-1]:
        value = target[component]
        assert isinstance(value, dict)
        target = value
    target[field_path[-1]] = replacement
    with pytest.raises(supervisor.BoundedSupervisorError):
        supervisor._validate_private_binding(tmp_path, private)


def test_private_binding_keeps_semantic_baseline_and_restoration_seal_distinct(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _materialize(tmp_path, monkeypatch)
    private = _materialized_private(tmp_path)
    baseline = private["baseline"]
    assert isinstance(baseline, dict)
    semantic = baseline["semantic_sha256"]
    restoration = baseline["restoration_payload_sha256"]
    baseline["semantic_sha256"] = restoration
    baseline["restoration_payload_sha256"] = semantic
    with pytest.raises(supervisor.BoundedSupervisorError):
        supervisor._validate_private_binding(tmp_path, private)


def test_private_binding_accepts_current_bound_baseline_and_seal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    summary, _, baseline_sha256 = _materialize(tmp_path, monkeypatch)
    private = _materialized_private(tmp_path)
    supervisor._validate_private_binding(tmp_path, private)
    baseline = private["baseline"]
    assert isinstance(baseline, dict)
    assert baseline["semantic_sha256"] == baseline_sha256
    assert baseline["restoration_payload_sha256"] == supervisor.RESTORATION_SHA256
    assert summary["private_binding_alias"] == private["binding_alias"]
    materialized = tmp_path / supervisor.PRIVATE_BINDING_RELATIVE
    linked = materialized.lstat()
    assert not materialized.is_symlink()
    assert linked.st_nlink == 1
    assert linked.st_mode & 0o777 == 0o600
    assert materialized.relative_to(tmp_path).parts[0] == "artifacts"


def test_materializer_rejects_real_private_binding_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _copy_schemas(tmp_path)
    private_path = tmp_path / "artifacts" / "private-fixture" / "binding.json"
    private_path.parent.mkdir(parents=True, mode=0o700)
    private_path.write_bytes(b"{}\n")
    private_path.chmod(0o600)
    digest = supervisor.sha256_bytes(private_path.read_bytes())
    monkeypatch.setattr(supervisor, "PRIVATE_BINDING_SHA256", digest)
    monkeypatch.setattr(supervisor, "verify_repository_identity", lambda *_: None)
    monkeypatch.setattr(supervisor, "_validate_base_authority", lambda *_: None)
    with pytest.raises(supervisor.BoundedSupervisorError):
        supervisor.materialize_authority(
            tmp_path,
            plan=_runtime_plan(),
            plan_sha256="2" * 64,
            expected_commit=COMMIT,
            authorization_reference=AUTHORIZATION_REFERENCE,
            private_security_binding_path=private_path,
            private_security_binding_sha256=digest,
            private_security_binding_seal_sha256="4" * 64,
            volume_observer=lambda: (_external_observation(), _system_observation()),
            utc_now=lambda: NOW,
        )


def _phase_documents(private: Mapping[str, object]) -> dict[str, dict[str, object]]:
    baseline = {
        "data": {
            "id": "global",
            "name": "global",
            "rules": [_rule("synthetic sealed baseline", source="198.51.100.0/24")],
        }
    }
    ruleset_id = "synthetic-ruleset-private"
    return {
        "prelaunch": {
            "/api/v1/instance-types": {
                "data": {
                    "gpu_1x_a10": {
                        "instance_type": _instance_type(),
                        "regions_with_capacity_available": [_region()],
                    }
                }
            },
            "/api/v1/images": {
                "data": [
                    {
                        "id": "synthetic-image-private",
                        "created_time": "2026-08-01T00:00:00Z",
                        "updated_time": "2026-08-01T00:00:00Z",
                        "name": "Synthetic image",
                        "description": "fixture",
                        "family": "lambda-stack-22-04",
                        "version": "22.4.5-2141",
                        "architecture": "x86_64",
                        "region": _region(),
                    }
                ]
            },
            "/api/v1/regions": {"data": [_region()]},
            "/api/v1/ssh-keys": {
                "data": [
                    {
                        "id": "synthetic-key-private",
                        "name": "fractal-lambda-codex",
                        "public_key": PUBLIC_KEY,
                    }
                ]
            },
            "/api/v1/firewall-rulesets": {"data": []},
            "/api/v1/firewall-rulesets/global": baseline,
            "/api/v1/instances": {"data": []},
        },
        "security": {
            "/api/v1/firewall-rulesets": {
                "data": [
                    {
                        "id": ruleset_id,
                        "name": private["owned_ruleset_name"],
                        "region": _region(),
                        "rules": [private["owned_ruleset_rule"]],
                        "created": "2026-08-11T20:00:00Z",
                        "instance_ids": [],
                    }
                ]
            },
            "/api/v1/firewall-rulesets/global": {
                "data": {
                    "id": "global",
                    "name": "global",
                    "rules": [private["strict_firewall_rule"]],
                }
            },
        },
        "post_launch": {"/api/v1/instances": {"data": [_instance("active", ruleset_id)]}},
        "termination": {"/api/v1/instances": {"data": [_instance("terminated", ruleset_id)]}},
        "terminal": {
            "/api/v1/firewall-rulesets": {"data": []},
            "/api/v1/firewall-rulesets/global": baseline,
        },
    }


def test_post_launch_rejects_extra_instance_and_persistent_mounts() -> None:
    private: dict[str, object] = {}
    state: dict[str, object] = {
        "owned_ruleset_id": "synthetic-ruleset-private",
        "bound_instance_id": None,
    }
    selected = _instance("active", "synthetic-ruleset-private")
    extra = dict(_instance("active", "synthetic-ruleset-private"))
    extra["id"] = "synthetic-extra-instance-private"
    with pytest.raises(supervisor.BoundedSupervisorError, match="exactly one total"):
        supervisor._validate_post_launch(
            {"/api/v1/instances": {"data": [selected, extra]}}, private, dict(state)
        )
    mounted = dict(selected)
    mounted["file_system_mounts"] = [{"mount_point": "/persistent"}]
    with pytest.raises(supervisor.BoundedSupervisorError, match="exactly one owned active"):
        supervisor._validate_post_launch(
            {"/api/v1/instances": {"data": [mounted]}}, private, dict(state)
        )


def test_termination_rejects_any_remaining_nonterminal_instance() -> None:
    state: dict[str, object] = {
        "owned_ruleset_id": "synthetic-ruleset-private",
        "bound_instance_id": "synthetic-instance-private",
    }
    terminal = _instance("terminated", "synthetic-ruleset-private")
    extra = dict(_instance("active", "synthetic-ruleset-private"))
    extra["id"] = "synthetic-extra-instance-private"
    with pytest.raises(supervisor.BoundedSupervisorError, match="nonterminal instance remains"):
        supervisor._validate_termination(
            {"/api/v1/instances": {"data": [terminal, extra]}}, {}, state
        )


def _execute_observer(
    tmp_path: Path,
    summary: Mapping[str, object],
    plan_sha256: str,
    *,
    phase: str,
    transport: supervisor.ReadOnlyTransport,
    monotonic_ns: Callable[[], int] = time.monotonic_ns,
    utc_now: Callable[[], datetime] = lambda: AFTER_NOW,
) -> dict[str, object]:
    return supervisor.execute_observer_phase(
        tmp_path,
        plan=_runtime_plan(),
        plan_sha256=plan_sha256,
        expected_commit=COMMIT,
        phase=phase,
        authorization_path=tmp_path / supervisor.AUTHORIZATION_RELATIVE,
        authorization_sha256=str(summary["authorization_sha256"]),
        private_binding_path=tmp_path / supervisor.PRIVATE_BINDING_RELATIVE,
        private_binding_sha256=str(summary["private_binding_sha256"]),
        transport=transport,
        credential_provider=lambda: "public-dummy-lambda-canary-never-retained",
        monotonic_ns=monotonic_ns,
        utc_now=utc_now,
        sleeper=lambda _: None,
    )


def test_exact_observer_phase_order_and_shell_free_commands() -> None:
    assert supervisor.PHASE_REQUESTS == {
        "prelaunch": (
            "/api/v1/instance-types",
            "/api/v1/images",
            "/api/v1/regions",
            "/api/v1/ssh-keys",
            "/api/v1/firewall-rulesets",
            "/api/v1/firewall-rulesets/global",
            "/api/v1/instances",
        ),
        "security": (
            "/api/v1/firewall-rulesets",
            "/api/v1/firewall-rulesets/global",
        ),
        "post_launch": ("/api/v1/instances",),
        "termination": ("/api/v1/instances",),
        "terminal": (
            "/api/v1/firewall-rulesets",
            "/api/v1/firewall-rulesets/global",
        ),
    }
    assert sum(map(len, supervisor.PHASE_REQUESTS.values())) == 13
    commands = contract.local_supervisor_argv_templates()
    assert set(commands) == {
        "materialize",
        "observe_prelaunch",
        "observe_security",
        "observe_post_launch",
        "observe_termination",
        "observe_terminal",
        "release_bootstrap",
        "verify_inbound_complete",
        "verify_inbound_failed",
        "archive_complete",
        "archive_failed",
        "prepare_bundle",
    }
    for argv in commands.values():
        assert argv[0:2] == ["${REPOSITORY_ROOT}/.venv/bin/python", "-I"]
        assert all(value not in argv for value in ("sh", "bash", "-c", "curl", "wget"))


def test_exact_local_supervisor_interpreter_loads_bound_modules(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    for relative in (
        "containers/sira-smoke/bounded/local_supervisor_bootstrap.py",
        "src/giclab/harness/t07_bounded_supervisor.py",
        "src/giclab/harness/t07_bounded_smoke.py",
    ):
        destination = repository / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, destination)
    plan_fixture = repository / "containers/sira-smoke/bounded/bounded-smoke-plan-v2.json"
    plan_fixture.parent.mkdir(parents=True, exist_ok=True)
    plan_fixture.write_bytes(b"{}\n")
    (repository / ".venv").symlink_to(ROOT / ".venv")
    subprocess.run(("git", "init", "-q", "-b", contract.BRANCH), cwd=repository, check=True)
    subprocess.run(("git", "add", "."), cwd=repository, check=True)
    subprocess.run(
        (
            "git",
            "-c",
            "user.name=GIC Test",
            "-c",
            "user.email=gic-test@example.invalid",
            "commit",
            "-q",
            "-m",
            "fixture",
        ),
        cwd=repository,
        check=True,
    )
    fixture_commit = (
        subprocess.check_output(("git", "rev-parse", "HEAD"), cwd=repository).decode().strip()
    )
    plan_path = repository / "containers/sira-smoke/bounded/bounded-smoke-plan-v2.json"
    substitutions = {
        "${REPOSITORY_ROOT}": str(repository),
        "${SUPERVISOR_SHA256}": supervisor.sha256_bytes(
            (repository / "src/giclab/harness/t07_bounded_supervisor.py").read_bytes()
        ),
        "${PLAN_SHA256}": supervisor.sha256_bytes(plan_path.read_bytes()),
        "${CONTRACT_SHA256}": supervisor.sha256_bytes(
            (repository / "src/giclab/harness/t07_bounded_smoke.py").read_bytes()
        ),
        "${EXECUTION_COMMIT}": fixture_commit,
        "${AUTHORIZATION_REFERENCE}": AUTHORIZATION_REFERENCE,
        "${PRIVATE_SECURITY_BINDING_PATH}": str(
            repository / "artifacts/private-binding-fixture.json"
        ),
        "${PRIVATE_SECURITY_BINDING_SEAL_SHA256}": "4" * 64,
    }
    argv = contract.materialize_argv(
        contract.local_supervisor_argv_templates()["materialize"], substitutions
    )
    completed = subprocess.run(
        (*argv, "--help"),
        cwd=repository,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        check=False,
        timeout=15,
    )
    assert completed.returncode == 0, completed.stderr.decode("utf-8", "replace")
    assert b"usage:" in completed.stdout


def test_actual_repository_base_authority_accepts_the_v2_candidate() -> None:
    plan = json.loads(
        (ROOT / "containers/sira-smoke/bounded/bounded-smoke-plan-v2.json").read_text(
            encoding="utf-8"
        )
    )
    supervisor._validate_base_authority(ROOT, plan)


def test_repository_identity_requires_reviewed_commit_ancestry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    reviewed = "a" * 40
    expected = "b" * 40
    monkeypatch.setattr(supervisor, "REVIEWED_IMPLEMENTATION_COMMIT", reviewed)
    calls: list[tuple[str, ...]] = []

    def related_git(root: Path, *args: str) -> str:
        assert root == tmp_path
        calls.append(args)
        if args[:2] == ("branch", "--show-current"):
            return supervisor.BRANCH
        if args[:2] == ("rev-parse", "HEAD"):
            return expected
        return ""

    monkeypatch.setattr(supervisor, "_git", related_git)
    supervisor.verify_repository_identity(tmp_path, expected)
    assert (
        "merge-base",
        "--is-ancestor",
        reviewed,
        expected,
    ) in calls

    def unrelated_git(root: Path, *args: str) -> str:
        if args[:2] == ("merge-base", "--is-ancestor"):
            raise supervisor.BoundedSupervisorError("synthetic unrelated history")
        return related_git(root, *args)

    monkeypatch.setattr(supervisor, "_git", unrelated_git)
    with pytest.raises(supervisor.BoundedSupervisorError, match="unrelated history"):
        supervisor.verify_repository_identity(tmp_path, expected)


def test_hash_first_local_loader_does_not_propagate_credentials_to_git(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bootstrap = _load_local_bootstrap()
    monkeypatch.setenv("LAMBDA_API_KEY", "PUBLIC_DUMMY_LAMBDA_CANARY")
    monkeypatch.setenv("SIRA_API_KEY", "PUBLIC_DUMMY_SIRA_CANARY")
    monkeypatch.setenv("OPENAI_API_KEY", "PUBLIC_DUMMY_OPENAI_CANARY")
    observed_environments: list[Mapping[str, str]] = []

    def fake_run(command: tuple[str, ...], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        environment = cast(Mapping[str, str], kwargs["env"])
        observed_environments.append(environment)
        stdout = (COMMIT + "\n").encode() if "rev-parse" in command else b""
        return subprocess.CompletedProcess(command, 0, stdout, b"")

    monkeypatch.setattr(bootstrap.subprocess, "run", fake_run)
    bootstrap._verify_clean_repository(tmp_path, COMMIT)
    assert len(observed_environments) == 2
    assert all(
        set(environment) == {"HOME", "LANG", "LC_ALL", "PATH"}
        and not {"LAMBDA_API_KEY", "SIRA_API_KEY", "OPENAI_API_KEY"}.intersection(environment)
        for environment in observed_environments
    )


def test_upload_bundle_is_exact_tracked_manifest_surface_and_excludes_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    artifact_paths = [
        "containers/sira-smoke/bounded/bootstrap.py",
        *(f"safe/member-{index:02d}.txt" for index in range(33)),
    ]
    artifacts: list[dict[str, object]] = []
    for index, relative in enumerate(artifact_paths):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        encoded = f"public fixture {index}\n".encode()
        path.write_bytes(encoded)
        artifacts.append(
            {
                "path": relative,
                "bytes": len(encoded),
                "sha256": hashlib.sha256(encoded).hexdigest(),
            }
        )
    plan_path = tmp_path / supervisor.BOUNDED_PLAN_RELATIVE
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text('{"synthetic":true}\n', encoding="utf-8")
    plan_sha256 = hashlib.sha256(plan_path.read_bytes()).hexdigest()
    (tmp_path / ".env").write_text("LAMBDA_API_KEY=PUBLIC_DUMMY_NEVER_UPLOAD\n")
    (tmp_path / "artifacts").mkdir()
    (tmp_path / "artifacts/private.txt").write_text("PUBLIC_DUMMY_PRIVATE\n")
    tracked = sorted({supervisor.BOUNDED_PLAN_RELATIVE.as_posix(), *artifact_paths})
    monkeypatch.setattr(
        supervisor,
        "_git",
        lambda root, *args: "\n".join(tracked),
    )
    rows, manifest_encoded = supervisor._plan_upload_rows(
        tmp_path,
        plan={"implementation": {"artifacts": artifacts}},
        plan_sha256=plan_sha256,
        expected_commit=COMMIT,
    )
    names = {name for name, _ in rows}
    manifest = json.loads(manifest_encoded)
    assert names == set(tracked)
    assert manifest["archive_member_count"] == 36
    assert ".env" not in names
    assert all(not name.startswith("artifacts/") and ".git" not in name for name in names)
    assert b"PUBLIC_DUMMY_NEVER_UPLOAD" not in manifest_encoded


def _patch_remote_paths(
    bootstrap: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> dict[str, Path]:
    home = tmp_path / "home/ubuntu"
    config = home / ".config/giclab"
    config.mkdir(parents=True)
    paths = {
        "bootstrap": home / "t07-bounded-bootstrap.py",
        "archive": home / "t07-bounded-repository.tar",
        "bundle": home / "t07-bounded-bundle",
        "plan": home
        / "t07-bounded-bundle/containers/sira-smoke/bounded/bounded-smoke-plan-v2.json",
        "contract": home / "t07-bounded-bundle/src/giclab/harness/t07_bounded_smoke.py",
        "authorization": home / "t07-bounded-authorization.json",
        "release": home / "t07-bounded-bootstrap-release.json",
        "secret": config / "sira_api_key",
        "output": home / "t07-bounded-output-0002",
    }
    for name, constant in (
        ("REMOTE_BOOTSTRAP_FILE", paths["bootstrap"]),
        ("REMOTE_BUNDLE_ARCHIVE", paths["archive"]),
        ("REMOTE_BUNDLE_ROOT", paths["bundle"]),
        ("REMOTE_PLAN_FILE", paths["plan"]),
        ("REMOTE_CONTRACT_FILE", paths["contract"]),
        ("REMOTE_AUTHORIZATION_FILE", paths["authorization"]),
        ("REMOTE_RELEASE_FILE", paths["release"]),
        ("REMOTE_SECRET_FILE", paths["secret"]),
        ("REMOTE_OUTPUT_ROOT", paths["output"]),
    ):
        monkeypatch.setattr(bootstrap, name, constant)
    paths["bootstrap"].write_text("# reviewed fixture\n")
    paths["authorization"].write_text("{}\n")
    paths["release"].write_text("{}\n")
    paths["secret"].write_text("PUBLIC_DUMMY_WINNER_SECRET\n")
    paths["secret"].chmod(0o600)
    return paths


def _remote_main_argv(
    paths: Mapping[str, Path], *, plan_sha256: str, archive_sha256: str, manifest_sha256: str
) -> list[str]:
    return [
        "--bootstrap-file-sha256",
        "9" * 64,
        "--bundle-archive",
        str(paths["archive"]),
        "--bundle-archive-sha256",
        archive_sha256,
        "--bundle-manifest-sha256",
        manifest_sha256,
        "--plan",
        str(paths["plan"]),
        "--plan-sha256",
        plan_sha256,
        "--contract-file",
        str(paths["contract"]),
        "--contract-sha256",
        "a" * 64,
        "--authorization",
        str(paths["authorization"]),
        "--authorization-sha256",
        "3" * 64,
        "--bootstrap-release",
        str(paths["release"]),
        "--bootstrap-release-sha256",
        "4" * 64,
        "--bundle-root",
        str(paths["bundle"]),
        "--secret-file",
        str(paths["secret"]),
        "--output-root",
        str(paths["output"]),
    ]


def test_self_consistent_upload_tamper_cannot_import_code_or_open_secret_before_release_binding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bootstrap = _load_remote_bootstrap()
    paths = _patch_remote_paths(bootstrap, tmp_path, monkeypatch)
    manifest = b'{"synthetic":true}\n'
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w", format=tarfile.USTAR_FORMAT) as archive:
        info = tarfile.TarInfo("BUNDLE_MANIFEST.json")
        info.size = len(manifest)
        info.mode = 0o444
        info.mtime = 0
        archive.addfile(info, io.BytesIO(manifest))
    archive_bytes = stream.getvalue()
    paths["archive"].write_bytes(archive_bytes)
    actual_archive_sha256 = hashlib.sha256(archive_bytes).hexdigest()
    manifest_sha256 = hashlib.sha256(manifest).hexdigest()
    monkeypatch.setattr(bootstrap, "_assert_remote_capacity", lambda root: None)
    monkeypatch.setattr(bootstrap, "_record_presecret_failure", lambda **kwargs: None)
    monkeypatch.setattr(bootstrap, "_validate_bootstrap_file", lambda **kwargs: None)
    monkeypatch.setattr(
        bootstrap,
        "validate_authorization",
        lambda *args, **kwargs: {"execution_commit": COMMIT},
    )
    monkeypatch.setattr(
        bootstrap,
        "validate_bootstrap_release",
        lambda *args, **kwargs: {
            "execution_commit": COMMIT,
            "bundle_archive_sha256": "f" * 64,
            "bundle_manifest_sha256": manifest_sha256,
            "bootstrap_file_sha256": "9" * 64,
        },
    )
    imported = False
    acquired = False

    def import_forbidden(*args: object, **kwargs: object) -> ModuleType:
        nonlocal imported
        imported = True
        raise AssertionError("untrusted contract imported")

    def acquire_forbidden(*args: object, **kwargs: object) -> object:
        nonlocal acquired
        acquired = True
        raise AssertionError("secret opened")

    monkeypatch.setattr(bootstrap, "_load_contract", import_forbidden)
    monkeypatch.setattr(bootstrap, "acquire_secret_lease", acquire_forbidden)
    with pytest.raises(bootstrap.BootstrapError, match="archive hash"):
        bootstrap.main(
            _remote_main_argv(
                paths,
                plan_sha256="2" * 64,
                archive_sha256=actual_archive_sha256,
                manifest_sha256=manifest_sha256,
            )
        )
    assert imported is False
    assert acquired is False
    assert paths["secret"].read_text() == "PUBLIC_DUMMY_WINNER_SECRET\n"


def test_replayed_single_use_root_cannot_open_or_destroy_winners_secret(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bootstrap = _load_remote_bootstrap()
    paths = _patch_remote_paths(bootstrap, tmp_path, monkeypatch)
    paths["archive"].write_bytes(b"synthetic archive")
    plan_bytes = b"{}\n"
    plan_sha256 = hashlib.sha256(plan_bytes).hexdigest()
    paths["output"].mkdir(mode=0o700)
    monkeypatch.setattr(bootstrap, "_record_presecret_failure", lambda **kwargs: None)
    monkeypatch.setattr(bootstrap, "_validate_bootstrap_file", lambda **kwargs: None)
    monkeypatch.setattr(
        bootstrap,
        "validate_authorization",
        lambda *args, **kwargs: {"execution_commit": COMMIT},
    )
    monkeypatch.setattr(
        bootstrap,
        "validate_bootstrap_release",
        lambda *args, **kwargs: {
            "execution_commit": COMMIT,
            "bundle_archive_sha256": "7" * 64,
            "bundle_manifest_sha256": "8" * 64,
            "bootstrap_file_sha256": "9" * 64,
        },
    )
    monkeypatch.setattr(
        bootstrap,
        "_validate_upload_bundle",
        lambda *args, **kwargs: (
            {"execution_commit": COMMIT},
            {"containers/sira-smoke/bounded/bounded-smoke-plan-v2.json": plan_bytes},
        ),
    )
    monkeypatch.setattr(bootstrap, "_validate_bundle_against_plan", lambda *a, **k: None)
    imported = False
    acquired = False

    def import_forbidden(*args: object, **kwargs: object) -> ModuleType:
        nonlocal imported
        imported = True
        raise AssertionError("contract imported by replay")

    def acquire_forbidden(*args: object, **kwargs: object) -> object:
        nonlocal acquired
        acquired = True
        raise AssertionError("winner secret opened by replay")

    monkeypatch.setattr(bootstrap, "_load_contract", import_forbidden)
    monkeypatch.setattr(bootstrap, "acquire_secret_lease", acquire_forbidden)
    with pytest.raises(bootstrap.BootstrapError, match="not fresh"):
        bootstrap.main(
            _remote_main_argv(
                paths,
                plan_sha256=plan_sha256,
                archive_sha256="7" * 64,
                manifest_sha256="8" * 64,
            )
        )
    assert imported is False
    assert acquired is False
    assert paths["secret"].read_text() == "PUBLIC_DUMMY_WINNER_SECRET\n"


def test_presecret_failure_burns_run_identity_and_cannot_be_replayed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bootstrap = _load_remote_bootstrap()
    paths = _patch_remote_paths(bootstrap, tmp_path, monkeypatch)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("SIRA_API_KEY", raising=False)
    monkeypatch.setattr(bootstrap, "_assert_remote_capacity", lambda root: None)
    authorization_calls = 0
    imported = False
    acquired = False

    def reject_authorization(*args: object, **kwargs: object) -> object:
        nonlocal authorization_calls
        authorization_calls += 1
        raise bootstrap.BootstrapError("synthetic authorization rejection")

    def import_forbidden(*args: object, **kwargs: object) -> ModuleType:
        nonlocal imported
        imported = True
        raise AssertionError("contract imported after burned run")

    def acquire_forbidden(*args: object, **kwargs: object) -> object:
        nonlocal acquired
        acquired = True
        raise AssertionError("secret opened after burned run")

    monkeypatch.setattr(bootstrap, "validate_authorization", reject_authorization)
    monkeypatch.setattr(bootstrap, "_load_contract", import_forbidden)
    monkeypatch.setattr(bootstrap, "acquire_secret_lease", acquire_forbidden)
    argv = _remote_main_argv(
        paths,
        plan_sha256="2" * 64,
        archive_sha256="7" * 64,
        manifest_sha256="8" * 64,
    )
    with pytest.raises(bootstrap.BootstrapError, match="authorization rejection"):
        bootstrap.main(argv)
    disposition = json.loads(
        (paths["output"] / "evidence/early-failure-disposition.json").read_text(encoding="utf-8")
    )
    assert disposition["failure_stage"] == "authorization_validation"
    assert disposition["failure_code"] == "bootstrap_contract_rejected"
    assert (paths["output"] / "EARLY_FAILURE_ARCHIVE_IDENTITY.json").is_file()

    with pytest.raises(bootstrap.BootstrapError, match="not fresh"):
        bootstrap.main(argv)
    assert authorization_calls == 1
    assert imported is False
    assert acquired is False
    assert paths["secret"].read_text() == "PUBLIC_DUMMY_WINNER_SECRET\n"


def test_hash_first_loaders_execute_verified_bytes_after_path_replacement(tmp_path: Path) -> None:
    local = _load_local_bootstrap()
    remote = _load_remote_bootstrap()
    source = tmp_path / "contract.py"
    verified = b"IDENTITY = 'verified'\n"
    source.write_bytes(verified)
    held = local._verified(source, hashlib.sha256(verified).hexdigest())
    replacement = tmp_path / "replacement.py"
    replacement.write_text("IDENTITY = 'replacement'\n", encoding="utf-8")
    replacement.replace(source)
    local_module = local._load_verified_bytes(source, held, "test_t07_verified_local")
    assert local_module.IDENTITY == "verified"

    source.write_bytes(verified)
    remote_held = remote._read_regular(source, max_bytes=1_024)
    replacement.write_text("IDENTITY = 'replacement'\n", encoding="utf-8")
    replacement.replace(source)
    remote_module = remote._load_contract(source, remote_held)
    assert remote_module.IDENTITY == "verified"


@pytest.mark.parametrize("sensitive_name", ["api_key", "API Key", "api-key", "api_token"])
def test_semantically_sensitive_key_value_records_are_dropped_from_projection(
    sensitive_name: str,
) -> None:
    schema = {
        "type": "object",
        "properties": {
            "tags": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "key": {"type": "string"},
                        "value": {"type": "string"},
                    },
                },
            }
        },
    }
    projected = supervisor._project_to_declared_schema(
        {
            "tags": [
                {"key": sensitive_name, "value": "PUBLIC_DUMMY_CANARY"},
                {"key": "project", "value": "gic-lab"},
            ]
        },
        schema,
        root_schema=schema,
    )
    assert projected == {"tags": [{"key": "project", "value": "gic-lab"}]}


def test_nested_semantically_sensitive_generic_record_is_dropped() -> None:
    schema = {
        "type": "object",
        "properties": {
            "metadata": {
                "type": "object",
                "additionalProperties": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "value": {"type": "string"},
                    },
                },
            }
        },
    }
    projected = supervisor._project_to_declared_schema(
        {"metadata": {"nested": {"name": "private_key", "value": "PUBLIC_DUMMY"}}},
        schema,
        root_schema=schema,
    )
    assert projected == {"metadata": {}}


def test_materialization_and_all_observer_phases_are_durable_and_secret_safe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    summary, plan_sha256, baseline_sha256 = _materialize(tmp_path, monkeypatch)
    authorization = tmp_path / supervisor.AUTHORIZATION_RELATIVE
    private_path = tmp_path / supervisor.PRIVATE_BINDING_RELATIVE
    assert authorization.stat().st_mode & 0o777 == 0o600
    assert private_path.stat().st_mode & 0o777 == 0o600
    private = json.loads(private_path.read_text(encoding="utf-8"))
    common = {
        "instance-types": {
            "data": {
                "gpu_1x_a10": {
                    "instance_type": _instance_type(),
                    "regions_with_capacity_available": [_region()],
                }
            }
        },
        "images": {
            "data": [
                {
                    "id": "synthetic-image-private",
                    "created_time": "2026-08-01T00:00:00Z",
                    "updated_time": "2026-08-01T00:00:00Z",
                    "name": "Synthetic image",
                    "description": "fixture",
                    "family": "lambda-stack-22-04",
                    "version": "22.4.5-2141",
                    "architecture": "x86_64",
                    "region": _region(),
                }
            ]
        },
        "regions": {"data": [_region()]},
        "ssh-keys": {
            "data": [
                {
                    "id": "synthetic-key-private",
                    "name": "fractal-lambda-codex",
                    "public_key": PUBLIC_KEY,
                }
            ]
        },
    }
    baseline_response = {
        "data": {
            "id": "global",
            "name": "global",
            "rules": [_rule("synthetic sealed baseline", source="198.51.100.0/24")],
        }
    }
    phases: list[tuple[str, dict[str, object]]] = [
        (
            "prelaunch",
            {
                "/api/v1/instance-types": common["instance-types"],
                "/api/v1/images": common["images"],
                "/api/v1/regions": common["regions"],
                "/api/v1/ssh-keys": common["ssh-keys"],
                "/api/v1/firewall-rulesets": {"data": []},
                "/api/v1/firewall-rulesets/global": baseline_response,
                "/api/v1/instances": {"data": []},
            },
        ),
        (
            "security",
            {
                "/api/v1/firewall-rulesets": {
                    "data": [
                        {
                            "id": "synthetic-ruleset-private",
                            "name": private["owned_ruleset_name"],
                            "region": _region(),
                            "rules": [private["owned_ruleset_rule"]],
                            "created": "2026-08-11T20:00:00Z",
                            "instance_ids": [],
                        }
                    ]
                },
                "/api/v1/firewall-rulesets/global": {
                    "data": {
                        "id": "global",
                        "name": "global",
                        "rules": [private["strict_firewall_rule"]],
                    }
                },
            },
        ),
        (
            "post_launch",
            {"/api/v1/instances": {"data": [_instance("active", "synthetic-ruleset-private")]}},
        ),
        (
            "termination",
            {"/api/v1/instances": {"data": [_instance("terminated", "synthetic-ruleset-private")]}},
        ),
        (
            "terminal",
            {
                "/api/v1/firewall-rulesets": {"data": []},
                "/api/v1/firewall-rulesets/global": baseline_response,
            },
        ),
    ]
    clock_value = 0

    def monotonic_ns() -> int:
        nonlocal clock_value
        clock_value += 1_000_000_000
        return clock_value

    for phase, documents in phases:
        transport = FakeTransport(documents)
        report = _execute_observer(
            tmp_path,
            summary,
            plan_sha256,
            phase=phase,
            transport=transport,
            monotonic_ns=monotonic_ns,
        )
        assert transport.paths == list(supervisor.PHASE_REQUESTS[phase])
        assert report["phase"] == phase
    state = json.loads((tmp_path / supervisor.STATE_RELATIVE).read_text(encoding="utf-8"))
    ledger = (tmp_path / supervisor.LEDGER_RELATIVE).read_bytes()
    assert state["status"] == "complete"
    assert state["request_count"] == 13
    assert state["event_count"] == 51
    assert len(ledger.splitlines()) == 51
    assert b"public-dummy-lambda-canary-never-retained" not in ledger
    response_root = tmp_path / supervisor.RESPONSES_RELATIVE
    retained_responses = b"".join(path.read_bytes() for path in sorted(response_root.iterdir()))
    assert JSON_SECRET_CANARY.encode() not in retained_responses
    assert b"jupyter_token" not in retained_responses
    assert b"unknown_secret_material" not in retained_responses
    assert baseline_sha256 in (
        tmp_path / supervisor.RUN_ROOT_RELATIVE / "terminal-report.json"
    ).read_text(encoding="utf-8")


def test_possible_send_failure_enters_nonreplay_cleanup_and_allows_expired_final_checks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    summary, plan_sha256, _ = _materialize(tmp_path, monkeypatch)

    class FailedTransport:
        def fetch(self, *args: object, **kwargs: object) -> supervisor.HttpResponse:
            del args, kwargs
            raise supervisor.TransportFailure("response_body", "response_body_failure", 17, 9)

    with pytest.raises(supervisor.BoundedSupervisorError, match="transport failed"):
        _execute_observer(
            tmp_path,
            summary,
            plan_sha256,
            phase="prelaunch",
            transport=FailedTransport(),
        )
    state = json.loads((tmp_path / supervisor.STATE_RELATIVE).read_text(encoding="utf-8"))
    events = [
        json.loads(line)
        for line in (tmp_path / supervisor.LEDGER_RELATIVE).read_text(encoding="utf-8").splitlines()
    ]
    assert state["status"] == "cleanup_required"
    assert state["next_phase"] == "terminal"
    assert state["attempted_request_ordinals"] == [1]
    assert [event["event_type"] for event in events[-2:]] == [
        "request_outcome_unknown_after_send",
        "phase_failed",
    ]
    assert events[-2]["failure_stage"] == "response_body"
    with pytest.raises(supervisor.BoundedSupervisorError, match="phase/state"):
        _execute_observer(
            tmp_path,
            summary,
            plan_sha256,
            phase="prelaunch",
            transport=FailedTransport(),
        )
    terminal = FakeTransport(
        {
            "/api/v1/firewall-rulesets": {"data": []},
            "/api/v1/firewall-rulesets/global": {
                "data": {
                    "id": "global",
                    "name": "global",
                    "rules": [_rule("synthetic sealed baseline", source="198.51.100.0/24")],
                }
            },
        }
    )
    report = _execute_observer(
        tmp_path,
        summary,
        plan_sha256,
        phase="terminal",
        transport=terminal,
        utc_now=lambda: NOW + timedelta(hours=2),
    )
    assert report["provider_termination_previously_verified"] is True
    state = json.loads((tmp_path / supervisor.STATE_RELATIVE).read_text(encoding="utf-8"))
    assert state["status"] == "cleanup_complete"
    assert state["attempted_request_ordinals"] == [1, 12, 13]


def test_post_launch_failure_can_only_continue_through_termination_and_final_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    summary, plan_sha256, _ = _materialize(tmp_path, monkeypatch)
    private = json.loads(
        (tmp_path / supervisor.PRIVATE_BINDING_RELATIVE).read_text(encoding="utf-8")
    )
    documents = _phase_documents(private)
    for phase in ("prelaunch", "security"):
        _execute_observer(
            tmp_path,
            summary,
            plan_sha256,
            phase=phase,
            transport=FakeTransport(documents[phase]),
        )

    class FailedPostLaunch:
        def fetch(self, *args: object, **kwargs: object) -> supervisor.HttpResponse:
            del args, kwargs
            raise supervisor.TransportFailure("response_body", "synthetic_failure", 0, 1)

    with pytest.raises(supervisor.BoundedSupervisorError, match="transport failed"):
        _execute_observer(
            tmp_path,
            summary,
            plan_sha256,
            phase="post_launch",
            transport=FailedPostLaunch(),
        )
    state = json.loads((tmp_path / supervisor.STATE_RELATIVE).read_text(encoding="utf-8"))
    assert state["status"] == "cleanup_required"
    assert state["next_phase"] == "termination"
    assert state["bound_instance_id"] is None
    termination = _execute_observer(
        tmp_path,
        summary,
        plan_sha256,
        phase="termination",
        transport=FakeTransport(documents["termination"]),
        utc_now=lambda: NOW + timedelta(hours=2),
    )
    assert termination["identity_recovered_during_cleanup"] is True
    terminal = _execute_observer(
        tmp_path,
        summary,
        plan_sha256,
        phase="terminal",
        transport=FakeTransport(documents["terminal"]),
        utc_now=lambda: NOW + timedelta(hours=3),
    )
    assert terminal["provider_termination_previously_verified"] is True
    state = json.loads((tmp_path / supervisor.STATE_RELATIVE).read_text(encoding="utf-8"))
    assert state["status"] == "cleanup_complete"
    assert state["attempted_request_ordinals"] == list(range(1, 14))


def _command_receipt(
    argv: list[str],
    *,
    returncode: int = 0,
    stdout: bytes = b"x",
    stderr: bytes = b"",
) -> bytes:
    return supervisor.canonical_json_bytes(
        {
            "argv_sha256": supervisor._argv_sha256(argv),
            "returncode": returncode,
            "stdout_bytes": len(stdout),
            "stdout_sha256": hashlib.sha256(stdout).hexdigest(),
            "stderr_bytes": len(stderr),
            "stderr_sha256": hashlib.sha256(stderr).hexdigest(),
            "elapsed_seconds": 0.01,
        }
    )


def _add_lifecycle_records(
    records: dict[str, bytes],
    *,
    plan: Mapping[str, object],
    root_name: str,
    condition: str,
    run_id: str,
    container_id: str,
    image_id: str,
) -> None:
    prefix = f"{root_name}/"
    common = {"${CONTAINER_ID}": container_id, "${RUN_ID}": run_id}
    remote_root = str(cast(Mapping[str, object], plan["storage"])["remote_active_root"])
    host_root = f"{remote_root}/evidence/{root_name}/payload-prestop"
    readiness_path = (
        "/giclab/attempt/browser-preflight.json"
        if root_name == "browser-preflight"
        else "/giclab/attempt/.giclab-entrypoint-ready"
    )
    raw_stdout = b"synthetic stdout\n"
    raw_stderr = b""
    if root_name == "browser-preflight":
        template = contract.browser_preflight_create_argv()
    elif root_name == "model-preflight":
        template = contract.model_preflight_create_argv()
    else:
        template = contract.container_create_argv(condition)
    substitutions = {
        "${SIRA_SECRET_FILE}": "/home/ubuntu/.config/giclab/sira_api_key",
        "${EXECUTION_COMMIT}": COMMIT,
        "${AUTHORIZATION_REFERENCE}": AUTHORIZATION_REFERENCE,
        "${IMAGE_ID}": image_id,
    }
    needed = {
        match.group(0) for item in template for match in re.finditer(r"\$\{[A-Z][A-Z0-9_]*\}", item)
    }
    create_argv = contract.materialize_argv(
        template,
        {key: value for key, value in substitutions.items() if key in needed},
    )
    create_stdout = (container_id + "\n").encode()
    records[prefix + "container-create.json"] = _command_receipt(
        list(create_argv), stdout=create_stdout, stderr=b""
    )
    actions: dict[str, tuple[str, dict[str, str], int]] = {
        "container-start.json": ("start_detached", common, 0),
        "container-inspect-before-stop-command.json": ("inspect", common, 0),
        "container-top-before-stop-command.json": ("top", common, 0),
        "container-readiness.json": (
            "readiness",
            {**common, "${READINESS_PATH}": readiness_path},
            0,
        ),
        "container-copy-out-prestop.json": (
            "copy_out",
            {**common, "${HOST_ATTEMPT_ROOT}": host_root},
            0,
        ),
        "container-stop.json": ("stop", common, 0),
        "container-kill.json": ("kill", common, 1),
        "container-terminal-inspect-command.json": ("inspect", common, 0),
        "container-remove.json": ("remove", common, 0),
        "container-removal-proof.json": ("inspect", common, 1),
        "container-residue-containers.json": ("container_residue", common, 0),
        "container-residue-networks.json": ("network_residue", common, 0),
        "container-residue-volumes.json": ("volume_residue", common, 0),
    }
    if root_name != "browser-preflight":
        actions.update(
            {
                "container-release.json": ("release", common, 0),
                "container-wait.json": ("wait", common, 0),
                "container-logs.json": ("logs", common, 0),
                "container-workload-result.json": ("wait", common, 0),
            }
        )
    for filename, (action, substitutions, returncode) in actions.items():
        argv = supervisor._render_lifecycle_argv(plan, action, substitutions)
        binds_raw_logs = (
            root_name == "browser-preflight" and filename == "container-start.json"
        ) or (
            root_name != "browser-preflight"
            and filename in {"container-logs.json", "container-workload-result.json"}
        )
        if filename in {
            "container-residue-containers.json",
            "container-residue-networks.json",
            "container-residue-volumes.json",
        }:
            receipt_stdout = b""
        elif filename == "container-inspect-before-stop-command.json":
            receipt_stdout = b"__PRESTOP_INSPECT__"
        elif filename == "container-top-before-stop-command.json":
            receipt_stdout = b"__PRESTOP_TOP__"
        elif filename == "container-terminal-inspect-command.json":
            receipt_stdout = b"__TERMINAL_INSPECT__"
        else:
            receipt_stdout = raw_stdout if binds_raw_logs else b"x"
        records[prefix + filename] = _command_receipt(
            argv, returncode=returncode, stdout=receipt_stdout, stderr=raw_stderr
        )
    payload_bytes = 32
    records[prefix + "container-id.txt"] = (container_id + "\n").encode()

    def option(name: str) -> str:
        return create_argv[create_argv.index(name) + 1]

    def options(name: str) -> list[str]:
        return [create_argv[index + 1] for index, value in enumerate(create_argv) if value == name]

    labels = dict(value.split("=", 1) for value in options("--label"))
    tmpfs = {value.split(":", 1)[0]: value.split(":", 1)[1] for value in options("--tmpfs")}
    mount_values = options("--mount")
    host_mounts: list[dict[str, object]] = []
    realized_mounts: list[dict[str, object]] = []
    for value in mount_values:
        fields = dict(part.split("=", 1) for part in value.split(",") if "=" in part)
        host_mounts.append(
            {
                "Type": fields["type"],
                "Source": fields["src"],
                "Target": fields["dst"],
                "ReadOnly": True,
            }
        )
        realized_mounts.append(
            {
                "Type": fields["type"],
                "Source": fields["src"],
                "Destination": fields["dst"],
                "RW": False,
            }
        )
    image_index = create_argv.index(image_id)
    pre_stop_inspect = supervisor.canonical_json_bytes(
        [
            {
                "Id": container_id,
                "Name": "/" + option("--name"),
                "Image": image_id,
                "State": {"Running": True, "Status": "running"},
                "Config": {
                    "Image": image_id,
                    "User": option("--user"),
                    "Entrypoint": [option("--entrypoint")],
                    "Cmd": list(create_argv[image_index + 1 :]),
                    "Labels": labels,
                    "Env": ["PATH=/usr/bin"],
                },
                "HostConfig": {
                    "Privileged": False,
                    "PidMode": "private",
                    "NetworkMode": option("--network"),
                    "IpcMode": option("--ipc"),
                    "CgroupnsMode": option("--cgroupns"),
                    "UTSMode": "",
                    "CapAdd": None,
                    "CapDrop": ["ALL"],
                    "SecurityOpt": ["no-new-privileges=true"],
                    "ReadonlyRootfs": True,
                    "Init": True,
                    "AutoRemove": False,
                    "RestartPolicy": {"Name": "no", "MaximumRetryCount": 0},
                    "NanoCpus": int(float(option("--cpus")) * 1_000_000_000),
                    "Memory": int(option("--memory")),
                    "MemorySwap": int(option("--memory-swap")),
                    "PidsLimit": int(option("--pids-limit")),
                    "ShmSize": int(option("--shm-size")),
                    "Tmpfs": tmpfs,
                    "Binds": None,
                    "VolumesFrom": None,
                    "Mounts": host_mounts,
                    "LogConfig": {
                        "Type": option("--log-driver"),
                        "Config": dict(value.split("=", 1) for value in options("--log-opt")),
                    },
                },
                "Mounts": realized_mounts,
            }
        ]
    )
    records[prefix + "container-inspect-before-stop.json"] = pre_stop_inspect
    process_name = "chromium" if root_name == "browser-preflight" else "python"
    records[prefix + "container-processes-before-stop.txt"] = (
        f"PID CMD\n1 init\n2 {process_name}\n".encode()
    )
    records[prefix + "container-inspect-before-stop-command.json"] = _command_receipt(
        supervisor._render_lifecycle_argv(plan, "inspect", common),
        stdout=pre_stop_inspect,
    )
    records[prefix + "container-top-before-stop-command.json"] = _command_receipt(
        supervisor._render_lifecycle_argv(plan, "top", common),
        stdout=records[prefix + "container-processes-before-stop.txt"],
    )
    records[prefix + "container-copy-out-prestop-budget.json"] = supervisor.canonical_json_bytes(
        {
            "phase": "prestop",
            "payload_bytes": payload_bytes,
            "payload_cap_bytes": 67_108_864,
            "within_cap": True,
            "copy_complete": True,
        }
    )
    records[prefix + "container-payload-capture.json"] = supervisor.canonical_json_bytes(
        {
            "schema_version": supervisor.SCHEMA_VERSION,
            "condition": condition,
            "copy_complete": True,
            "selected_phase": "prestop",
            "payload_root": "payload",
            "payload_bytes": payload_bytes,
            "payload_cap_bytes": 67_108_864,
            "captured_before_removal": True,
        }
    )
    records[prefix + "stdout.log"] = raw_stdout
    records[prefix + "stderr.log"] = raw_stderr
    terminal_inspect = supervisor.canonical_json_bytes(
        [{"Id": container_id, "State": {"Running": False, "Status": "exited"}}]
    )
    records[prefix + "container-terminal-inspect.json"] = terminal_inspect
    records[prefix + "container-terminal-inspect-command.json"] = _command_receipt(
        supervisor._render_lifecycle_argv(plan, "inspect", common),
        stdout=terminal_inspect,
    )
    records[prefix + "container-cleanup.json"] = supervisor.canonical_json_bytes(
        {
            "schema_version": supervisor.SCHEMA_VERSION,
            "condition": condition,
            "container_id_sha256": hashlib.sha256(container_id.encode()).hexdigest(),
            "terminal_state_observed": True,
            "removed": True,
            "owned_container_residue_count": 0,
            "owned_network_residue_count": 0,
            "owned_volume_residue_count": 0,
            "browser_process_residue_count": 0,
            "process_evidence_captured_before_removal": True,
            "payload_capture_complete_before_removal": True,
            "payload_capture_phase": "prestop",
            "payload_bytes": payload_bytes,
            "pre_stop_running_state_observed": True,
            "pre_stop_process_capture_succeeded": True,
            "pre_stop_process_count": 2,
        }
    )


def _release_for_fixture(
    run_root: Path, plan: Mapping[str, object]
) -> tuple[dict[str, object], bytes]:
    release_path = run_root / "BOOTSTRAP_RELEASE.json"
    if release_path.is_file():
        encoded = release_path.read_bytes()
        return json.loads(encoded), encoded
    selected = cast(Mapping[str, object], plan["lambda"])
    release = {
        "schema_version": supervisor.SCHEMA_VERSION,
        "plan_id": supervisor.PLAN_ID,
        "host_run_id": supervisor.HOST_RUN_ID,
        "authorization_reference": AUTHORIZATION_REFERENCE,
        "execution_commit": COMMIT,
        "plan_sha256": "2" * 64,
        "authorization_sha256": "3" * 64,
        "private_binding_sha256": "4" * 64,
        "observer_state_sha256": "5" * 64,
        "post_launch_report_sha256": "6" * 64,
        "bundle_archive_sha256": "7" * 64,
        "bundle_manifest_sha256": "8" * 64,
        "bootstrap_file_sha256": "9" * 64,
        "provider_active_observed_at_utc": "2026-08-11T20:00:00Z",
        "selected_provider_image": {
            "alias": selected["image_alias"],
            "family": selected["image_family"],
            "version": selected["image_version"],
            "attestation": "confirmed-in-provider-console",
            "binding_basis": "prelaunch-offered-plus-user-console-attestation",
            "post_launch_api_image_observation_available": False,
        },
        "issued_at_utc": "2026-08-11T20:00:01Z",
        "bootstrap_release": True,
        "single_use_output_root": "/home/ubuntu/t07-bounded-output-0002",
    }
    return release, supervisor.canonical_json_bytes(release)


def _write_complete_inbound(
    run_root: Path,
    *,
    secret_member: bool = False,
    extra_record: bytes | None = None,
) -> dict[str, bytes]:
    inbound = run_root / "inbound"
    inbound.mkdir()
    plan = _runtime_plan()
    release, release_encoded = _release_for_fixture(run_root, plan)
    image_id = "sha256:" + "a" * 64
    installed = b"playwright==1.39.0\n"
    records: dict[str, bytes] = {}
    artifact = cast(
        Mapping[str, object],
        cast(Mapping[str, object], plan["implementation"])["artifacts"][0],
    )
    records["bootstrap-authority.json"] = supervisor.canonical_json_bytes(
        {
            "schema_version": supervisor.SCHEMA_VERSION,
            "plan_id": supervisor.PLAN_ID,
            "host_run_id": supervisor.HOST_RUN_ID,
            "authorization_reference": release["authorization_reference"],
            "execution_commit": release["execution_commit"],
            "plan_sha256": release["plan_sha256"],
            "contract_sha256": artifact["sha256"],
            "authorization_sha256": release["authorization_sha256"],
            "private_binding_sha256": release["private_binding_sha256"],
            "bootstrap_release_sha256": hashlib.sha256(release_encoded).hexdigest(),
            "bundle_archive_sha256": release["bundle_archive_sha256"],
            "bundle_manifest_sha256": release["bundle_manifest_sha256"],
            "bootstrap_file_sha256": release["bootstrap_file_sha256"],
            "observer_state_sha256": release["observer_state_sha256"],
            "post_launch_report_sha256": release["post_launch_report_sha256"],
            "provider_active_observed_at_utc": release["provider_active_observed_at_utc"],
            "selected_provider_image": release["selected_provider_image"],
            "authority_validation_complete": True,
            "secret_value_or_hash_retained": False,
        }
    )
    lifecycle = (
        ("browser-preflight", "BROWSER-PREFLIGHT", "RUN-T07-BOUNDED-BROWSER-PREFLIGHT-0002"),
        ("model-preflight", "MODEL-PREFLIGHT", "RUN-T07-BOUNDED-MODEL-PREFLIGHT-0002"),
        ("reactive", "SIRA-REACTIVE", contract.RUN_IDS["SIRA-REACTIVE"]),
        ("simulative", "SIRA-SIMULATIVE", contract.RUN_IDS["SIRA-SIMULATIVE"]),
    )
    for index, (root_name, condition, run_id) in enumerate(lifecycle, start=1):
        _add_lifecycle_records(
            records,
            plan=plan,
            root_name=root_name,
            condition=condition,
            run_id=run_id,
            container_id=str(index) * 64,
            image_id=image_id,
        )
    limits = cast(Mapping[str, object], plan["limits"])
    meter_base = {
        "schema_version": supervisor.SCHEMA_VERSION,
        "scope": None,
        "argv_sha256": None,
        "returncode": None,
        "stdout_bytes": None,
        "stderr_bytes": None,
        "elapsed_ms": None,
        "failure_code": None,
        "aggregate_call_count": 0,
        "aggregate_output_bytes": 0,
        "work_call_count": 0,
        "work_output_bytes": 0,
        "cleanup_call_count": 0,
        "cleanup_output_bytes": 0,
        "aggregate_call_cap": limits["docker_lifecycle_calls"],
        "aggregate_output_cap_bytes": limits["docker_control_output_bytes"],
        "cleanup_reserved_calls": limits["docker_cleanup_reserved_calls"],
        "cleanup_reserved_output_bytes": limits["docker_cleanup_reserved_output_bytes"],
    }
    command_digest = "b" * 64
    meter_events = [
        {**meter_base, "event_sequence": 1, "event_type": "meter_started"},
        {
            **meter_base,
            "event_sequence": 2,
            "event_type": "command_started",
            "scope": "work",
            "argv_sha256": command_digest,
            "aggregate_call_count": 1,
            "work_call_count": 1,
        },
        {
            **meter_base,
            "event_sequence": 3,
            "event_type": "command_completed",
            "scope": "work",
            "argv_sha256": command_digest,
            "returncode": 0,
            "stdout_bytes": 2,
            "stderr_bytes": 0,
            "elapsed_ms": 1,
            "aggregate_call_count": 1,
            "aggregate_output_bytes": 2,
            "work_call_count": 1,
            "work_output_bytes": 2,
        },
    ]
    records["command-meter.jsonl"] = b"".join(
        json.dumps(event, separators=(",", ":"), sort_keys=True).encode() + b"\n"
        for event in meter_events
    )
    records["bootstrap-execution.json"] = supervisor.canonical_json_bytes(
        {
            "schema_version": supervisor.SCHEMA_VERSION,
            "plan_id": supervisor.PLAN_ID,
            "run_id": supervisor.HOST_RUN_ID,
            "record_kind": "remote_bootstrap_execution_interval",
            "started_at_utc": "2026-08-11T20:00:00Z",
            "ended_at_utc": "2026-08-11T20:00:10Z",
            "wall_clock_seconds": 10.0,
            "status": "completed",
            "provider_allocation_accounting": False,
            "cost_accounting_authority": "local-post-termination-compute-closeout",
        }
    )
    records["secret-cleanup.json"] = supervisor.canonical_json_bytes(
        {
            "schema_version": supervisor.SCHEMA_VERSION,
            "secret_variable_name": "SIRA_API_KEY",
            "secret_file_basename": "sira_api_key",
            "held_identity_established_before_preflight": True,
            "truncated_before_unlink": True,
            "unlinked": True,
            "absence_verified": True,
            "path_identity_replaced": False,
            "value_or_hash_retained": False,
            "manual_fallback_deletion_required": False,
        }
    )
    provider_image = {
        "alias": contract.SELECTED_IMAGE_ALIAS,
        "family": contract.SELECTED_IMAGE_FAMILY,
        "version": contract.SELECTED_IMAGE_VERSION,
        "attestation": "confirmed-in-provider-console",
        "binding_basis": "prelaunch-offered-plus-user-console-attestation",
        "post_launch_api_image_observation_available": False,
    }
    info_format = (
        '{"driver":{{json .Driver}},"root":{{json .DockerRootDir}},'
        '"operating_system":{{json .OperatingSystem}},"os_type":{{json .OSType}},'
        '"architecture":{{json .Architecture}},"cgroup_driver":{{json .CgroupDriver}},'
        '"cgroup_version":{{json .CgroupVersion}},'
        '"security_options":{{json .SecurityOptions}}}'
    )
    host_commands = [
        ["/usr/bin/docker", "version", "--format", "{{json .}}"],
        ["/usr/bin/docker", "info", "--format", info_format],
        [
            "/usr/bin/nvidia-smi",
            "--query-gpu=name,uuid,driver_version",
            "--format=csv,noheader,nounits",
        ],
    ]
    records["host-environment.json"] = supervisor.canonical_json_bytes(
        {
            "schema_version": supervisor.SCHEMA_VERSION,
            "captured_before_image_build": True,
            "provider_image": provider_image,
            "provider_image_identity_basis": "user-attested-not-postlaunch-api-observed",
            "os_release": {
                "id": "ubuntu",
                "version_id": "22.04",
                "pretty_name": "Ubuntu 22.04 LTS",
            },
            "kernel": {"system": "Linux", "release": "6.8.0", "machine": "x86_64"},
            "bootstrap_python": {"executable": "/usr/bin/python3", "version": "3.10.12"},
            "docker": {
                "client_version": "27.5.1",
                "client_os": "linux",
                "client_arch": "amd64",
                "server_version": "27.5.1",
                "server_os": "linux",
                "server_arch": "amd64",
                "storage_driver": "overlay2",
                "root_dir_sha256": "c" * 64,
                "operating_system": "Ubuntu 22.04 LTS",
                "os_type": "linux",
                "architecture": "x86_64",
                "cgroup_driver": "systemd",
                "cgroup_version": "2",
                "security_options": ["name=seccomp,profile=builtin"],
            },
            "gpus": [{"name": "NVIDIA A10", "uuid_sha256": "d" * 64, "driver_version": "570.00"}],
            "commands": [
                {
                    "argv": argv,
                    "argv_sha256": supervisor._argv_sha256(argv),
                    "returncode": 0,
                    "stdout_bytes": 1,
                    "stderr_bytes": 0,
                    "elapsed_seconds": 0.01,
                }
                for argv in host_commands
            ],
            "secret_values_retained": False,
        }
    )
    records["browser-preflight/payload/installed-packages.txt"] = installed
    records["browser-preflight/payload/browser-preflight.png"] = b"\x89PNG\r\n\x1a\nfixture"
    records["browser-preflight/payload/browser-preflight.json"] = supervisor.canonical_json_bytes(
        {
            "schema_version": supervisor.SCHEMA_VERSION,
            "source": "local-static-file",
            "network_mode": "none",
            "browser_actions": 1,
            "screenshot_captures": 1,
            "title": "GIC Lab T07 local browser preflight",
            "screenshot": "browser-preflight.png",
            "browser_running_before_container_stop": True,
            "browser_closed_by_fixture": False,
            "runtime_uid": 1000,
            "runtime_gid": 1000,
            "playwright_version": contract.PLAYWRIGHT_VERSION,
            "chromium_revision": contract.CHROMIUM_REVISION,
            "chromium_browser_version": contract.CHROMIUM_VERSION,
            "chromium_executable_sha256": "e" * 64,
            "installed_package_manifest_sha256": hashlib.sha256(installed).hexdigest(),
        }
    )
    records["model-preflight/payload/model-availability.json"] = supervisor.canonical_json_bytes(
        {
            "schema_version": supervisor.SCHEMA_VERSION,
            "method": "GET",
            "scheme": "https",
            "host": "api.openai.com",
            "path": "/v1/models/gpt-4o-2024-11-20",
            "http_status": 200,
            "response_bytes": 128,
            "model": contract.MODEL,
            "available": True,
            "retry_count": 0,
            "redirect_follow_count": 0,
        }
    )
    runtime_plan = cast(Mapping[str, object], plan["source_and_runtime"])
    provenance = {
        "schema_version": supervisor.SCHEMA_VERSION,
        "base_image": runtime_plan["base_image"],
        "base_image_index_digest": runtime_plan["base_image_index_digest"],
        "base_image_amd64_manifest": runtime_plan["base_image_amd64_manifest"],
        "base_image_amd64_config": runtime_plan["base_image_amd64_config"],
        "source_commit": runtime_plan["upstream_commit"],
        "source_tree": runtime_plan["upstream_tree"],
        "uv_lock_sha256": runtime_plan["uv_lock_sha256"],
        "routing_patch_sha256": runtime_plan["routing_patch_sha256"],
        "runtime_adaptation_sha256": runtime_plan["runtime_adaptation_sha256"],
        "playwright_version": runtime_plan["playwright"],
        "chromium_revision": runtime_plan["chromium_revision"],
        "chromium_version": runtime_plan["chromium_version"],
        "chromium_executable_sha256": "e" * 64,
        "installed_package_manifest_sha256": hashlib.sha256(installed).hexdigest(),
        "image_id": image_id,
        "platform": runtime_plan["platform"],
    }
    records["image-provenance.json"] = supervisor.canonical_json_bytes(provenance)
    records["image-inspect.json"] = supervisor.canonical_json_bytes([{"Id": image_id}])
    pair_conditions: list[dict[str, object]] = []
    decisions: dict[str, dict[str, object]] = {}
    completions: dict[str, dict[str, object]] = {}
    for mode, condition in (("reactive", "SIRA-REACTIVE"), ("simulative", "SIRA-SIMULATIVE")):
        provider_budget = {
            "schema_version": supervisor.SCHEMA_VERSION,
            "model_revision": contract.MODEL,
            "request_service_tier": "default",
            "observed_response_service_tiers": ["default"],
            "default_service_tier_response_count": 1,
            "cost_usd": 0.25,
            "input_tokens": 50,
            "cached_input_tokens": 0,
            "output_tokens": 50,
            "total_tokens": 100,
            "model_call_attempts": 1,
            "browser_actions": 1,
            "unreconciled_provider_attempts": 0,
            "output_bytes": 10,
        }
        runtime = {
            "schema_version": supervisor.SCHEMA_VERSION,
            "python_executable": "/opt/sira/.venv/bin/python",
            "python_version": "3.10.12",
            "os": "Linux",
            "architecture": "x86_64",
            "upstream_runner": "/opt/sira/scripts/run_web_agent.py",
            "runtime_adaptation_sha256": contract.RUNTIME_ADAPTATION_SHA256,
            "routing_sha256": contract.ROUTING_SHA256,
            "environment_variable_names": ["SIRA_API_KEY"],
            "secret_variable_names": ["SIRA_API_KEY"],
        }
        cleanup = {
            "schema_version": supervisor.SCHEMA_VERSION,
            "tracked_browser_environments": 1,
            "close_error_types": [],
            "all_environment_closes_succeeded": True,
        }
        payloads = {
            f"{mode}/payload/provider-budget.json": supervisor.canonical_json_bytes(
                provider_budget
            ),
            f"{mode}/payload/runtime-environment.json": supervisor.canonical_json_bytes(runtime),
            f"{mode}/payload/runtime-cleanup.json": supervisor.canonical_json_bytes(cleanup),
            f"{mode}/payload/sira-output/session.json": supervisor.canonical_json_bytes(
                {"history": [[{"screenshot": "iVBORw0KGgo="}]]}
            ),
            f"{mode}/payload/source-logs/session.log": b"synthetic source log\n",
        }
        records.update(payloads)
        raw_rows = [
            {"path": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
            for name, data in sorted(payloads.items())
        ]
        template = list(contract.container_create_argv(condition))
        substitutions = {
            "${SIRA_SECRET_FILE}": "/home/ubuntu/.config/giclab/sira_api_key",
            "${EXECUTION_COMMIT}": COMMIT,
            "${AUTHORIZATION_REFERENCE}": AUTHORIZATION_REFERENCE,
            "${IMAGE_ID}": image_id,
        }
        create_argv = list(contract.materialize_argv(template, substitutions))
        inner_argv = list(contract.condition_inner_argv(condition))
        configuration_refs = [
            "containers/sira-smoke/bounded/bounded-smoke-plan-v2.json",
            "experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/conditions/"
            + ("smoke-reactive.yaml" if mode == "reactive" else "smoke-simulative.yaml"),
            f"{mode}/resolved-command.json",
        ]
        records[f"{mode}/resolved-command.json"] = supervisor.canonical_json_bytes(
            {
                "schema_version": supervisor.SCHEMA_VERSION,
                "condition": condition,
                "run_id": contract.RUN_IDS[condition],
                "container_create_argv": create_argv,
                "container_create_argv_sha256": contract.template_sha256(create_argv),
                "inner_argv": inner_argv,
                "inner_argv_sha256": contract.template_sha256(inner_argv),
                "configuration_refs": configuration_refs,
            }
        )
        field_provenance = {
            "source_kind": "observed_from_locked_experiment_assignment",
            "selected_mode": "derived_from_locked_condition_plan",
            "assignment_policy_sha256": "observed_file_hash",
            "resolved_configuration_refs": "observed_repository_paths",
            "raw_artifact_refs": "observed_owned_output_paths",
            "confidence": "unavailable_from_pinned_source",
            "override": "unavailable_from_pinned_source",
            "fallback": "unavailable_from_pinned_source",
            "critic": "unavailable_from_pinned_source",
            "configurator": "unavailable_from_pinned_source",
            "per_step_planning": "unavailable_from_pinned_source",
        }
        decisions[mode] = {
            "schema_version": supervisor.SCHEMA_VERSION,
            "plan_id": supervisor.PLAN_ID,
            "host_run_id": supervisor.HOST_RUN_ID,
            "run_id": contract.RUN_IDS[condition],
            "condition": condition,
            "source_kind": "experiment_assignment",
            "selected_mode": mode,
            "assignment_policy_sha256": supervisor.CONDITION_PLAN_SHA256[condition],
            "resolved_configuration_refs": configuration_refs,
            "raw_artifact_roots": [
                f"{mode}/payload/sira-output",
                f"{mode}/payload/source-logs",
            ],
            "field_level_provenance": field_provenance,
            "confidence": None,
            "override": None,
            "fallback": None,
            "critic": None,
            "configurator": None,
            "per_step_planning": None,
            "interpretation_allowed": False,
        }
        records[f"{mode}/regulation-decision.json"] = supervisor.canonical_json_bytes(
            decisions[mode]
        )
        completion_provenance = {
            "raw_artifacts": "observed_file_bytes",
            "runtime": "observed_container_output",
            "accounting": "observed_provider_budget_boundary",
            "cleanup": "observed_runtime_close_record",
        }
        completions[mode] = {
            "schema_version": supervisor.SCHEMA_VERSION,
            "plan_id": supervisor.PLAN_ID,
            "host_run_id": supervisor.HOST_RUN_ID,
            "run_id": contract.RUN_IDS[condition],
            "condition": condition,
            "raw_artifacts": raw_rows,
            "raw_session_refs": [f"{mode}/payload/sira-output/session.json"],
            "source_log_refs": [f"{mode}/payload/source-logs/session.log"],
            "resolved_configuration_refs": configuration_refs,
            "field_level_provenance": completion_provenance,
            "interpretation_allowed": False,
        }
        records[f"{mode}/condition-completion.json"] = supervisor.canonical_json_bytes(
            completions[mode]
        )
        pair_conditions.append(
            {
                "condition": condition,
                "run_id": contract.RUN_IDS[condition],
                "cost_usd": 0.25,
                "model_tokens": 100,
                "model_call_attempts": 1,
                "browser_actions": 1,
                "wall_seconds": 1.0,
                "output_bytes": sum(len(data) for data in payloads.values()),
            }
        )
    events: list[dict[str, object]] = []
    for mode, condition in (("reactive", "SIRA-REACTIVE"), ("simulative", "SIRA-SIMULATIVE")):
        for event_type, reference, raw_refs, provenance in (
            (
                "condition_assignment_bound",
                f"{mode}/regulation-decision.json",
                [],
                decisions[mode]["field_level_provenance"],
            ),
            (
                "condition_execution_completed",
                f"{mode}/condition-completion.json",
                [row["path"] for row in completions[mode]["raw_artifacts"]],
                completions[mode]["field_level_provenance"],
            ),
        ):
            events.append(
                {
                    "schema_version": supervisor.SCHEMA_VERSION,
                    "plan_id": supervisor.PLAN_ID,
                    "host_run_id": supervisor.HOST_RUN_ID,
                    "run_id": contract.RUN_IDS[condition],
                    "event_sequence": len(events) + 1,
                    "event_type": event_type,
                    "condition": condition,
                    "source_kind": "experiment_assignment",
                    "evidence_reference": reference,
                    "raw_artifact_refs": raw_refs,
                    "resolved_configuration_refs": completions[mode]["resolved_configuration_refs"],
                    "field_level_provenance": provenance,
                    "monotonic_timestamp_ns": len(events) + 1,
                    "wall_timestamp_utc": f"2026-08-11T20:00:0{len(events) + 1}Z",
                    "interpretation_allowed": False,
                }
            )
    records["normalized-events.jsonl"] = b"".join(
        json.dumps(event, separators=(",", ":"), sort_keys=True).encode() + b"\n"
        for event in events
    )
    records["pair-budget.json"] = supervisor.canonical_json_bytes(
        {
            "schema_version": supervisor.SCHEMA_VERSION,
            "plan_id": supervisor.PLAN_ID,
            "host_run_id": supervisor.HOST_RUN_ID,
            "condition_order": list(contract.CONDITION_ORDER),
            "conditions": pair_conditions,
            "within_all_caps": True,
        }
    )
    reactive_argv = list(contract.container_create_argv("SIRA-REACTIVE"))
    simulative_argv = list(contract.container_create_argv("SIRA-SIMULATIVE"))
    differences = [
        {"index": index, "reactive": left, "simulative": right}
        for index, (left, right) in enumerate(zip(reactive_argv, simulative_argv, strict=True))
        if left != right
    ]
    records["pair-equivalence.json"] = supervisor.canonical_json_bytes(
        {
            "schema_version": supervisor.SCHEMA_VERSION,
            "plan_id": supervisor.PLAN_ID,
            "host_run_id": supervisor.HOST_RUN_ID,
            "condition_order": list(contract.CONDITION_ORDER),
            "reactive_command_sha256": contract.template_sha256(reactive_argv),
            "simulative_command_sha256": contract.template_sha256(simulative_argv),
            "difference_count": len(differences),
            "differences": differences,
            "canonical_condition_diff_only": True,
            "trace_instrumentation_changed_contrast": False,
            "interpretation_allowed": False,
        }
    )
    if secret_member:
        records["reactive/payload/API_KEY=PUBLICDUMMYVALUE.txt"] = b"safe\n"
    if extra_record is not None:
        records["auxiliary-observation.json"] = extra_record
    rows = [
        {"path": name, "bytes": len(encoded), "sha256": hashlib.sha256(encoded).hexdigest()}
        for name, encoded in sorted(records.items())
    ]
    manifest = supervisor.canonical_json_bytes(
        {
            "schema_version": "0.1.0",
            "plan_id": supervisor.PLAN_ID,
            "host_run_id": supervisor.HOST_RUN_ID,
            "files": rows,
            "file_count": len(rows),
            "total_bytes": sum(len(encoded) for encoded in records.values()),
        }
    )
    archive = inbound / "t07-bounded-evidence.zip"
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_STORED) as output:
        output.writestr("EVIDENCE_MANIFEST.json", manifest)
        for name, encoded in sorted(records.items()):
            output.writestr(name, encoded)
    archive_encoded = archive.read_bytes()
    (inbound / "ARCHIVE_IDENTITY.json").write_bytes(
        supervisor.canonical_json_bytes(
            {
                "archive": archive.name,
                "bytes": len(archive_encoded),
                "sha256": hashlib.sha256(archive_encoded).hexdigest(),
                "source_retained": True,
            }
        )
    )
    (inbound / "TERMINATE_REQUIRED.json").write_bytes(
        supervisor.canonical_json_bytes(
            {
                "schema_version": supervisor.SCHEMA_VERSION,
                "provider_termination_required": True,
                "bootstrap_complete": True,
                "message_retained": False,
                "secret_cleanup_verified": True,
                "manual_secret_deletion_required": False,
                "manual_credential_rotation_required": False,
            }
        )
    )
    return records


def test_success_verifier_replays_every_command_meter_counter_transition(tmp_path: Path) -> None:
    run_root = tmp_path / "run"
    run_root.mkdir()
    records = _write_complete_inbound(run_root)
    events = [json.loads(line) for line in records["command-meter.jsonl"].splitlines()]
    events[1]["aggregate_call_count"] = 0
    events[1]["work_call_count"] = 0
    records["command-meter.jsonl"] = b"".join(
        json.dumps(event, separators=(",", ":"), sort_keys=True).encode() + b"\n"
        for event in events
    )
    rows = {
        name: (len(encoded), hashlib.sha256(encoded).hexdigest())
        for name, encoded in records.items()
    }
    with pytest.raises(supervisor.BoundedSupervisorError, match="counter"):
        plan = _runtime_plan()
        release, release_encoded = _release_for_fixture(run_root, plan)
        supervisor._verify_success_surface(
            records,
            rows,
            plan=plan,
            bootstrap_release=release,
            bootstrap_release_sha256=hashlib.sha256(release_encoded).hexdigest(),
        )


def test_condition_completion_must_bind_the_complete_payload_surface(tmp_path: Path) -> None:
    run_root = tmp_path / "run"
    run_root.mkdir()
    records = _write_complete_inbound(run_root)
    completion = json.loads(records["reactive/condition-completion.json"])
    completion["raw_artifacts"] = completion["raw_artifacts"][:-1]
    records["reactive/condition-completion.json"] = supervisor.canonical_json_bytes(completion)
    rows = {
        name: (len(encoded), hashlib.sha256(encoded).hexdigest())
        for name, encoded in records.items()
    }
    with pytest.raises(supervisor.BoundedSupervisorError, match="raw artifact binding"):
        plan = _runtime_plan()
        release, release_encoded = _release_for_fixture(run_root, plan)
        supervisor._verify_success_surface(
            records,
            rows,
            plan=plan,
            bootstrap_release=release,
            bootstrap_release_sha256=hashlib.sha256(release_encoded).hexdigest(),
        )


def _verify_complete_records(run_root: Path, records: Mapping[str, bytes]) -> None:
    rows = {
        name: (len(encoded), hashlib.sha256(encoded).hexdigest())
        for name, encoded in records.items()
    }
    plan = _runtime_plan()
    release, release_encoded = _release_for_fixture(run_root, plan)
    supervisor._verify_success_surface(
        records,
        rows,
        plan=plan,
        bootstrap_release=release,
        bootstrap_release_sha256=hashlib.sha256(release_encoded).hexdigest(),
    )


def test_success_verifier_rejects_unsafe_realized_container_policy(tmp_path: Path) -> None:
    run_root = tmp_path / "run"
    run_root.mkdir()
    records = _write_complete_inbound(run_root)
    name = "reactive/container-inspect-before-stop.json"
    inspected = json.loads(records[name])
    inspected[0]["HostConfig"]["Privileged"] = True
    records[name] = supervisor.canonical_json_bytes(inspected)
    receipt_name = "reactive/container-inspect-before-stop-command.json"
    receipt = json.loads(records[receipt_name])
    receipt["stdout_bytes"] = len(records[name])
    receipt["stdout_sha256"] = hashlib.sha256(records[name]).hexdigest()
    records[receipt_name] = supervisor.canonical_json_bytes(receipt)
    with pytest.raises(supervisor.BoundedSupervisorError, match="inspect policy"):
        _verify_complete_records(run_root, records)


def test_success_verifier_binds_exact_create_invocation(tmp_path: Path) -> None:
    run_root = tmp_path / "run"
    run_root.mkdir()
    records = _write_complete_inbound(run_root)
    receipt = json.loads(records["simulative/container-create.json"])
    receipt["argv_sha256"] = "f" * 64
    records["simulative/container-create.json"] = supervisor.canonical_json_bytes(receipt)
    with pytest.raises(supervisor.BoundedSupervisorError, match="command receipt"):
        _verify_complete_records(run_root, records)


def test_success_verifier_replays_empty_residue_receipts(tmp_path: Path) -> None:
    run_root = tmp_path / "run"
    run_root.mkdir()
    records = _write_complete_inbound(run_root)
    name = "model-preflight/container-residue-networks.json"
    receipt = json.loads(records[name])
    receipt["stdout_bytes"] = 1
    receipt["stdout_sha256"] = hashlib.sha256(b"x").hexdigest()
    records[name] = supervisor.canonical_json_bytes(receipt)
    with pytest.raises(supervisor.BoundedSupervisorError, match="residue receipt"):
        _verify_complete_records(run_root, records)


def test_success_verifier_reconciles_one_history_step_to_browser_budget(tmp_path: Path) -> None:
    run_root = tmp_path / "run"
    run_root.mkdir()
    records = _write_complete_inbound(run_root)
    name = "reactive/payload/sira-output/session.json"
    session = json.loads(records[name])
    session["history"].append(session["history"][0])
    records[name] = supervisor.canonical_json_bytes(session)
    completion_name = "reactive/condition-completion.json"
    completion = json.loads(records[completion_name])
    for row in completion["raw_artifacts"]:
        if row["path"] == name:
            row["bytes"] = len(records[name])
            row["sha256"] = hashlib.sha256(records[name]).hexdigest()
    records[completion_name] = supervisor.canonical_json_bytes(completion)
    with pytest.raises(supervisor.BoundedSupervisorError, match="browser-step"):
        _verify_complete_records(run_root, records)


def test_success_verifier_binds_remote_bootstrap_to_exact_local_release(tmp_path: Path) -> None:
    run_root = tmp_path / "run"
    run_root.mkdir()
    records = _write_complete_inbound(run_root)
    authority = json.loads(records["bootstrap-authority.json"])
    authority["execution_commit"] = "f" * 40
    records["bootstrap-authority.json"] = supervisor.canonical_json_bytes(authority)
    with pytest.raises(supervisor.BoundedSupervisorError, match="authority binding"):
        _verify_complete_records(run_root, records)


def _bounded_test_clocks(
    tmp_path: Path,
) -> tuple[Callable[[], int], Callable[[], datetime]]:
    first = json.loads(
        (tmp_path / supervisor.LEDGER_RELATIVE).read_text(encoding="utf-8").splitlines()[0]
    )
    monotonic_value = int(first["monotonic_timestamp_ns"])
    wall_offset = 0

    def monotonic_ns() -> int:
        nonlocal monotonic_value
        monotonic_value += 1_000_000_000
        return monotonic_value

    def utc_now() -> datetime:
        nonlocal wall_offset
        wall_offset += 1
        return NOW + timedelta(seconds=wall_offset)

    return monotonic_ns, utc_now


def _observe_through_post_launch(
    tmp_path: Path,
    *,
    summary: Mapping[str, object],
    plan_sha256: str,
) -> tuple[
    dict[str, dict[str, object]],
    Callable[[], int],
    Callable[[], datetime],
]:
    private = json.loads(
        (tmp_path / supervisor.PRIVATE_BINDING_RELATIVE).read_text(encoding="utf-8")
    )
    documents = _phase_documents(private)
    monotonic_ns, utc_now = _bounded_test_clocks(tmp_path)
    for phase in ("prelaunch", "security", "post_launch"):
        _execute_observer(
            tmp_path,
            summary,
            plan_sha256,
            phase=phase,
            transport=FakeTransport(documents[phase]),
            monotonic_ns=monotonic_ns,
            utc_now=utc_now,
        )
    supervisor.issue_bootstrap_release(
        tmp_path,
        plan=_runtime_plan(),
        plan_sha256=plan_sha256,
        expected_commit=COMMIT,
        authorization_path=tmp_path / supervisor.AUTHORIZATION_RELATIVE,
        authorization_sha256=str(summary["authorization_sha256"]),
        private_binding_path=tmp_path / supervisor.PRIVATE_BINDING_RELATIVE,
        private_binding_sha256=str(summary["private_binding_sha256"]),
        provider_image_attestation="confirmed-in-provider-console",
        utc_now=utc_now,
    )
    return documents, monotonic_ns, utc_now


def _verify_inbound_and_finish_observer(
    tmp_path: Path,
    *,
    summary: Mapping[str, object],
    plan_sha256: str,
    documents: Mapping[str, Mapping[str, object]],
    monotonic_ns: Callable[[], int],
    utc_now: Callable[[], datetime],
) -> None:
    supervisor.verify_inbound_evidence(
        tmp_path,
        plan=_runtime_plan(),
        plan_sha256=plan_sha256,
        expected_commit=COMMIT,
        authorization_path=tmp_path / supervisor.AUTHORIZATION_RELATIVE,
        authorization_sha256=str(summary["authorization_sha256"]),
        private_binding_path=tmp_path / supervisor.PRIVATE_BINDING_RELATIVE,
        private_binding_sha256=str(summary["private_binding_sha256"]),
        disposition="complete",
        utc_now=utc_now,
    )
    for phase in ("termination", "terminal"):
        _execute_observer(
            tmp_path,
            summary,
            plan_sha256,
            phase=phase,
            transport=FakeTransport(documents[phase]),
            monotonic_ns=monotonic_ns,
            utc_now=utc_now,
        )


def test_observer_replay_rejects_coordinated_state_and_report_timestamp_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    summary, plan_sha256, _ = _materialize(tmp_path, monkeypatch)
    documents, monotonic_ns, utc_now = _observe_through_post_launch(
        tmp_path, summary=summary, plan_sha256=plan_sha256
    )
    for phase in ("termination", "terminal"):
        _execute_observer(
            tmp_path,
            summary,
            plan_sha256,
            phase=phase,
            transport=FakeTransport(documents[phase]),
            monotonic_ns=monotonic_ns,
            utc_now=utc_now,
        )
    run_root = tmp_path / supervisor.RUN_ROOT_RELATIVE
    state_path = tmp_path / supervisor.STATE_RELATIVE
    report_path = run_root / "post_launch-report.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    report = json.loads(report_path.read_text(encoding="utf-8"))
    drifted = "2026-08-11T20:59:59Z"
    state["provider_active_observed_at_utc"] = drifted
    report["provider_active_observed_at_utc"] = drifted
    state_path.write_bytes(supervisor.canonical_json_bytes(state))
    report_path.write_bytes(supervisor.canonical_json_bytes(report))
    authorization = json.loads(
        (tmp_path / supervisor.AUTHORIZATION_RELATIVE).read_text(encoding="utf-8")
    )
    private = json.loads(
        (tmp_path / supervisor.PRIVATE_BINDING_RELATIVE).read_text(encoding="utf-8")
    )
    with pytest.raises(supervisor.BoundedSupervisorError, match="request ledger"):
        supervisor._verify_observer_evidence(
            tmp_path,
            authorization=authorization,
            private=private,
            authorization_sha256=str(summary["authorization_sha256"]),
            private_binding_sha256=str(summary["private_binding_sha256"]),
            disposition="complete",
        )


def test_complete_archive_reads_back_hashes_and_retains_local_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    summary, plan_sha256, _ = _materialize(tmp_path, monkeypatch)
    run_root = tmp_path / supervisor.RUN_ROOT_RELATIVE
    documents, monotonic_ns, utc_now = _observe_through_post_launch(
        tmp_path, summary=summary, plan_sha256=plan_sha256
    )
    _write_complete_inbound(run_root)
    _verify_inbound_and_finish_observer(
        tmp_path,
        summary=summary,
        plan_sha256=plan_sha256,
        documents=documents,
        monotonic_ns=monotonic_ns,
        utc_now=utc_now,
    )
    inbound = run_root / "inbound"
    external_mount = tmp_path / "external"
    external_mount.mkdir(exist_ok=True)
    external_parent = external_mount / "GIC-Lab/t07/sealed-artifacts"
    monkeypatch.setattr(supervisor, "EXTERNAL_MOUNT", external_mount)
    monkeypatch.setattr(supervisor, "EXTERNAL_PARENT", external_parent)
    monkeypatch.setattr(supervisor, "EXTERNAL_FINAL", external_parent / supervisor.HOST_RUN_ID)
    monkeypatch.setattr(lambda_archive, "APPROVED_MOUNT", external_mount)
    external = _external_observation(external_mount)
    system = replace(_system_observation(), mount_path=tmp_path / "system")
    result = supervisor.archive_evidence(
        tmp_path,
        plan=_runtime_plan(),
        plan_sha256=plan_sha256,
        expected_commit=COMMIT,
        authorization_path=tmp_path / supervisor.AUTHORIZATION_RELATIVE,
        authorization_sha256=str(summary["authorization_sha256"]),
        private_binding_path=tmp_path / supervisor.PRIVATE_BINDING_RELATIVE,
        private_binding_sha256=str(summary["private_binding_sha256"]),
        disposition="complete",
        volume_observer=lambda: (external, system),
        utc_now=utc_now,
    )
    assert result["source_destination_hashes_verified"] is True
    assert result["source_retained"] is True
    assert result["total_file_count"] == result["file_count"] + 3
    assert int(result["total_file_count"]) <= supervisor.MAX_ARCHIVE_FILES
    destination = external_parent / supervisor.HOST_RUN_ID
    assert destination.is_dir()
    assert (destination / "SEAL.json").is_file()
    assert (destination / "upload-bundle/t07-bounded-repository.tar").is_file()
    assert (destination / "upload-bundle/t07-bounded-bootstrap.py").is_file()
    assert (inbound / "t07-bounded-evidence.zip").is_file()
    assert (run_root / "INBOUND_VERIFICATION.json").is_file()


def test_complete_archive_rejects_secret_inside_a_self_consistent_zip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    summary, plan_sha256, _ = _materialize(tmp_path, monkeypatch)
    run_root = tmp_path / supervisor.RUN_ROOT_RELATIVE
    _observe_through_post_launch(tmp_path, summary=summary, plan_sha256=plan_sha256)
    _write_complete_inbound(run_root, secret_member=True)
    with pytest.raises(supervisor.BoundedSupervisorError, match="credential-shaped"):
        supervisor.verify_inbound_evidence(
            tmp_path,
            plan=_runtime_plan(),
            plan_sha256=plan_sha256,
            expected_commit=COMMIT,
            authorization_path=tmp_path / supervisor.AUTHORIZATION_RELATIVE,
            authorization_sha256=str(summary["authorization_sha256"]),
            private_binding_path=tmp_path / supervisor.PRIVATE_BINDING_RELATIVE,
            private_binding_sha256=str(summary["private_binding_sha256"]),
            disposition="complete",
            utc_now=lambda: AFTER_NOW,
        )


@pytest.mark.parametrize(
    "canary",
    (
        b'{"access_key":"PUBLIC_DUMMY_ACCESS_0123456789"}\n',
        b'{"key":"api_key","value":"PUBLIC_DUMMY_ACCESS_0123456789"}\n',
        b'{"outer":{"key": "api_key",\n  "value": "PUBLIC_DUMMY_ACCESS_0123456789"}}\n',
        b'{"key":"credential","value":"PUBLIC_DUMMY_CREDENTIAL_0123456789"}\n',
        b'{"authorization":"PUBLIC_DUMMY_AUTHORIZATION_0123456789"}\n',
    ),
)
def test_inbound_zip_scan_rejects_semantic_secret_key_shapes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, canary: bytes
) -> None:
    summary, plan_sha256, _ = _materialize(tmp_path, monkeypatch)
    run_root = tmp_path / supervisor.RUN_ROOT_RELATIVE
    _observe_through_post_launch(tmp_path, summary=summary, plan_sha256=plan_sha256)
    _write_complete_inbound(run_root, extra_record=canary)
    with pytest.raises(supervisor.BoundedSupervisorError, match="credential-shaped"):
        supervisor.verify_inbound_evidence(
            tmp_path,
            plan=_runtime_plan(),
            plan_sha256=plan_sha256,
            expected_commit=COMMIT,
            authorization_path=tmp_path / supervisor.AUTHORIZATION_RELATIVE,
            authorization_sha256=str(summary["authorization_sha256"]),
            private_binding_path=tmp_path / supervisor.PRIVATE_BINDING_RELATIVE,
            private_binding_sha256=str(summary["private_binding_sha256"]),
            disposition="complete",
            utc_now=lambda: AFTER_NOW,
        )


@pytest.mark.parametrize(
    "canary",
    (
        b'{"access_key":"PUBLIC_DUMMY_ACCESS_0123456789"}\n',
        b'{"key":"api_key","value":"PUBLIC_DUMMY_ACCESS_0123456789"}\n',
        b'{"outer":{"key": "api_key",\n  "value": "PUBLIC_DUMMY_ACCESS_0123456789"}}\n',
        b'{"key":"credential","value":"PUBLIC_DUMMY_CREDENTIAL_0123456789"}\n',
        b'{"authorization":"PUBLIC_DUMMY_AUTHORIZATION_0123456789"}\n',
    ),
)
def test_external_copy_scan_rejects_semantic_secret_key_shapes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, canary: bytes
) -> None:
    source = tmp_path / "source.json"
    source.write_bytes(canary)
    external_mount = tmp_path / "external"
    external_mount.mkdir()
    external_parent = external_mount / "GIC-Lab/t07/sealed-artifacts"
    monkeypatch.setattr(supervisor, "EXTERNAL_MOUNT", external_mount)
    monkeypatch.setattr(supervisor, "EXTERNAL_PARENT", external_parent)
    monkeypatch.setattr(supervisor, "EXTERNAL_FINAL", external_parent / supervisor.HOST_RUN_ID)
    monkeypatch.setattr(lambda_archive, "APPROVED_MOUNT", external_mount)
    external = _external_observation(external_mount)
    with pytest.raises(supervisor.BoundedSupervisorError, match="credential-shaped"):
        supervisor._copy_archive_tree(
            tmp_path,
            files=[
                supervisor.ArchiveSource(
                    relative="source.json",
                    path=source,
                    byte_count=len(canary),
                    sha256=hashlib.sha256(canary).hexdigest(),
                    content_class="runtime_evidence",
                )
            ],
            disposition="failed",
            volume_observer=lambda: (external, _system_observation()),
            utc_now=lambda: AFTER_NOW,
        )


def test_local_bootstrap_release_tamper_is_rejected_before_inbound_verification(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    summary, plan_sha256, _ = _materialize(tmp_path, monkeypatch)
    run_root = tmp_path / supervisor.RUN_ROOT_RELATIVE
    _observe_through_post_launch(tmp_path, summary=summary, plan_sha256=plan_sha256)
    release_path = tmp_path / supervisor.BOOTSTRAP_RELEASE_RELATIVE
    release = json.loads(release_path.read_text(encoding="utf-8"))
    release["execution_commit"] = "f" * 40
    release_path.write_bytes(supervisor.canonical_json_bytes(release))
    _write_complete_inbound(run_root)
    with pytest.raises(supervisor.BoundedSupervisorError, match="local authority binding"):
        supervisor.verify_inbound_evidence(
            tmp_path,
            plan=_runtime_plan(),
            plan_sha256=plan_sha256,
            expected_commit=COMMIT,
            authorization_path=tmp_path / supervisor.AUTHORIZATION_RELATIVE,
            authorization_sha256=str(summary["authorization_sha256"]),
            private_binding_path=tmp_path / supervisor.PRIVATE_BINDING_RELATIVE,
            private_binding_sha256=str(summary["private_binding_sha256"]),
            disposition="complete",
            utc_now=lambda: AFTER_NOW,
        )


def test_released_early_bootstrap_failure_is_admitted_for_failed_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    summary, plan_sha256, _ = _materialize(tmp_path, monkeypatch)
    _, _, utc_now = _observe_through_post_launch(tmp_path, summary=summary, plan_sha256=plan_sha256)
    remote = tmp_path / "remote"
    remote.mkdir()
    cleanup = remote / "cleanup.json"
    cleanup.write_bytes(
        supervisor.canonical_json_bytes(
            {
                "schema_version": supervisor.SCHEMA_VERSION,
                "secret_variable_name": "SIRA_API_KEY",
                "secret_file_basename": "sira_api_key",
                "held_identity_established_before_preflight": True,
                "truncated_before_unlink": True,
                "unlinked": True,
                "absence_verified": True,
                "path_identity_replaced": False,
                "value_or_hash_retained": False,
                "manual_fallback_deletion_required": False,
            }
        )
    )
    bootstrap = _load_remote_bootstrap()
    bootstrap.package_early_failure_evidence(
        remote / "t07-bounded-output-0002",
        failure_stage="invocation_validation",
        secret_target_identity_established=True,
        secret_cleanup_verified=True,
        secret_value_read=False,
        secret_cleanup_source=cleanup,
    )
    remote_failure = remote / "t07-bounded-output-0002-early-failure"
    inbound = tmp_path / supervisor.RUN_ROOT_RELATIVE / "inbound"
    inbound.mkdir()
    for name in (
        "t07-bounded-early-failure-evidence.zip",
        "EARLY_FAILURE_ARCHIVE_IDENTITY.json",
        "TERMINATE_REQUIRED.json",
    ):
        shutil.copy2(remote_failure / name, inbound / name)
    result = supervisor.verify_inbound_evidence(
        tmp_path,
        plan=_runtime_plan(),
        plan_sha256=plan_sha256,
        expected_commit=COMMIT,
        authorization_path=tmp_path / supervisor.AUTHORIZATION_RELATIVE,
        authorization_sha256=str(summary["authorization_sha256"]),
        private_binding_path=tmp_path / supervisor.PRIVATE_BINDING_RELATIVE,
        private_binding_sha256=str(summary["private_binding_sha256"]),
        disposition="failed",
        utc_now=utc_now,
    )
    assert result["all_member_hashes_verified"] is True
    receipt = json.loads(
        (tmp_path / supervisor.INBOUND_VERIFICATION_RELATIVE).read_text(encoding="utf-8")
    )
    assert receipt["verification"]["remote_archive_kind"] == "early_failure"
    state = json.loads((tmp_path / supervisor.STATE_RELATIVE).read_text(encoding="utf-8"))
    assert state["status"] == "cleanup_required"
    assert state["next_phase"] == "termination"


def test_self_consistent_early_failure_omission_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    summary, plan_sha256, _ = _materialize(tmp_path, monkeypatch)
    _, _, utc_now = _observe_through_post_launch(tmp_path, summary=summary, plan_sha256=plan_sha256)
    remote = tmp_path / "remote"
    remote.mkdir()
    cleanup = remote / "cleanup.json"
    cleanup.write_bytes(
        supervisor.canonical_json_bytes(
            {
                "schema_version": supervisor.SCHEMA_VERSION,
                "secret_variable_name": "SIRA_API_KEY",
                "secret_file_basename": "sira_api_key",
                "held_identity_established_before_preflight": True,
                "truncated_before_unlink": True,
                "unlinked": True,
                "absence_verified": True,
                "path_identity_replaced": False,
                "value_or_hash_retained": False,
                "manual_fallback_deletion_required": False,
            }
        )
    )
    bootstrap = _load_remote_bootstrap()
    bootstrap.package_early_failure_evidence(
        remote / "t07-bounded-output-0002",
        failure_stage="invocation_validation",
        secret_target_identity_established=True,
        secret_cleanup_verified=True,
        secret_value_read=False,
        secret_cleanup_source=cleanup,
    )
    failure_root = remote / "t07-bounded-output-0002-early-failure"
    archive = failure_root / "t07-bounded-early-failure-evidence.zip"
    with zipfile.ZipFile(archive) as opened:
        members = {name: opened.read(name) for name in opened.namelist()}
    disposition_name = "evidence/early-failure-disposition.json"
    disposition = json.loads(members[disposition_name])
    disposition.pop("secret_value_read")
    members[disposition_name] = supervisor.canonical_json_bytes(disposition)
    manifest = json.loads(members.pop("FAILURE_EVIDENCE_MANIFEST.json"))
    rows = [
        {
            "path": name,
            "bytes": len(encoded),
            "sha256": hashlib.sha256(encoded).hexdigest(),
        }
        for name, encoded in members.items()
    ]
    manifest["files"] = rows
    manifest["file_count"] = len(rows)
    manifest["payload_bytes"] = sum(len(encoded) for encoded in members.values())
    manifest_encoded = supervisor.canonical_json_bytes(manifest)
    archive.unlink()
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_STORED) as output:
        output.writestr("FAILURE_EVIDENCE_MANIFEST.json", manifest_encoded)
        for name, encoded in members.items():
            output.writestr(name, encoded)
    archive_encoded = archive.read_bytes()
    (failure_root / "EARLY_FAILURE_ARCHIVE_IDENTITY.json").write_bytes(
        supervisor.canonical_json_bytes(
            {
                "schema_version": supervisor.SCHEMA_VERSION,
                "archive": archive.name,
                "bytes": len(archive_encoded),
                "sha256": hashlib.sha256(archive_encoded).hexdigest(),
                "manifest_sha256": hashlib.sha256(manifest_encoded).hexdigest(),
                "secret_scan_passed": True,
                "source_retained": True,
            }
        )
    )
    inbound = tmp_path / supervisor.INBOUND_RELATIVE
    inbound.mkdir()
    for name in (
        archive.name,
        "EARLY_FAILURE_ARCHIVE_IDENTITY.json",
        "TERMINATE_REQUIRED.json",
    ):
        shutil.copy2(failure_root / name, inbound / name)
    with pytest.raises(supervisor.BoundedSupervisorError, match="disposition binding"):
        supervisor.verify_inbound_evidence(
            tmp_path,
            plan=_runtime_plan(),
            plan_sha256=plan_sha256,
            expected_commit=COMMIT,
            authorization_path=tmp_path / supervisor.AUTHORIZATION_RELATIVE,
            authorization_sha256=str(summary["authorization_sha256"]),
            private_binding_path=tmp_path / supervisor.PRIVATE_BINDING_RELATIVE,
            private_binding_sha256=str(summary["private_binding_sha256"]),
            disposition="failed",
            utc_now=utc_now,
        )


def test_archive_source_rejects_members_outside_exact_verified_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _materialize(tmp_path, monkeypatch)
    run_root = tmp_path / supervisor.RUN_ROOT_RELATIVE
    (run_root / "INBOUND_VERIFICATION.json").write_text(
        '{"verification":{"bootstrap_release_present":false,'
        '"remote_archive_kind":"not-produced-before-bootstrap"}}\n',
        encoding="utf-8",
    )
    (run_root / "OBSERVER_EVIDENCE_VERIFICATION.json").write_text(
        '{"completed_response_ordinals":[],"phase_report_sha256s":{}}\n',
        encoding="utf-8",
    )
    (run_root / "COMPUTE_USE_CLOSEOUT.json").write_text("{}\n", encoding="utf-8")
    responses = run_root / "responses"
    (responses / "extra.json").write_text("{}\n", encoding="utf-8")
    assert supervisor.MAX_ARCHIVE_PAYLOAD_FILES + 3 == supervisor.MAX_ARCHIVE_FILES == 128
    with pytest.raises(supervisor.BoundedSupervisorError, match="exact verified member set"):
        supervisor._safe_source_files(tmp_path, disposition="failed")


def test_normal_failure_rejects_missing_rotation_after_incomplete_secret_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    summary, plan_sha256, _ = _materialize(tmp_path, monkeypatch)
    _, _, utc_now = _observe_through_post_launch(tmp_path, summary=summary, plan_sha256=plan_sha256)
    run_root = tmp_path / supervisor.RUN_ROOT_RELATIVE
    records = _write_complete_inbound(run_root)
    inbound = run_root / "inbound"
    for path in inbound.iterdir():
        path.unlink()

    remote = tmp_path / "remote-normal-failure"
    evidence = remote / "evidence"
    evidence.mkdir(parents=True)
    (evidence / "bootstrap-authority.json").write_bytes(records["bootstrap-authority.json"])
    (remote / "TERMINATE_REQUIRED.json").write_bytes(
        supervisor.canonical_json_bytes(
            {
                "schema_version": supervisor.SCHEMA_VERSION,
                "provider_termination_required": True,
                "failure_stage": "condition_execution",
                "failure_class": "bootstrap_contract_rejected",
                "message_retained": False,
                "secret_cleanup_verified": False,
                "manual_secret_deletion_required": True,
                "manual_credential_rotation_required": False,
                "secret_target_validation_completed": True,
                "secret_value_read": True,
            }
        )
    )
    bootstrap = _load_remote_bootstrap()
    archive = bootstrap.package_failure_evidence(remote, evidence, contract)
    for path in (
        archive,
        remote / "FAILURE_ARCHIVE_IDENTITY.json",
        remote / "TERMINATE_REQUIRED.json",
    ):
        shutil.copy2(path, inbound / path.name)

    with pytest.raises(supervisor.BoundedSupervisorError, match="termination receipt drifted"):
        supervisor.verify_inbound_evidence(
            tmp_path,
            plan=_runtime_plan(),
            plan_sha256=plan_sha256,
            expected_commit=COMMIT,
            authorization_path=tmp_path / supervisor.AUTHORIZATION_RELATIVE,
            authorization_sha256=str(summary["authorization_sha256"]),
            private_binding_path=tmp_path / supervisor.PRIVATE_BINDING_RELATIVE,
            private_binding_sha256=str(summary["private_binding_sha256"]),
            disposition="failed",
            utc_now=utc_now,
        )


def test_compute_closeout_keeps_unverified_remote_secret_cleanup_unresolved(
    tmp_path: Path,
) -> None:
    (tmp_path / supervisor.RUN_ROOT_RELATIVE).mkdir(parents=True)
    (tmp_path / supervisor.BOOTSTRAP_RELEASE_RELATIVE).write_text("{}\n", encoding="utf-8")
    state = {
        "status": "cleanup_complete",
        "cleanup_origin_phase": "post_launch",
        "bound_instance_id": "synthetic-instance-private",
        "termination_verified": True,
        "provider_active_observed_at_utc": "2026-08-11T20:00:10Z",
        "provider_terminal_observed_at_utc": "2026-08-11T20:01:10Z",
    }
    record = supervisor._write_compute_closeout(
        tmp_path,
        authorization={"supervised_wall_started_at_utc": "2026-08-11T20:00:00Z"},
        state=state,
        disposition="failed",
        inbound_verification={
            "remote_archive_kind": "early_failure",
            "secret_cleanup_verified": False,
            "manual_secret_deletion_required": True,
            "manual_credential_rotation_required": True,
        },
        observer_verification={
            "provider_active_observed_at_utc": state["provider_active_observed_at_utc"],
            "provider_terminal_observed_at_utc": state["provider_terminal_observed_at_utc"],
            "failed_phases": [],
        },
        inbound_verification_sha256="a" * 64,
    )
    assert record["billing_stop_verified"] is True
    assert record["remote_secret_cleanup_verified"] is False
    assert record["manual_secret_deletion_required"] is True
    assert record["manual_credential_rotation_required"] is True
    assert record["provider_and_security_cleanup_complete"] is False
    assert record["unresolved_billing_or_security"] is True


def test_compute_closeout_keeps_detected_credential_rotation_unresolved(
    tmp_path: Path,
) -> None:
    (tmp_path / supervisor.RUN_ROOT_RELATIVE).mkdir(parents=True)
    (tmp_path / supervisor.BOOTSTRAP_RELEASE_RELATIVE).write_text("{}\n", encoding="utf-8")
    state = {
        "status": "cleanup_complete",
        "cleanup_origin_phase": "post_launch",
        "bound_instance_id": "synthetic-instance-private",
        "termination_verified": True,
        "provider_active_observed_at_utc": "2026-08-11T20:00:10Z",
        "provider_terminal_observed_at_utc": "2026-08-11T20:01:10Z",
    }
    record = supervisor._write_compute_closeout(
        tmp_path,
        authorization={"supervised_wall_started_at_utc": "2026-08-11T20:00:00Z"},
        state=state,
        disposition="failed",
        inbound_verification={
            "remote_archive_kind": "failure",
            "secret_cleanup_verified": True,
            "manual_secret_deletion_required": False,
            "manual_credential_rotation_required": True,
        },
        observer_verification={
            "provider_active_observed_at_utc": state["provider_active_observed_at_utc"],
            "provider_terminal_observed_at_utc": state["provider_terminal_observed_at_utc"],
            "failed_phases": [],
        },
        inbound_verification_sha256="a" * 64,
    )
    assert record["billing_stop_verified"] is True
    assert record["remote_secret_cleanup_verified"] is False
    assert record["manual_credential_rotation_required"] is True
    assert record["provider_and_security_cleanup_complete"] is False
    assert record["unresolved_billing_or_security"] is True


@pytest.mark.parametrize(
    ("failed_phases", "expected_billing_stop"),
    ((["security"], True), ([], False)),
)
def test_compute_closeout_distinguishes_security_failure_from_post_security_uncertainty(
    tmp_path: Path, failed_phases: list[str], expected_billing_stop: bool
) -> None:
    (tmp_path / supervisor.RUN_ROOT_RELATIVE).mkdir(parents=True)
    state = {
        "status": "cleanup_complete",
        "cleanup_origin_phase": "security",
        "bound_instance_id": None,
        "termination_verified": False,
        "provider_active_observed_at_utc": None,
        "provider_terminal_observed_at_utc": None,
    }
    record = supervisor._write_compute_closeout(
        tmp_path,
        authorization={"supervised_wall_started_at_utc": "2026-08-11T20:00:00Z"},
        state=state,
        disposition="failed",
        inbound_verification={"remote_archive_kind": "not-produced-before-bootstrap"},
        observer_verification={
            "provider_active_observed_at_utc": None,
            "provider_terminal_observed_at_utc": None,
            "failed_phases": failed_phases,
        },
        inbound_verification_sha256="a" * 64,
    )
    assert record["billing_stop_verified"] is expected_billing_stop
    assert record["unresolved_billing_or_security"] is (not expected_billing_stop)
