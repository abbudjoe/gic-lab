from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import stat
from collections.abc import Callable, Iterator, Mapping
from pathlib import Path
from types import ModuleType
from typing import cast

import pytest
import yaml
from jsonschema import Draft202012Validator

from giclab.harness import t09_model_metadata_receipt as metadata
from giclab.harness import t09_pragmatic_provider as provider
from giclab.harness.t09_provider_contracts import V12_PROVIDER_CONTRACT

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "experiments/EXP-0001-sira-simulative-vs-reactive"
PROFILE = EXPERIMENT / "run-plans/proposals/T09_PILOT_RUNTIME_PROFILE_V12.yaml"
V12_PLAN = EXPERIMENT / "run-plans/proposals/PLAN-EXP0001-PILOT-V12.yaml"
BASE_COMMIT = "42a8ce6945c29f4221e03bb836f18421e50f3b1e"
BASE_TREE = "4271fccaf870cfd6a7963ac43daba5b616a0104a"
V11_PLAN_BYTES = 14_754
V11_PLAN_SHA256 = "34a405d06521bd3fb55379721dff9c5795954fcb099d641587e2169b37575411"
HOST_SOURCE = ROOT / "containers/sira-smoke/pragmatic/t09_remote_runner.py"
OPENAI_FIXTURE_VALUE = b"fixture-openai-metadata-value-v12"
LAMBDA_FIXTURE_VALUE = b"fixture-lambda-provider-value-v12"
APPROVED_DOTENV_BYTES = (
    b"OPENAI_API_KEY=" + OPENAI_FIXTURE_VALUE + b"\nLAMBDA_API_KEY=" + LAMBDA_FIXTURE_VALUE + b"\n"
)


