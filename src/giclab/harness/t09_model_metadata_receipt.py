"""The single pre-launch model-metadata request and its offline receipt.

The provider and host used to have two owners for the same model-availability
check.  This module makes the ownership boundary explicit: a local control
plane performs one authenticated GET, seals a redacted receipt, and every later
plane validates that receipt without contacting OpenAI.

The module intentionally contains no provider, Lambda, browser, or scientific
execution code.  Its transport is injectable for local tests and the real
transport has no retry, redirect, pagination, or response-header retention
path.
"""

from __future__ import annotations

import contextlib
import datetime as _datetime
import hashlib
import http.client
import json
import math
import os
import re
import ssl
import stat
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final, Protocol, cast


class ModelMetadataReceiptError(RuntimeError):
    """The model-metadata receipt contract failed closed."""


class ModelMetadataContract(Protocol):
    """The small provider identity surface needed by receipt validation."""

    @property
    def version(self) -> str: ...

    @property
    def plan_id(self) -> str: ...

    @property
    def host_run_id(self) -> str: ...


@dataclass(frozen=True, slots=True)
class ModelMetadataResponse:
    """A transport response with no retained headers or credential material."""

    status: int
    body: bytes = field(repr=False)
    response_completed_at: float


class ModelMetadataTransport(Protocol):
    """The only injectable boundary capable of sending the metadata GET."""

    def get_model_metadata(
        self,
        model_id: str,
        *,
        credential: bytearray,
    ) -> ModelMetadataResponse: ...


MODEL_METADATA_SCHEMA_VERSION: Final = "1.0.0"
MODEL_METADATA_RECEIPT_TYPE: Final = "t09-model-metadata-prelaunch"
MODEL_METADATA_HOST: Final = "api.openai.com"
MODEL_METADATA_PATH_PREFIX: Final = "/v1/models/"
MODEL_METADATA_MODEL_ID: Final = "gpt-4o-2024-11-20"
MODEL_METADATA_PLAN_ID: Final = "PLAN-EXP0001-PILOT-V12"
MODEL_METADATA_HOST_RUN_ID: Final = "RUN-T09-PILOT-HOST-AUTONOMOUS-0005"
MODEL_METADATA_ENDPOINT: Final = (
    f"https://{MODEL_METADATA_HOST}{MODEL_METADATA_PATH_PREFIX}{MODEL_METADATA_MODEL_ID}"
)
MODEL_METADATA_TERMINAL_STATE: Final = "model-metadata-verified"
MODEL_METADATA_MAX_RESPONSE_BYTES: Final = 65_536
MODEL_METADATA_MAX_DOTENV_BYTES: Final = 65_536
MODEL_METADATA_MAX_AGE_SECONDS: Final = 1_800.0


@dataclass(frozen=True, slots=True)
class _StaticV12Contract:
    version: str = "V12"
    plan_id: str = MODEL_METADATA_PLAN_ID
    host_run_id: str = MODEL_METADATA_HOST_RUN_ID


MODEL_METADATA_RECEIPT_FIELDS: Final = frozenset(
    {
        "schema_version",
        "receipt_type",
        "authorization_reference",
        "authorization_source_sha256",
        "authorization_overlay_sha256",
        "repository_commit",
        "repository_tree",
        "plan_id",
        "plan_sha256",
        "provider_contract_version",
        "host_run_id",
        "model_endpoint",
        "requested_model_id",
        "returned_model_id",
        "http_status",
        "request_count",
        "redirect_count",
        "retry_count",
        "pagination_count",
        "request_started_at",
        "response_completed_at",
        "receipt_created_at",
        "response_body_sha256",
        "public_price_contract_sha256",
        "public_deprecation_observation_sha256",
        "terminal_state",
    }
)

MODEL_METADATA_AUTHORIZATION_FIELDS: Final = frozenset(
    {
        "schema_version",
        "authorization_reference",
        "authorization_source_sha256",
        "provider_contract_version",
        "repository_commit",
        "repository_tree",
        "plan_id",
        "plan_sha256",
        "host_run_id",
        "public_price_contract_sha256",
        "public_deprecation_observation_sha256",
        "model_metadata_receipt_sha256",
        "authorized",
        "single_use",
    }
)

_HEX40: Final = re.compile(r"^[a-f0-9]{40}$")
_HEX64: Final = re.compile(r"^[a-f0-9]{64}$")
_SAFE_ID: Final = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$")
_RFC3339: Final = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?"
    r"(?:Z|[+-](?:[01]\d|2[0-3]):[0-5]\d)$"
)
_DOTENV_VALUE: Final = re.compile(rb"^[A-Za-z0-9._:/+\-=]{16,4096}$")
_SECRET_FIELD_MARKERS: Final = (
    "secret",
    "credential",
    "authorization_header",
    "api_key",
    "token",
    "account_id",
    "account_identifier",
    "cookie",
    "password",
    "email",
    "header",
)


def _canonical_bytes(value: object) -> bytes:
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


