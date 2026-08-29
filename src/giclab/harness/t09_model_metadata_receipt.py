"""One local model-metadata request, one durable secret-free receipt.

This module owns the only OpenAI request allowed by the V12 handoff.  The
provider and host consume the canonical receipt without constructing a network
transport.  Private-file helpers intentionally hold descriptors while checking
ownership, link count, mode, content bounds, and path identity.
"""

from __future__ import annotations

import contextlib
import datetime as datetime_module
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
from enum import StrEnum
from pathlib import Path
from typing import Final, Protocol, cast


class ModelMetadataReceiptError(RuntimeError):
    """A receipt, its authority, or its private-file contract failed closed."""


class ModelMetadataReceiptValidationPolicy(StrEnum):
    """The two intentionally different freshness policies."""

    PRELAUNCH_FRESH = "prelaunch-fresh"
    DURABLE_OFFLINE = "durable-offline"


class ModelMetadataContract(Protocol):
    @property
    def version(self) -> str: ...

    @property
    def plan_id(self) -> str: ...

    @property
    def host_run_id(self) -> str: ...


@dataclass(frozen=True, slots=True)
class ModelMetadataResponse:
    """The retained response surface excludes headers and account data."""

    status: int
    body: bytes = field(repr=False)
    response_completed_at: float


class ModelMetadataTransport(Protocol):
    """Injectable boundary for the sole authenticated request."""

    def get_model_metadata(
        self,
        model_id: str,
        *,
        credential: bytearray,
    ) -> ModelMetadataResponse: ...


MODEL_METADATA_SCHEMA_VERSION: Final = "1.0.0"
MODEL_METADATA_RECEIPT_TYPE: Final = "t09-model-metadata-prelaunch"
MODEL_METADATA_HOST: Final = "api.openai.com"
MODEL_METADATA_MODEL_ID: Final = "gpt-4o-2024-11-20"
MODEL_METADATA_PATH: Final = f"/v1/models/{MODEL_METADATA_MODEL_ID}"
MODEL_METADATA_ENDPOINT: Final = f"https://{MODEL_METADATA_HOST}{MODEL_METADATA_PATH}"
MODEL_METADATA_PLAN_ID: Final = "PLAN-EXP0001-PILOT-V12"
MODEL_METADATA_HOST_RUN_ID: Final = "RUN-T09-PILOT-HOST-AUTONOMOUS-0005"
MODEL_METADATA_RECEIPT_FILENAME: Final = "model-metadata-receipt.json"
MODEL_METADATA_TERMINAL_STATE: Final = "model-metadata-verified"
MODEL_METADATA_PRELAUNCH_FRESHNESS_SECONDS: Final = 1_800.0
MODEL_METADATA_MAX_AGE_SECONDS: Final = MODEL_METADATA_PRELAUNCH_FRESHNESS_SECONDS
MODEL_METADATA_MAX_PRIVATE_BYTES: Final = 65_536

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
_DOTENV_VALUE: Final = re.compile(rb"^[A-Za-z0-9._:/+\-=]{16,4096}$")
_OPENAI_DOTENV_ASSIGNMENT: Final = b"OPENAI_API_KEY"
_LAMBDA_DOTENV_ASSIGNMENT: Final = b"LAMBDA_API_KEY"
_SENSITIVE_FIELD_FRAGMENTS: Final = (
    "api_key",
    "authorization_header",
    "credential",
    "account_identifier",
    "account_id",
    "password",
    "cookie",
    "secret",
)


@dataclass(frozen=True, slots=True)
class _V12Identity:
    version: str = "V12"
    plan_id: str = MODEL_METADATA_PLAN_ID
    host_run_id: str = MODEL_METADATA_HOST_RUN_ID


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
    """Return the SHA-256 of the canonical semantic projection."""

    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _fsync_parent(path: Path) -> None:
    descriptor = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _validate_private_parent(path: Path, *, label: str) -> None:
    if not path.is_absolute():
        raise ModelMetadataReceiptError(f"{label} path must be absolute")
    try:
        parent = path.parent.stat(follow_symlinks=False)
    except OSError as exc:
        raise ModelMetadataReceiptError(f"{label} parent is unavailable") from exc
    if (
        not stat.S_ISDIR(parent.st_mode)
        or parent.st_uid != os.getuid()
        or stat.S_IMODE(parent.st_mode) & 0o022
    ):
        raise ModelMetadataReceiptError(f"{label} parent metadata is unsafe")


