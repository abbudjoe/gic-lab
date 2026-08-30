from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType

import pytest

from giclab.harness import t09_pragmatic_provider as provider
from giclab.harness.t09_provider_contracts import V11_PROVIDER_CONTRACT
from giclab.registry import load_json

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_COMMIT = "a" * 40
PUBLIC_KEY = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIFixture t09-fixture"
PUBLIC_IPV4 = "203.0.113.7"


@dataclass
class FakeClock:
    now: float = 2_000_000_000.0

    def __call__(self) -> float:
        self.now += 1.0
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


@dataclass
class FakeTransport:
    responses: list[object]
    clock: FakeClock
    events: list[str] = field(default_factory=list)
    calls: list[tuple[str, str, bytes | None]] = field(default_factory=list)

    def send(
        self,
        method: str,
        path: str,
        *,
        body: bytes | None,
        credential: bytearray,
    ) -> provider.ProviderResponse:
        assert method in {"GET", "POST"}
        assert path in provider.ALLOWED_PATHS
        assert credential == bytearray(b"lambda-fixture-credential")
        assert self.responses
        self.events.append(f"provider:{method}:{path}")
        self.calls.append((method, path, body))
        value = self.responses.pop(0)
        if isinstance(value, BaseException):
            raise value
        status = 200
        if isinstance(value, tuple):
            status, value = value
            assert isinstance(status, int)
        return provider.ProviderResponse(
            status,
            "application/json",
            value if isinstance(value, bytes) else json.dumps(value).encode(),
            self.clock(),
        )


@dataclass
class ProviderFixture:
    root: Path
    clock: FakeClock
    authorization: Path
    dotenv: Path
    public_ip: Path
    public_key: Path
    image_archive: Path
    capabilities: dict[int, Path]
    global_firewall: dict[str, object]

    @property
    def contract(self):  # type: ignore[no-untyped-def]
        return V11_PROVIDER_CONTRACT

    @property
    def plan_sha256(self) -> str:
        return provider.file_sha256(ROOT / self.contract.provider_profile_path)


