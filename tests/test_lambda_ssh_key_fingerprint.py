from __future__ import annotations

import base64
import hashlib
import json
import shutil
import stat
from datetime import UTC, datetime
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from giclab.harness.lambda_request_ledger_v3 import LedgerEventType
from giclab.harness.lambda_ssh_key_fingerprint import (
    API_HOST,
    LEDGER_SCHEMA_RELATIVE_PATH,
    MAX_LEDGER_BYTES,
    MAX_LEDGER_EVENT_BYTES,
    MAX_LEDGER_EVENTS,
    MAX_LEDGER_EVENTS_PER_REQUEST,
    MAX_PREFLIGHT_DISPOSITION_BYTES,
    MAX_RESPONSE_BYTES,
    PLAN_ID,
    PLAN_RELATIVE_PATH,
    RUN_ID,
    SSH_KEYS_PATH,
    LedgerLimits,
    PublicKeyFormat,
    SSHKeyFingerprintError,
    SSHKeyFingerprintPlan,
    SSHKeyRequest,
    SSHKeyRunBinding,
    load_ssh_key_fingerprint_plan,
    parse_public_key,
    project_account_ssh_keys,
)
from giclab.harness.lambda_ssh_key_request_ledger import (
    FsyncSSHKeyRequestLedger,
    SSHKeyRequestContext,
    SSHKeyRequestLedgerError,
)
from giclab.registry import load_json
from giclab.validation import ROOT

ACCOUNT_NAMES = (
    "aic-codex-lambda",
    "codex-fawx-20260527",
    "fractal-lambda-codex",
)


def _ssh_string(value: bytes) -> bytes:
    return len(value).to_bytes(4, "big") + value


def _ed25519_wire(seed: int) -> bytes:
    key = bytes((seed + index) % 256 for index in range(32))
    return _ssh_string(b"ssh-ed25519") + _ssh_string(key)