def _same_identity(left: os.stat_result, right: os.stat_result) -> bool:
    return (left.st_dev, left.st_ino) == (right.st_dev, right.st_ino)


def _read_private_bytes(path: Path, *, label: str) -> bytes:
    _validate_private_parent(path, label=label)
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise ModelMetadataReceiptError(f"{label} is unavailable") from exc
    try:
        before = os.fstat(descriptor)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_uid != os.getuid()
            or before.st_nlink != 1
            or stat.S_IMODE(before.st_mode) != 0o600
            or not 0 < before.st_size <= MODEL_METADATA_MAX_PRIVATE_BYTES
        ):
            raise ModelMetadataReceiptError(f"{label} metadata is unsafe")
        raw = os.read(descriptor, MODEL_METADATA_MAX_PRIVATE_BYTES + 1)
        held_after = os.fstat(descriptor)
        try:
            path_after = path.stat(follow_symlinks=False)
        except OSError as exc:
            raise ModelMetadataReceiptError(f"{label} path changed while held") from exc
        stable_fields = ("st_size", "st_mtime_ns", "st_ctime_ns")
        if (
            len(raw) != before.st_size
            or not _same_identity(before, held_after)
            or not _same_identity(before, path_after)
            or any(getattr(before, name) != getattr(held_after, name) for name in stable_fields)
            or path_after.st_nlink != 1
            or stat.S_IMODE(path_after.st_mode) != 0o600
        ):
            raise ModelMetadataReceiptError(f"{label} changed while held")
        return raw
    finally:
        os.close(descriptor)


def _read_openai_dotenv_bytes(path: Path) -> bytearray:
    """Read the approved external dotenv shape without relaxing private JSON.

    Unlike receipts, authorization overlays, and state files, the qualified
    repository-external dotenv may be mode 0644.  Its dedicated policy rejects
    every group/world-writable mode while retaining the same held-descriptor,
    no-follow, ownership, link-count, size, parent, and path-identity controls.
    """

    label = "OpenAI dotenv"
    _validate_private_parent(path, label=label)
    flags = (
        os.O_RDONLY
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_NONBLOCK", 0)
        | getattr(os, "O_CLOEXEC", 0)
    )
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise ModelMetadataReceiptError(f"{label} is unavailable") from exc
    raw = bytearray()
    try:
        before = os.fstat(descriptor)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_uid != os.getuid()
            or before.st_nlink != 1
            or stat.S_IMODE(before.st_mode) & 0o022
            or not 0 < before.st_size <= MODEL_METADATA_MAX_PRIVATE_BYTES
        ):
            raise ModelMetadataReceiptError(f"{label} metadata is unsafe")

        raw = bytearray(before.st_size + 1)
        offset = 0
        while offset < len(raw):
            target = memoryview(raw)[offset:]
            try:
                count = os.readv(descriptor, [target])
            finally:
                target.release()
            if count == 0:
                break
            offset += count

        held_after = os.fstat(descriptor)
        try:
            path_after = path.stat(follow_symlinks=False)
        except OSError as exc:
            raise ModelMetadataReceiptError(f"{label} path changed while held") from exc
        stable_fields = (
            "st_mode",
            "st_uid",
            "st_nlink",
            "st_size",
            "st_mtime_ns",
            "st_ctime_ns",
        )
        if (
            offset != before.st_size
            or not _same_identity(before, held_after)
            or not _same_identity(before, path_after)
            or not stat.S_ISREG(held_after.st_mode)
            or not stat.S_ISREG(path_after.st_mode)
            or any(getattr(before, name) != getattr(held_after, name) for name in stable_fields)
            or any(getattr(before, name) != getattr(path_after, name) for name in stable_fields)
            or stat.S_IMODE(path_after.st_mode) & 0o022
        ):
            raise ModelMetadataReceiptError(f"{label} changed while held")
        del raw[offset:]
        return raw
    except OSError as exc:
        _destroy_bytearray(raw)
        raise ModelMetadataReceiptError(f"{label} changed while held") from exc
    except BaseException:
        _destroy_bytearray(raw)
        raise
    finally:
        os.close(descriptor)


def _write_all(descriptor: int, encoded: bytes) -> None:
    written = 0
    while written < len(encoded):
        count = os.write(descriptor, encoded[written:])
        if count <= 0:
            raise ModelMetadataReceiptError("private write made no progress")
        written += count


