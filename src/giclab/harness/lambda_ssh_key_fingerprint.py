"""Offline contracts for the T07 Gate L1A SSH-key fingerprint recovery gate.

The module is deliberately transport-free.  It validates the one-response account
shape, parses supported public-key encodings in process, computes the standard
OpenSSH SHA-256 fingerprint over the SSH wire blob, and validates the immutable
future plan.  Importing or calling these helpers performs no network or secret I/O.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Final

from jsonschema import Draft202012Validator, FormatChecker

PLAN_ID: Final = "PLAN-T07-GATE-L1A-LAMBDA-SSH-KEY-FINGERPRINT-V1"
RUN_ID: Final = "RUN-T07-L1A-LAMBDA-SSH-KEY-FINGERPRINT-0001"
PENDING_AUTHORIZATION_REFERENCE: Final = "AUTH-T07-GATE-L1A-LAMBDA-SSH-KEY-FINGERPRINT-V1-PENDING"
PLAN_RELATIVE_PATH: Final = "containers/sira-smoke/lambda/gate-l1a-ssh-key-fingerprint-plan-v1.json"
API_BASE_URL: Final = "https://cloud.lambda.ai"
API_HOST: Final = "cloud.lambda.ai"
SSH_KEYS_PATH: Final = "/api/v1/ssh-keys"
API_SPEC_URL: Final = "https://docs.lambda.ai/api/cloud/spec.json"
API_SPEC_VERSION: Final = "1.10.0"
API_SPEC_BYTES: Final = 239_644
API_SPEC_SHA256: Final = "365488015cf79fda38e1268f44a9e2d4af4fe2794ad3c6878c78a7e1f98caded"
API_SPEC_RETRIEVED_AT_UTC: Final = "2026-08-10T15:59:37.767582Z"
EXECUTOR_IDENTITY: Final = (
    "giclab.harness.lambda_ssh_key_executor.execute_authorized_ssh_key_fingerprint"
)
ARCHIVER_IDENTITY: Final = "giclab.harness.lambda_ssh_key_archive.DurableSSHKeyArchiver"
ENTRYPOINT_MODULE: Final = "giclab.harness.lambda_ssh_key_executor"
EXECUTION_WORKING_DIRECTORY: Final = "/Users/joseph/.codex/worktrees/84b1/gic-lab"
EXECUTION_PYTHON: Final = f"{EXECUTION_WORKING_DIRECTORY}/.venv/bin/python"
EXECUTION_WRAPPER: Final = (
    f"{EXECUTION_WORKING_DIRECTORY}/containers/sira-smoke/lambda/run_gate_l1a.py"
)

BASELINE_COMMIT: Final = "ae0ec40cb2da067a66f1a8d3d0e5aca857fd9491"
MAX_RESPONSE_BYTES: Final = 131_072
MAX_PUBLIC_KEY_TEXT_BYTES: Final = 4_096
MAX_ACCOUNT_KEYS: Final = 128
APPROVED_ACCOUNT_KEY_NAMES: Final = (
    "aic-codex-lambda",
    "codex-fawx-20260527",
    "fractal-lambda-codex",
)
MAX_LEDGER_BYTES: Final = 49_152
MAX_LEDGER_EVENTS: Final = 24
MAX_LEDGER_EVENTS_PER_REQUEST: Final = 9
MAX_LEDGER_EVENT_BYTES: Final = 2_048
MAX_PREFLIGHT_DISPOSITION_BYTES: Final = 16_384
MAX_LOCAL_RAW_PRIVATE_EVIDENCE_BYTES: Final = 196_608
MAX_SANITIZED_MATCH_REPORT_BYTES: Final = 16_384
MAX_LOCAL_VERIFICATION_BYTES: Final = 65_536
MAX_EXTERNAL_ARCHIVE_BYTES: Final = 524_288
MAX_AGGREGATE_RETAINED_BYTES: Final = 1_048_576
MAX_PROVIDER_WALL_SECONDS: Final = 30
MAX_ARCHIVE_WALL_SECONDS: Final = 60
MAX_TOTAL_WALL_SECONDS: Final = 150
MAX_LOCAL_PROCESS_CALLS: Final = 15
MAX_LOCAL_PROCESS_OUTPUT_BYTES: Final = 37_879_810
MAX_LOCAL_FILE_CREATES: Final = 7
MAX_EXTERNAL_FILE_CREATES: Final = 7
MAX_EXTERNAL_DIRECTORY_CREATES: Final = 4
LOCAL_PREWRITE_FLOOR_BYTES: Final = 8_590_868_480
LOCAL_RETAINED_FLOOR_BYTES: Final = 8_589_934_592

RUN_ROOT_RELATIVE_PATH: Final = (
    "artifacts/t07/lambda/gate-l1a/RUN-T07-L1A-LAMBDA-SSH-KEY-FINGERPRINT-0001"
)
LEDGER_RELATIVE_PATH: Final = f"{RUN_ROOT_RELATIVE_PATH}/request-ledger.jsonl"
RAW_RESPONSE_RELATIVE_PATH: Final = f"{RUN_ROOT_RELATIVE_PATH}/ssh-keys-response.json"
PRIVATE_MANIFEST_RELATIVE_PATH: Final = f"{RUN_ROOT_RELATIVE_PATH}/private-evidence.json"
PRIVATE_SEAL_RELATIVE_PATH: Final = f"{RUN_ROOT_RELATIVE_PATH}/PRIVATE_EVIDENCE_SEAL.json"
SANITIZED_REPORT_RELATIVE_PATH: Final = f"{RUN_ROOT_RELATIVE_PATH}/match-report.json"
LOCAL_VERIFICATION_RELATIVE_PATH: Final = f"{RUN_ROOT_RELATIVE_PATH}/archive-finalization.jsonl"
PREFLIGHT_DISPOSITION_ROOT_RELATIVE_PATH: Final = (
    "artifacts/t07/lambda/gate-l1a/preflight-dispositions"
)
ARCHIVE_ROOT: Final = "/Volumes/Macintosh HD - Data/GIC-Lab/t07/sealed-artifacts"

RESPONSE_SCHEMA_RELATIVE_PATH: Final = (
    "containers/sira-smoke/lambda/endpoint-schemas-l1a/ssh-keys.schema.json"
)
FINGERPRINT_SCHEMA_RELATIVE_PATH: Final = "schemas/t07-lambda-ssh-key-fingerprint.schema.json"
MATCH_SCHEMA_RELATIVE_PATH: Final = "schemas/t07-local-public-key-match.schema.json"
LEDGER_SCHEMA_RELATIVE_PATH: Final = "schemas/t07-lambda-ssh-key-request-ledger.schema.json"

_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_COMMIT = re.compile(r"^[a-f0-9]{40}$")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_ACCOUNT_ALIAS = re.compile(r"^account-key-[0-9]{4}$")
_PRIVATE_LABELS = (
    "PRIVATE KEY",
    "ENCRYPTED PRIVATE KEY",
    "RSA PRIVATE KEY",
    "OPENSSH PRIVATE KEY",
    "EC PRIVATE KEY",
    "DSA PRIVATE KEY",
)
_RSA_OID = bytes.fromhex("2a864886f70d010101")
_ED25519_OID = bytes.fromhex("2b6570")


class SSHKeyFingerprintError(ValueError):
    """A public-key, response, evidence, or plan contract failed closed."""


class PublicKeyFormat(StrEnum):
    OPENSSH = "openssh"
    RFC4716 = "rfc4716"
    PKCS8_PUBLIC = "pkcs8-public"
    PEM_RSA_PUBLIC = "pem-rsa-public"


class SSHKeyHttpMethod(StrEnum):
    GET = "GET"


@dataclass(frozen=True, slots=True)
class SSHKeyRequest:
    request_id: str = "ssh-key-fingerprints"
    method: SSHKeyHttpMethod = SSHKeyHttpMethod.GET
    path: str = SSH_KEYS_PATH
    max_response_bytes: int = MAX_RESPONSE_BYTES

    def __post_init__(self) -> None:
        if (
            self.request_id != "ssh-key-fingerprints"
            or self.method is not SSHKeyHttpMethod.GET
            or self.path != SSH_KEYS_PATH
            or self.max_response_bytes != MAX_RESPONSE_BYTES
        ):
            raise SSHKeyFingerprintError("one-request endpoint identity drifted")


@dataclass(frozen=True, slots=True)
class SSHKeyRunBinding:
    repository_commit: str
    implementation_commit: str
    authorization_reference: str
    authorization_sha256: str
    run_id: str = RUN_ID
    plan_id: str = PLAN_ID

    def __post_init__(self) -> None:
        if (
            self.run_id != RUN_ID
            or self.plan_id != PLAN_ID
            or _COMMIT.fullmatch(self.repository_commit) is None
            or _COMMIT.fullmatch(self.implementation_commit) is None
            or _IDENTIFIER.fullmatch(self.authorization_reference) is None
            or self.authorization_reference == PENDING_AUTHORIZATION_REFERENCE
            or _SHA256.fullmatch(self.authorization_sha256) is None
        ):
            raise SSHKeyFingerprintError("one-request execution binding is invalid")


@dataclass(frozen=True, slots=True)
class ParsedPublicKey:
    """Canonical public-key identity derived without retaining private material."""

    algorithm: str
    fingerprint: str
    wire_blob: bytes
    source_format: PublicKeyFormat

    def __post_init__(self) -> None:
        expected = _standard_fingerprint(self.wire_blob)
        if self.fingerprint != expected or self.algorithm not in {"ssh-ed25519", "ssh-rsa"}:
            raise SSHKeyFingerprintError("parsed public-key identity is inconsistent")


@dataclass(frozen=True, slots=True)
class PrivateAccountKeyRecord:
    """Ignored-evidence representation; never render this object publicly."""

    account_alias: str
    raw_api_key_id: str
    name: str
    public_key_body: str
    algorithm: str
    fingerprint: str
    source_format: str
    multiplicity: int
    unknown_key_names: tuple[str, ...]

    def __post_init__(self) -> None:
        if (
            _ACCOUNT_ALIAS.fullmatch(self.account_alias) is None
            or not self.raw_api_key_id
            or not self.name
            or not self.public_key_body
            or self.algorithm not in {"ssh-ed25519", "ssh-rsa"}
            or not self.fingerprint.startswith("SHA256:")
            or self.multiplicity < 1
            or tuple(sorted(set(self.unknown_key_names))) != self.unknown_key_names
        ):
            raise SSHKeyFingerprintError("private account-key record is invalid")


@dataclass(frozen=True, slots=True)
class AccountKeyProjection:
    response_sha256: str
    response_bytes: int
    records: tuple[PrivateAccountKeyRecord, ...]
    compatible_extension_key_names: tuple[str, ...]

    def private_manifest_document(self) -> dict[str, object]:
        """Return the private, ignored manifest. It must never be committed."""

        return {
            "schema_version": "0.1.0",
            "plan_id": PLAN_ID,
            "run_id": RUN_ID,
            "raw_response": {
                "relative_path": RAW_RESPONSE_RELATIVE_PATH,
                "bytes": self.response_bytes,
                "sha256": self.response_sha256,
            },
            "account_keys": [
                {
                    "account_key_alias": record.account_alias,
                    "raw_api_key_id": record.raw_api_key_id,
                    "name": record.name,
                    "algorithm": record.algorithm,
                    "fingerprint": record.fingerprint,
                    "source_format": record.source_format,
                    "multiplicity": record.multiplicity,
                    "unknown_key_names": list(record.unknown_key_names),
                }
                for record in self.records
            ],
            "compatible_extension_key_names": list(self.compatible_extension_key_names),
            "raw_values_publicly_retained": False,
        }


def _standard_fingerprint(wire_blob: bytes) -> str:
    encoded = base64.b64encode(hashlib.sha256(wire_blob).digest()).decode("ascii")
    return f"SHA256:{encoded.rstrip('=')}"


def _ssh_string(value: bytes) -> bytes:
    if len(value) > 0xFFFFFFFF:
        raise SSHKeyFingerprintError("SSH field exceeds its wire limit")
    return len(value).to_bytes(4, "big") + value


def _read_ssh_string(blob: bytes, offset: int) -> tuple[bytes, int]:
    if offset < 0 or offset + 4 > len(blob):
        raise SSHKeyFingerprintError("SSH public-key wire encoding is truncated")
    length = int.from_bytes(blob[offset : offset + 4], "big")
    start = offset + 4
    end = start + length
    if end > len(blob):
        raise SSHKeyFingerprintError("SSH public-key wire field exceeds the blob")
    return blob[start:end], end


def _positive_ssh_mpint(value: bytes, *, field: str) -> int:
    if not value:
        raise SSHKeyFingerprintError(f"RSA {field} is empty")
    if value[0] & 0x80:
        raise SSHKeyFingerprintError(f"RSA {field} is negative")
    if len(value) > 1 and value[0] == 0 and not (value[1] & 0x80):
        raise SSHKeyFingerprintError(f"RSA {field} is not minimally encoded")
    number = int.from_bytes(value, "big", signed=False)
    if number <= 0:
        raise SSHKeyFingerprintError(f"RSA {field} is not positive")
    return number


def _parse_ssh_wire(blob: bytes, source_format: PublicKeyFormat) -> ParsedPublicKey:
    algorithm_raw, offset = _read_ssh_string(blob, 0)
    try:
        algorithm = algorithm_raw.decode("ascii")
    except UnicodeDecodeError:
        raise SSHKeyFingerprintError("SSH public-key algorithm is not ASCII") from None
    if algorithm == "ssh-ed25519":
        key_bytes, offset = _read_ssh_string(blob, offset)
        if len(key_bytes) != 32:
            raise SSHKeyFingerprintError("Ed25519 public key must contain 32 bytes")
    elif algorithm == "ssh-rsa":
        exponent_raw, offset = _read_ssh_string(blob, offset)
        modulus_raw, offset = _read_ssh_string(blob, offset)
        exponent = _positive_ssh_mpint(exponent_raw, field="exponent")
        _positive_ssh_mpint(modulus_raw, field="modulus")
        if exponent < 3 or exponent % 2 == 0:
            raise SSHKeyFingerprintError("RSA exponent is invalid")
    else:
        raise SSHKeyFingerprintError("SSH public-key algorithm is unsupported")
    if offset != len(blob):
        raise SSHKeyFingerprintError("SSH public-key wire encoding has trailing bytes")
    return ParsedPublicKey(
        algorithm=algorithm,
        fingerprint=_standard_fingerprint(blob),
        wire_blob=blob,
        source_format=source_format,
    )


def _decode_base64(value: str, *, context: str) -> bytes:
    compact = "".join(value.split())
    if not compact or len(compact) > 16_384 or len(compact) % 4 == 1:
        raise SSHKeyFingerprintError(f"{context} base64 is invalid")
    try:
        return base64.b64decode(compact, validate=True)
    except (ValueError, binascii.Error):
        raise SSHKeyFingerprintError(f"{context} base64 is invalid") from None


def _parse_openssh(value: str) -> ParsedPublicKey:
    lines = value.strip().splitlines()
    if len(lines) != 1:
        raise SSHKeyFingerprintError("OpenSSH input must contain exactly one key")
    fields = lines[0].split(None, 2)
    if len(fields) < 2 or fields[0] not in {"ssh-ed25519", "ssh-rsa"}:
        raise SSHKeyFingerprintError("OpenSSH public-key prefix is unsupported")
    blob = _decode_base64(fields[1], context="OpenSSH")
    parsed = _parse_ssh_wire(blob, PublicKeyFormat.OPENSSH)
    if parsed.algorithm != fields[0]:
        raise SSHKeyFingerprintError("OpenSSH prefix and wire algorithm differ")
    return parsed


def _parse_rfc4716(value: str) -> ParsedPublicKey:
    begin = "---- BEGIN SSH2 PUBLIC KEY ----"
    end = "---- END SSH2 PUBLIC KEY ----"
    lines = [line.strip() for line in value.strip().splitlines()]
    if lines.count(begin) != 1 or lines.count(end) != 1 or not lines:
        raise SSHKeyFingerprintError("RFC4716 input must contain one complete block")
    if lines[0] != begin or lines[-1] != end or begin in lines[1:] or end in lines[:-1]:
        raise SSHKeyFingerprintError("RFC4716 block boundaries are invalid")
    payload_lines: list[str] = []
    header_phase = True
    continuation = False
    for line in lines[1:-1]:
        if not line:
            continue
        if continuation:
            continuation = line.endswith("\\")
            continue
        if header_phase and ":" in line:
            name, _, header_value = line.partition(":")
            if not name or not header_value:
                raise SSHKeyFingerprintError("RFC4716 header is malformed")
            continuation = line.endswith("\\")
            continue
        header_phase = False
        if ":" in line or "\\" in line:
            raise SSHKeyFingerprintError("RFC4716 payload is malformed")
        payload_lines.append(line)
    if continuation or not payload_lines:
        raise SSHKeyFingerprintError("RFC4716 block is incomplete")
    blob = _decode_base64("".join(payload_lines), context="RFC4716")
    return _parse_ssh_wire(blob, PublicKeyFormat.RFC4716)


@dataclass(slots=True)
class _DERReader:
    data: bytes
    offset: int = 0

    def read(self, expected_tag: int) -> bytes:
        if self.offset >= len(self.data) or self.data[self.offset] != expected_tag:
            raise SSHKeyFingerprintError("DER tag is invalid")
        self.offset += 1
        if self.offset >= len(self.data):
            raise SSHKeyFingerprintError("DER length is missing")
        first = self.data[self.offset]
        self.offset += 1
        if first < 0x80:
            length = first
        else:
            count = first & 0x7F
            if count == 0 or count > 4 or self.offset + count > len(self.data):
                raise SSHKeyFingerprintError("DER length is invalid")
            length_bytes = self.data[self.offset : self.offset + count]
            self.offset += count
            if length_bytes[0] == 0:
                raise SSHKeyFingerprintError("DER length is not canonical")
            length = int.from_bytes(length_bytes, "big")
            if length < 0x80:
                raise SSHKeyFingerprintError("DER length uses a noncanonical form")
        end = self.offset + length
        if end > len(self.data):
            raise SSHKeyFingerprintError("DER value is truncated")
        value = self.data[self.offset : end]
        self.offset = end
        return value

    def require_end(self) -> None:
        if self.offset != len(self.data):
            raise SSHKeyFingerprintError("DER value has trailing bytes")


def _der_positive_integer(reader: _DERReader, *, field: str) -> int:
    encoded = reader.read(0x02)
    if not encoded or encoded[0] & 0x80:
        raise SSHKeyFingerprintError(f"DER RSA {field} is not positive")
    if len(encoded) > 1 and encoded[0] == 0 and not (encoded[1] & 0x80):
        raise SSHKeyFingerprintError(f"DER RSA {field} is not minimally encoded")
    number = int.from_bytes(encoded, "big")
    if number <= 0:
        raise SSHKeyFingerprintError(f"DER RSA {field} is zero")
    return number


def _ssh_mpint(number: int) -> bytes:
    if number <= 0:
        raise SSHKeyFingerprintError("SSH mpint source must be positive")
    encoded = number.to_bytes((number.bit_length() + 7) // 8, "big")
    if encoded[0] & 0x80:
        encoded = b"\x00" + encoded
    return encoded


def _rsa_wire_from_pkcs1(der: bytes, source_format: PublicKeyFormat) -> ParsedPublicKey:
    outer = _DERReader(der)
    sequence = outer.read(0x30)
    outer.require_end()
    inner = _DERReader(sequence)
    modulus = _der_positive_integer(inner, field="modulus")
    exponent = _der_positive_integer(inner, field="exponent")
    inner.require_end()
    if exponent < 3 or exponent % 2 == 0:
        raise SSHKeyFingerprintError("DER RSA exponent is invalid")
    blob = (
        _ssh_string(b"ssh-rsa")
        + _ssh_string(_ssh_mpint(exponent))
        + _ssh_string(_ssh_mpint(modulus))
    )
    return _parse_ssh_wire(blob, source_format)


def _parse_spki(der: bytes) -> ParsedPublicKey:
    outer = _DERReader(der)
    sequence = outer.read(0x30)
    outer.require_end()
    spki = _DERReader(sequence)
    algorithm_sequence = spki.read(0x30)
    algorithm_reader = _DERReader(algorithm_sequence)
    oid = algorithm_reader.read(0x06)
    if oid == _RSA_OID:
        if (
            algorithm_reader.offset < len(algorithm_reader.data)
            and algorithm_reader.read(0x05) != b""
        ):
            raise SSHKeyFingerprintError("RSA SPKI parameters are invalid")
        algorithm_reader.require_end()
    elif oid == _ED25519_OID:
        algorithm_reader.require_end()
    else:
        raise SSHKeyFingerprintError("SPKI public-key algorithm is unsupported")
    bit_string = spki.read(0x03)
    spki.require_end()
    if not bit_string or bit_string[0] != 0:
        raise SSHKeyFingerprintError("SPKI public-key bit string is invalid")
    key_payload = bit_string[1:]
    if oid == _RSA_OID:
        return _rsa_wire_from_pkcs1(key_payload, PublicKeyFormat.PKCS8_PUBLIC)
    if len(key_payload) != 32:
        raise SSHKeyFingerprintError("Ed25519 SPKI payload must contain 32 bytes")
    blob = _ssh_string(b"ssh-ed25519") + _ssh_string(key_payload)
    return _parse_ssh_wire(blob, PublicKeyFormat.PKCS8_PUBLIC)


def _pem_payload(value: str, label: str) -> bytes:
    begin = f"-----BEGIN {label}-----"
    end = f"-----END {label}-----"
    lines = [line.strip() for line in value.strip().splitlines()]
    if (
        lines.count(begin) != 1
        or lines.count(end) != 1
        or lines[0] != begin
        or lines[-1] != end
        or any(line.startswith("-----BEGIN ") for line in lines[1:])
        or any(line.startswith("-----END ") for line in lines[:-1])
    ):
        raise SSHKeyFingerprintError("PEM input must contain exactly one complete block")
    return _decode_base64("".join(lines[1:-1]), context=label)


def parse_public_key(value: str) -> ParsedPublicKey:
    """Parse one supported public key and compute its OpenSSH fingerprint."""

    if not isinstance(value, str):
        raise SSHKeyFingerprintError("public key must be text")
    try:
        encoded = value.encode("utf-8")
    except UnicodeEncodeError:
        raise SSHKeyFingerprintError("public key must be UTF-8") from None
    if not encoded or len(encoded) > MAX_PUBLIC_KEY_TEXT_BYTES or "\x00" in value:
        raise SSHKeyFingerprintError("public-key text violates its byte contract")
    upper = value.upper()
    if any(f"-----BEGIN {label}-----" in upper for label in _PRIVATE_LABELS):
        raise SSHKeyFingerprintError("private-key input is forbidden")
    stripped = value.strip()
    if stripped.startswith("---- BEGIN SSH2 PUBLIC KEY ----"):
        return _parse_rfc4716(stripped)
    if stripped.startswith("-----BEGIN PUBLIC KEY-----"):
        return _parse_spki(_pem_payload(stripped, "PUBLIC KEY"))
    if stripped.startswith("-----BEGIN RSA PUBLIC KEY-----"):
        return _rsa_wire_from_pkcs1(
            _pem_payload(stripped, "RSA PUBLIC KEY"),
            PublicKeyFormat.PEM_RSA_PUBLIC,
        )
    if "-----BEGIN " in stripped or "-----END " in stripped:
        raise SSHKeyFingerprintError("PEM public-key label is unsupported")
    return _parse_openssh(stripped)


def _strict_json_object(encoded: bytes) -> dict[str, object]:
    def object_pairs(values: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in values:
            if not isinstance(key, str) or key in result:
                raise ValueError
            result[key] = value
        return result

    try:
        decoded = json.loads(
            encoded,
            object_pairs_hook=object_pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError()),
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        raise SSHKeyFingerprintError("SSH-key response is not strict JSON") from None
    if not isinstance(decoded, dict):
        raise SSHKeyFingerprintError("SSH-key response must be an object")
    return decoded


def project_account_ssh_keys(encoded: bytes) -> AccountKeyProjection:
    """Validate and privately project the single authorized SSH-key response."""

    if not encoded or len(encoded) > MAX_RESPONSE_BYTES:
        raise SSHKeyFingerprintError("SSH-key response violates its byte cap")
    document = _strict_json_object(encoded)
    if set(document) != {"data"}:
        raise SSHKeyFingerprintError("SSH-key response envelope is incompatible")
    rows = document["data"]
    if not isinstance(rows, list) or len(rows) > MAX_ACCOUNT_KEYS:
        raise SSHKeyFingerprintError("SSH-key response data cardinality is invalid")

    authoritative: list[tuple[str, str, str, tuple[str, ...], ParsedPublicKey]] = []
    counts: dict[tuple[str, str, str], int] = {}
    first_details: dict[tuple[str, str, str], tuple[tuple[str, ...], ParsedPublicKey]] = {}
    raw_id_rows: dict[str, tuple[str, str]] = {}
    name_fingerprints: dict[str, str] = {}
    extension_names: set[str] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise SSHKeyFingerprintError(f"SSH-key row {index} is not an object")
        required = {"id", "name", "public_key"}
        if not required.issubset(row):
            raise SSHKeyFingerprintError(f"SSH-key row {index} omits a required field")
        raw_id = row["id"]
        name = row["name"]
        public_key = row["public_key"]
        if (
            not isinstance(raw_id, str)
            or not isinstance(name, str)
            or not isinstance(public_key, str)
            or not raw_id
            or len(raw_id) > 256
            or not 1 <= len(name) <= 64
            or not 1 <= len(public_key.encode("utf-8")) <= MAX_PUBLIC_KEY_TEXT_BYTES
        ):
            raise SSHKeyFingerprintError(f"SSH-key row {index} has an invalid field type")
        unknown = tuple(sorted(set(row) - required))
        extension_names.update(unknown)
        parsed = parse_public_key(public_key)
        raw_identity = (name, parsed.fingerprint)
        previous_raw = raw_id_rows.get(raw_id)
        if previous_raw is not None and previous_raw != raw_identity:
            raise SSHKeyFingerprintError("one raw SSH-key ID has conflicting metadata")
        raw_id_rows[raw_id] = raw_identity
        previous_fingerprint = name_fingerprints.get(name)
        if previous_fingerprint is not None and previous_fingerprint != parsed.fingerprint:
            raise SSHKeyFingerprintError("duplicate SSH-key name has different key material")
        name_fingerprints[name] = parsed.fingerprint
        identity = (raw_id, name, public_key)
        counts[identity] = counts.get(identity, 0) + 1
        if identity not in first_details:
            first_details[identity] = (unknown, parsed)
            authoritative.append((raw_id, name, public_key, unknown, parsed))

    records: list[PrivateAccountKeyRecord] = []
    for ordinal, (raw_id, name, public_key, unknown, parsed) in enumerate(authoritative, start=1):
        identity = (raw_id, name, public_key)
        records.append(
            PrivateAccountKeyRecord(
                account_alias=f"account-key-{ordinal:04d}",
                raw_api_key_id=raw_id,
                name=name,
                public_key_body=public_key,
                algorithm=parsed.algorithm,
                fingerprint=parsed.fingerprint,
                source_format=parsed.source_format.value,
                multiplicity=counts[identity],
                unknown_key_names=unknown,
            )
        )
    if len(records) != len(APPROVED_ACCOUNT_KEY_NAMES) or {
        record.name for record in records
    } != set(APPROVED_ACCOUNT_KEY_NAMES):
        raise SSHKeyFingerprintError("account SSH-key candidate set drifted")
    return AccountKeyProjection(
        response_sha256=hashlib.sha256(encoded).hexdigest(),
        response_bytes=len(encoded),
        records=tuple(records),
        compatible_extension_key_names=tuple(sorted(extension_names)),
    )


@dataclass(frozen=True, slots=True)
class LedgerLimits:
    max_bytes: int
    max_events: int
    max_events_per_request: int
    max_event_bytes: int
    max_preflight_disposition_bytes: int

    def __post_init__(self) -> None:
        expected = (
            MAX_LEDGER_BYTES,
            MAX_LEDGER_EVENTS,
            MAX_LEDGER_EVENTS_PER_REQUEST,
            MAX_LEDGER_EVENT_BYTES,
            MAX_PREFLIGHT_DISPOSITION_BYTES,
        )
        if (
            self.max_bytes,
            self.max_events,
            self.max_events_per_request,
            self.max_event_bytes,
            self.max_preflight_disposition_bytes,
        ) != expected or self.max_events * self.max_event_bytes > self.max_bytes:
            raise SSHKeyFingerprintError("one-request ledger limits drifted")


@dataclass(frozen=True, slots=True)
class PlanArtifactBinding:
    path: str
    sha256: str

    def __post_init__(self) -> None:
        candidate = Path(self.path)
        if (
            candidate.is_absolute()
            or ".." in candidate.parts
            or _SHA256.fullmatch(self.sha256) is None
        ):
            raise SSHKeyFingerprintError("implementation artifact binding is invalid")


@dataclass(frozen=True, slots=True)
class SSHKeyFingerprintPlan:
    implementation_commit: str
    implementation_artifacts: tuple[PlanArtifactBinding, ...]
    plan_sha256: str
    ledger_schema_sha256: str
    response_schema_sha256: str
    fingerprint_schema_sha256: str
    match_schema_sha256: str
    limits: LedgerLimits
    requests: tuple[SSHKeyRequest, ...]
    document: Mapping[str, object]
    plan_id: str = PLAN_ID
    run_id: str = RUN_ID
    max_calls: int = 1
    run_root_relative_path: str = RUN_ROOT_RELATIVE_PATH
    ledger_relative_path: str = LEDGER_RELATIVE_PATH
    ledger_schema_relative_path: str = LEDGER_SCHEMA_RELATIVE_PATH
    preflight_disposition_root_relative_path: str = PREFLIGHT_DISPOSITION_ROOT_RELATIVE_PATH
    transport_kind: str = "in-process-https"
    local_prewrite_floor_bytes: int = LOCAL_PREWRITE_FLOOR_BYTES


def _object(value: object, *, context: str) -> dict[str, object]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise SSHKeyFingerprintError(f"{context} must be an object")
    return value


def _integer(value: object, *, context: str) -> int:
    if type(value) is not int:
        raise SSHKeyFingerprintError(f"{context} must be an integer")
    return value


def _hash_bound_file(repository_root: Path, relative: str, expected: str) -> None:
    candidate = Path(relative)
    if candidate.is_absolute() or ".." in candidate.parts or _SHA256.fullmatch(expected) is None:
        raise SSHKeyFingerprintError("plan file binding is invalid")
    path = repository_root / candidate
    try:
        encoded = path.read_bytes()
    except OSError:
        raise SSHKeyFingerprintError("plan-bound file is unavailable") from None
    if hashlib.sha256(encoded).hexdigest() != expected:
        raise SSHKeyFingerprintError("plan-bound file hash drifted")


def load_ssh_key_fingerprint_plan(
    repository_root: Path,
    path: Path,
    *,
    expected_sha256: str,
) -> SSHKeyFingerprintPlan:
    """Load the exact unauthorized one-request plan using local I/O only."""

    root = repository_root.resolve(strict=True)
    if root != repository_root.absolute() or _SHA256.fullmatch(expected_sha256) is None:
        raise SSHKeyFingerprintError("repository or expected plan identity is invalid")
    try:
        encoded = path.read_bytes()
    except OSError:
        raise SSHKeyFingerprintError("one-request plan is unavailable") from None
    if hashlib.sha256(encoded).hexdigest() != expected_sha256:
        raise SSHKeyFingerprintError("one-request plan hash drifted")
    document = _strict_json_object(encoded)
    if (
        document.get("schema_version") != "0.1.0"
        or document.get("plan_id") != PLAN_ID
        or document.get("decision_state") != "unauthorized"
        or document.get("provider") != "lambda-on-demand-cloud"
        or document.get("api_base_url") != API_BASE_URL
        or document.get("actor") != "future-codex-operator-gpt-5.6-sol-max"
    ):
        raise SSHKeyFingerprintError("one-request plan identity drifted")
    api_spec = _object(document.get("api_spec"), context="api_spec")
    if api_spec != {
        "url": API_SPEC_URL,
        "version": API_SPEC_VERSION,
        "bytes": API_SPEC_BYTES,
        "sha256": API_SPEC_SHA256,
        "retrieved_at_utc": API_SPEC_RETRIEVED_AT_UTC,
    }:
        raise SSHKeyFingerprintError("one-request public API binding drifted")
    implementation = _object(
        document.get("implementation_binding"), context="implementation_binding"
    )
    if implementation.get("baseline_commit") != BASELINE_COMMIT:
        raise SSHKeyFingerprintError("one-request baseline commit drifted")
    implementation_commit = implementation.get("implementation_commit")
    if (
        not isinstance(implementation_commit, str)
        or _COMMIT.fullmatch(implementation_commit) is None
    ):
        raise SSHKeyFingerprintError("one-request implementation commit is invalid")
    raw_artifacts = implementation.get("implementation_artifacts")
    if not isinstance(raw_artifacts, list) or not raw_artifacts:
        raise SSHKeyFingerprintError("one-request implementation manifest is missing")
    artifacts: list[PlanArtifactBinding] = []
    for raw in raw_artifacts:
        item = _object(raw, context="implementation artifact")
        if set(item) != {"path", "sha256"}:
            raise SSHKeyFingerprintError("implementation artifact fields drifted")
        relative = item["path"]
        digest = item["sha256"]
        if not isinstance(relative, str) or not isinstance(digest, str):
            raise SSHKeyFingerprintError("implementation artifact types drifted")
        binding = PlanArtifactBinding(relative, digest)
        _hash_bound_file(root, binding.path, binding.sha256)
        artifacts.append(binding)
    if len({item.path for item in artifacts}) != len(artifacts):
        raise SSHKeyFingerprintError("implementation artifact paths repeat")
    if (
        implementation.get("transport_identity")
        != "giclab.harness.lambda_inventory_v3.LambdaHttpsInventoryTransportV3"
        or implementation.get("ledger_identity")
        != "giclab.harness.lambda_ssh_key_request_ledger.FsyncSSHKeyRequestLedger"
        or implementation.get("fingerprint_identity")
        != "giclab.harness.lambda_ssh_key_fingerprint.project_account_ssh_keys"
        or implementation.get("match_identity")
        != "giclab.harness.lambda_ssh_key_match.match_account_to_local_keys"
        or implementation.get("executor_identity") != EXECUTOR_IDENTITY
        or implementation.get("archive_identity") != ARCHIVER_IDENTITY
        or implementation.get("entrypoint_module") != ENTRYPOINT_MODULE
        or implementation.get("entrypoint_wrapper") != EXECUTION_WRAPPER
    ):
        raise SSHKeyFingerprintError("one-request implementation composition drifted")

    run = _object(document.get("run_identity"), context="run_identity")
    if run != {
        "run_id": RUN_ID,
        "attempt": 1,
        "experiment_id": "EXP-0001",
        "profile_plan_id": "PLAN-EXP0001-SMOKE",
        "gate": "T07-L1A",
        "branch": "phase-1/sira-smoke-lambda",
    }:
        raise SSHKeyFingerprintError("one-request run identity drifted")
    execution = _object(document.get("execution_contract"), context="execution_contract")
    if execution != {
        "working_directory": EXECUTION_WORKING_DIRECTORY,
        "argv_prefix": [EXECUTION_PYTHON, EXECUTION_WRAPPER],
        "shell": False,
        "credential_on_argv": False,
        "credential_environment_variable": "LAMBDA_API_KEY",
        "exact_arguments_from_authorization": [
            "--repository-root",
            "--plan",
            "--plan-sha256",
            "--expected-commit",
            "--implementation-commit",
            "--authorization-reference",
            "--authorization-sha256",
        ],
    }:
        raise SSHKeyFingerprintError("one-request execution command drifted")
    requests = document.get("requests")
    expected_request: dict[str, object] = {
        "request_id": "ssh-key-fingerprints",
        "method": "GET",
        "scheme": "https",
        "host": API_HOST,
        "path": SSH_KEYS_PATH,
        "query_key_names": [],
        "max_response_bytes": MAX_RESPONSE_BYTES,
        "response_schema_path": RESPONSE_SCHEMA_RELATIVE_PATH,
    }
    if not isinstance(requests, list) or len(requests) != 1:
        raise SSHKeyFingerprintError("one-request plan cardinality drifted")
    request = _object(requests[0], context="request")
    response_schema_sha256 = request.get("response_schema_sha256")
    if not isinstance(response_schema_sha256, str):
        raise SSHKeyFingerprintError("response-schema hash is missing")
    expected_request["response_schema_sha256"] = response_schema_sha256
    if request != expected_request:
        raise SSHKeyFingerprintError("one-request endpoint contract drifted")

    ledger = _object(document.get("ledger_contract"), context="ledger_contract")
    ledger_schema_sha256 = ledger.get("schema_sha256")
    if (
        ledger.get("schema_path") != LEDGER_SCHEMA_RELATIVE_PATH
        or ledger.get("relative_path") != LEDGER_RELATIVE_PATH
        or ledger.get("transport_kind") != "in-process-https"
        or not isinstance(ledger_schema_sha256, str)
    ):
        raise SSHKeyFingerprintError("one-request ledger binding drifted")
    ledger_limits = _object(ledger.get("limits"), context="ledger limits")
    limits = LedgerLimits(
        _integer(ledger_limits.get("max_bytes"), context="ledger max_bytes"),
        _integer(ledger_limits.get("max_events"), context="ledger max_events"),
        _integer(
            ledger_limits.get("max_events_per_request"),
            context="ledger max_events_per_request",
        ),
        _integer(ledger_limits.get("max_event_bytes"), context="ledger max_event_bytes"),
        _integer(
            ledger_limits.get("max_preflight_disposition_bytes"),
            context="ledger max_preflight_disposition_bytes",
        ),
    )
    output = _object(document.get("output"), context="output")
    expected_paths = {
        "run_root_relative_path": RUN_ROOT_RELATIVE_PATH,
        "raw_response_relative_path": RAW_RESPONSE_RELATIVE_PATH,
        "private_manifest_relative_path": PRIVATE_MANIFEST_RELATIVE_PATH,
        "private_seal_relative_path": PRIVATE_SEAL_RELATIVE_PATH,
        "sanitized_report_relative_path": SANITIZED_REPORT_RELATIVE_PATH,
        "local_verification_relative_path": LOCAL_VERIFICATION_RELATIVE_PATH,
        "archive_root": ARCHIVE_ROOT,
        "archive_run_directory": RUN_ID,
        "raw_response_public": False,
        "source_retained": True,
        "no_internal_fallback": True,
    }
    if output != expected_paths:
        raise SSHKeyFingerprintError("one-request output paths drifted")
    schema_contract = _object(document.get("schema_contract"), context="schema_contract")
    fingerprint_schema_sha256 = schema_contract.get("fingerprint_schema_sha256")
    match_schema_sha256 = schema_contract.get("match_schema_sha256")
    if (
        schema_contract.get("fingerprint_schema_path") != FINGERPRINT_SCHEMA_RELATIVE_PATH
        or schema_contract.get("match_schema_path") != MATCH_SCHEMA_RELATIVE_PATH
        or not isinstance(fingerprint_schema_sha256, str)
        or not isinstance(match_schema_sha256, str)
    ):
        raise SSHKeyFingerprintError("one-request evidence-schema binding drifted")
    for relative, digest in (
        (RESPONSE_SCHEMA_RELATIVE_PATH, response_schema_sha256),
        (LEDGER_SCHEMA_RELATIVE_PATH, ledger_schema_sha256),
        (FINGERPRINT_SCHEMA_RELATIVE_PATH, fingerprint_schema_sha256),
        (MATCH_SCHEMA_RELATIVE_PATH, match_schema_sha256),
    ):
        _hash_bound_file(root, relative, digest)
        try:
            schema = json.loads((root / relative).read_bytes())
            Draft202012Validator.check_schema(schema)
        except Exception:
            raise SSHKeyFingerprintError("one-request schema is invalid") from None

    numeric_limits = _object(document.get("limits"), context="limits")
    expected_limits = {
        "max_calls": 1,
        "max_total_response_bytes": MAX_RESPONSE_BYTES,
        "max_local_raw_private_evidence_bytes": MAX_LOCAL_RAW_PRIVATE_EVIDENCE_BYTES,
        "max_sanitized_match_report_bytes": MAX_SANITIZED_MATCH_REPORT_BYTES,
        "max_local_verification_bytes": MAX_LOCAL_VERIFICATION_BYTES,
        "max_external_archive_bytes": MAX_EXTERNAL_ARCHIVE_BYTES,
        "max_aggregate_retained_bytes": MAX_AGGREGATE_RETAINED_BYTES,
        "max_provider_wall_seconds": MAX_PROVIDER_WALL_SECONDS,
        "max_archive_wall_seconds": MAX_ARCHIVE_WALL_SECONDS,
        "max_total_wall_seconds": MAX_TOTAL_WALL_SECONDS,
        "max_local_process_calls": MAX_LOCAL_PROCESS_CALLS,
        "max_local_process_output_bytes": MAX_LOCAL_PROCESS_OUTPUT_BYTES,
        "max_local_file_creates": MAX_LOCAL_FILE_CREATES,
        "max_external_file_creates": MAX_EXTERNAL_FILE_CREATES,
        "max_external_directory_creates": MAX_EXTERNAL_DIRECTORY_CREATES,
        "local_prewrite_floor_bytes": LOCAL_PREWRITE_FLOOR_BYTES,
        "local_retained_floor_bytes": LOCAL_RETAINED_FLOOR_BYTES,
        "automatic_retries": 0,
        "pagination_requests": 0,
        "redirects_followed": 0,
        "mutation_calls": 0,
        "provider_cost_usd": 0,
        "model_api_calls": 0,
        "model_tokens": 0,
        "browser_actions": 0,
        "ssh_operations": 0,
        "private_key_reads": 0,
        "sira_executions": 0,
    }
    if numeric_limits != expected_limits:
        raise SSHKeyFingerprintError("one-request numeric limits drifted")
    if document.get("authorization") != {
        "authorized": False,
        "authorization_reference": PENDING_AUTHORIZATION_REFERENCE,
    }:
        raise SSHKeyFingerprintError("one-request plan must remain unauthorized")
    secret_contract = _object(document.get("secret_contract"), context="secret_contract")
    if secret_contract != {
        "variable": "LAMBDA_API_KEY",
        "channel": "supervisor-secret-channel",
        "print_allowed": False,
        "hash_allowed": False,
        "persist_allowed": False,
        "return_allowed": False,
        "forbidden_fallbacks": ["SIRA_API_KEY", "OPENAI_API_KEY"],
    }:
        raise SSHKeyFingerprintError("one-request secret contract drifted")
    return SSHKeyFingerprintPlan(
        implementation_commit=implementation_commit,
        implementation_artifacts=tuple(artifacts),
        plan_sha256=expected_sha256,
        ledger_schema_sha256=ledger_schema_sha256,
        response_schema_sha256=response_schema_sha256,
        fingerprint_schema_sha256=fingerprint_schema_sha256,
        match_schema_sha256=match_schema_sha256,
        limits=limits,
        requests=(SSHKeyRequest(),),
        document=document,
    )


def validate_document_against_schema(
    document: Mapping[str, object],
    *,
    repository_root: Path,
    schema_relative_path: str,
) -> None:
    """Validate an evidence document against one repository-owned schema."""

    try:
        schema = json.loads((repository_root / schema_relative_path).read_bytes())
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
    except Exception:
        raise SSHKeyFingerprintError("evidence schema is unavailable or invalid") from None
    errors = list(validator.iter_errors(dict(document)))
    if errors:
        raise SSHKeyFingerprintError("evidence document violates its schema")


def canonical_json_bytes(document: Mapping[str, object], *, max_bytes: int) -> bytes:
    encoded = (
        json.dumps(
            dict(document),
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        + b"\n"
    )
    if len(encoded) > max_bytes:
        raise SSHKeyFingerprintError("canonical evidence exceeds its byte cap")
    return encoded


def implementation_hashes(
    repository_root: Path,
    relative_paths: Sequence[str],
) -> tuple[PlanArtifactBinding, ...]:
    """Render exact local implementation hashes without modifying the repository."""

    bindings: list[PlanArtifactBinding] = []
    for relative in relative_paths:
        path = repository_root / relative
        try:
            encoded = path.read_bytes()
        except OSError:
            raise SSHKeyFingerprintError("implementation artifact is unavailable") from None
        bindings.append(PlanArtifactBinding(relative, hashlib.sha256(encoded).hexdigest()))
    return tuple(bindings)