def _rsa_wire(modulus: int = 0xD5A1B2C3D4E5F607, exponent: int = 65537) -> bytes:
    def mpint(value: int) -> bytes:
        encoded = value.to_bytes((value.bit_length() + 7) // 8, "big")
        return b"\x00" + encoded if encoded[0] & 0x80 else encoded

    return _ssh_string(b"ssh-rsa") + _ssh_string(mpint(exponent)) + _ssh_string(mpint(modulus))


def _openssh(wire: bytes, algorithm: str, comment: str = "fixture") -> str:
    return f"{algorithm} {base64.b64encode(wire).decode()} {comment}"


def _der(tag: int, payload: bytes) -> bytes:
    if len(payload) < 128:
        length = bytes([len(payload)])
    else:
        encoded = len(payload).to_bytes((len(payload).bit_length() + 7) // 8, "big")
        length = bytes([0x80 | len(encoded)]) + encoded
    return bytes([tag]) + length + payload


def _der_integer(value: int) -> bytes:
    encoded = value.to_bytes((value.bit_length() + 7) // 8, "big")
    if encoded[0] & 0x80:
        encoded = b"\x00" + encoded
    return _der(0x02, encoded)


def _rsa_pkcs1(modulus: int = 0xD5A1B2C3D4E5F607, exponent: int = 65537) -> bytes:
    return _der(0x30, _der_integer(modulus) + _der_integer(exponent))


def _pem(label: str, der: bytes) -> str:
    payload = base64.b64encode(der).decode()
    lines = [payload[index : index + 64] for index in range(0, len(payload), 64)]
    return f"-----BEGIN {label}-----\n" + "\n".join(lines) + f"\n-----END {label}-----\n"


def _rsa_spki() -> bytes:
    rsa_oid = _der(0x06, bytes.fromhex("2a864886f70d010101"))
    algorithm = _der(0x30, rsa_oid + _der(0x05, b""))
    return _der(0x30, algorithm + _der(0x03, b"\x00" + _rsa_pkcs1()))


def _account_response(
    keys: tuple[str, str, str],
    *,
    extra_rows: list[dict[str, object]] | None = None,
) -> bytes:
    rows: list[dict[str, object]] = [
        {"id": f"raw-id-{index}", "name": name, "public_key": key}
        for index, (name, key) in enumerate(zip(ACCOUNT_NAMES, keys, strict=True), start=1)
    ]
    if extra_rows:
        rows.extend(extra_rows)
    return json.dumps({"data": rows}, sort_keys=True, separators=(",", ":")).encode()


def test_valid_openssh_ed25519_agrees_with_fixed_standard_vector() -> None:
    public_key = (
        "ssh-ed25519 "
        "AAAAC3NzaC1lZDI1NTE5AAAAIAABAgMEBQYHCAkKCwwNDg8QERITFBUWFxgZGhscHR4f "
        "fixed-vector"
    )
    parsed = parse_public_key(public_key)
    assert parsed.algorithm == "ssh-ed25519"
    assert parsed.source_format is PublicKeyFormat.OPENSSH
    assert parsed.fingerprint == "SHA256:ZkAslGjFiUHdGf/WUL8rQvkib4PTvQatUV0OUQSncCA"


def test_valid_openssh_rsa() -> None:
    wire = _rsa_wire()
    parsed = parse_public_key(_openssh(wire, "ssh-rsa"))
    assert parsed.algorithm == "ssh-rsa"
    assert parsed.wire_blob == wire
    assert parsed.fingerprint == (
        "SHA256:" + base64.b64encode(hashlib.sha256(wire).digest()).decode().rstrip("=")
    )


def test_valid_rfc4716() -> None:
    wire = _ed25519_wire(11)
    encoded = base64.b64encode(wire).decode()
    value = (
        "---- BEGIN SSH2 PUBLIC KEY ----\n"
        'Comment: "synthetic public fixture"\n'
        f"{encoded[:32]}\n{encoded[32:]}\n"
        "---- END SSH2 PUBLIC KEY ----\n"
    )
    parsed = parse_public_key(value)
    assert parsed.source_format is PublicKeyFormat.RFC4716
    assert parsed.wire_blob == wire


def test_valid_pkcs8_spki_public_key() -> None:
    parsed = parse_public_key(_pem("PUBLIC KEY", _rsa_spki()))
    assert parsed.source_format is PublicKeyFormat.PKCS8_PUBLIC
    assert parsed.algorithm == "ssh-rsa"
    assert parsed.wire_blob == _rsa_wire()


def test_valid_pem_rsa_public_key() -> None:
    parsed = parse_public_key(_pem("RSA PUBLIC KEY", _rsa_pkcs1()))
    assert parsed.source_format is PublicKeyFormat.PEM_RSA_PUBLIC
    assert parsed.algorithm == "ssh-rsa"
    assert parsed.wire_blob == _rsa_wire()


@pytest.mark.parametrize(
    "value",
    [
        "ssh-ed25519 !!!not-base64!!!",
        _openssh(_ssh_string(b"ecdsa-sha2-nistp256") + _ssh_string(b"bad"), "ssh-rsa"),
        "-----BEGIN PRIVATE KEY-----\nAA==\n-----END PRIVATE KEY-----",
        "-----BEGIN RSA PRIVATE KEY-----\nAA==\n-----END RSA PRIVATE KEY-----",
        _openssh(_ed25519_wire(1), "ssh-ed25519")
        + "\n"
        + _openssh(_ed25519_wire(2), "ssh-ed25519"),
        "---- BEGIN SSH2 PUBLIC KEY ----\nComment: incomplete\\\n---- END SSH2 PUBLIC KEY ----",
    ],
)
def test_malformed_unsupported_private_and_multikey_inputs_fail(value: str) -> None:
    with pytest.raises(SSHKeyFingerprintError):
        parse_public_key(value)


def test_account_projection_collapses_only_exact_repeated_rows() -> None:
    keys = tuple(_openssh(_ed25519_wire(seed), "ssh-ed25519") for seed in (1, 2, 3))
    duplicate = {"id": "raw-id-1", "name": ACCOUNT_NAMES[0], "public_key": keys[0]}
    projection = project_account_ssh_keys(_account_response(keys, extra_rows=[duplicate]))
    assert len(projection.records) == 3
    assert projection.records[0].multiplicity == 2
    assert [item.account_alias for item in projection.records] == [
        "account-key-0001",
        "account-key-0002",
        "account-key-0003",
    ]


def test_account_projection_records_only_additive_key_names() -> None:
    keys = tuple(_openssh(_ed25519_wire(seed), "ssh-ed25519") for seed in (1, 2, 3))
    document = json.loads(_account_response(keys))
    document["data"][0]["provider_extension"] = "SENSITIVE-SCALAR-CANARY"
    encoded = json.dumps(document, separators=(",", ":")).encode()
    projection = project_account_ssh_keys(encoded)
    manifest = json.dumps(projection.private_manifest_document(), sort_keys=True)
    assert projection.compatible_extension_key_names == ("provider_extension",)
    assert "provider_extension" in manifest
    assert "SENSITIVE-SCALAR-CANARY" not in manifest


def test_duplicate_name_with_different_material_fails() -> None:
    keys = tuple(_openssh(_ed25519_wire(seed), "ssh-ed25519") for seed in (1, 2, 3))
    conflicting = {
        "id": "raw-id-4",
        "name": ACCOUNT_NAMES[0],
        "public_key": _openssh(_ed25519_wire(99), "ssh-ed25519"),
    }
    with pytest.raises(SSHKeyFingerprintError, match="duplicate SSH-key name"):
        project_account_ssh_keys(_account_response(keys, extra_rows=[conflicting]))


@pytest.mark.parametrize(
    "mutator",
    [
        lambda document: document.update({"page_token": None}),
        lambda document: document["data"][0].pop("public_key"),
        lambda document: document["data"][0].update({"public_key": 3}),
        lambda document: document["data"][0].update({"name": "unapproved-new-key"}),
    ],
)
def test_response_schema_pagination_type_and_candidate_drift_fail(mutator: object) -> None:
    keys = tuple(_openssh(_ed25519_wire(seed), "ssh-ed25519") for seed in (1, 2, 3))
    document = json.loads(_account_response(keys))
    assert callable(mutator)
    mutator(document)
    with pytest.raises(SSHKeyFingerprintError):
        project_account_ssh_keys(json.dumps(document).encode())


def test_response_byte_cap_is_exact() -> None:
    with pytest.raises(SSHKeyFingerprintError):
        project_account_ssh_keys(b"{" + b" " * MAX_RESPONSE_BYTES)


def test_new_evidence_schemas_are_well_formed() -> None:
    for relative in (
        "schemas/t07-lambda-ssh-key-fingerprint.schema.json",
        "schemas/t07-local-public-key-match.schema.json",
        "schemas/t07-lambda-ssh-key-request-ledger.schema.json",
        "containers/sira-smoke/lambda/endpoint-schemas-l1a/ssh-keys.schema.json",
    ):
        Draft202012Validator.check_schema(load_json(ROOT / relative))


def test_one_request_plan_is_exact_when_committed() -> None:
    path = ROOT / PLAN_RELATIVE_PATH
    if not path.exists():
        pytest.skip("plan is generated after the reviewed implementation commit")
    encoded = path.read_bytes()
    plan = load_ssh_key_fingerprint_plan(
        ROOT,
        path,
        expected_sha256=hashlib.sha256(encoded).hexdigest(),
    )
    assert plan.plan_id == PLAN_ID
    assert plan.run_id == RUN_ID
    assert plan.max_calls == 1
    assert len(plan.requests) == 1
    assert plan.requests[0].path == SSH_KEYS_PATH
    assert plan.requests[0].method.value == "GET"
    assert plan.document["api_base_url"] == f"https://{API_HOST}"
    assert plan.document["authorization"]["authorized"] is False


def test_module_has_no_account_transport_or_shell_http_primitive() -> None:
    source = (ROOT / "src/giclab/harness/lambda_ssh_key_fingerprint.py").read_text()
    for forbidden in (
        "urllib.request",
        "http.client",
        "requests.",
        "subprocess",
        "curl",
        "wget",
    ):
        assert forbidden not in source


def _synthetic_ledger_plan(repository: Path) -> SSHKeyFingerprintPlan:
    schema_source = ROOT / LEDGER_SCHEMA_RELATIVE_PATH
    schema_target = repository / LEDGER_SCHEMA_RELATIVE_PATH
    schema_target.parent.mkdir(parents=True)
    shutil.copyfile(schema_source, schema_target)
    digest = hashlib.sha256(schema_target.read_bytes()).hexdigest()
    return SSHKeyFingerprintPlan(
        implementation_commit="1" * 40,
        implementation_artifacts=(),
        plan_sha256="2" * 64,
        ledger_schema_sha256=digest,
        response_schema_sha256="3" * 64,
        fingerprint_schema_sha256="4" * 64,
        match_schema_sha256="5" * 64,
        limits=LedgerLimits(
            MAX_LEDGER_BYTES,
            MAX_LEDGER_EVENTS,
            MAX_LEDGER_EVENTS_PER_REQUEST,
            MAX_LEDGER_EVENT_BYTES,
            MAX_PREFLIGHT_DISPOSITION_BYTES,
        ),
        requests=(SSHKeyRequest(),),
        document={},
    )


def _synthetic_run_binding() -> SSHKeyRunBinding:
    return SSHKeyRunBinding(
        repository_commit="6" * 40,
        implementation_commit="1" * 40,
        authorization_reference="AUTH-T07-L1A-UNIT-TEST",
        authorization_sha256="7" * 64,
    )


def test_fresh_one_request_ledger_success_path_is_fsynced_and_nonreusable(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    plan = _synthetic_ledger_plan(repository)
    ticks = iter(range(1, 100))
    ledger = FsyncSSHKeyRequestLedger.create(
        repository,
        plan=plan,
        run_binding=_synthetic_run_binding(),
        monotonic_ns=lambda: next(ticks),
        utc_now=lambda: datetime(2026, 8, 10, 16, 0, tzinfo=UTC),
    )
    ledger.reserve_capacity()
    context = SSHKeyRequestContext()
    ledger.append(LedgerEventType.RUN_PREFLIGHT_STARTED)
    ledger.append(LedgerEventType.SECRET_PRESENCE_CHECK_PASSED)
    ledger.append(LedgerEventType.RUN_PREFLIGHT_PASSED)
    ledger.append(LedgerEventType.REQUEST_INTENT_COMMITTED, request=context)
    ledger.append(LedgerEventType.REQUEST_SEND_STARTED, request=context)
    ledger.append(
        LedgerEventType.RESPONSE_HEADERS_RECEIVED,
        request=context,
        http_status=200,
        content_type="application/json",
        elapsed_ms=5,
    )
    ledger.append(
        LedgerEventType.RESPONSE_BODY_PROGRESS,
        request=context,
        bytes_received=128,
        http_status=200,
        content_type="application/json",
        elapsed_ms=6,
    )
    ledger.append(
        LedgerEventType.RESPONSE_BODY_COMPLETED,
        request=context,
        bytes_received=256,
        http_status=200,
        content_type="application/json",
        elapsed_ms=7,
    )
    ledger.append(
        LedgerEventType.RESPONSE_VALIDATION_PASSED,
        request=context,
        bytes_received=256,
        http_status=200,
        content_type="application/json",
        elapsed_ms=8,
    )
    ledger.append(LedgerEventType.INVENTORY_VALIDATION_STARTED)
    ledger.append(LedgerEventType.INVENTORY_VALIDATION_PASSED)
    ledger.append(LedgerEventType.ARCHIVE_STARTED)
    ledger.append(LedgerEventType.ARCHIVE_PASSED)
    ledger.append(LedgerEventType.RUN_STOPPED)
    snapshot = ledger.seal(require_success=True)
    assert snapshot.events == 14
    assert snapshot.bytes <= MAX_LEDGER_BYTES
    assert stat.S_IMODE(snapshot.path.stat().st_mode) == 0o400
    with pytest.raises(SSHKeyRequestLedgerError):
        FsyncSSHKeyRequestLedger.create(
            repository,
            plan=plan,
            run_binding=_synthetic_run_binding(),
        )


def test_one_request_ledger_rejects_send_before_intent(tmp_path: Path) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    plan = _synthetic_ledger_plan(repository)
    ledger = FsyncSSHKeyRequestLedger.create(
        repository,
        plan=plan,
        run_binding=_synthetic_run_binding(),
    )
    ledger.reserve_capacity()
    ledger.append(LedgerEventType.RUN_PREFLIGHT_STARTED)
    ledger.append(LedgerEventType.SECRET_PRESENCE_CHECK_PASSED)
    ledger.append(LedgerEventType.RUN_PREFLIGHT_PASSED)
    with pytest.raises(SSHKeyRequestLedgerError):
        ledger.append(
            LedgerEventType.REQUEST_SEND_STARTED,
            request=SSHKeyRequestContext(),
        )
    ledger.close_preserving_incomplete()