def _write_private_exclusive(path: Path, value: Mapping[str, object]) -> None:
    _validate_private_parent(path, label="private output")
    if os.path.lexists(path):
        raise ModelMetadataReceiptError("private output is not fresh")
    encoded = _canonical_bytes(value)
    if not 0 < len(encoded) <= MODEL_METADATA_MAX_PRIVATE_BYTES:
        raise ModelMetadataReceiptError("private output exceeds its bound")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o600)
    complete = False
    try:
        _write_all(descriptor, encoded)
        os.fsync(descriptor)
        held = os.fstat(descriptor)
        path_metadata = path.stat(follow_symlinks=False)
        if (
            not stat.S_ISREG(held.st_mode)
            or held.st_uid != os.getuid()
            or held.st_nlink != 1
            or stat.S_IMODE(held.st_mode) != 0o600
            or held.st_size != len(encoded)
            or not _same_identity(held, path_metadata)
        ):
            raise ModelMetadataReceiptError("sealed private output metadata drifted")
        complete = True
    finally:
        os.close(descriptor)
        if not complete:
            with contextlib.suppress(OSError):
                path.unlink()
    _fsync_parent(path)


def _rewrite_held_private(path: Path, value: Mapping[str, object]) -> None:
    """Rewrite an existing private marker while proving the path stayed held."""

    _validate_private_parent(path, label="private state")
    encoded = _canonical_bytes(value)
    flags = os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        before = os.fstat(descriptor)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_uid != os.getuid()
            or before.st_nlink != 1
            or stat.S_IMODE(before.st_mode) != 0o600
        ):
            raise ModelMetadataReceiptError("private state metadata is unsafe")
        os.ftruncate(descriptor, 0)
        os.lseek(descriptor, 0, os.SEEK_SET)
        _write_all(descriptor, encoded)
        os.fsync(descriptor)
        after = os.fstat(descriptor)
        path_after = path.stat(follow_symlinks=False)
        if (
            not _same_identity(before, after)
            or not _same_identity(before, path_after)
            or after.st_size != len(encoded)
            or after.st_nlink != 1
            or stat.S_IMODE(after.st_mode) != 0o600
        ):
            raise ModelMetadataReceiptError("private state path changed while held")
    finally:
        os.close(descriptor)
    _fsync_parent(path)


def _reject_duplicate_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ModelMetadataReceiptError("JSON contains duplicate fields")
        result[key] = value
    return result


def _decode_object(raw: bytes, *, label: str, canonical: bool) -> dict[str, object]:
    try:
        loaded: object = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_pairs,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ModelMetadataReceiptError) as exc:
        raise ModelMetadataReceiptError(f"{label} is malformed JSON") from exc
    if not isinstance(loaded, dict):
        raise ModelMetadataReceiptError(f"{label} must be a JSON object")
    result = cast(dict[str, object], loaded)
    if canonical and raw != _canonical_bytes(result):
        raise ModelMetadataReceiptError(f"{label} is not canonically sealed")
    return result


def _load_private_object(path: Path, *, label: str, canonical: bool = True) -> dict[str, object]:
    return _decode_object(_read_private_bytes(path, label=label), label=label, canonical=canonical)


def _require_hex(value: object, *, length: int, label: str) -> str:
    pattern = _HEX40 if length == 40 else _HEX64
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        raise ModelMetadataReceiptError(f"{label} is malformed")
    return value


def _require_safe_id(value: object, *, label: str) -> str:
    if not isinstance(value, str) or _SAFE_ID.fullmatch(value) is None:
        raise ModelMetadataReceiptError(f"{label} is malformed")
    return value


def _reject_sensitive_fields(value: object, *, path: str = "") -> None:
    if isinstance(value, dict):
        for raw_key, nested in value.items():
            key = str(raw_key).casefold()
            if any(fragment in key for fragment in _SENSITIVE_FIELD_FRAGMENTS):
                raise ModelMetadataReceiptError(
                    f"secret-bearing extension field is forbidden: {path}{raw_key}"
                )
            _reject_sensitive_fields(nested, path=f"{path}{raw_key}.")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _reject_sensitive_fields(nested, path=f"{path}{index}.")


def _overlay_projection(overlay: Mapping[str, object]) -> dict[str, object]:
    projection = dict(overlay)
    projection["model_metadata_receipt_sha256"] = None
    return projection