def semantic_projection_sha256(value: Mapping[str, object]) -> str:
    """Hash the deterministic, sorted semantic representation of a receipt."""

    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _fsync_parent(path: Path) -> None:
    descriptor = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _safe_private_file_bytes(path: Path, *, maximum_bytes: int, label: str) -> bytes:
    if not path.is_absolute():
        raise ModelMetadataReceiptError(f"{label} path must be absolute")
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except OSError as exc:
        raise ModelMetadataReceiptError(f"{label} is unavailable") from exc
    try:
        before = os.fstat(descriptor)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_uid != os.getuid()
            or before.st_nlink != 1
            or stat.S_IMODE(before.st_mode) != 0o600
            or not 0 < before.st_size <= maximum_bytes
        ):
            raise ModelMetadataReceiptError(f"{label} metadata is unsafe")
        raw = os.read(descriptor, maximum_bytes + 1)
        after = os.fstat(descriptor)
        if len(raw) != before.st_size or (
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
        ) != (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
        ):
            raise ModelMetadataReceiptError(f"{label} changed while held")
        return raw
    finally:
        os.close(descriptor)


def _reject_duplicate_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ModelMetadataReceiptError("JSON contains duplicate fields")
        result[key] = value
    return result


def _load_private_json(path: Path, *, maximum_bytes: int, label: str) -> dict[str, object]:
    raw = _safe_private_file_bytes(path, maximum_bytes=maximum_bytes, label=label)
    try:
        loaded: object = json.loads(raw.decode("utf-8"), object_pairs_hook=_reject_duplicate_pairs)
    except (UnicodeDecodeError, json.JSONDecodeError, ModelMetadataReceiptError) as exc:
        raise ModelMetadataReceiptError(f"{label} is malformed JSON") from exc
    if not isinstance(loaded, dict) or any(not isinstance(key, str) for key in loaded):
        raise ModelMetadataReceiptError(f"{label} must be a JSON object")
    return cast(dict[str, object], loaded)


def _write_exclusive(path: Path, value: Mapping[str, object]) -> None:
    if not path.is_absolute() or not path.parent.is_dir() or os.path.lexists(path):
        raise ModelMetadataReceiptError("receipt output must be a fresh absolute path")
    encoded = _canonical_bytes(value)
    descriptor = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        os.fchmod(descriptor, 0o600)
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_uid != os.getuid()
            or metadata.st_nlink != 1
            or stat.S_IMODE(metadata.st_mode) != 0o600
        ):
            raise ModelMetadataReceiptError("sealed receipt metadata is unsafe")
        offset = 0
        while offset < len(encoded):
            written = os.write(descriptor, encoded[offset:])
            if written <= 0:
                raise OSError("short receipt write")
            offset += written
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    _fsync_parent(path)


def _authorization_overlay_projection(overlay: Mapping[str, object]) -> dict[str, object]:
    """Return the non-circular authorization projection bound into a receipt."""

    projection = dict(overlay)
    projection["model_metadata_receipt_sha256"] = None
    return projection


def _write_existing_private_json(path: Path, value: Mapping[str, object]) -> None:
    """Atomically seal a controlled update to the already-held auth overlay inode."""

    if not path.is_absolute() or not path.parent.is_dir():
        raise ModelMetadataReceiptError("authorization overlay path is invalid")
    encoded = _canonical_bytes(value)
    try:
        descriptor = os.open(
            path,
            os.O_RDWR | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0),
        )
    except OSError as exc:
        raise ModelMetadataReceiptError("authorization overlay is unavailable") from exc
    try:
        before = os.fstat(descriptor)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_uid != os.getuid()
            or before.st_nlink != 1
            or stat.S_IMODE(before.st_mode) != 0o600
            or not 0 < before.st_size <= 65_536
        ):
            raise ModelMetadataReceiptError("authorization overlay metadata is unsafe")
        os.lseek(descriptor, 0, os.SEEK_SET)
        raw = os.read(descriptor, 65_537)
        if len(raw) != before.st_size or raw != _canonical_bytes(
            _load_private_json_from_bytes(raw)
        ):
            raise ModelMetadataReceiptError("authorization overlay changed while held")
        os.fchmod(descriptor, 0o600)
        os.ftruncate(descriptor, 0)
        os.lseek(descriptor, 0, os.SEEK_SET)
        offset = 0
        while offset < len(encoded):
            written = os.write(descriptor, encoded[offset:])
            if written <= 0:
                raise OSError("short authorization overlay write")
            offset += written
        os.fsync(descriptor)
        after = os.fstat(descriptor)
        path_after = os.stat(path, follow_symlinks=False)
        if (
            not stat.S_ISREG(after.st_mode)
            or after.st_uid != os.getuid()
            or after.st_nlink != 1
            or stat.S_IMODE(after.st_mode) != 0o600
            or path_after.st_dev != after.st_dev
            or path_after.st_ino != after.st_ino
            or after.st_size != len(encoded)
        ):
            raise ModelMetadataReceiptError("authorization overlay sealing failed")
    except OSError as exc:
        raise ModelMetadataReceiptError("authorization overlay sealing failed") from exc
    finally:
        os.close(descriptor)
    _fsync_parent(path)