def _canonical(value: object) -> bytes:
    return (
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _private_bytes(path: Path, value: bytes) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.write_bytes(value)
    path.chmod(0o600)


def _private_json(path: Path, value: object) -> None:
    _private_bytes(path, _canonical(value))


class FakeClock:
    def __init__(self, *values: float) -> None:
        self._values: Iterator[float] = iter(values)

    def __call__(self) -> float:
        return next(self._values)


class FakeMetadataTransport:
    def __init__(
        self,
        *,
        completed_at: float,
        returned_model: str = metadata.MODEL_METADATA_MODEL_ID,
        status: int = 200,
        failure: BaseException | None = None,
    ) -> None:
        self.completed_at = completed_at
        self.returned_model = returned_model
        self.status = status
        self.failure = failure
        self.calls: list[str] = []
        self.openai_credential_matches: list[bool] = []
        self.lambda_credential_matches: list[bool] = []
        self.credential_references: list[bytearray] = []

    def get_model_metadata(
        self,
        model_id: str,
        *,
        credential: bytearray,
    ) -> metadata.ModelMetadataResponse:
        self.calls.append(model_id)
        self.openai_credential_matches.append(credential == OPENAI_FIXTURE_VALUE)
        self.lambda_credential_matches.append(credential == LAMBDA_FIXTURE_VALUE)
        self.credential_references.append(credential)
        if self.failure is not None:
            raise self.failure
        return metadata.ModelMetadataResponse(
            status=self.status,
            body=_canonical({"id": self.returned_model}),
            response_completed_at=self.completed_at,
        )


class FakeLambdaTransport:
    def __init__(self, *, received_at: float = 0.0) -> None:
        self.received_at = received_at
        self.calls: list[tuple[str, str]] = []

    def send(
        self,
        method: str,
        path: str,
        *,
        body: bytes | None,
        credential: bytearray,
    ) -> provider.ProviderResponse:
        del body, credential
        self.calls.append((method, path))
        return provider.ProviderResponse(
            status=200,
            content_type="application/json",
            body=_canonical({"data": {"instance_ids": ["fixture-instance-id"]}}),
            received_at_epoch=self.received_at,
        )


def _authorization_files(tmp_path: Path) -> tuple[Path, Path, str]:
    plan_sha256 = _sha256(PROFILE)
    overlay = tmp_path / "authorization-overlay.json"
    _private_json(
        overlay,
        {
            "schema_version": metadata.MODEL_METADATA_SCHEMA_VERSION,
            "authorization_reference": "AUTH-T09-V12-CATEGORY3-FIXTURE-0001",
            "authorization_source_sha256": "1" * 64,
            "provider_contract_version": "V12",
            "repository_commit": BASE_COMMIT,
            "repository_tree": BASE_TREE,
            "plan_id": V12_PROVIDER_CONTRACT.plan_id,
            "plan_sha256": plan_sha256,
            "host_run_id": V12_PROVIDER_CONTRACT.host_run_id,
            "public_price_contract_sha256": "2" * 64,
            "public_deprecation_observation_sha256": "3" * 64,
            "model_metadata_receipt_sha256": None,
            "authorized": True,
            "single_use": True,
        },
    )
    dotenv = tmp_path / "openai.env"
    _private_bytes(dotenv, APPROVED_DOTENV_BYTES)
    dotenv.chmod(0o644)
    return overlay, dotenv, plan_sha256


def _create_receipt(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    base: float = 1_700_000_000.0,
    returned_model: str = metadata.MODEL_METADATA_MODEL_ID,
    status: int = 200,
    failure: BaseException | None = None,
) -> tuple[Path, Path, FakeMetadataTransport, str]:
    overlay, dotenv, plan_sha256 = _authorization_files(tmp_path)
    transport = FakeMetadataTransport(
        completed_at=base + 0.25,
        returned_model=returned_model,
        status=status,
        failure=failure,
    )
    output = tmp_path / metadata.MODEL_METADATA_RECEIPT_FILENAME
    monkeypatch.setattr(provider, "_verify_clean_package", lambda repository, commit: None)
    provider.model_metadata_preflight(
        contract=V12_PROVIDER_CONTRACT,
        repository=ROOT,
        package_commit=BASE_COMMIT,
        authorization_overlay=overlay,
        openai_dotenv=dotenv,
        output=output,
        transport=transport,
        clock=FakeClock(base, base + 0.5),
    )
    return output, overlay, transport, plan_sha256


def _validate_provider_immutable(
    receipt: Path,
    overlay: Path,
    plan_sha256: str,
) -> dict[str, object]:
    return provider._validate_model_metadata_receipt_for_provider(
        receipt,
        contract=V12_PROVIDER_CONTRACT,
        package_commit=BASE_COMMIT,
        package_tree=BASE_TREE,
        plan_sha256=plan_sha256,
        authorization_ledger=overlay,
    )


def _load_host() -> ModuleType:
    specification = importlib.util.spec_from_file_location("t09_v12_host_fixture", HOST_SOURCE)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def _patch_launch_phase_a(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    overlay: Path,
    response_epoch: float,
) -> tuple[Path, Path, Path, Path, Path]:
    """Install fake-only provider preparation boundaries for launch tests."""

    tmp_path.mkdir(mode=0o700, parents=True, exist_ok=True)
    capability = tmp_path / "launch-capability.json"
    private_root = tmp_path / "private"
    public_ipv4 = tmp_path / "public-ipv4"
    ssh_key = tmp_path / "id.pub"
    lambda_dotenv = tmp_path / "lambda.env"
    public_ipv4.write_text("203.0.113.9\n")
    ssh_key.write_text("ssh-ed25519 AAAAFIXTURE t09-v12\n")
    lambda_dotenv.write_text("not-read\n")

    monkeypatch.setattr(provider, "_assert_launch_capability_unused", lambda path: None)
    monkeypatch.setattr(provider, "_verify_clean_package", lambda repository, commit: None)
    monkeypatch.setattr(
        provider,
        "validate_authorization_ledger",
        lambda *args, **kwargs: {
            **json.loads(overlay.read_text()),
            "authorization_ledger_sha256": _sha256(overlay),
        },
    )
    monkeypatch.setattr(provider, "load_campaign_lifecycle", lambda *args, **kwargs: object())
    monkeypatch.setattr(provider, "launch_capability_path", lambda *args, **kwargs: capability)
    monkeypatch.setattr(
        provider,
        "load_dotenv_assignment",
        lambda path, name: bytearray(b"fixture-lambda-credential"),
    )
    monkeypatch.setattr(provider, "_response_documents", lambda root: {})
    monkeypatch.setattr(provider, "_validate_prelaunch_documents", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        provider.RequestRecorder,
        "request",
        lambda self, *args, **kwargs: provider.ProviderResponse(
            200,
            "application/json",
            b"{}",
            response_epoch,
        ),
    )

    def consume_capability(path: Path, **kwargs: object) -> None:
        del kwargs
        provider.write_exclusive(
            path,
            {
                "schema_version": "1.0.0",
                "state": "consumed-during-local-preparation",
                "replay_allowed": False,
            },
        )

    monkeypatch.setattr(provider, "_consume_launch_capability", consume_capability)
    return capability, private_root, public_ipv4, ssh_key, lambda_dotenv


def test_local_gate_owns_exactly_one_request_and_seals_no_secret(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    default_transport_constructions = 0
    lambda_transport_constructions = 0

    def forbid_default_transport(*args: object, **kwargs: object) -> None:
        nonlocal default_transport_constructions
        del args, kwargs
        default_transport_constructions += 1
        raise AssertionError("network fallback was constructed")

    def forbid_lambda_transport(*args: object, **kwargs: object) -> None:
        nonlocal lambda_transport_constructions
        del args, kwargs
        lambda_transport_constructions += 1
        raise AssertionError("provider launch transport was constructed")

    monkeypatch.setattr(metadata, "OpenAIModelMetadataTransport", forbid_default_transport)
    monkeypatch.setattr(provider, "LambdaTransport", forbid_lambda_transport)
    overlay, dotenv, plan_sha256 = _authorization_files(tmp_path)
    source_before = dotenv.read_bytes()
    metadata_before = dotenv.stat()
    transport = FakeMetadataTransport(completed_at=1_700_000_000.25)
    receipt = tmp_path / metadata.MODEL_METADATA_RECEIPT_FILENAME
    monkeypatch.setattr(provider, "_verify_clean_package", lambda repository, commit: None)
    provider.model_metadata_preflight(
        contract=V12_PROVIDER_CONTRACT,
        repository=ROOT,
        package_commit=BASE_COMMIT,
        authorization_overlay=overlay,
        openai_dotenv=dotenv,
        output=receipt,
        transport=transport,
        clock=FakeClock(1_700_000_000.0, 1_700_000_000.5),
    )
    assert transport.calls == [metadata.MODEL_METADATA_MODEL_ID]
    assert transport.openai_credential_matches == [True]
    assert transport.lambda_credential_matches == [False]
    assert all(len(value) == 0 for value in transport.credential_references)
    assert default_transport_constructions == 0
    assert lambda_transport_constructions == 0
    assert stat.S_IMODE(receipt.stat().st_mode) == 0o600
    assert receipt.stat().st_uid == os.getuid()
    assert receipt.stat().st_nlink == 1
    raw = receipt.read_bytes()
    assert raw == _canonical(json.loads(raw))
    assert b"Authorization" not in raw
    assert b"account" not in raw
    document = json.loads(raw)
    assert document["request_count"] == 1
    assert (
        document["redirect_count"],
        document["retry_count"],
        document["pagination_count"],
    ) == (0, 0, 0)
    assert json.loads(overlay.read_text())["model_metadata_receipt_sha256"] == (
        metadata.model_metadata_receipt_sha256(receipt)
    )
    assert metadata.semantic_projection_sha256(
        _validate_provider_immutable(receipt, overlay, plan_sha256)
    ) == metadata.model_metadata_receipt_sha256(receipt)
    states = list(tmp_path.glob(".t09-model-metadata-*.state.json"))
    assert len(states) == 1
    assert json.loads(states[0].read_text())["state"] == "consumed-after-send-attempt"
    source_after = dotenv.stat()
    source_bytes_unchanged = dotenv.read_bytes() == source_before == APPROVED_DOTENV_BYTES
    assert source_bytes_unchanged is True
    assert stat.S_IMODE(source_after.st_mode) == stat.S_IMODE(metadata_before.st_mode) == 0o644
    assert source_after.st_uid == metadata_before.st_uid == os.getuid()
    assert source_after.st_ino == metadata_before.st_ino
    assert source_after.st_nlink == metadata_before.st_nlink == 1
    assert source_after.st_mtime_ns == metadata_before.st_mtime_ns
    assert source_after.st_ctime_ns == metadata_before.st_ctime_ns
    generated_contains_fixture = any(
        OPENAI_FIXTURE_VALUE in path.read_bytes() or LAMBDA_FIXTURE_VALUE in path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file() and path != dotenv
    )
    assert generated_contains_fixture is False


@pytest.mark.parametrize(
    ("returned_model", "status"),
    (("gpt-4o-other", 200), (metadata.MODEL_METADATA_MODEL_ID, 503)),
)
def test_local_gate_rejects_wrong_model_or_status_after_one_attempt(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    returned_model: str,
    status: int,
) -> None:
    overlay, dotenv, plan_sha256 = _authorization_files(tmp_path)
    transport = FakeMetadataTransport(
        completed_at=100.25,
        returned_model=returned_model,
        status=status,
    )
    monkeypatch.setattr(provider, "_verify_clean_package", lambda repository, commit: None)
    with pytest.raises(provider.T09ProviderError, match="receipt was not sealed"):
        provider.model_metadata_preflight(
            contract=V12_PROVIDER_CONTRACT,
            repository=ROOT,
            package_commit=BASE_COMMIT,
            authorization_overlay=overlay,
            openai_dotenv=dotenv,
            output=tmp_path / "receipt.json",
            transport=transport,
            clock=FakeClock(100.0, 100.5),
        )
    assert len(transport.calls) == 1
    assert not (tmp_path / "receipt.json").exists()
    assert plan_sha256 == _sha256(PROFILE)
    state = json.loads(next(tmp_path.glob(".t09-model-metadata-*.state.json")).read_text())
    assert state["state"] == "consumed-after-send-attempt"
    assert state["replay_allowed"] is False


def test_failed_local_gate_and_missing_receipt_make_zero_lambda_posts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    base = 1_700_000_000.0
    source_root = tmp_path / "failed-local-gate"
    overlay, dotenv, _plan_sha256 = _authorization_files(source_root)
    metadata_transport = FakeMetadataTransport(
        completed_at=base + 0.25,
        returned_model="gpt-4o-other",
    )
    missing_receipt = source_root / metadata.MODEL_METADATA_RECEIPT_FILENAME
    monkeypatch.setattr(provider, "_verify_clean_package", lambda repository, commit: None)
    with pytest.raises(provider.T09ProviderError, match="receipt was not sealed"):
        provider.model_metadata_preflight(
            contract=V12_PROVIDER_CONTRACT,
            repository=ROOT,
            package_commit=BASE_COMMIT,
            authorization_overlay=overlay,
            openai_dotenv=dotenv,
            output=missing_receipt,
            transport=metadata_transport,
            clock=FakeClock(base, base + 0.5),
        )
    assert len(metadata_transport.calls) == 1
    assert not missing_receipt.exists()

    _capability, private_root, public_ipv4, ssh_key, lambda_dotenv = _patch_launch_phase_a(
        monkeypatch,
        tmp_path / "launch",
        overlay=overlay,
        response_epoch=base + 1.0,
    )
    lambda_transport = FakeLambdaTransport()
    with pytest.raises(provider.T09ProviderError, match="receipt validation failed"):
        provider.launch_campaign(
            contract=V12_PROVIDER_CONTRACT,
            repository=ROOT,
            package_commit=BASE_COMMIT,
            authorization_ledger=overlay,
            dotenv=lambda_dotenv,
            private_root=private_root,
            public_ipv4_file=public_ipv4,
            ssh_public_key_file=ssh_key,
            transport=lambda_transport,
            model_metadata_receipt=missing_receipt,
            clock=lambda: base + 1.0,
            sleeper=lambda seconds: None,
        )
    assert lambda_transport.calls == []
    assert not private_root.exists()


def test_loaded_credential_is_zeroed_when_authorization_reservation_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    overlay, dotenv, plan_sha256 = _authorization_files(tmp_path)
    reference = "AUTH-T09-V12-CATEGORY3-FIXTURE-0001"
    overlay_sha256 = metadata.model_metadata_authorization_overlay_sha256(overlay)
    occupied_state = metadata._authorization_state_path(overlay, reference)
    _private_json(occupied_state, {"fixture": "occupied"})
    credential = bytearray(b"fixture-openai-key-123456")
    monkeypatch.setattr(
        metadata,
        "load_openai_dotenv_assignment",
        lambda path: credential,
    )
    transport = FakeMetadataTransport(completed_at=100.25)
    with pytest.raises(metadata.ModelMetadataReceiptError, match="reserved or consumed"):
        metadata.create_model_metadata_receipt(
            repository_commit=BASE_COMMIT,
            repository_tree=BASE_TREE,
            plan_id=V12_PROVIDER_CONTRACT.plan_id,
            plan_sha256=plan_sha256,
            provider_contract_version=V12_PROVIDER_CONTRACT.version,
            host_run_id=V12_PROVIDER_CONTRACT.host_run_id,
            authorization_reference=reference,
            authorization_source_sha256="1" * 64,
            authorization_overlay_sha256=overlay_sha256,
            public_price_contract_sha256="2" * 64,
            public_deprecation_observation_sha256="3" * 64,
            output=tmp_path / metadata.MODEL_METADATA_RECEIPT_FILENAME,
            dotenv=dotenv,
            authorization_overlay=overlay,
            transport=transport,
            clock=lambda: 100.0,
        )
    assert credential == bytearray()
    assert transport.calls == []


def test_authorization_output_and_unknown_outcome_are_nonreplayable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    receipt, overlay, transport, _plan_sha256 = _create_receipt(monkeypatch, tmp_path)
    dotenv = tmp_path / "openai.env"
    with pytest.raises(provider.T09ProviderError, match="receipt was not sealed"):
        provider.model_metadata_preflight(
            contract=V12_PROVIDER_CONTRACT,
            repository=ROOT,
            package_commit=BASE_COMMIT,
            authorization_overlay=overlay,
            openai_dotenv=dotenv,
            output=tmp_path / "second.json",
            transport=transport,
            clock=FakeClock(200.0, 200.5),
        )
    assert len(transport.calls) == 1
    with pytest.raises(provider.T09ProviderError, match="receipt was not sealed"):
        provider.model_metadata_preflight(
            contract=V12_PROVIDER_CONTRACT,
            repository=ROOT,
            package_commit=BASE_COMMIT,
            authorization_overlay=overlay,
            openai_dotenv=dotenv,
            output=receipt,
            transport=transport,
            clock=FakeClock(300.0, 300.5),
        )

    failure_root = tmp_path / "unknown"
    overlay2, dotenv2, _ = _authorization_files(failure_root)
    failing = FakeMetadataTransport(
        completed_at=400.25,
        failure=RuntimeError("fixture unknown outcome"),
    )
    with pytest.raises(provider.T09ProviderError, match="receipt was not sealed"):
        provider.model_metadata_preflight(
            contract=V12_PROVIDER_CONTRACT,
            repository=ROOT,
            package_commit=BASE_COMMIT,
            authorization_overlay=overlay2,
            openai_dotenv=dotenv2,
            output=failure_root / "receipt.json",
            transport=failing,
            clock=FakeClock(400.0),
        )
    assert len(failing.calls) == 1
    failed_state = json.loads(
        next(failure_root.glob(".t09-model-metadata-*.state.json")).read_text()
    )
    assert failed_state["state"] == "consumed-after-send-attempt"
    assert not (failure_root / "receipt.json").exists()


@pytest.mark.parametrize(
    ("mode", "raw"),
    (
        (0o600, b"\n  # fixture comment\nOPENAI_API_KEY=" + OPENAI_FIXTURE_VALUE + b"\n"),
        (
            0o644,
            b"LAMBDA_API_KEY="
            + LAMBDA_FIXTURE_VALUE
            + b"\n# fixture comment\nOPENAI_API_KEY="
            + OPENAI_FIXTURE_VALUE,
        ),
    ),
    ids=("mode-0600-openai-only", "mode-0644-approved-mixed"),
)
def test_dotenv_accepts_safe_0600_and_0644_with_order_independent_allowlist(
    tmp_path: Path,
    mode: int,
    raw: bytes,
) -> None:
    path = tmp_path / f"approved-{mode:o}.env"
    _private_bytes(path, raw)
    path.chmod(mode)
    before = path.stat()
    selected = metadata.load_openai_dotenv_assignment(path)
    matched = selected == OPENAI_FIXTURE_VALUE
    metadata._destroy_bytearray(selected)
    after = path.stat()
    assert matched is True
    assert (path.read_bytes() == raw) is True
    assert stat.S_IMODE(after.st_mode) == mode
    assert (after.st_uid, after.st_ino, after.st_nlink) == (
        before.st_uid,
        before.st_ino,
        before.st_nlink,
    )
    assert (after.st_mtime_ns, after.st_ctime_ns) == (
        before.st_mtime_ns,
        before.st_ctime_ns,
    )


@pytest.mark.parametrize(
    "raw",
    (
        b"LAMBDA_API_KEY=" + LAMBDA_FIXTURE_VALUE + b"\n",
        b"OPENAI_API_KEY="
        + OPENAI_FIXTURE_VALUE
        + b"\nOPENAI_API_KEY=fixture-openai-second-value-v12\n",
        APPROVED_DOTENV_BYTES + b"LAMBDA_API_KEY=fixture-lambda-second-value-v12\n",
        APPROVED_DOTENV_BYTES + b"THIRD_API_KEY=fixture-third-assignment-v12\n",
        b"OPENAI_API_KEY\n",
        b"OPENAI-API-KEY=" + OPENAI_FIXTURE_VALUE + b"\n",
        b"export OPENAI_API_KEY=" + OPENAI_FIXTURE_VALUE + b"\n",
        b"OPENAI_API_KEY='fixture-openai-quoted-value-v12'\n",
        b'OPENAI_API_KEY="fixture-openai-quoted-value-v12"\n',
        b"OPENAI_API_KEY=${FIXTURE_OPENAI_VALUE}\n",
        b"OPENAI_API_KEY=$(fixture-command)\n",
        b"OPENAI_API_KEY=fixture-openai-continuation-v12\\\ncontinued-value\n",
        b"OPENAI_API_KEY=fixture-openai\nmultiline-value\n",
        b"OPENAI_API_KEY =" + OPENAI_FIXTURE_VALUE + b"\n",
        b"OPENAI_API_KEY=too-short\n",
        b"OPENAI_API_KEY=" + b"x" * 4097 + b"\n",
    ),
    ids=(
        "missing-openai",
        "duplicate-openai",
        "duplicate-lambda",
        "unknown-assignment",
        "missing-separator",
        "malformed-name",
        "export-syntax",
        "single-quoted-value",
        "double-quoted-value",
        "interpolation",
        "command-substitution",
        "line-continuation",
        "multiline-value",
        "ambiguous-whitespace",
        "short-value",
        "over-bound-value",
    ),
)
def test_dotenv_rejects_missing_duplicates_unknown_or_shell_syntax(
    tmp_path: Path,
    raw: bytes,
) -> None:
    path = tmp_path / "rejected.env"
    _private_bytes(path, raw)
    with pytest.raises(metadata.ModelMetadataReceiptError) as raised:
        metadata.load_openai_dotenv_assignment(path)
    error_bytes = str(raised.value).encode()
    error_contains_fixture = (
        OPENAI_FIXTURE_VALUE in error_bytes or LAMBDA_FIXTURE_VALUE in error_bytes
    )
    assert error_contains_fixture is False


def test_dotenv_zeroes_raw_ignored_and_exceptional_selected_buffers(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    actual_destroy = metadata._destroy_bytearray
    destroyed_sizes: list[tuple[int, int]] = []

    def observed_destroy(value: bytearray) -> None:
        before = len(value)
        actual_destroy(value)
        destroyed_sizes.append((before, len(value)))

    monkeypatch.setattr(metadata, "_destroy_bytearray", observed_destroy)
    accepted = tmp_path / "accepted.env"
    _private_bytes(accepted, APPROVED_DOTENV_BYTES)
    accepted.chmod(0o644)
    selected = metadata.load_openai_dotenv_assignment(accepted)
    selected_matches = selected == OPENAI_FIXTURE_VALUE
    metadata._destroy_bytearray(selected)
    assert selected_matches is True
    assert (len(LAMBDA_FIXTURE_VALUE), 0) in destroyed_sizes
    assert (len(APPROVED_DOTENV_BYTES), 0) in destroyed_sizes
    assert all(after == 0 for _before, after in destroyed_sizes)

    destroyed_sizes.clear()
    rejected = tmp_path / "duplicate.env"
    _private_bytes(
        rejected,
        b"OPENAI_API_KEY="
        + OPENAI_FIXTURE_VALUE
        + b"\nOPENAI_API_KEY=fixture-openai-second-value-v12\n",
    )
    with pytest.raises(metadata.ModelMetadataReceiptError):
        metadata.load_openai_dotenv_assignment(rejected)
    assert (len(OPENAI_FIXTURE_VALUE), 0) in destroyed_sizes
    assert all(after == 0 for _before, after in destroyed_sizes)


@pytest.mark.parametrize("mode", (0o620, 0o602, 0o666))
def test_dotenv_rejects_group_or_world_write_bits(tmp_path: Path, mode: int) -> None:
    path = tmp_path / f"writable-{mode:o}.env"
    _private_bytes(path, APPROVED_DOTENV_BYTES)
    path.chmod(mode)
    with pytest.raises(metadata.ModelMetadataReceiptError, match="metadata is unsafe"):
        metadata.load_openai_dotenv_assignment(path)


def test_dotenv_rejects_symlink_hardlink_nonregular_unsafe_parent_and_relative_path(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.env"
    _private_bytes(source, APPROVED_DOTENV_BYTES)

    symlink = tmp_path / "symlink.env"
    symlink.symlink_to(source)
    with pytest.raises(metadata.ModelMetadataReceiptError):
        metadata.load_openai_dotenv_assignment(symlink)

    hardlink = tmp_path / "hardlink.env"
    os.link(source, hardlink)
    with pytest.raises(metadata.ModelMetadataReceiptError, match="metadata is unsafe"):
        metadata.load_openai_dotenv_assignment(source)
    hardlink.unlink()

    nonregular = tmp_path / "directory.env"
    nonregular.mkdir(mode=0o700)
    with pytest.raises(metadata.ModelMetadataReceiptError, match="metadata is unsafe"):
        metadata.load_openai_dotenv_assignment(nonregular)

    unsafe_parent = tmp_path / "unsafe-parent"
    unsafe_parent.mkdir(mode=0o700)
    unsafe_path = unsafe_parent / "openai.env"
    _private_bytes(unsafe_path, APPROVED_DOTENV_BYTES)
    unsafe_parent.chmod(0o777)
    with pytest.raises(metadata.ModelMetadataReceiptError, match="parent metadata is unsafe"):
        metadata.load_openai_dotenv_assignment(unsafe_path)

    with pytest.raises(metadata.ModelMetadataReceiptError, match="path must be absolute"):
        metadata.load_openai_dotenv_assignment(Path("relative-openai.env"))


def test_dotenv_rejects_path_replacement_while_descriptor_is_held(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    path = tmp_path / "openai.env"
    displaced = tmp_path / "displaced.env"
    _private_bytes(path, APPROVED_DOTENV_BYTES)
    actual_readv = os.readv
    replaced = False

    def replacing_readv(descriptor: int, buffers: list[memoryview]) -> int:
        nonlocal replaced
        count = actual_readv(descriptor, buffers)
        if not replaced:
            replaced = True
            path.replace(displaced)
            _private_bytes(path, APPROVED_DOTENV_BYTES)
        return count

    monkeypatch.setattr(metadata.os, "readv", replacing_readv)
    with pytest.raises(metadata.ModelMetadataReceiptError, match="changed while held"):
        metadata.load_openai_dotenv_assignment(path)


@pytest.mark.parametrize("drift", ("truncate", "same-size-mutation"))
def test_dotenv_rejects_mutation_or_truncation_while_descriptor_is_held(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    drift: str,
) -> None:
    path = tmp_path / "openai.env"
    _private_bytes(path, APPROVED_DOTENV_BYTES)
    actual_readv = os.readv
    changed = False

    def mutating_readv(descriptor: int, buffers: list[memoryview]) -> int:
        nonlocal changed
        count = actual_readv(descriptor, buffers)
        if not changed:
            changed = True
            if drift == "truncate":
                path.write_bytes(b"")
            else:
                path.write_bytes(b"z" * len(APPROVED_DOTENV_BYTES))
        return count

    monkeypatch.setattr(metadata.os, "readv", mutating_readv)
    with pytest.raises(metadata.ModelMetadataReceiptError, match="changed while held"):
        metadata.load_openai_dotenv_assignment(path)


def test_dotenv_mode_policy_does_not_relax_private_json_controls(tmp_path: Path) -> None:
    for name in ("receipt.json", "authorization-overlay.json", "state.json"):
        path = tmp_path / name
        _private_json(path, {"fixture": True})
        path.chmod(0o644)
        with pytest.raises(metadata.ModelMetadataReceiptError, match="metadata is unsafe"):
            metadata._load_private_object(path, label=name)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("provider_contract_version", "V11"),
        ("repository_commit", "a" * 40),
        ("repository_tree", "b" * 40),
        ("plan_sha256", "c" * 64),
        ("plan_id", "PLAN-EXP0001-PILOT-V11"),
        ("host_run_id", "RUN-T09-PILOT-HOST-AUTONOMOUS-0004"),
        ("authorization_reference", "AUTH-T09-V12-WRONG"),
        ("authorization_source_sha256", "d" * 64),
        ("requested_model_id", "gpt-4o-other"),
        ("returned_model_id", "gpt-4o-other"),
        ("model_endpoint", "https://api.openai.com/v1/models/gpt-4o-other"),
        ("http_status", 201),
        ("request_count", 2),
        ("redirect_count", 1),
        ("retry_count", 1),
        ("pagination_count", 1),
    ),
)
def test_provider_rejects_every_wrong_immutable_binding(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    field: str,
    value: object,
) -> None:
    receipt, overlay, _transport, plan_sha256 = _create_receipt(monkeypatch, tmp_path)
    document = json.loads(receipt.read_text())
    document[field] = value
    _private_json(receipt, document)
    with pytest.raises(metadata.ModelMetadataReceiptError):
        _validate_provider_immutable(receipt, overlay, plan_sha256)


def test_v11_receipt_identity_is_rejected_by_v12_provider(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    receipt, overlay, _transport, plan_sha256 = _create_receipt(monkeypatch, tmp_path)
    document = json.loads(receipt.read_text())
    document.update(
        {
            "provider_contract_version": "V11",
            "plan_id": "PLAN-EXP0001-PILOT-V11",
            "host_run_id": "RUN-T09-PILOT-HOST-AUTONOMOUS-0004",
            "authorization_reference": "AUTH-T09-V11-CATEGORY3-FIXTURE-0001",
        }
    )
    _private_json(receipt, document)
    with pytest.raises(metadata.ModelMetadataReceiptError, match="fixed semantics"):
        _validate_provider_immutable(receipt, overlay, plan_sha256)


def test_response_or_receipt_after_provider_launch_is_rejected_before_send(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    base = 1_700_000_000.0
    receipt, overlay, _transport, plan_sha256 = _create_receipt(
        monkeypatch,
        tmp_path,
        base=base,
    )
    validated = _validate_provider_immutable(receipt, overlay, plan_sha256)
    lambda_transport = FakeLambdaTransport()
    recorder_root = tmp_path / "provider"
    recorder_root.mkdir(mode=0o700)
    recorder = provider.RequestRecorder(
        recorder_root,
        lambda_transport,
        bytearray(b"fixture-lambda-credential"),
    )
    prepared = recorder.prepare(
        "launch",
        "POST",
        "/api/v1/instance-operations/launch",
        body={"fixture": True},
    )

    def reject_after_launch() -> float:
        boundary = base + 0.1
        metadata.admit_model_metadata_receipt_at_prelaunch_boundary(
            validated,
            boundary_epoch=boundary,
        )
        return boundary

    with pytest.raises(metadata.ModelMetadataReceiptError, match="after provider launch"):
        recorder.send_prepared(prepared, final_admission=reject_after_launch)
    assert lambda_transport.calls == []
    assert not (recorder_root / "request-journal.jsonl").exists()


def test_phase_a_failure_makes_zero_transport_calls(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    base = 1_700_000_000.0
    receipt, overlay, _metadata_transport, _plan_sha256 = _create_receipt(
        monkeypatch,
        tmp_path / "receipt-source",
        base=base,
    )
    _capability, private_root, public_ipv4, ssh_key, lambda_dotenv = _patch_launch_phase_a(
        monkeypatch,
        tmp_path / "launch",
        overlay=overlay,
        response_epoch=base + 10.0,
    )

    def fail_preparation(path: Path, **kwargs: object) -> None:
        del path, kwargs
        raise provider.T09ProviderError("fixture Phase A preparation failed")

    monkeypatch.setattr(provider, "_consume_launch_capability", fail_preparation)
    lambda_transport = FakeLambdaTransport()
    with pytest.raises(provider.T09ProviderError, match="Phase A preparation failed"):
        provider.launch_campaign(
            contract=V12_PROVIDER_CONTRACT,
            repository=ROOT,
            package_commit=BASE_COMMIT,
            authorization_ledger=overlay,
            dotenv=lambda_dotenv,
            private_root=private_root,
            public_ipv4_file=public_ipv4,
            ssh_public_key_file=ssh_key,
            transport=lambda_transport,
            model_metadata_receipt=receipt,
            clock=lambda: base + 10.0,
            sleeper=lambda seconds: None,
        )
    assert lambda_transport.calls == []
    assert not (private_root / "launch-send-intent.json").exists()


def test_receipt_security_duplicate_fields_and_path_replacement_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    receipt, overlay, _transport, plan_sha256 = _create_receipt(monkeypatch, tmp_path)
    symlink = tmp_path / "receipt-link.json"
    symlink.symlink_to(receipt)
    with pytest.raises(metadata.ModelMetadataReceiptError):
        _validate_provider_immutable(symlink, overlay, plan_sha256)

    hardlink = tmp_path / "receipt-hardlink.json"
    os.link(receipt, hardlink)
    with pytest.raises(metadata.ModelMetadataReceiptError):
        _validate_provider_immutable(receipt, overlay, plan_sha256)
    hardlink.unlink()

    duplicate = tmp_path / "duplicate.json"
    _private_bytes(duplicate, b'{"schema_version":"1.0.0","schema_version":"1.0.0"}\n')
    with pytest.raises(metadata.ModelMetadataReceiptError, match="malformed JSON"):
        _validate_provider_immutable(duplicate, overlay, plan_sha256)

    actual_stat = Path.stat

    def replaced_stat(
        path: Path,
        *,
        follow_symlinks: bool = True,
    ) -> os.stat_result:
        observed = actual_stat(path, follow_symlinks=follow_symlinks)
        if path == receipt and not follow_symlinks:
            fields = list(observed)
            fields[1] = observed.st_ino + 1
            return os.stat_result(fields)
        return observed

    monkeypatch.setattr(Path, "stat", replaced_stat)
    with pytest.raises(metadata.ModelMetadataReceiptError, match="changed while held"):
        _validate_provider_immutable(receipt, overlay, plan_sha256)


def _final_admission(
    *,
    receipt: Path,
    overlay: Path,
    plan_sha256: str,
    expected_sha256: str,
    boundary: Callable[[], float],
) -> Callable[[], float]:
    def admit() -> float:
        validated = _validate_provider_immutable(receipt, overlay, plan_sha256)
        assert metadata.semantic_projection_sha256(validated) == expected_sha256
        sampled = boundary()
        metadata.admit_model_metadata_receipt_at_prelaunch_boundary(
            validated,
            boundary_epoch=sampled,
        )
        return sampled

    return admit


def test_final_boundary_is_inclusive_at_exactly_1800_and_sends_once(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    base = 1_700_000_000.0
    receipt, overlay, metadata_transport, plan_sha256 = _create_receipt(
        monkeypatch,
        tmp_path,
        base=base,
    )
    retained_root = tmp_path / "entry"
    retained_root.mkdir(mode=0o700)
    retained = retained_root / metadata.MODEL_METADATA_RECEIPT_FILENAME
    expected = metadata.copy_model_metadata_receipt(receipt, retained)
    transport = FakeLambdaTransport(received_at=base + 1_800.6)
    recorder = provider.RequestRecorder(
        retained_root,
        transport,
        bytearray(b"fixture-lambda-credential"),
        clock=lambda: base + 1_801.0,
    )
    prepared = recorder.prepare(
        "launch",
        "POST",
        "/api/v1/instance-operations/launch",
        body={"fixture": True},
    )
    response = recorder.send_prepared(
        prepared,
        final_admission=_final_admission(
            receipt=retained,
            overlay=overlay,
            plan_sha256=plan_sha256,
            expected_sha256=expected,
            boundary=lambda: base + 1_800.5,
        ),
    )
    assert response.status == 200
    assert transport.calls == [("POST", "/api/v1/instance-operations/launch")]
    assert len(metadata_transport.calls) == 1
    events = [
        json.loads(line)
        for line in (retained_root / "request-journal.jsonl").read_text().splitlines()
    ]
    assert [event["event"] for event in events] == [
        "send-started",
        "response-complete",
    ]
    assert events[0]["send_started_at_epoch"] == base + 1_800.5


def test_final_boundary_rejects_more_than_1800_with_zero_post(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    base = 1_700_000_000.0
    receipt, overlay, _metadata_transport, plan_sha256 = _create_receipt(
        monkeypatch,
        tmp_path,
        base=base,
    )
    root = tmp_path / "entry"
    root.mkdir(mode=0o700)
    retained = root / metadata.MODEL_METADATA_RECEIPT_FILENAME
    expected = metadata.copy_model_metadata_receipt(receipt, retained)
    transport = FakeLambdaTransport()
    recorder = provider.RequestRecorder(
        root,
        transport,
        bytearray(b"fixture-lambda-credential"),
    )
    prepared = recorder.prepare(
        "launch",
        "POST",
        "/api/v1/instance-operations/launch",
        body={"fixture": True},
    )
    with pytest.raises(metadata.ModelMetadataReceiptError, match="stale"):
        recorder.send_prepared(
            prepared,
            final_admission=_final_admission(
                receipt=retained,
                overlay=overlay,
                plan_sha256=plan_sha256,
                expected_sha256=expected,
                boundary=lambda: base + 1_800.500_001,
            ),
        )
    assert transport.calls == []
    assert not (root / "request-journal.jsonl").exists()


def test_crossing_window_during_phase_a_consumes_intent_but_posts_zero(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    base = 1_700_000_000.0
    receipt, overlay, _metadata_transport, _plan_sha256 = _create_receipt(
        monkeypatch,
        tmp_path / "receipt-source",
        base=base,
    )
    capability = tmp_path / "launch-capability.json"
    private_root = tmp_path / "private"
    public_ipv4 = tmp_path / "public-ipv4"
    ssh_key = tmp_path / "id.pub"
    lambda_dotenv = tmp_path / "lambda.env"
    public_ipv4.write_text("203.0.113.9\n")
    ssh_key.write_text("ssh-ed25519 AAAAFIXTURE t09-v12\n")
    lambda_dotenv.write_text("not-read\n")

    monkeypatch.setattr(provider, "_assert_launch_capability_unused", lambda path: None)
    monkeypatch.setattr(provider, "_verify_clean_package", lambda repository, commit: None)
    monkeypatch.setattr(
        provider,
        "validate_authorization_ledger",
        lambda *args, **kwargs: {
            **json.loads(overlay.read_text()),
            "authorization_ledger_sha256": _sha256(overlay),
        },
    )
    monkeypatch.setattr(provider, "load_campaign_lifecycle", lambda *args, **kwargs: object())
    monkeypatch.setattr(provider, "launch_capability_path", lambda *args, **kwargs: capability)
    monkeypatch.setattr(
        provider,
        "load_dotenv_assignment",
        lambda path, name: bytearray(b"fixture-lambda-credential"),
    )
    monkeypatch.setattr(provider, "_response_documents", lambda root: {})
    monkeypatch.setattr(provider, "_validate_prelaunch_documents", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        provider.RequestRecorder,
        "request",
        lambda self, *args, **kwargs: provider.ProviderResponse(
            200,
            "application/json",
            b"{}",
            base + 1_799.0,
        ),
    )

    def consume_capability(path: Path, **kwargs: object) -> None:
        del kwargs
        provider.write_exclusive(
            path,
            {
                "schema_version": "1.0.0",
                "state": "consumed-during-local-preparation",
                "replay_allowed": False,
            },
        )

    monkeypatch.setattr(provider, "_consume_launch_capability", consume_capability)
    transport = FakeLambdaTransport()
    crossing_clock = FakeClock(
        base + 1_799.0,
        base + 1_799.5,
        base + 1_800.6,
        base + 1_801.0,
    )
    with pytest.raises(
        provider.T09ProviderError,
        match="provider launch boundary",
    ):
        provider.launch_campaign(
            contract=V12_PROVIDER_CONTRACT,
            repository=ROOT,
            package_commit=BASE_COMMIT,
            authorization_ledger=overlay,
            dotenv=lambda_dotenv,
            private_root=private_root,
            public_ipv4_file=public_ipv4,
            ssh_public_key_file=ssh_key,
            transport=transport,
            model_metadata_receipt=receipt,
            clock=crossing_clock,
            sleeper=lambda seconds: None,
        )
    assert transport.calls == []
    assert json.loads(capability.read_text())["replay_allowed"] is False
    send_intent = json.loads((private_root / "launch-send-intent.json").read_text())
    assert send_intent["state"] == "durable-before-final-admission"
    assert send_intent["replay_allowed"] is False
    assert send_intent["transport_calls_completed"] == 0
    assert send_intent["send_started_at_epoch"] is None
    assert not (private_root / "entry-source/request-journal.jsonl").exists()


@pytest.mark.parametrize("elapsed", (1_800.1, 3_600.1))
def test_host_accepts_provider_admitted_receipt_durably_offline(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    elapsed: float,
) -> None:
    base = 1_700_000_000.0
    receipt, _overlay, metadata_transport, _plan_sha256 = _create_receipt(
        monkeypatch,
        tmp_path,
        base=base,
    )
    host = _load_host()
    monkeypatch.setattr(
        host,
        "model_metadata_preflight",
        lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("offline host attempted metadata fallback")
        ),
    )
    host_clock_calls = 0

    def delayed_clock() -> float:
        nonlocal host_clock_calls
        host_clock_calls += 1
        return base + elapsed

    monkeypatch.setattr(host.time, "time", delayed_clock)
    artifact_root = tmp_path / "artifacts"
    (artifact_root / "pilot-v12").mkdir(mode=0o700, parents=True)
    acknowledgement = host.validate_model_metadata_receipt_offline(
        contract=V12_PROVIDER_CONTRACT,
        receipt_path=receipt,
        repository=ROOT,
        package_commit=BASE_COMMIT,
        provider_entry={
            "model_metadata_receipt_sha256": metadata.model_metadata_receipt_sha256(receipt),
            "authorization_reference": "AUTH-T09-V12-CATEGORY3-FIXTURE-0001",
            "authorization_source_sha256": "1" * 64,
            "provider_preflight_started_at_epoch": base + 1.0,
        },
        artifact_root=artifact_root,
    )
    assert acknowledgement["validation_mode"] == "offline-sealed-receipt"
    assert acknowledgement["model_metadata_network_requests"] == 0
    assert acknowledgement["host_runtime_model_metadata_request_count"] == 0
    assert acknowledgement["openai_transport_used"] is False
    assert host_clock_calls == 0
    assert len(metadata_transport.calls) == 1


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("model_metadata_receipt_sha256", "f" * 64),
        ("authorization_reference", "AUTH-T09-V12-WRONG"),
        ("authorization_source_sha256", "4" * 64),
        ("provider_preflight_started_at_epoch", 1_699_999_999.0),
    ),
)
def test_host_binding_drift_fails_before_acknowledgement(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    field: str,
    value: object,
) -> None:
    base = 1_700_000_000.0
    receipt, _overlay, _transport, _plan_sha256 = _create_receipt(
        monkeypatch,
        tmp_path,
        base=base,
    )
    entry: dict[str, object] = {
        "model_metadata_receipt_sha256": metadata.model_metadata_receipt_sha256(receipt),
        "authorization_reference": "AUTH-T09-V12-CATEGORY3-FIXTURE-0001",
        "authorization_source_sha256": "1" * 64,
        "provider_preflight_started_at_epoch": base + 1.0,
    }
    entry[field] = value
    host = _load_host()
    artifact_root = tmp_path / "artifacts"
    (artifact_root / "pilot-v12").mkdir(mode=0o700, parents=True)
    with pytest.raises(host.T09HostError):
        host.validate_model_metadata_receipt_offline(
            contract=V12_PROVIDER_CONTRACT,
            receipt_path=receipt,
            repository=ROOT,
            package_commit=BASE_COMMIT,
            provider_entry=entry,
            artifact_root=artifact_root,
        )
    assert not (artifact_root / "pilot-v12/model-metadata-receipt-acknowledgement.json").exists()
    assert not (artifact_root / "pilot-v12/frozen-run-manifest.json").exists()


@pytest.mark.parametrize("drift", ("request-count", "unsafe-hardlink"))
def test_host_count_or_file_metadata_drift_fails_before_manifest(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    drift: str,
) -> None:
    base = 1_700_000_000.0
    receipt, _overlay, _transport, _plan_sha256 = _create_receipt(
        monkeypatch,
        tmp_path / "receipt-source",
        base=base,
    )
    expected_sha256 = metadata.model_metadata_receipt_sha256(receipt)
    if drift == "request-count":
        document = json.loads(receipt.read_text())
        document["request_count"] = 2
        _private_json(receipt, document)
        expected_sha256 = metadata.model_metadata_receipt_sha256(receipt)
    else:
        os.link(receipt, tmp_path / "receipt-hardlink.json")
    host = _load_host()
    artifact_root = tmp_path / "artifacts"
    (artifact_root / "pilot-v12").mkdir(mode=0o700, parents=True)
    with pytest.raises(host.T09HostError):
        host.validate_model_metadata_receipt_offline(
            contract=V12_PROVIDER_CONTRACT,
            receipt_path=receipt,
            repository=ROOT,
            package_commit=BASE_COMMIT,
            provider_entry={
                "model_metadata_receipt_sha256": expected_sha256,
                "authorization_reference": "AUTH-T09-V12-CATEGORY3-FIXTURE-0001",
                "authorization_source_sha256": "1" * 64,
                "provider_preflight_started_at_epoch": base + 1.0,
            },
            artifact_root=artifact_root,
        )
    assert not (artifact_root / "pilot-v12/model-metadata-receipt-acknowledgement.json").exists()
    assert not (artifact_root / "pilot-v12/frozen-run-manifest.json").exists()


def test_end_to_end_fake_handoff_owns_one_openai_get_and_no_provider_or_host_gets(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    base = 1_700_000_000.0
    default_transport_constructions = 0

    def forbid_default_transport(*args: object, **kwargs: object) -> None:
        nonlocal default_transport_constructions
        del args, kwargs
        default_transport_constructions += 1
        raise AssertionError("provider or host constructed an OpenAI transport")

    monkeypatch.setattr(metadata, "OpenAIModelMetadataTransport", forbid_default_transport)
    receipt, overlay, metadata_transport, plan_sha256 = _create_receipt(
        monkeypatch,
        tmp_path / "receipt-source",
        base=base,
    )
    provider_root = tmp_path / "provider"
    provider_root.mkdir(mode=0o700)
    retained = provider_root / metadata.MODEL_METADATA_RECEIPT_FILENAME
    expected_sha256 = metadata.copy_model_metadata_receipt(receipt, retained)
    lambda_transport = FakeLambdaTransport(received_at=base + 100.6)
    recorder = provider.RequestRecorder(
        provider_root,
        lambda_transport,
        bytearray(b"fixture-lambda-credential"),
        clock=lambda: base + 101.0,
    )
    prepared = recorder.prepare(
        "launch",
        "POST",
        "/api/v1/instance-operations/launch",
        body={"fixture": True},
    )
    boundary = base + 100.5
    recorder.send_prepared(
        prepared,
        final_admission=_final_admission(
            receipt=retained,
            overlay=overlay,
            plan_sha256=plan_sha256,
            expected_sha256=expected_sha256,
            boundary=lambda: boundary,
        ),
    )

    host = _load_host()
    monkeypatch.setattr(
        host,
        "model_metadata_preflight",
        lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("offline host attempted metadata fallback")
        ),
    )
    artifact_root = tmp_path / "host-artifacts"
    (artifact_root / "pilot-v12").mkdir(mode=0o700, parents=True)
    acknowledgement = host.validate_model_metadata_receipt_offline(
        contract=V12_PROVIDER_CONTRACT,
        receipt_path=retained,
        repository=ROOT,
        package_commit=BASE_COMMIT,
        provider_entry={
            "model_metadata_receipt_sha256": expected_sha256,
            "authorization_reference": "AUTH-T09-V12-CATEGORY3-FIXTURE-0001",
            "authorization_source_sha256": "1" * 64,
            "provider_preflight_started_at_epoch": boundary,
        },
        artifact_root=artifact_root,
    )
    assert len(metadata_transport.calls) == 1
    assert lambda_transport.calls == [("POST", "/api/v1/instance-operations/launch")]
    assert default_transport_constructions == 0
    assert acknowledgement["provider_launch_model_metadata_request_count"] == 0
    assert acknowledgement["host_runtime_model_metadata_request_count"] == 0
    assert acknowledgement["openai_transport_used"] is False


def _normalized_pair_diffs(path: Path) -> list[dict[str, object]]:
    document = json.loads(path.read_text())
    result: list[dict[str, object]] = []
    for raw in cast(list[dict[str, object]], document["pair_diffs"]):
        item = dict(raw)
        item["pair_id"] = str(item["pair_id"]).replace("V11", "VERSION").replace("V12", "VERSION")
        result.append(item)
    return result


def test_frozen_science_flags_pair_diffs_and_v11_evidence_are_unchanged() -> None:
    v11_plan = EXPERIMENT / "run-plans/proposals/PLAN-EXP0001-PILOT-V11.yaml"
    assert len(v11_plan.read_bytes()) == V11_PLAN_BYTES
    assert _sha256(v11_plan) == V11_PLAN_SHA256

    plan = yaml.safe_load(V12_PLAN.read_text())
    assert isinstance(plan, dict)
    status = cast(Mapping[str, object], plan["status"])
    for name in (
        "authorized",
        "execution_allowed",
        "cloud_mutation_allowed",
        "paid_compute_allowed",
        "live_qualification_performed",
        "pilot_executed",
    ):
        assert status[name] is False
    identities = cast(Mapping[str, object], plan["identities"])
    assert identities["empirical_run_roots_materialized"] is False
    science = cast(Mapping[str, object], plan["scientific_contract"])
    assert science["sira_commit"] == "93fb8d72de71f9a4a13419670adeb34d93cf7acd"
    assert science["model_revision_for_every_role"] == "gpt-4o-2024-11-20"
    assert science["condition_retries_after_empirical_entry"] == 0

    lifecycle = cast(
        Mapping[str, object],
        yaml.safe_load(PROFILE.read_text())["provider_lifecycle"],
    )
    assert lifecycle["model_metadata_request_count_total"] == 1
    assert lifecycle["provider_launch_model_metadata_request_count"] == 0
    assert lifecycle["host_runtime_model_metadata_request_count"] == 0
    assert lifecycle["model_metadata_freshness_owner"] == ("provider-final-transport-boundary")
    assert lifecycle["provider_launch_requires_current_freshness"] is True
    assert lifecycle["host_runtime_requires_current_freshness"] is False
    assert lifecycle["model_metadata_receipt_replay_allowed"] is False

    dotenv_input = cast(
        Mapping[str, object],
        cast(Mapping[str, object], plan["implementation_bindings"])["model_metadata_receipt"],
    )["dotenv_input"]
    assert dotenv_input == {
        "source": "existing-qualified-repository-external-file",
        "parent_policy": "current-user-owned-directory-not-group-or-world-writable",
        "file_type": "regular",
        "current_user_owner_required": True,
        "single_link_required": True,
        "no_follow_required": True,
        "eligible_mode_policy": "no-group-or-world-write-bits",
        "regression_covered_modes": ["0600", "0644"],
        "required_assignment": "OPENAI_API_KEY",
        "optional_assignment": "LAMBDA_API_KEY",
        "unknown_assignments_allowed": False,
        "selected_assignment": "OPENAI_API_KEY",
        "source_mutation_allowed": False,
    }

    proposal_root = EXPERIMENT / "contracts/proposals"
    assert _normalized_pair_diffs(
        proposal_root / "T09_PILOT_COMMAND_MANIFESTS_V11.json"
    ) == _normalized_pair_diffs(proposal_root / "T09_PILOT_COMMAND_MANIFESTS_V12.json")
    assert all(
        item["valid"] is True
        for item in _normalized_pair_diffs(proposal_root / "T09_PILOT_COMMAND_MANIFESTS_V12.json")
    )
    assert not (ROOT / "artifacts/EXP-0001/pilot-v12").exists()


def test_receipt_schema_accepts_exact_document_and_has_no_extensions(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    receipt, _overlay, _transport, _plan_sha256 = _create_receipt(monkeypatch, tmp_path)
    schema = json.loads((ROOT / "schemas/t09-model-metadata-receipt.schema.json").read_text())
    Draft202012Validator(schema).validate(json.loads(receipt.read_text()))
    assert schema["additionalProperties"] is False