def _validate_overlay(
    overlay: Mapping[str, object],
    *,
    contract: ModelMetadataContract,
    package_commit: str,
    package_tree: str,
    plan_sha256: str,
    require_receipt_binding: bool,
) -> dict[str, object]:
    if set(overlay) != MODEL_METADATA_AUTHORIZATION_FIELDS:
        raise ModelMetadataReceiptError("authorization overlay fields drifted")
    _reject_sensitive_fields(overlay)
    if (
        overlay.get("schema_version") != MODEL_METADATA_SCHEMA_VERSION
        or contract.version != "V12"
        or overlay.get("provider_contract_version") != contract.version
        or overlay.get("repository_commit") != package_commit
        or overlay.get("repository_tree") != package_tree
        or overlay.get("plan_id") != contract.plan_id
        or overlay.get("plan_sha256") != plan_sha256
        or overlay.get("host_run_id") != contract.host_run_id
        or overlay.get("authorized") is not True
        or overlay.get("single_use") is not True
    ):
        raise ModelMetadataReceiptError("authorization overlay immutable binding drifted")
    reference = _require_safe_id(
        overlay.get("authorization_reference"),
        label="authorization reference",
    )
    if not reference.startswith("AUTH-T09-V12-") or reference.startswith("AUTH-T09-V11-"):
        raise ModelMetadataReceiptError("authorization is not fresh V12 authority")
    for field_name in (
        "authorization_source_sha256",
        "public_price_contract_sha256",
        "public_deprecation_observation_sha256",
    ):
        _require_hex(overlay.get(field_name), length=64, label=field_name)
    bound = overlay.get("model_metadata_receipt_sha256")
    if bound is not None:
        _require_hex(bound, length=64, label="receipt binding")
    if require_receipt_binding and not isinstance(bound, str):
        raise ModelMetadataReceiptError("authorization overlay lacks its receipt binding")
    return dict(overlay)


def validate_model_metadata_authorization_overlay(
    path: Path,
    *,
    contract: ModelMetadataContract,
    package_commit: str,
    package_tree: str,
    plan_sha256: str,
    require_receipt_binding: bool = False,
) -> dict[str, object]:
    return _validate_overlay(
        _load_private_object(path, label="authorization overlay"),
        contract=contract,
        package_commit=package_commit,
        package_tree=package_tree,
        plan_sha256=plan_sha256,
        require_receipt_binding=require_receipt_binding,
    )


def model_metadata_authorization_overlay_sha256(path: Path) -> str:
    overlay = _load_private_object(path, label="authorization overlay")
    if set(overlay) != MODEL_METADATA_AUTHORIZATION_FIELDS:
        raise ModelMetadataReceiptError("authorization overlay fields drifted")
    return semantic_projection_sha256(_overlay_projection(overlay))


def _authorization_state_path(overlay_path: Path, reference: str) -> Path:
    digest = hashlib.sha256(f"{MODEL_METADATA_RECEIPT_TYPE}:{reference}".encode()).hexdigest()
    return overlay_path.parent / f".t09-model-metadata-{digest}.state.json"


def _reserve_authorization(
    overlay_path: Path,
    *,
    reference: str,
    overlay_sha256: str,
    requested_at: float,
) -> Path:
    state_path = _authorization_state_path(overlay_path, reference)
    try:
        _write_private_exclusive(
            state_path,
            {
                "schema_version": MODEL_METADATA_SCHEMA_VERSION,
                "authorization_reference": reference,
                "authorization_overlay_sha256": overlay_sha256,
                "request_count": 1,
                "state": "reserved-before-send",
                "send_attempt_started_at": _format_timestamp(requested_at),
                "replay_allowed": False,
            },
        )
    except (FileExistsError, ModelMetadataReceiptError, OSError) as exc:
        raise ModelMetadataReceiptError("authorization was already reserved or consumed") from exc
    return state_path


def _finish_authorization_attempt(
    state_path: Path,
    *,
    reference: str,
    overlay_sha256: str,
    attempted_at: float,
    completed_at: float,
) -> None:
    _rewrite_held_private(
        state_path,
        {
            "schema_version": MODEL_METADATA_SCHEMA_VERSION,
            "authorization_reference": reference,
            "authorization_overlay_sha256": overlay_sha256,
            "request_count": 1,
            "state": "consumed-after-send-attempt",
            "send_attempt_started_at": _format_timestamp(attempted_at),
            "send_attempt_finished_at": _format_timestamp(completed_at),
            "replay_allowed": False,
        },
    )


