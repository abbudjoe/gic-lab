from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import stat
import time
from pathlib import Path
from types import ModuleType

import pytest
import yaml
from jsonschema import Draft202012Validator

from giclab.harness import t09_model_metadata_receipt as metadata
from giclab.harness import t09_pragmatic_provider as provider
from giclab.harness.t09_provider_contracts import V12_PROVIDER_CONTRACT

ROOT = Path(__file__).resolve().parents[1]
EXP = ROOT / "experiments/EXP-0001-sira-simulative-vs-reactive"
BASE_COMMIT = "42a8ce6945c29f4221e03bb836f18421e50f3b1e"
BASE_TREE = "4271fccaf870cfd6a7963ac43daba5b616a0104a"
V11_PLAN_BYTES = 14_754
V11_PLAN_SHA256 = "34a405d06521bd3fb55379721dff9c5795954fcb099d641587e2169b37575411"
HOST_SOURCE = ROOT / "containers/sira-smoke/pragmatic/t09_remote_runner.py"


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
    ).encode("utf-8")


def _private_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_canonical(value))
    path.chmod(0o600)


def _private_text(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(value)
    path.chmod(0o600)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class _Clock:
    def __init__(self, *values: float) -> None:
        self._values = iter(values)

    def __call__(self) -> float:
        return next(self._values)


class _FakeMetadataTransport:
    def __init__(self, response_id: str = metadata.MODEL_METADATA_MODEL_ID) -> None:
        self.calls: list[tuple[str, bytes]] = []
        self.response_id = response_id
        self.response_completed_at = 0.0

    def get_model_metadata(
        self,
        model_id: str,
        *,
        credential: bytearray,
    ) -> metadata.ModelMetadataResponse:
        self.calls.append((model_id, bytes(credential)))
        body = _canonical({"id": self.response_id})
        return metadata.ModelMetadataResponse(
            status=200,
            body=body,
            response_completed_at=self.response_completed_at,
        )


class _FakeProviderTransport:
    def __init__(self) -> None:
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
        raise AssertionError("provider transport must not be reached by a failed receipt gate")


def _authorization_fixture(tmp_path: Path) -> tuple[Path, Path, str]:
    profile = EXP / "run-plans/proposals/T09_PILOT_RUNTIME_PROFILE_V12.yaml"
    plan_sha256 = _sha256(profile)
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
    dotenv = tmp_path / "openai-fixture.env"
    _private_text(dotenv, b"OPENAI_API_KEY=fixture-openai-key-123456\n")
    return overlay, dotenv, plan_sha256


def _run_local_preflight(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    response_id: str = metadata.MODEL_METADATA_MODEL_ID,
) -> tuple[Path, Path, _FakeMetadataTransport, float, str]:
    overlay, dotenv, plan_sha256 = _authorization_fixture(tmp_path)
    transport = _FakeMetadataTransport(response_id)
    base = time.time()
    transport.response_completed_at = base - 0.5
    monkeypatch.setattr(provider, "_verify_clean_package", lambda repository, package: None)
    output = tmp_path / "model-metadata-receipt.json"
    provider.model_metadata_preflight(
        contract=V12_PROVIDER_CONTRACT,
        repository=ROOT,
        package_commit=BASE_COMMIT,
        authorization_overlay=overlay,
        openai_dotenv=dotenv,
        output=output,
        transport=transport,
        clock=_Clock(base - 1.0, base),
    )
    return output, overlay, transport, base, plan_sha256


def _provider_validate(
    receipt_path: Path,
    overlay: Path,
    *,
    launch_started_at: float | None = None,
) -> dict[str, object]:
    return provider._validate_model_metadata_receipt_for_provider(
        receipt_path,
        contract=V12_PROVIDER_CONTRACT,
        repository=ROOT,
        package_commit=BASE_COMMIT,
        plan_sha256=_sha256(EXP / "run-plans/proposals/T09_PILOT_RUNTIME_PROFILE_V12.yaml"),
        authorization_ledger=overlay,
        launch_started_at=time.time() + 10.0 if launch_started_at is None else launch_started_at,
    )


def _load_host() -> ModuleType:
    specification = importlib.util.spec_from_file_location("giclab_t09_v12_host", HOST_SOURCE)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def test_v12_metadata_cli_has_no_lambda_authority_arguments() -> None:
    args = provider.parser().parse_args(
        [
            "--provider-contract",
            "V12",
            "--repository",
            str(ROOT),
            "--package-commit",
            BASE_COMMIT,
            "model-metadata-preflight",
            "--openai-dotenv",
            "/private/openai.env",
            "--authorization-overlay",
            "/private/authorization-overlay.json",
            "--output",
            "/private/model-metadata-receipt.json",
        ]
    )
    assert args.authorization_ledger is None
    assert args.dotenv is None
    assert args.private_root is None
    assert args.operation == "model-metadata-preflight"


def test_local_preflight_emits_one_exact_metadata_get_and_no_lambda_calls(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    output, _overlay, transport, _base, _plan_sha256 = _run_local_preflight(monkeypatch, tmp_path)
    assert len(transport.calls) == 1
    assert transport.calls[0][0] == "gpt-4o-2024-11-20"
    assert transport.calls[0][1] == b"fixture-openai-key-123456"
    assert not any(path.name == "lambda" for path in tmp_path.iterdir())
    assert stat.S_IMODE(output.stat().st_mode) == 0o600
    assert output.stat().st_nlink == 1
    assert output.stat().st_uid == os.getuid()


def test_local_preflight_accepts_only_exact_returned_model_identity(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    overlay, dotenv, _plan_sha256 = _authorization_fixture(tmp_path)
    transport = _FakeMetadataTransport("gpt-4o-other")
    base = time.time()
    transport.response_completed_at = base + 0.5
    monkeypatch.setattr(provider, "_verify_clean_package", lambda repository, package: None)
    with pytest.raises(provider.T09ProviderError, match="receipt was not sealed"):
        provider.model_metadata_preflight(
            contract=V12_PROVIDER_CONTRACT,
            repository=ROOT,
            package_commit=BASE_COMMIT,
            authorization_overlay=overlay,
            openai_dotenv=dotenv,
            output=tmp_path / "wrong-model.json",
            transport=transport,
            clock=_Clock(base, base + 1.0),
        )
    assert len(transport.calls) == 1


def test_failed_model_gate_makes_zero_lambda_launch_posts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    overlay, _dotenv, _plan_sha256 = _authorization_fixture(tmp_path)
    transport = _FakeProviderTransport()
    monkeypatch.setattr(provider, "_assert_launch_capability_unused", lambda path: None)
    monkeypatch.setattr(provider, "_verify_clean_package", lambda repository, package: None)
    monkeypatch.setattr(
        provider,
        "validate_authorization_ledger",
        lambda *args, **kwargs: {
            **json.loads(overlay.read_text()),
            "authorization_ledger_sha256": _sha256(overlay),
        },
    )
    monkeypatch.setattr(provider, "load_campaign_lifecycle", lambda *args, **kwargs: object())
    with pytest.raises(provider.T09ProviderError, match="requires the model metadata receipt"):
        provider.launch_campaign(
            contract=V12_PROVIDER_CONTRACT,
            repository=ROOT,
            package_commit=BASE_COMMIT,
            authorization_ledger=overlay,
            dotenv=tmp_path / "lambda.env",
            private_root=tmp_path / "private-root",
            public_ipv4_file=tmp_path / "ipv4",
            ssh_public_key_file=tmp_path / "ssh.pub",
            transport=transport,
        )
    assert transport.calls == []
    assert not (tmp_path / "private-root").exists()


def test_provider_accepts_valid_bound_receipt_and_makes_no_openai_call(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    output, overlay, transport, _base, _plan_sha256 = _run_local_preflight(monkeypatch, tmp_path)
    monkeypatch.setattr(
        metadata,
        "OpenAIModelMetadataTransport",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("provider must not call OpenAI")),
    )
    validated = _provider_validate(output, overlay)
    assert validated["authorization_reference"] == "AUTH-T09-V12-CATEGORY3-FIXTURE-0001"
    assert validated["request_count"] == 1
    assert len(transport.calls) == 1


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("plan_sha256", "a" * 64),
        ("repository_commit", "b" * 40),
        ("repository_tree", "c" * 40),
        ("authorization_reference", "AUTH-T09-V12-WRONG"),
        ("host_run_id", "RUN-T09-PILOT-HOST-AUTONOMOUS-WRONG"),
        ("requested_model_id", "gpt-4o-other"),
        ("returned_model_id", "gpt-4o-other"),
        ("model_endpoint", "https://api.openai.com/v1/models/gpt-4o-other"),
    ),
)
def test_provider_rejects_wrong_receipt_binding(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    field: str,
    value: object,
) -> None:
    output, overlay, _transport, _base, _plan_sha256 = _run_local_preflight(monkeypatch, tmp_path)
    document = json.loads(output.read_text())
    document[field] = value
    _private_json(output, document)
    with pytest.raises(metadata.ModelMetadataReceiptError):
        _provider_validate(output, overlay)


def test_provider_rejects_v11_receipt_and_receipt_created_after_launch(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    output, overlay, _transport, base, _plan_sha256 = _run_local_preflight(monkeypatch, tmp_path)
    v11 = json.loads(output.read_text())
    v11["provider_contract_version"] = "V11"
    _private_json(output, v11)
    with pytest.raises(metadata.ModelMetadataReceiptError):
        _provider_validate(output, overlay)

    output, overlay, _transport, base, _plan_sha256 = _run_local_preflight(
        monkeypatch, tmp_path / "late"
    )
    with pytest.raises(metadata.ModelMetadataReceiptError, match="created after"):
        _provider_validate(output, overlay, launch_started_at=base - 0.25)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("request_count", 0),
        ("redirect_count", 1),
        ("retry_count", 1),
        ("pagination_count", 1),
    ),
)
def test_receipt_request_counts_are_exactly_one_zero_zero_zero(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    field: str,
    value: int,
) -> None:
    output, overlay, _transport, _base, _plan_sha256 = _run_local_preflight(monkeypatch, tmp_path)
    document = json.loads(output.read_text())
    document[field] = value
    _private_json(output, document)
    with pytest.raises(metadata.ModelMetadataReceiptError):
        _provider_validate(output, overlay)