def _host_runner() -> ModuleType:
    path = ROOT / "containers/sira-smoke/pragmatic/t09_remote_runner.py"
    spec = importlib.util.spec_from_file_location("giclab_t09_v15_host_fixture", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def provider_fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ProviderFixture:
    contract = V11_PROVIDER_CONTRACT
    dotenv = tmp_path / ".env"
    dotenv.write_text(
        "OPENAI_API_KEY=openai-fixture-credential\nLAMBDA_API_KEY=lambda-fixture-credential\n",
        encoding="utf-8",
    )
    dotenv.chmod(0o600)
    public_ip = tmp_path / "public-ip.private"
    public_ip.write_text(PUBLIC_IPV4, encoding="utf-8")
    public_key = tmp_path / "key.pub"
    public_key.write_text(PUBLIC_KEY, encoding="utf-8")
    image_archive = tmp_path / "retained-image-fixture.tar"
    image_archive.write_bytes(b"privacy-safe-retained-image-fixture")
    image_archive.chmod(0o600)
    authorization = tmp_path / "authorization.json"
    authorization.write_text(
        json.dumps(
            {
                "schema_version": "0.1.0",
                "authorization_source_sha256": "b" * 64,
                "authorization_reference": "AUTH-T09-V11-TEST-CATEGORY3-0001",
                "authorized": True,
                "single_use": True,
                "clean_package_commit": PACKAGE_COMMIT,
                "plan_id": contract.plan_id,
                "plan_sha256": provider.file_sha256(ROOT / contract.provider_profile_path),
                "max_lambda_instances": 1,
                "max_preflight_launch_count": 8,
                "max_empirical_launch_count": 1,
                "maximum_preflight_instance_active_seconds": 21_600,
                "maximum_cumulative_preflight_active_seconds": 43_200,
                "persistent_filesystems": 0,
                "preflight_lambda_cost_cap_usd": 10.0,
                "lambda_cost_cap_usd": 8.0,
                "openai_cost_cap_usd": 40.0,
                "aggregate_cost_cap_usd": 58.0,
                "prior_t09_cost_usd": 33.14878958732642,
                "cumulative_t09_cost_cap_usd": 90.0,
                "replacement_image_policy": "retained-exact-load-or-one-fallback-build-v1",
                "artifact_destination": "/Volumes/Macintosh HD - Data/GIC-Lab/t09/v11",
            }
        ),
        encoding="utf-8",
    )
    authorization.chmod(0o600)
    capabilities = {
        slot: tmp_path / f"launch-capabilities/slot-{slot}.json"
        for slot in range(1, contract.max_launch_count + 1)
    }
    monkeypatch.setattr(provider, "_verify_clean_package", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        provider,
        "launch_capability_path",
        lambda slot, *, contract: capabilities[slot],
    )

    def fake_image_identity(
        path: Path,
        *,
        expected_bytes: int,
        expected_sha256: str,
    ) -> None:
        assert path.resolve(strict=True) == image_archive.resolve(strict=True)
        assert expected_bytes == provider.SLOT1_IMAGE_ARCHIVE_BYTES
        assert expected_sha256 == provider.SLOT1_IMAGE_ARCHIVE_SHA256

    monkeypatch.setattr(provider, "_safe_regular_identity", fake_image_identity)
    return ProviderFixture(
        root=tmp_path,
        clock=FakeClock(),
        authorization=authorization,
        dotenv=dotenv,
        public_ip=public_ip,
        public_key=public_key,
        image_archive=image_archive,
        capabilities=capabilities,
        global_firewall={
            "data": {
                "id": "global",
                "name": "global",
                "workspace_id": "workspace-fixture",
                "rules": [
                    {
                        "protocol": "tcp",
                        "port_range": [22, 22],
                        "source_network": f"{PUBLIC_IPV4}/32",
                        "description": "fixture",
                    }
                ],
            }
        },
    )


def _instance(fixture: ProviderFixture, slot: int, *, status: str) -> dict[str, object]:
    return {
        "id": f"instance-fixture-{slot:04d}",
        "name": fixture.contract.instance_name,
        "hostname": fixture.contract.instance_name,
        "instance_type": {"name": provider.INSTANCE_TYPE},
        "region": {"name": provider.REGION},
        "status": status,
        "ip": f"198.51.100.{slot + 8}",
        "file_system_names": [],
    }


def _launch_prefix(fixture: ProviderFixture, slot: int) -> list[object]:
    return [
        {
            "data": {
                provider.INSTANCE_TYPE: {
                    "instance_type": {
                        "name": provider.INSTANCE_TYPE,
                        "price_cents_per_hour": 129,
                    },
                    "regions_with_capacity_available": [{"name": provider.REGION}],
                }
            }
        },
        {
            "data": [
                {
                    "id": provider.IMAGE_ID,
                    "region": {"name": provider.REGION},
                    "family": "lambda-stack-22-04",
                }
            ]
        },
        {"data": [{"name": provider.SSH_KEY_NAME, "public_key": PUBLIC_KEY}]},
        fixture.global_firewall,
        {"data": []},
        {"data": []},
        {"data": {"instance_ids": [f"instance-fixture-{slot:04d}"]}},
    ]


def _launch(
    fixture: ProviderFixture,
    *,
    root: Path,
    slot: int,
    prior: Path | None,
    transport: FakeTransport,
) -> Path:
    return provider.launch_campaign(
        contract=fixture.contract,
        repository=ROOT,
        package_commit=PACKAGE_COMMIT,
        authorization_ledger=fixture.authorization,
        dotenv=fixture.dotenv,
        private_root=root,
        public_ipv4_file=fixture.public_ip,
        ssh_public_key_file=fixture.public_key,
        transport=transport,
        launch_slot=slot,
        prior_private_root=prior,
        slot1_image_archive=fixture.image_archive if prior is not None else None,
        clock=fixture.clock,
        sleeper=fixture.clock.sleep,
    )


def _close_provider_entry_slot(
    fixture: ProviderFixture,
    *,
    slot: int,
    prior: Path | None = None,
) -> tuple[Path, FakeTransport]:
    root = fixture.root / f"provider-entry-failed-slot-{slot}"
    instance = _instance(fixture, slot, status="terminated")
    transport = FakeTransport(
        [
            *copy.deepcopy(_launch_prefix(fixture, slot)),
            RuntimeError("active poll transport ambiguity"),
            RuntimeError("termination response ambiguity"),
            {"data": [instance]},
            {"data": []},
            copy.deepcopy(fixture.global_firewall),
            {"data": []},
        ],
        fixture.clock,
    )
    with pytest.raises(provider.T09ProviderError, match="exact launched instance was closed"):
        _launch(
            fixture,
            root=root,
            slot=slot,
            prior=prior,
            transport=transport,
        )
    assert load_json(root / "PROVISIONAL_OWNER_CLOSED.json")["provider_disposition"] == "absent"
    return root, transport


def _open_provider_entry_slot(
    fixture: ProviderFixture,
    *,
    slot: int,
    prior: Path,
    events: list[str] | None = None,
) -> tuple[Path, Path, FakeTransport]:
    root = fixture.root / f"provider-entry-open-slot-{slot}"
    transport = FakeTransport(
        [
            *copy.deepcopy(_launch_prefix(fixture, slot)),
            {"data": [_instance(fixture, slot, status="active")]},
        ],
        fixture.clock,
        events=events if events is not None else [],
    )
    receipt = _launch(
        fixture,
        root=root,
        slot=slot,
        prior=prior,
        transport=transport,
    )
    return root, receipt, transport


def _validate_eligibility(fixture: ProviderFixture, root: Path) -> dict[str, object]:
    return provider._validate_replacement_launch_eligibility(
        root,
        contract=fixture.contract,
        repository=ROOT,
        package_commit=PACKAGE_COMMIT,
        slot1_image_archive=fixture.image_archive,
    )


def _normalized_copy(
    fixture: ProviderFixture,
    source: Path,
    *,
    name: str,
) -> tuple[Path, provider.ProviderEntryReplacementNormalization]:
    target = fixture.root / name
    target.mkdir(mode=0o700)
    eligibility_path = provider._replacement_launch_eligibility_path(source)
    eligibility = _validate_eligibility(fixture, source)
    result = provider._normalize_provider_entry_replacement_authority(
        source,
        target / provider.PROVIDER_ENTRY_AUTHORITY_ROOT_NAME,
        eligibility=eligibility,
        contract=fixture.contract,
        package_commit=PACKAGE_COMMIT,
        plan_sha256=fixture.plan_sha256,
    )
    provider._copy_exact_private_file(
        eligibility_path,
        target / "replacement-launch-eligibility.json",
        label="test retained eligibility",
    )
    return target, result


def test_historical_v14_validation_and_normalization_dispatch_diverged(
    provider_fixture: ProviderFixture,
) -> None:
    direct, _ = _close_provider_entry_slot(provider_fixture, slot=1)
    assert _validate_eligibility(provider_fixture, direct)["eligibility_kind"] == (
        provider.PROVIDER_ENTRY_FAILED_PREEMPIRICAL_ELIGIBILITY_KIND
    )
    historical = subprocess.run(
        [
            "git",
            "show",
            "2db290530c36c92562fe6b25f7a4f6aafd77b548:src/giclab/harness/t09_pragmatic_provider.py",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    validator_offset = historical.index(
        'if value.get("eligibility_kind") == "provider-entry-failed-preempirical"'
    )
    dispatch_offset = historical.index(
        "provider-entry replacement evidence cannot be normalized as a host closeout"
    )
    assert validator_offset < dispatch_offset
    assert "return value\n    entry_source" in historical[validator_offset:dispatch_offset]


def test_provider_entry_authority_normalizes_and_revalidates_semantically(
    provider_fixture: ProviderFixture,
) -> None:
    direct, _ = _close_provider_entry_slot(provider_fixture, slot=1)
    initial = _validate_eligibility(provider_fixture, direct)
    direct_authority = provider._resolve_provider_entry_replacement_authority(
        direct,
        contract=provider_fixture.contract,
        package_commit=PACKAGE_COMMIT,
        plan_sha256=provider_fixture.plan_sha256,
        closed_launch_slot=1,
    )
    original = {
        path.relative_to(direct_authority.authority_root).as_posix(): (
            path.stat().st_size,
            provider.file_sha256(path),
        )
        for path in provider._provider_entry_authority_files(
            direct_authority,
            contract=provider_fixture.contract,
            package_commit=PACKAGE_COMMIT,
            plan_sha256=provider_fixture.plan_sha256,
            closed_launch_slot=1,
            require_exact_root_members=False,
        )
    }
    retained_root, result = _normalized_copy(
        provider_fixture,
        direct,
        name="retained-provider-entry-authority",
    )
    retained = _validate_eligibility(provider_fixture, retained_root)
    assert retained == initial
    assert result.closed_launch_slot == 1
    assert result.normalized_manifest_sha256 == provider.file_sha256(
        retained_root / "slot2-eligibility-source/source-manifest.json"
    )
    assert result.source_evidence_manifest_sha256 == result.normalized_manifest_sha256
    assert original == {
        path.relative_to(direct_authority.authority_root).as_posix(): (
            path.stat().st_size,
            provider.file_sha256(path),
        )
        for path in provider._provider_entry_authority_files(
            direct_authority,
            contract=provider_fixture.contract,
            package_commit=PACKAGE_COMMIT,
            plan_sha256=provider_fixture.plan_sha256,
            closed_launch_slot=1,
            require_exact_root_members=False,
        )
    }
    host_binding = _host_runner().slot2_authority_binding(retained_root)
    assert (
        host_binding["replacement_eligibility_preempirical_source_manifest_sha256"]
        == result.normalized_manifest_sha256
    )
    assert (
        host_binding["normalized_slot2_authority_tree_manifest_sha256"]
        == result.normalized_manifest_sha256
    )


def test_full_provider_entry_replacement_normalizes_before_live_authority(
    provider_fixture: ProviderFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    direct, _ = _close_provider_entry_slot(provider_fixture, slot=1)
    events: list[str] = []
    original_normalize = provider._normalize_provider_entry_replacement_authority
    original_load = provider.load_dotenv_assignment
    original_consume = provider._consume_launch_capability

    def tracked_normalize(*args: object, **kwargs: object):  # type: ignore[no-untyped-def]
        events.append("normalize")
        return original_normalize(*args, **kwargs)  # type: ignore[arg-type]

    def tracked_load(*args: object, **kwargs: object):  # type: ignore[no-untyped-def]
        events.append("credential")
        return original_load(*args, **kwargs)  # type: ignore[arg-type]

    def tracked_consume(*args: object, **kwargs: object):  # type: ignore[no-untyped-def]
        events.append("capability")
        return original_consume(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(
        provider, "_normalize_provider_entry_replacement_authority", tracked_normalize
    )
    monkeypatch.setattr(provider, "load_dotenv_assignment", tracked_load)
    monkeypatch.setattr(provider, "_consume_launch_capability", tracked_consume)
    root, receipt_path, transport = _open_provider_entry_slot(
        provider_fixture,
        slot=2,
        prior=direct,
        events=events,
    )
    assert events.index("normalize") < events.index("credential")
    assert events.index("credential") < events.index("provider:GET:/api/v1/instance-types")
    assert events.index("provider:GET:/api/v1/instances") < events.index("capability")
    assert events.index("capability") < events.index(
        "provider:POST:/api/v1/instance-operations/launch"
    )
    assert len([call for call in transport.calls if call[0] == "GET"]) == 7
    assert (
        len(
            [
                call
                for call in transport.calls
                if call[:2]
                == (
                    "POST",
                    "/api/v1/instance-operations/launch",
                )
            ]
        )
        == 1
    )
    receipt = load_json(receipt_path)
    assert receipt["launch_slot"] == 2
    campaign = load_json(root / "entry-source/campaign-launch-binding.json")
    hashes = [
        campaign["replacement_eligibility_sha256"],
        campaign["replacement_eligibility_preempirical_source_manifest_sha256"],
        campaign["normalized_slot2_authority_tree_manifest_sha256"],
    ]
    assert all(isinstance(value, str) and len(value) == 64 for value in hashes)
    assert hashes[1] == hashes[2]
    validated = provider.validate_entry_receipt_source_bound(
        receipt_path,
        root / "entry-source",
        contract=provider_fixture.contract,
        package_commit=PACKAGE_COMMIT,
        plan_sha256=provider_fixture.plan_sha256,
    )
    assert validated == receipt


def test_provider_entry_replacement_is_slot_generic_through_slot_three(
    provider_fixture: ProviderFixture,
) -> None:
    slot1, _ = _close_provider_entry_slot(provider_fixture, slot=1)
    slot2, _ = _close_provider_entry_slot(provider_fixture, slot=2, prior=slot1)
    current_receipt = provider._replacement_launch_eligibility_path(slot2)
    assert current_receipt.name == "replacement-launch-eligibility-slot-2.json"
    assert load_json(current_receipt)["closed_launch_slot"] == 2
    slot3, entry_path, _ = _open_provider_entry_slot(
        provider_fixture,
        slot=3,
        prior=slot2,
    )
    assert load_json(entry_path)["launch_slot"] == 3
    assert load_json(slot3 / "replacement-launch-eligibility.json")["closed_launch_slot"] == 2
    assert (
        load_json(slot3 / "slot2-eligibility-source/source-manifest.json")["closed_launch_slot"]
        == 2
    )


def test_normalization_failure_precedes_credentials_provider_and_capability(
    provider_fixture: ProviderFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    direct, closeout_transport = _close_provider_entry_slot(provider_fixture, slot=1)
    before = {
        path.relative_to(direct).as_posix(): provider.file_sha256(path)
        for path in direct.rglob("*")
        if path.is_file()
    }
    credential_loads = 0

    def fail_normalization(*_args: object, **_kwargs: object) -> None:
        raise provider.T09ProviderError("fixture normalization failure")

    def count_credential(*_args: object, **_kwargs: object) -> bytearray:
        nonlocal credential_loads
        credential_loads += 1
        return bytearray(b"unreachable-fixture-credential")

    monkeypatch.setattr(
        provider,
        "_normalize_provider_entry_replacement_authority",
        fail_normalization,
    )
    monkeypatch.setattr(provider, "load_dotenv_assignment", count_credential)
    transport = FakeTransport([], provider_fixture.clock)
    failed_root = provider_fixture.root / "normalization-failed-slot-2"
    with pytest.raises(provider.T09ProviderError, match="fixture normalization failure"):
        _launch(
            provider_fixture,
            root=failed_root,
            slot=2,
            prior=direct,
            transport=transport,
        )
    assert credential_loads == 0
    assert transport.calls == []
    assert not provider_fixture.capabilities[2].exists()
    failure = load_json(failed_root / "REPLACEMENT_AUTHORITY_NORMALIZATION_FAILED.json")
    assert failure["provider_requests"] == 0
    assert failure["credential_loads"] == 0
    assert failure["next_launch_capability_consumed"] is False
    assert before == {
        path.relative_to(direct).as_posix(): provider.file_sha256(path)
        for path in direct.rglob("*")
        if path.is_file()
    }
    assert (
        len(
            [
                call
                for call in closeout_transport.calls
                if call[:2] == ("POST", "/api/v1/instance-operations/terminate")
            ]
        )
        == 1
    )


def test_unknown_eligibility_kind_fails_before_any_live_authority(
    provider_fixture: ProviderFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    direct, _ = _close_provider_entry_slot(provider_fixture, slot=1)
    receipt_path = direct / "replacement-launch-eligibility.json"
    receipt = load_json(receipt_path)
    receipt["eligibility_kind"] = "unknown-provider-entry-kind"
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    receipt_path.chmod(0o600)
    credential_loads = 0

    def count_credential(*_args: object, **_kwargs: object) -> bytearray:
        nonlocal credential_loads
        credential_loads += 1
        return bytearray(b"unreachable-fixture-credential")

    monkeypatch.setattr(provider, "load_dotenv_assignment", count_credential)
    transport = FakeTransport([], provider_fixture.clock)
    with pytest.raises(provider.T09ProviderError, match="kind is unsupported"):
        _launch(
            provider_fixture,
            root=provider_fixture.root / "unknown-kind-slot-2",
            slot=2,
            prior=direct,
            transport=transport,
        )
    assert credential_loads == 0
    assert transport.calls == []
    assert not provider_fixture.capabilities[2].exists()


@pytest.mark.parametrize(
    "mutation",
    [
        "manifest",
        "member",
        "closeout",
        "cleanup",
        "partial",
        "symlink",
        "hardlink",
        "nonregular",
        "unknown",
        "mode",
    ],
)
def test_retained_provider_entry_authority_tampering_fails_closed(
    provider_fixture: ProviderFixture,
    mutation: str,
) -> None:
    direct, _ = _close_provider_entry_slot(provider_fixture, slot=1)
    retained, _ = _normalized_copy(
        provider_fixture,
        direct,
        name=f"tampered-{mutation}",
    )
    authority = retained / provider.PROVIDER_ENTRY_AUTHORITY_ROOT_NAME
    manifest = authority / "source-manifest.json"
    member = authority / "provisional-owned-state.json"
    if mutation == "manifest":
        value = load_json(manifest)
        value["source_private_root_identity_sha256"] = "f" * 64
        manifest.write_text(json.dumps(value), encoding="utf-8")
        manifest.chmod(0o600)
    elif mutation == "member":
        member.write_bytes(member.read_bytes() + b"\n")
    elif mutation == "closeout":
        closed = authority / "PROVISIONAL_OWNER_CLOSED.json"
        closed.write_bytes(closed.read_bytes() + b"\n")
    elif mutation == "cleanup":
        latest = sorted((authority / "preflight-cleanup-state/versions").iterdir())[-1]
        latest.write_bytes(latest.read_bytes() + b"\n")
    elif mutation == "partial":
        member.unlink()
    elif mutation == "symlink":
        member.unlink()
        member.symlink_to(authority / "PROVISIONAL_OWNER_CLOSED.json")
    elif mutation == "hardlink":
        member.unlink()
        os.link(authority / "PROVISIONAL_OWNER_CLOSED.json", member)
    elif mutation == "nonregular":
        member.unlink()
        os.mkfifo(member, mode=0o600)
    elif mutation == "unknown":
        extra = authority / "unknown-member.json"
        extra.write_text("{}\n", encoding="utf-8")
        extra.chmod(0o600)
    else:
        member.chmod(0o640)
    with pytest.raises(provider.T09ProviderError):
        _validate_eligibility(provider_fixture, retained)


@pytest.mark.parametrize(
    ("constant", "value", "message"),
    [
        ("PROVIDER_ENTRY_AUTHORITY_MAX_FILES", 1, "file-count cap"),
        ("PROVIDER_ENTRY_AUTHORITY_MAX_BYTES", 1, "byte cap"),
    ],
)
def test_provider_entry_authority_caps_fail_before_normalization(
    provider_fixture: ProviderFixture,
    monkeypatch: pytest.MonkeyPatch,
    constant: str,
    value: int,
    message: str,
) -> None:
    direct, _ = _close_provider_entry_slot(provider_fixture, slot=1)
    eligibility = _validate_eligibility(provider_fixture, direct)
    target = provider_fixture.root / f"cap-failure-{constant}"
    target.mkdir(mode=0o700)
    monkeypatch.setattr(provider, constant, value)
    with pytest.raises(provider.T09ProviderError, match=message):
        provider._normalize_provider_entry_replacement_authority(
            direct,
            target / provider.PROVIDER_ENTRY_AUTHORITY_ROOT_NAME,
            eligibility=eligibility,
            contract=provider_fixture.contract,
            package_commit=PACKAGE_COMMIT,
            plan_sha256=provider_fixture.plan_sha256,
        )


@pytest.mark.parametrize("field", ["plan_id", "host_run_id", "closed_launch_slot"])
def test_provider_entry_identity_drift_fails_closed(
    provider_fixture: ProviderFixture,
    field: str,
) -> None:
    direct, _ = _close_provider_entry_slot(provider_fixture, slot=1)
    receipt_path = direct / "replacement-launch-eligibility.json"
    receipt = load_json(receipt_path)
    receipt[field] = 0 if field == "closed_launch_slot" else f"wrong-{field}"
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    receipt_path.chmod(0o600)
    with pytest.raises(provider.T09ProviderError):
        _validate_eligibility(provider_fixture, direct)


def test_provider_entry_wrong_owner_metadata_fails_closed(
    provider_fixture: ProviderFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    direct, _ = _close_provider_entry_slot(provider_fixture, slot=1)
    retained, _ = _normalized_copy(
        provider_fixture,
        direct,
        name="wrong-owner-retained",
    )
    actual_uid = os.getuid()
    monkeypatch.setattr(os, "getuid", lambda: actual_uid + 1)
    with pytest.raises(provider.T09ProviderError, match="unsafe"):
        _validate_eligibility(provider_fixture, retained)


def test_provider_entry_binding_rejects_cross_slot_and_changed_hashes(
    provider_fixture: ProviderFixture,
) -> None:
    direct, _ = _close_provider_entry_slot(provider_fixture, slot=1)
    root, receipt_path, _ = _open_provider_entry_slot(
        provider_fixture,
        slot=2,
        prior=direct,
    )
    campaign_path = root / "entry-source/campaign-launch-binding.json"
    campaign = load_json(campaign_path)
    campaign["replacement_eligibility_preempirical_source_manifest_sha256"] = "f" * 64
    campaign_path.write_text(json.dumps(campaign), encoding="utf-8")
    campaign_path.chmod(0o600)
    source_manifest = root / "entry-source/source-manifest.json"
    source_manifest.unlink()
    provider.seal_source_bundle(root / "entry-source", contract=provider_fixture.contract)
    with pytest.raises(provider.T09ProviderError, match="authority hashes drifted"):
        provider.validate_entry_receipt_source_bound(
            receipt_path,
            root / "entry-source",
            contract=provider_fixture.contract,
            package_commit=PACKAGE_COMMIT,
            plan_sha256=provider_fixture.plan_sha256,
        )


def test_provider_entry_manifest_is_deterministic_and_source_bound(
    provider_fixture: ProviderFixture,
) -> None:
    direct, _ = _close_provider_entry_slot(provider_fixture, slot=1)
    first, first_result = _normalized_copy(provider_fixture, direct, name="first-normalized")
    second, second_result = _normalized_copy(provider_fixture, direct, name="second-normalized")
    first_manifest = load_json(first / "slot2-eligibility-source/source-manifest.json")
    second_manifest = load_json(second / "slot2-eligibility-source/source-manifest.json")
    assert first_manifest == second_manifest
    assert first_result.normalized_manifest_sha256 == second_result.normalized_manifest_sha256
    assert first_manifest["authority_type"] == (
        provider.PROVIDER_ENTRY_FAILED_PREEMPIRICAL_ELIGIBILITY_KIND
    )
    assert (
        first_manifest["source_private_root_identity_sha256"]
        == hashlib.sha256(str(direct.resolve()).encode()).hexdigest()
    )