def load_openai_dotenv_assignment(path: Path) -> bytearray:
    """Select one OpenAI value from the strict approved mixed dotenv shape."""

    raw = _read_openai_dotenv_bytes(path)
    lines: list[bytearray] = []
    selected: bytearray | None = None
    lambda_seen = False
    try:
        lines = raw.split(b"\n")
        for line in lines:
            if line.endswith(b"\r"):
                line.pop()
            stripped = line.strip()
            name: bytearray | None = None
            value: bytearray | None = None
            try:
                if not stripped or stripped.startswith(b"#"):
                    continue
                if stripped != line:
                    raise ModelMetadataReceiptError("OpenAI dotenv syntax is unsupported")
                separator = stripped.find(b"=")
                if separator <= 0:
                    raise ModelMetadataReceiptError("OpenAI dotenv syntax is unsupported")
                name = stripped[:separator]
                value = stripped[separator + 1 :]
                if name != _OPENAI_DOTENV_ASSIGNMENT and name != _LAMBDA_DOTENV_ASSIGNMENT:
                    raise ModelMetadataReceiptError("OpenAI dotenv assignment name is unsupported")
                if _DOTENV_VALUE.fullmatch(value) is None:
                    raise ModelMetadataReceiptError("OpenAI dotenv value syntax is unsupported")
                if name == _OPENAI_DOTENV_ASSIGNMENT:
                    if selected is not None:
                        raise ModelMetadataReceiptError("OPENAI_API_KEY assignment is ambiguous")
                    selected = bytearray(value)
                else:
                    if lambda_seen:
                        raise ModelMetadataReceiptError("LAMBDA_API_KEY assignment is ambiguous")
                    lambda_seen = True
            finally:
                if value is not None:
                    _destroy_bytearray(value)
                if name is not None:
                    _destroy_bytearray(name)
                _destroy_bytearray(stripped)
        if selected is None:
            raise ModelMetadataReceiptError("OPENAI_API_KEY assignment is missing")
        result = selected
        selected = None
        return result
    finally:
        if selected is not None:
            _destroy_bytearray(selected)
        for line in lines:
            _destroy_bytearray(line)
        _destroy_bytearray(raw)


def _destroy_bytearray(value: bytearray) -> None:
    for index in range(len(value)):
        value[index] = 0
    value.clear()


def _finite_epoch(value: object, *, label: str) -> float:
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not math.isfinite(float(value))
        or float(value) < 0
    ):
        raise ModelMetadataReceiptError(f"{label} is malformed")
    return float(value)