def _load_private_json_from_bytes(raw: bytes) -> dict[str, object]:
    try:
        loaded: object = json.loads(raw.decode("utf-8"), object_pairs_hook=_reject_duplicate_pairs)
    except (UnicodeDecodeError, json.JSONDecodeError, ModelMetadataReceiptError) as exc:
        raise ModelMetadataReceiptError("authorization overlay is malformed JSON") from exc
    if not isinstance(loaded, dict) or any(not isinstance(key, str) for key in loaded):
        raise ModelMetadataReceiptError("authorization overlay must be a JSON object")
    return cast(dict[str, object], loaded)


def _destroy_bytearray(value: bytearray) -> None:
    for index in range(len(value)):
        value[index] = 0
    value.clear()


def _forbidden_secret_fields(value: object, *, prefix: str = "") -> list[str]:
    hits: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if not isinstance(key, str):
                hits.append(prefix or "<non-string-key>")
                continue
            key_lower = key.casefold()
            if any(marker in key_lower for marker in _SECRET_FIELD_MARKERS):
                hits.append(f"{prefix}.{key}" if prefix else key)
            hits.extend(
                _forbidden_secret_fields(child, prefix=f"{prefix}.{key}" if prefix else key)
            )
    elif isinstance(value, list):
        for index, child in enumerate(value):
            hits.extend(_forbidden_secret_fields(child, prefix=f"{prefix}[{index}]"))
    return hits


def _timestamp(value: object, *, label: str) -> float:
    if not isinstance(value, str) or _RFC3339.fullmatch(value) is None:
        raise ModelMetadataReceiptError(f"{label} is not an RFC3339 timestamp")
    try:
        parsed = _datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
        result = parsed.timestamp()
    except (OverflowError, OSError, ValueError) as exc:
        raise ModelMetadataReceiptError(f"{label} is not an RFC3339 timestamp") from exc
    if parsed.tzinfo is None:
        raise ModelMetadataReceiptError(f"{label} lacks a timezone")
    if not math.isfinite(result):
        raise ModelMetadataReceiptError(f"{label} is not finite")
    return result


def _timestamp_text(value: float, *, label: str) -> str:
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not math.isfinite(float(value))
    ):
        raise ModelMetadataReceiptError(f"{label} clock value is malformed")
    if value < 0:
        raise ModelMetadataReceiptError(f"{label} clock value is negative")
    try:
        return (
            _datetime.datetime.fromtimestamp(float(value), tz=_datetime.UTC)
            .isoformat(timespec="microseconds")
            .replace("+00:00", "Z")
        )
    except (OverflowError, OSError, ValueError) as exc:
        raise ModelMetadataReceiptError(f"{label} clock value is out of range") from exc


def _require_hex(value: object, *, length: int, label: str) -> str:
    if (
        not isinstance(value, str)
        or (length == 40 and _HEX40.fullmatch(value) is None)
        or (length == 64 and _HEX64.fullmatch(value) is None)
    ):
        raise ModelMetadataReceiptError(f"{label} is malformed")
    return value


def _require_id(value: object, *, label: str) -> str:
    if not isinstance(value, str) or _SAFE_ID.fullmatch(value) is None:
        raise ModelMetadataReceiptError(f"{label} is malformed")
    return value


def _validate_overlay(
    overlay: Mapping[str, object],
    *,
    contract: ModelMetadataContract,
    package_commit: str,
    package_tree: str,
    plan_sha256: str,
    require_receipt_binding: bool = False,
) -> dict[str, object]:
    if set(overlay) != MODEL_METADATA_AUTHORIZATION_FIELDS:
        raise ModelMetadataReceiptError("authorization overlay fields drifted")
    if _forbidden_secret_fields(overlay):
        raise ModelMetadataReceiptError("authorization overlay contains secret-bearing fields")
    if overlay.get("schema_version") != MODEL_METADATA_SCHEMA_VERSION:
        raise ModelMetadataReceiptError("authorization overlay schema version drifted")
    if overlay.get("provider_contract_version") != contract.version or contract.version != "V12":
        raise ModelMetadataReceiptError("authorization overlay crosses provider contracts")
    if overlay.get("authorized") is not True or overlay.get("single_use") is not True:
        raise ModelMetadataReceiptError("authorization overlay is not a single authorized use")
    if overlay.get("repository_commit") != package_commit:
        raise ModelMetadataReceiptError("authorization overlay commit drifted")
    if overlay.get("repository_tree") != package_tree:
        raise ModelMetadataReceiptError("authorization overlay tree drifted")
    if overlay.get("plan_id") != contract.plan_id or overlay.get("plan_sha256") != plan_sha256:
        raise ModelMetadataReceiptError("authorization overlay plan binding drifted")
    if overlay.get("host_run_id") != contract.host_run_id:
        raise ModelMetadataReceiptError("authorization overlay host binding drifted")
    reference = _require_id(overlay.get("authorization_reference"), label="authorization reference")
    if reference.startswith("AUTH-T09-V11-") or not reference.startswith("AUTH-T09-V12-"):
        raise ModelMetadataReceiptError("authorization reference is not fresh V12 authority")
    _require_hex(
        overlay.get("authorization_source_sha256"),
        length=64,
        label="authorization source",
    )
    _require_hex(
        overlay.get("public_price_contract_sha256"),
        length=64,
        label="public price contract",
    )
    _require_hex(
        overlay.get("public_deprecation_observation_sha256"),
        length=64,
        label="public deprecation observation",
    )
    receipt_sha256 = overlay.get("model_metadata_receipt_sha256")
    if receipt_sha256 is not None:
        _require_hex(receipt_sha256, length=64, label="model metadata receipt")
    if require_receipt_binding and not isinstance(receipt_sha256, str):
        raise ModelMetadataReceiptError("authorization overlay lacks the receipt binding")
    return dict(overlay)