def test_receipt_replay_and_output_reuse_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    output, overlay, transport, _base, _plan_sha256 = _run_local_preflight(monkeypatch, tmp_path)
    with pytest.raises(provider.T09ProviderError, match="receipt was not sealed"):
        provider.model_metadata_preflight(
            contract=V12_PROVIDER_CONTRACT,
            repository=ROOT,
            package_commit=BASE_COMMIT,
            authorization_overlay=overlay,
            openai_dotenv=tmp_path / "openai-fixture.env",
            output=tmp_path / "second-receipt.json",
            transport=transport,
            clock=_Clock(time.time(), time.time() + 1.0),
        )
    assert len(transport.calls) == 1
    with pytest.raises(provider.T09ProviderError, match="receipt was not sealed"):
        metadata.model_metadata_receipt_sha256(output)
        provider.model_metadata_preflight(
            contract=V12_PROVIDER_CONTRACT,
            repository=ROOT,
            package_commit=BASE_COMMIT,
            authorization_overlay=overlay,
            openai_dotenv=tmp_path / "openai-fixture.env",
            output=output,
            transport=transport,
            clock=_Clock(time.time(), time.time() + 1.0),
        )


def test_strict_dotenv_accepts_only_openai_assignment(
    tmp_path: Path,
) -> None:
    dotenv = tmp_path / "bad.env"
    _private_text(dotenv, b"OPENAI_API_KEY=fixture-openai-key-123456\nOTHER=value\n")
    with pytest.raises(metadata.ModelMetadataReceiptError):
        metadata.load_openai_dotenv_assignment(dotenv)