def _format_timestamp(epoch: float) -> str:
    checked = _finite_epoch(epoch, label="timestamp")
    return (
        datetime_module.datetime.fromtimestamp(
            checked,
            tz=datetime_module.UTC,
        )
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


def _parse_timestamp(value: object, *, label: str) -> float:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ModelMetadataReceiptError(f"{label} is malformed")
    try:
        parsed = datetime_module.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ModelMetadataReceiptError(f"{label} is malformed") from exc
    if parsed.tzinfo is None:
        raise ModelMetadataReceiptError(f"{label} lacks a timezone")
    return _finite_epoch(parsed.timestamp(), label=label)


def _parse_exact_model(body: bytes) -> str:
    if not 0 < len(body) <= MODEL_METADATA_MAX_PRIVATE_BYTES:
        raise ModelMetadataReceiptError("model metadata response size is invalid")
    document = _decode_object(body, label="model metadata response", canonical=False)
    if document.get("id") != MODEL_METADATA_MODEL_ID:
        raise ModelMetadataReceiptError("returned model identity is not exact")
    return MODEL_METADATA_MODEL_ID


class OpenAIModelMetadataTransport:
    """A one-shot HTTPS transport with no retry, redirect, or pagination path."""

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
            raise ModelMetadataReceiptError("transport model identity drifted")
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
                MODEL_METADATA_PATH,
                headers={
                    "Accept": "application/json",
                    "Authorization": "Bearer " + credential.decode("ascii", "strict"),
                    "User-Agent": "giclab-t09-v12-model-metadata/1",
                },
            )
            response = connection.getresponse()
            if response.status != 200 or response.getheader("Location") is not None:
                raise ModelMetadataReceiptError("model metadata response was not exact HTTP 200")
            if response.getheader("Content-Type", "").split(";", 1)[0].casefold() != (
                "application/json"
            ):
                raise ModelMetadataReceiptError("model metadata response is not JSON")
            body = response.read(MODEL_METADATA_MAX_PRIVATE_BYTES + 1)
            if len(body) > MODEL_METADATA_MAX_PRIVATE_BYTES:
                raise ModelMetadataReceiptError("model metadata response exceeds its cap")
            return ModelMetadataResponse(
                status=response.status,
                body=body,
                response_completed_at=self._clock(),
            )
        except (OSError, ssl.SSLError, http.client.HTTPException) as exc:
            raise ModelMetadataReceiptError(
                "model metadata request outcome is unavailable"
            ) from exc
        finally:
            with contextlib.suppress(OSError):
                connection.close()


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
    """Perform exactly one send attempt and seal exactly one receipt."""

    _require_hex(repository_commit, length=40, label="repository commit")
    _require_hex(repository_tree, length=40, label="repository tree")
    for label, value in (
        ("plan SHA-256", plan_sha256),
        ("authorization source SHA-256", authorization_source_sha256),
        ("authorization overlay SHA-256", authorization_overlay_sha256),
        ("public price SHA-256", public_price_contract_sha256),
        ("public deprecation SHA-256", public_deprecation_observation_sha256),
    ):
        _require_hex(value, length=64, label=label)
    if (
        provider_contract_version != "V12"
        or plan_id != MODEL_METADATA_PLAN_ID
        or host_run_id != MODEL_METADATA_HOST_RUN_ID
        or not authorization_reference.startswith("AUTH-T09-V12-")
    ):
        raise ModelMetadataReceiptError("receipt identity is not exact V12")
    _validate_private_parent(output, label="receipt output")
    if os.path.lexists(output):
        raise ModelMetadataReceiptError("receipt output is not fresh")
    overlay = validate_model_metadata_authorization_overlay(
        authorization_overlay,
        contract=_V12Identity(),
        package_commit=repository_commit,
        package_tree=repository_tree,
        plan_sha256=plan_sha256,
    )
    observed_overlay_sha = model_metadata_authorization_overlay_sha256(authorization_overlay)
    if (
        overlay.get("model_metadata_receipt_sha256") is not None
        or observed_overlay_sha != authorization_overlay_sha256
        or overlay.get("authorization_reference") != authorization_reference
        or overlay.get("authorization_source_sha256") != authorization_source_sha256
        or overlay.get("public_price_contract_sha256") != public_price_contract_sha256
        or overlay.get("public_deprecation_observation_sha256")
        != public_deprecation_observation_sha256
    ):
        raise ModelMetadataReceiptError("receipt authority binding drifted")

    credential = load_openai_dotenv_assignment(dotenv)
    try:
        request_started = _finite_epoch(clock(), label="request start")
        state_path = _reserve_authorization(
            authorization_overlay,
            reference=authorization_reference,
            overlay_sha256=observed_overlay_sha,
            requested_at=request_started,
        )
    except BaseException:
        _destroy_bytearray(credential)
        raise
    response: ModelMetadataResponse | None = None
    attempt_error: BaseException | None = None
    try:
        selected_transport = transport or OpenAIModelMetadataTransport(clock=clock)
        try:
            response = selected_transport.get_model_metadata(
                MODEL_METADATA_MODEL_ID,
                credential=credential,
            )
        except BaseException as exc:
            attempt_error = exc
        completed_for_state = (
            request_started
            if response is None
            else _finite_epoch(response.response_completed_at, label="response completion")
        )
        _finish_authorization_attempt(
            state_path,
            reference=authorization_reference,
            overlay_sha256=observed_overlay_sha,
            attempted_at=request_started,
            completed_at=max(request_started, completed_for_state),
        )
        if attempt_error is not None:
            raise ModelMetadataReceiptError(
                "model metadata request failed after its one send attempt"
            ) from attempt_error
        assert response is not None
        response_completed = _finite_epoch(
            response.response_completed_at,
            label="response completion",
        )
        if response.status != 200:
            raise ModelMetadataReceiptError("model metadata HTTP status was not exactly 200")
        returned_model = _parse_exact_model(response.body)
        receipt_created = _finite_epoch(clock(), label="receipt creation")
        if not request_started <= response_completed <= receipt_created:
            raise ModelMetadataReceiptError("receipt timestamp ordering drifted")
        receipt: dict[str, object] = {
            "schema_version": MODEL_METADATA_SCHEMA_VERSION,
            "receipt_type": MODEL_METADATA_RECEIPT_TYPE,
            "authorization_reference": authorization_reference,
            "authorization_source_sha256": authorization_source_sha256,
            "authorization_overlay_sha256": observed_overlay_sha,
            "repository_commit": repository_commit,
            "repository_tree": repository_tree,
            "plan_id": plan_id,
            "plan_sha256": plan_sha256,
            "provider_contract_version": provider_contract_version,
            "host_run_id": host_run_id,
            "model_endpoint": MODEL_METADATA_ENDPOINT,
            "requested_model_id": MODEL_METADATA_MODEL_ID,
            "returned_model_id": returned_model,
            "http_status": 200,
            "request_count": 1,
            "redirect_count": 0,
            "retry_count": 0,
            "pagination_count": 0,
            "request_started_at": _format_timestamp(request_started),
            "response_completed_at": _format_timestamp(response_completed),
            "receipt_created_at": _format_timestamp(receipt_created),
            "response_body_sha256": hashlib.sha256(response.body).hexdigest(),
            "public_price_contract_sha256": public_price_contract_sha256,
            "public_deprecation_observation_sha256": (public_deprecation_observation_sha256),
            "terminal_state": MODEL_METADATA_TERMINAL_STATE,
        }
        _write_private_exclusive(output, receipt)
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
    validation_policy: ModelMetadataReceiptValidationPolicy,
) -> dict[str, object]:
    if set(document) != MODEL_METADATA_RECEIPT_FIELDS:
        raise ModelMetadataReceiptError("receipt fields drifted")
    _reject_sensitive_fields(document)
    fixed: Mapping[str, object] = {
        "schema_version": MODEL_METADATA_SCHEMA_VERSION,
        "receipt_type": MODEL_METADATA_RECEIPT_TYPE,
        "provider_contract_version": "V12",
        "plan_id": contract.plan_id,
        "host_run_id": contract.host_run_id,
        "model_endpoint": MODEL_METADATA_ENDPOINT,
        "requested_model_id": MODEL_METADATA_MODEL_ID,
        "returned_model_id": MODEL_METADATA_MODEL_ID,
        "http_status": 200,
        "request_count": 1,
        "redirect_count": 0,
        "retry_count": 0,
        "pagination_count": 0,
        "terminal_state": MODEL_METADATA_TERMINAL_STATE,
    }
    if contract.version != "V12" or any(document.get(key) != value for key, value in fixed.items()):
        raise ModelMetadataReceiptError("receipt fixed semantics drifted")
    if (
        document.get("repository_commit") != package_commit
        or document.get("repository_tree") != package_tree
        or document.get("plan_sha256") != plan_sha256
    ):
        raise ModelMetadataReceiptError("receipt package or plan binding drifted")
    _require_hex(package_commit, length=40, label="package commit")
    _require_hex(package_tree, length=40, label="package tree")
    for field_name in (
        "authorization_source_sha256",
        "authorization_overlay_sha256",
        "plan_sha256",
        "response_body_sha256",
        "public_price_contract_sha256",
        "public_deprecation_observation_sha256",
    ):
        _require_hex(document.get(field_name), length=64, label=field_name)
    reference = _require_safe_id(
        document.get("authorization_reference"),
        label="authorization reference",
    )
    if not reference.startswith("AUTH-T09-V12-"):
        raise ModelMetadataReceiptError("receipt authorization is not V12")
    if expected_authorization_reference is not None and reference != (
        expected_authorization_reference
    ):
        raise ModelMetadataReceiptError("receipt authorization reference drifted")
    if (
        expected_authorization_source_sha256 is not None
        and document.get("authorization_source_sha256") != expected_authorization_source_sha256
    ):
        raise ModelMetadataReceiptError("receipt authorization source drifted")
    if (
        expected_authorization_overlay_sha256 is not None
        and document.get("authorization_overlay_sha256") != expected_authorization_overlay_sha256
    ):
        raise ModelMetadataReceiptError("receipt authorization overlay drifted")
    started = _parse_timestamp(document.get("request_started_at"), label="request start")
    completed = _parse_timestamp(
        document.get("response_completed_at"),
        label="response completion",
    )
    created = _parse_timestamp(document.get("receipt_created_at"), label="receipt creation")
    if not started <= completed <= created:
        raise ModelMetadataReceiptError("receipt timestamp ordering drifted")
    launch = (
        None
        if launch_started_at is None
        else _finite_epoch(
            launch_started_at,
            label="provider launch boundary",
        )
    )
    if launch is not None and (completed > launch or created > launch):
        raise ModelMetadataReceiptError("receipt was completed after provider launch")
    if validation_policy is ModelMetadataReceiptValidationPolicy.PRELAUNCH_FRESH:
        boundary = _finite_epoch(
            time.time() if now is None else now,
            label="freshness boundary",
        )
        if created > boundary or boundary - created > (MODEL_METADATA_PRELAUNCH_FRESHNESS_SECONDS):
            raise ModelMetadataReceiptError("receipt is stale at provider admission")
        if launch is not None and launch != boundary:
            raise ModelMetadataReceiptError("provider launch and freshness clocks differ")
    elif validation_policy is not ModelMetadataReceiptValidationPolicy.DURABLE_OFFLINE:
        raise ModelMetadataReceiptError("unknown receipt validation policy")
    return dict(document)