def _authorization_consumption_path(overlay_path: Path, authorization_reference: str) -> Path:
    digest = hashlib.sha256(
        f"{MODEL_METADATA_RECEIPT_TYPE}:{authorization_reference}".encode()
    ).hexdigest()
    return overlay_path.parent / f".t09-model-metadata-{digest}.consumed"


def _consume_authorization(overlay_path: Path, authorization_reference: str) -> None:
    marker = _authorization_consumption_path(overlay_path, authorization_reference)
    try:
        _write_exclusive(
            marker,
            {
                "schema_version": MODEL_METADATA_SCHEMA_VERSION,
                "authorization_reference": authorization_reference,
                "consumed_for": MODEL_METADATA_RECEIPT_TYPE,
                "request_count": 1,
            },
        )
    except (FileExistsError, ModelMetadataReceiptError) as exc:
        raise ModelMetadataReceiptError("authorization reference was already consumed") from exc


def _parse_model_id(body: bytes) -> str:
    try:
        value: object = json.loads(body.decode("utf-8"), object_pairs_hook=_reject_duplicate_pairs)
    except (UnicodeDecodeError, json.JSONDecodeError, ModelMetadataReceiptError) as exc:
        raise ModelMetadataReceiptError("model metadata response is malformed JSON") from exc
    if not isinstance(value, dict) or value.get("id") != MODEL_METADATA_MODEL_ID:
        raise ModelMetadataReceiptError("returned model identity is not exact")
    return MODEL_METADATA_MODEL_ID