def test_receipt_schema_has_no_secret_or_header_material(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    output, _overlay, _transport, _base, _plan_sha256 = _run_local_preflight(monkeypatch, tmp_path)
    raw = output.read_bytes()
    assert b"fixture-openai-key" not in raw
    assert b"authorization_header" not in raw
    assert b"api_key" not in raw
    assert b"account_identifier" not in raw
    document = json.loads(raw)
    document["api_key"] = "fixture-openai-key-123456"
    _private_json(output, document)
    with pytest.raises(metadata.ModelMetadataReceiptError):
        _provider_validate(output, _authorization_fixture(tmp_path / "other")[0])


def test_receipt_path_security_and_malformed_json_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    output, overlay, _transport, _base, _plan_sha256 = _run_local_preflight(monkeypatch, tmp_path)
    symlink = tmp_path / "receipt-symlink.json"
    symlink.symlink_to(output)
    with pytest.raises(metadata.ModelMetadataReceiptError):
        _provider_validate(symlink, overlay)

    hardlink = tmp_path / "receipt-hardlink.json"
    os.link(output, hardlink)
    with pytest.raises(metadata.ModelMetadataReceiptError):
        _provider_validate(hardlink, overlay)

    output.chmod(0o640)
    with pytest.raises(metadata.ModelMetadataReceiptError):
        _provider_validate(output, overlay)
    output.chmod(0o600)

    malformed = tmp_path / "malformed.json"
    _private_text(malformed, b"{")
    with pytest.raises(metadata.ModelMetadataReceiptError):
        _provider_validate(malformed, overlay)

    actual_uid = os.getuid()
    monkeypatch.setattr(metadata.os, "getuid", lambda: actual_uid + 1)
    with pytest.raises(metadata.ModelMetadataReceiptError):
        _provider_validate(output, overlay)


def test_replaced_receipt_fails_before_host_manifest_publication(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    output, _overlay, _transport, _base, _plan_sha256 = _run_local_preflight(monkeypatch, tmp_path)
    document = json.loads(output.read_text())
    document["returned_model_id"] = "gpt-4o-other"
    _private_json(output, document)
    artifact_root = tmp_path / "artifacts"
    (artifact_root / "pilot-v12").mkdir(parents=True, mode=0o700)
    host = _load_host()
    with pytest.raises(host.T09HostError):
        host.validate_model_metadata_receipt_offline(
            receipt_path=output,
            repository=ROOT,
            package_commit=BASE_COMMIT,
            provider_entry={
                "model_metadata_receipt_sha256": "4" * 64,
                "authorization_reference": "AUTH-T09-V12-CATEGORY3-FIXTURE-0001",
                "authorization_source_sha256": "1" * 64,
                "provider_preflight_started_at_epoch": time.time() + 10,
            },
            artifact_root=artifact_root,
        )
    assert not (artifact_root / "pilot-v7/frozen-run-manifest.json").exists()


def test_host_accepts_bound_receipt_with_openai_transport_disabled(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    output, _overlay, transport, _base, _plan_sha256 = _run_local_preflight(monkeypatch, tmp_path)
    host = _load_host()
    monkeypatch.setattr(
        host,
        "model_metadata_preflight",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("V12 fallback network path used")),
    )
    monkeypatch.setattr(
        metadata,
        "OpenAIModelMetadataTransport",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("OpenAI transport constructed")),
    )
    artifact_root = tmp_path / "artifacts"
    (artifact_root / "pilot-v12").mkdir(parents=True, mode=0o700)
    acknowledgement = host.validate_model_metadata_receipt_offline(
        receipt_path=output,
        repository=ROOT,
        package_commit=BASE_COMMIT,
        provider_entry={
            "model_metadata_receipt_sha256": metadata.model_metadata_receipt_sha256(output),
            "authorization_reference": "AUTH-T09-V12-CATEGORY3-FIXTURE-0001",
            "authorization_source_sha256": "1" * 64,
            "provider_preflight_started_at_epoch": time.time() + 10,
        },
        artifact_root=artifact_root,
    )
    assert acknowledgement["model_metadata_network_requests"] == 0
    assert acknowledgement["provider_launch_model_metadata_request_count"] == 0
    assert acknowledgement["host_runtime_model_metadata_request_count"] == 0
    assert acknowledgement["openai_transport_used"] is False
    assert (artifact_root / "pilot-v12/model-metadata-receipt-acknowledgement.json").is_file()
    assert len(transport.calls) == 1


def test_v12_runtime_has_no_metadata_network_fallback() -> None:
    source = HOST_SOURCE.read_text(encoding="utf-8")
    preflight = source.split("def preflight(", 1)[1]
    gate_start = preflight.index("if dynamic_contract is V12_PROVIDER_CONTRACT:")
    gate = preflight[gate_start : preflight.index("    post_metadata_core_gate", gate_start)]
    v12_branch = gate.split("    else:", 1)[0]
    assert "validate_model_metadata_receipt_offline(" in v12_branch
    assert "model_metadata_preflight(" not in v12_branch


def test_v11_plan_and_scientific_contract_remain_immutable() -> None:
    v11_plan_path = EXP / "run-plans/proposals/PLAN-EXP0001-PILOT-V11.yaml"
    assert v11_plan_path.stat().st_size == V11_PLAN_BYTES
    assert _sha256(v11_plan_path) == V11_PLAN_SHA256
    v11 = yaml.safe_load(v11_plan_path.read_text())
    v12 = yaml.safe_load((EXP / "run-plans/proposals/PLAN-EXP0001-PILOT-V12.yaml").read_text())
    assert v12["scientific_contract"] == v11["scientific_contract"]
    assert v12["scientific_contract"]["sira_commit"] == ("93fb8d72de71f9a4a13419670adeb34d93cf7acd")
    assert v12["scientific_contract"]["model_revision_for_every_role"] == ("gpt-4o-2024-11-20")


def test_v12_pair_diffs_and_task_commands_remain_valid() -> None:
    commands = json.loads(
        (EXP / "contracts/proposals/T09_PILOT_COMMAND_MANIFESTS_V12.json").read_text()
    )
    pair_diffs = commands["pair_diffs"]
    assert len(pair_diffs) == 2
    assert all(pair["valid"] is True for pair in pair_diffs)
    assert commands["model_metadata_request_count_total"] == 1
    assert commands["provider_launch_model_metadata_request_count"] == 0
    assert commands["host_runtime_model_metadata_request_count"] == 0
    for attempt in commands["manifests"]:
        argv = attempt["argv"]
        assert argv[argv.index("--model") + 1] == "gpt-4o-2024-11-20"
        assert argv[argv.index("--max_retry") + 1] == "0"
    protocol_sha256 = _sha256(EXP / "protocol.yaml")
    config_sha256 = _sha256(EXP / "config.yaml")
    assert {
        item["protocol_sha256"]
        for item in json.loads(
            (EXP / "contracts/proposals/T09_PILOT_EXECUTION_CONTRACT_V12.json").read_text()
        )["attempts"]
    } == {protocol_sha256}
    assert {
        item["config_sha256"]
        for item in json.loads(
            (EXP / "contracts/proposals/T09_PILOT_EXECUTION_CONTRACT_V12.json").read_text()
        )["attempts"]
    } == {config_sha256}


def test_v12_unauthorized_flags_and_run_roots_are_frozen() -> None:
    plan_path = EXP / "run-plans/proposals/PLAN-EXP0001-PILOT-V12.yaml"
    plan = yaml.safe_load(plan_path.read_text())
    assert plan["status"] == {
        **plan["status"],
        "authorized": False,
        "execution_allowed": False,
        "cloud_mutation_allowed": False,
        "paid_compute_allowed": False,
        "live_qualification_performed": False,
        "pilot_executed": False,
    }
    assert plan["identities"]["empirical_run_roots_materialized"] is False
    assert all(
        attempt["output_root"] == "not-materialized-until-category-3"
        for attempt in plan["attempts"]
    )
    artifact_root = ROOT / "artifacts"
    assert not any("autonomous-0005" in str(path).lower() for path in artifact_root.rglob("*"))


def test_v12_schemas_validate_the_plan_execution_contract_and_receipt(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    plan_path = EXP / "run-plans/proposals/PLAN-EXP0001-PILOT-V12.yaml"
    plan = yaml.safe_load(plan_path.read_text())
    plan_schema = json.loads((ROOT / "schemas/t09-v12-plan.schema.json").read_text())
    Draft202012Validator(plan_schema).validate(plan)
    execution_path = EXP / "contracts/proposals/T09_PILOT_EXECUTION_CONTRACT_V12.json"
    execution = json.loads(execution_path.read_text())
    execution_schema = json.loads(
        (ROOT / "schemas/t09-sira-pilot-v12-execution.schema.json").read_text()
    )
    Draft202012Validator(execution_schema).validate(execution)
    output, _overlay, _transport, _base, _plan_sha256 = _run_local_preflight(monkeypatch, tmp_path)
    receipt_document = json.loads(output.read_text())
    receipt_schema = json.loads(
        (ROOT / "schemas/t09-model-metadata-receipt.schema.json").read_text()
    )
    Draft202012Validator(receipt_schema).validate(receipt_document)


def test_exact_gate_receipt_provider_host_integration_has_one_total_fake_openai_request(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    output, _overlay, transport, _base, _plan_sha256 = _run_local_preflight(monkeypatch, tmp_path)
    _provider_validate(output, _overlay)
    host = _load_host()
    artifact_root = tmp_path / "artifacts"
    (artifact_root / "pilot-v12").mkdir(parents=True, mode=0o700)
    acknowledgement = host.validate_model_metadata_receipt_offline(
        receipt_path=output,
        repository=ROOT,
        package_commit=BASE_COMMIT,
        provider_entry={
            "model_metadata_receipt_sha256": metadata.model_metadata_receipt_sha256(output),
            "authorization_reference": "AUTH-T09-V12-CATEGORY3-FIXTURE-0001",
            "authorization_source_sha256": "1" * 64,
            "provider_preflight_started_at_epoch": time.time() + 10,
        },
        artifact_root=artifact_root,
    )
    assert acknowledgement["receipt_request_count"] == 1
    assert acknowledgement["model_metadata_network_requests"] == 0
    assert len(transport.calls) == 1