def admit_model_metadata_receipt_at_prelaunch_boundary(
    document: Mapping[str, object],
    *,
    boundary_epoch: float,
) -> None:
    """Apply only the final, in-memory time admission.

    The caller must first perform full immutable validation on freshly read
    receipt bytes. Sampling the boundary after that read leaves this function
    with no filesystem, subprocess, sleep, or network capability. Exactly
    1,800.0 seconds is admitted; any greater age is rejected.
    """

    boundary = _finite_epoch(boundary_epoch, label="provider launch boundary")
    completed = _parse_timestamp(
        document.get("response_completed_at"),
        label="response completion",
    )
    created = _parse_timestamp(document.get("receipt_created_at"), label="receipt creation")
    if completed > boundary or created > boundary:
        raise ModelMetadataReceiptError("receipt was completed after provider launch")
    if boundary - created > MODEL_METADATA_PRELAUNCH_FRESHNESS_SECONDS:
        raise ModelMetadataReceiptError("receipt is stale at provider admission")


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
    validation_policy: ModelMetadataReceiptValidationPolicy,
) -> dict[str, object]:
    """Validate canonical bytes and exact immutable or freshness bindings."""

    document = _load_private_object(path, label="model metadata receipt")
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
        validation_policy=validation_policy,
    )
    if authorization_overlay is not None:
        overlay = validate_model_metadata_authorization_overlay(
            authorization_overlay,
            contract=contract,
            package_commit=package_commit,
            package_tree=package_tree,
            plan_sha256=plan_sha256,
            require_receipt_binding=True,
        )
        overlay_sha = model_metadata_authorization_overlay_sha256(authorization_overlay)
        if (
            validated["authorization_reference"] != overlay["authorization_reference"]
            or validated["authorization_source_sha256"] != overlay["authorization_source_sha256"]
            or validated["authorization_overlay_sha256"] != overlay_sha
            or overlay["model_metadata_receipt_sha256"] != semantic_projection_sha256(validated)
        ):
            raise ModelMetadataReceiptError("receipt disagrees with its authorization overlay")
    return validated