class OpenAIModelMetadataTransport:
    """One-shot HTTPS transport for the exact model metadata endpoint."""

    def __init__(
        self,
        *,
        context: ssl.SSLContext | None = None,
        timeout_seconds: float = 60.0,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._context = context or ssl.create_default_context()
        self._timeout_seconds = timeout_seconds
        self._clock = clock

    def get_model_metadata(
        self,
        model_id: str,
        *,
        credential: bytearray,
    ) -> ModelMetadataResponse:
        if model_id != MODEL_METADATA_MODEL_ID:
            raise ModelMetadataReceiptError("transport model identity is not exact")
        if not 16 <= len(credential) <= 4_096 or any(
            marker in credential for marker in (b"\r", b"\n", b"\0")
        ):
            raise ModelMetadataReceiptError("OpenAI credential is malformed")
        connection = http.client.HTTPSConnection(
            MODEL_METADATA_HOST,
            443,
            timeout=self._timeout_seconds,
            context=self._context,
        )
        try:
            connection.request(
                "GET",
                f"{MODEL_METADATA_PATH_PREFIX}{model_id}",
                headers={
                    "Accept": "application/json",
                    "Authorization": "Bearer " + credential.decode("ascii", "strict"),
                    "User-Agent": "giclab-t09-model-metadata-v1/1",
                },
            )
            response = connection.getresponse()
            if not 200 <= response.status < 300:
                raise ModelMetadataReceiptError("model metadata HTTP status was not successful")
            if response.getheader("Location") is not None:
                raise ModelMetadataReceiptError("model metadata redirect is forbidden")
            content_type = response.getheader("Content-Type", "").split(";", 1)[0].casefold()
            if content_type != "application/json":
                raise ModelMetadataReceiptError("model metadata response is not JSON")
            body = bytearray()
            while chunk := response.read(16_384):
                body.extend(chunk)
                if len(body) > MODEL_METADATA_MAX_RESPONSE_BYTES:
                    raise ModelMetadataReceiptError("model metadata response exceeds its cap")
            return ModelMetadataResponse(
                status=response.status,
                body=bytes(body),
                response_completed_at=self._clock(),
            )
        except (OSError, ssl.SSLError, http.client.HTTPException) as exc:
            raise ModelMetadataReceiptError(
                "model metadata transport outcome is unavailable"
            ) from exc
        finally:
            with contextlib.suppress(OSError):
                connection.close()


def load_openai_dotenv_assignment(path: Path) -> bytearray:
    """Read only OPENAI_API_KEY from a held, non-shell dotenv file."""

    raw = _safe_private_file_bytes(
        path,
        maximum_bytes=MODEL_METADATA_MAX_DOTENV_BYTES,
        label="OpenAI dotenv",
    )
    selected: bytearray | None = None
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(b"#"):
            continue
        if b"=" not in stripped:
            raise ModelMetadataReceiptError("OpenAI dotenv syntax is unsupported")
        raw_name, raw_value = stripped.split(b"=", 1)
        if raw_name != b"OPENAI_API_KEY" or _DOTENV_VALUE.fullmatch(raw_value) is None:
            raise ModelMetadataReceiptError("OpenAI dotenv contains a non-OpenAI assignment")
        if selected is not None:
            raise ModelMetadataReceiptError("OpenAI dotenv assignment is ambiguous")
        selected = bytearray(raw_value)
    if selected is None:
        raise ModelMetadataReceiptError("OPENAI_API_KEY assignment is missing")
    return selected


def create_model_metadata_receipt(
    *,
    repository_commit: str,
    repository_tree: str,
    plan_id: str,
    plan_sha256: str,
    provider_contract_version: str,
    host_run_id: str,
    authorization_reference: str,
    authorization_source_sha256: str,
    authorization_overlay_sha256: str,
    public_price_contract_sha256: str,
    public_deprecation_observation_sha256: str,
    output: Path,
    dotenv: Path,
    authorization_overlay: Path,
    transport: ModelMetadataTransport | None = None,
    clock: Callable[[], float] = time.time,
) -> Path:
    """Perform the sole GET and seal one immutable receipt."""

    if provider_contract_version != "V12":
        raise ModelMetadataReceiptError("model metadata receipt is only valid for V12")
    if plan_id != MODEL_METADATA_PLAN_ID or host_run_id != MODEL_METADATA_HOST_RUN_ID:
        raise ModelMetadataReceiptError("model metadata receipt identity is not exact V12")
    _require_hex(repository_commit, length=40, label="repository commit")
    _require_hex(repository_tree, length=40, label="repository tree")
    _require_hex(plan_sha256, length=64, label="plan SHA-256")
    _require_hex(authorization_source_sha256, length=64, label="authorization source SHA-256")
    _require_hex(authorization_overlay_sha256, length=64, label="authorization overlay SHA-256")
    _require_hex(public_price_contract_sha256, length=64, label="public price contract SHA-256")
    _require_hex(
        public_deprecation_observation_sha256,
        length=64,
        label="public deprecation observation SHA-256",
    )
    _require_id(plan_id, label="plan ID")
    _require_id(host_run_id, label="host run ID")
    _require_id(authorization_reference, label="authorization reference")
    if not authorization_reference.startswith("AUTH-T09-V12-"):
        raise ModelMetadataReceiptError("authorization reference is not fresh V12 authority")
    if not output.is_absolute() or not output.parent.is_dir() or os.path.lexists(output):
        raise ModelMetadataReceiptError("receipt output must be a fresh absolute path")

    overlay = validate_model_metadata_authorization_overlay(
        authorization_overlay,
        contract=_StaticV12Contract(),
        package_commit=repository_commit,
        package_tree=repository_tree,
        plan_sha256=plan_sha256,
    )
    if overlay.get("model_metadata_receipt_sha256") is not None:
        raise ModelMetadataReceiptError("authorization overlay was already bound to a receipt")
    overlay_sha256 = model_metadata_authorization_overlay_sha256(authorization_overlay)
    if (
        overlay_sha256 != authorization_overlay_sha256
        or overlay.get("authorization_reference") != authorization_reference
        or overlay.get("authorization_source_sha256") != authorization_source_sha256
        or overlay.get("public_price_contract_sha256") != public_price_contract_sha256
        or overlay.get("public_deprecation_observation_sha256")
        != public_deprecation_observation_sha256
    ):
        raise ModelMetadataReceiptError("receipt authorization binding is inconsistent")

    credential = load_openai_dotenv_assignment(dotenv)
    request_started_epoch = clock()
    try:
        _consume_authorization(authorization_overlay, authorization_reference)
        selected_transport = transport or OpenAIModelMetadataTransport(clock=clock)
        response = selected_transport.get_model_metadata(
            MODEL_METADATA_MODEL_ID,
            credential=credential,
        )
        response_completed_epoch = response.response_completed_at
        if (
            not isinstance(response_completed_epoch, (int, float))
            or isinstance(response_completed_epoch, bool)
            or not math.isfinite(float(response_completed_epoch))
        ):
            raise ModelMetadataReceiptError("model metadata response timestamp is malformed")
        if response.status != 200:
            raise ModelMetadataReceiptError("model metadata HTTP status was not exactly 200")
        if len(response.body) > MODEL_METADATA_MAX_RESPONSE_BYTES:
            raise ModelMetadataReceiptError("model metadata response exceeds its cap")
        returned_model_id = _parse_model_id(response.body)
        receipt_created_epoch = clock()
        if not (request_started_epoch <= response_completed_epoch <= receipt_created_epoch):
            raise ModelMetadataReceiptError("model metadata receipt timestamps are unordered")
        receipt: dict[str, object] = {
            "schema_version": MODEL_METADATA_SCHEMA_VERSION,
            "receipt_type": MODEL_METADATA_RECEIPT_TYPE,
            "authorization_reference": authorization_reference,
            "authorization_source_sha256": authorization_source_sha256,
            "authorization_overlay_sha256": authorization_overlay_sha256,
            "repository_commit": repository_commit,
            "repository_tree": repository_tree,
            "plan_id": plan_id,
            "plan_sha256": plan_sha256,
            "provider_contract_version": provider_contract_version,
            "host_run_id": host_run_id,
            "model_endpoint": MODEL_METADATA_ENDPOINT,
            "requested_model_id": MODEL_METADATA_MODEL_ID,
            "returned_model_id": returned_model_id,
            "http_status": response.status,
            "request_count": 1,
            "redirect_count": 0,
            "retry_count": 0,
            "pagination_count": 0,
            "request_started_at": _timestamp_text(request_started_epoch, label="request start"),
            "response_completed_at": _timestamp_text(
                response_completed_epoch,
                label="response completion",
            ),
            "receipt_created_at": _timestamp_text(receipt_created_epoch, label="receipt creation"),
            "response_body_sha256": hashlib.sha256(response.body).hexdigest(),
            "public_price_contract_sha256": public_price_contract_sha256,
            "public_deprecation_observation_sha256": public_deprecation_observation_sha256,
            "terminal_state": MODEL_METADATA_TERMINAL_STATE,
        }
        _write_exclusive(output, receipt)
        return output
    finally:
        _destroy_bytearray(credential)


def _validate_receipt_document(
    document: Mapping[str, object],
    *,
    contract: ModelMetadataContract,
    package_commit: str,
    package_tree: str,
    plan_sha256: str,
    expected_authorization_reference: str | None,
    expected_authorization_source_sha256: str | None,
    expected_authorization_overlay_sha256: str | None,
    launch_started_at: float | None,
    now: float | None,
    require_fresh: bool,
) -> dict[str, object]:
    if set(document) != MODEL_METADATA_RECEIPT_FIELDS:
        raise ModelMetadataReceiptError("model metadata receipt fields drifted")
    if _forbidden_secret_fields(document):
        raise ModelMetadataReceiptError("model metadata receipt contains secret-bearing fields")
    if document.get("schema_version") != MODEL_METADATA_SCHEMA_VERSION:
        raise ModelMetadataReceiptError("model metadata receipt schema version drifted")
    if document.get("receipt_type") != MODEL_METADATA_RECEIPT_TYPE:
        raise ModelMetadataReceiptError("model metadata receipt type drifted")
    if document.get("provider_contract_version") != contract.version or contract.version != "V12":
        raise ModelMetadataReceiptError("model metadata receipt crosses provider contracts")
    if document.get("plan_id") != contract.plan_id or document.get("plan_sha256") != plan_sha256:
        raise ModelMetadataReceiptError("model metadata receipt plan binding drifted")
    if document.get("host_run_id") != contract.host_run_id:
        raise ModelMetadataReceiptError("model metadata receipt host binding drifted")
    if document.get("repository_commit") != package_commit:
        raise ModelMetadataReceiptError("model metadata receipt commit binding drifted")
    if document.get("repository_tree") != package_tree:
        raise ModelMetadataReceiptError("model metadata receipt tree binding drifted")
    if document.get("model_endpoint") != MODEL_METADATA_ENDPOINT:
        raise ModelMetadataReceiptError("model metadata endpoint drifted")
    if document.get("requested_model_id") != MODEL_METADATA_MODEL_ID:
        raise ModelMetadataReceiptError("requested model identity drifted")
    if document.get("returned_model_id") != MODEL_METADATA_MODEL_ID:
        raise ModelMetadataReceiptError("returned model identity drifted")
    if document.get("terminal_state") != MODEL_METADATA_TERMINAL_STATE:
        raise ModelMetadataReceiptError("model metadata terminal state drifted")
    if document.get("http_status") != 200:
        raise ModelMetadataReceiptError("model metadata status is not successful")
    for field_name in ("request_count", "redirect_count", "retry_count", "pagination_count"):
        value = document.get(field_name)
        expected = 1 if field_name == "request_count" else 0
        if type(value) is not int or value != expected:
            raise ModelMetadataReceiptError(f"model metadata {field_name} drifted")
    for field_name in (
        "repository_commit",
        "repository_tree",
        "plan_sha256",
        "authorization_source_sha256",
        "authorization_overlay_sha256",
        "response_body_sha256",
        "public_price_contract_sha256",
        "public_deprecation_observation_sha256",
    ):
        _require_hex(
            document.get(field_name),
            length=40 if field_name in {"repository_commit", "repository_tree"} else 64,
            label=field_name,
        )
    reference = _require_id(
        document.get("authorization_reference"),
        label="authorization reference",
    )
    if reference.startswith("AUTH-T09-V11-") or not reference.startswith("AUTH-T09-V12-"):
        raise ModelMetadataReceiptError("model metadata receipt authorization is not fresh V12")
    if (
        expected_authorization_reference is not None
        and reference != expected_authorization_reference
    ):
        raise ModelMetadataReceiptError("model metadata authorization reference drifted")
    if (
        expected_authorization_source_sha256 is not None
        and document.get("authorization_source_sha256") != expected_authorization_source_sha256
    ):
        raise ModelMetadataReceiptError("model metadata authorization source drifted")
    if (
        expected_authorization_overlay_sha256 is not None
        and document.get("authorization_overlay_sha256") != expected_authorization_overlay_sha256
    ):
        raise ModelMetadataReceiptError("model metadata authorization overlay drifted")
    started = _timestamp(document.get("request_started_at"), label="request start")
    completed = _timestamp(document.get("response_completed_at"), label="response completion")
    created = _timestamp(document.get("receipt_created_at"), label="receipt creation")
    if not started <= completed <= created:
        raise ModelMetadataReceiptError("model metadata timestamp ordering drifted")
    if launch_started_at is not None:
        if (
            not isinstance(launch_started_at, (int, float))
            or isinstance(launch_started_at, bool)
            or not math.isfinite(float(launch_started_at))
        ):
            raise ModelMetadataReceiptError("provider launch clock is malformed")
        if created > float(launch_started_at) or completed > float(launch_started_at):
            raise ModelMetadataReceiptError(
                "model metadata receipt was created after provider launch"
            )
    if require_fresh:
        current = time.time() if now is None else now
        if (
            not isinstance(current, (int, float))
            or isinstance(current, bool)
            or not math.isfinite(float(current))
        ):
            raise ModelMetadataReceiptError("receipt freshness clock is malformed")
        if created > float(current) or float(current) - created > MODEL_METADATA_MAX_AGE_SECONDS:
            raise ModelMetadataReceiptError("model metadata receipt is stale")
    return dict(document)


def validate_model_metadata_receipt(
    path: Path,
    *,
    contract: ModelMetadataContract,
    package_commit: str,
    package_tree: str,
    plan_sha256: str,
    authorization_overlay: Path | None = None,
    expected_authorization_reference: str | None = None,
    expected_authorization_source_sha256: str | None = None,
    expected_authorization_overlay_sha256: str | None = None,
    launch_started_at: float | None = None,
    now: float | None = None,
    require_fresh: bool = True,
) -> dict[str, object]:
    """Validate one receipt, optionally against the still-held auth overlay."""

    raw = _safe_private_file_bytes(path, maximum_bytes=65_536, label="model metadata receipt")
    try:
        loaded: object = json.loads(raw.decode("utf-8"), object_pairs_hook=_reject_duplicate_pairs)
    except (UnicodeDecodeError, json.JSONDecodeError, ModelMetadataReceiptError) as exc:
        raise ModelMetadataReceiptError("model metadata receipt is malformed JSON") from exc
    if not isinstance(loaded, dict):
        raise ModelMetadataReceiptError("model metadata receipt is not an object")
    document = cast(dict[str, object], loaded)
    if raw != _canonical_bytes(document):
        raise ModelMetadataReceiptError("model metadata receipt is not canonically sealed")
    validated = _validate_receipt_document(
        document,
        contract=contract,
        package_commit=package_commit,
        package_tree=package_tree,
        plan_sha256=plan_sha256,
        expected_authorization_reference=expected_authorization_reference,
        expected_authorization_source_sha256=expected_authorization_source_sha256,
        expected_authorization_overlay_sha256=expected_authorization_overlay_sha256,
        launch_started_at=launch_started_at,
        now=now,
        require_fresh=require_fresh,
    )
    if authorization_overlay is not None:
        _safe_private_file_bytes(
            authorization_overlay,
            maximum_bytes=65_536,
            label="authorization overlay",
        )
        overlay = _load_private_json(
            authorization_overlay,
            maximum_bytes=65_536,
            label="authorization overlay",
        )
        _validate_overlay(
            overlay,
            contract=contract,
            package_commit=package_commit,
            package_tree=package_tree,
            plan_sha256=plan_sha256,
            require_receipt_binding=True,
        )
        overlay_sha256 = semantic_projection_sha256(_authorization_overlay_projection(overlay))
        if validated.get("authorization_overlay_sha256") != overlay_sha256:
            raise ModelMetadataReceiptError("receipt is not bound to the authorization overlay")
        if overlay.get("model_metadata_receipt_sha256") != semantic_projection_sha256(validated):
            raise ModelMetadataReceiptError("authorization overlay receipt binding disagrees")
        if validated.get("authorization_reference") != overlay.get("authorization_reference"):
            raise ModelMetadataReceiptError("receipt and authorization reference disagree")
        if validated.get("authorization_source_sha256") != overlay.get(
            "authorization_source_sha256"
        ):
            raise ModelMetadataReceiptError("receipt and authorization source disagree")
        if validated.get("public_price_contract_sha256") != overlay.get(
            "public_price_contract_sha256"
        ) or validated.get("public_deprecation_observation_sha256") != overlay.get(
            "public_deprecation_observation_sha256"
        ):
            raise ModelMetadataReceiptError("receipt and public metadata bindings disagree")
    return validated


def validate_model_metadata_authorization_overlay(
    path: Path,
    *,
    contract: ModelMetadataContract,
    package_commit: str,
    package_tree: str,
    plan_sha256: str,
    require_receipt_binding: bool = False,
) -> dict[str, object]:
    """Validate the private, credential-free Category 3 overlay by exact identity."""

    raw = _safe_private_file_bytes(path, maximum_bytes=65_536, label="authorization overlay")
    overlay = _load_private_json(path, maximum_bytes=65_536, label="authorization overlay")
    validated = _validate_overlay(
        overlay,
        contract=contract,
        package_commit=package_commit,
        package_tree=package_tree,
        plan_sha256=plan_sha256,
        require_receipt_binding=require_receipt_binding,
    )
    if hashlib.sha256(raw).hexdigest() != hashlib.sha256(_canonical_bytes(validated)).hexdigest():
        raise ModelMetadataReceiptError("authorization overlay is not canonically sealed")
    return validated


def model_metadata_authorization_overlay_sha256(path: Path) -> str:
    """Hash the receipt-independent semantic projection of an auth overlay."""

    raw = _safe_private_file_bytes(path, maximum_bytes=65_536, label="authorization overlay")
    overlay = _load_private_json(path, maximum_bytes=65_536, label="authorization overlay")
    if raw != _canonical_bytes(overlay):
        raise ModelMetadataReceiptError("authorization overlay is not canonically sealed")
    return semantic_projection_sha256(_authorization_overlay_projection(overlay))


def bind_model_metadata_receipt_to_authorization_overlay(
    path: Path,
    *,
    receipt_sha256: str,
) -> None:
    """Seal the receipt hash into the consumed V12 authorization overlay."""

    _require_hex(receipt_sha256, length=64, label="model metadata receipt")
    overlay = _load_private_json(path, maximum_bytes=65_536, label="authorization overlay")
    if set(overlay) != MODEL_METADATA_AUTHORIZATION_FIELDS:
        raise ModelMetadataReceiptError("authorization overlay fields drifted")
    if overlay.get("model_metadata_receipt_sha256") is not None:
        raise ModelMetadataReceiptError("authorization overlay was already receipt-bound")
    updated = dict(overlay)
    updated["model_metadata_receipt_sha256"] = receipt_sha256
    _write_existing_private_json(path, updated)


def model_metadata_receipt_sha256(path: Path) -> str:
    """Return the semantic hash of a validated canonical receipt file."""

    raw = _safe_private_file_bytes(path, maximum_bytes=65_536, label="model metadata receipt")
    try:
        loaded: object = json.loads(raw.decode("utf-8"), object_pairs_hook=_reject_duplicate_pairs)
    except (UnicodeDecodeError, json.JSONDecodeError, ModelMetadataReceiptError) as exc:
        raise ModelMetadataReceiptError("model metadata receipt is malformed JSON") from exc
    if not isinstance(loaded, dict) or raw != _canonical_bytes(loaded):
        raise ModelMetadataReceiptError("model metadata receipt is not canonically sealed")
    return semantic_projection_sha256(cast(dict[str, object], loaded))


__all__ = [
    "MODEL_METADATA_AUTHORIZATION_FIELDS",
    "MODEL_METADATA_ENDPOINT",
    "MODEL_METADATA_HOST_RUN_ID",
    "MODEL_METADATA_MODEL_ID",
    "MODEL_METADATA_PLAN_ID",
    "MODEL_METADATA_RECEIPT_FIELDS",
    "MODEL_METADATA_RECEIPT_TYPE",
    "MODEL_METADATA_SCHEMA_VERSION",
    "MODEL_METADATA_TERMINAL_STATE",
    "ModelMetadataReceiptError",
    "ModelMetadataResponse",
    "ModelMetadataTransport",
    "OpenAIModelMetadataTransport",
    "bind_model_metadata_receipt_to_authorization_overlay",
    "create_model_metadata_receipt",
    "load_openai_dotenv_assignment",
    "model_metadata_authorization_overlay_sha256",
    "model_metadata_receipt_sha256",
    "semantic_projection_sha256",
    "validate_model_metadata_authorization_overlay",
    "validate_model_metadata_receipt",
]