def bind_model_metadata_receipt_to_authorization_overlay(
    path: Path,
    *,
    receipt_sha256: str,
) -> None:
    _require_hex(receipt_sha256, length=64, label="receipt SHA-256")
    overlay = _load_private_object(path, label="authorization overlay")
    if (
        set(overlay) != MODEL_METADATA_AUTHORIZATION_FIELDS
        or overlay.get("model_metadata_receipt_sha256") is not None
    ):
        raise ModelMetadataReceiptError("authorization overlay was already receipt-bound")
    updated = dict(overlay)
    updated["model_metadata_receipt_sha256"] = receipt_sha256
    _rewrite_held_private(path, updated)


def copy_model_metadata_receipt(source: Path, output: Path) -> str:
    document = _load_private_object(source, label="model metadata receipt")
    if set(document) != MODEL_METADATA_RECEIPT_FIELDS:
        raise ModelMetadataReceiptError("receipt fields drifted")
    _write_private_exclusive(output, document)
    return semantic_projection_sha256(document)


def model_metadata_receipt_sha256(path: Path) -> str:
    document = _load_private_object(path, label="model metadata receipt")
    if set(document) != MODEL_METADATA_RECEIPT_FIELDS:
        raise ModelMetadataReceiptError("receipt fields drifted")
    return semantic_projection_sha256(document)
