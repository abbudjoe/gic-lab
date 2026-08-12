"""Future one-shot Lambda/Jupyter bootstrap for the T07 bounded smoke.

Importing this file is inert.  The executable path requires a fresh, separately
authorized binding, a fresh remote root, and a secret file supplied outside the
bundle.  It never performs a Lambda mutation; the user remains responsible for the
manual console lifecycle in the bound runbook.
"""

from __future__ import annotations

import argparse
import base64
import contextlib
import hashlib
import http.client
import io
import json
import math
import os
import platform
import re
import selectors
import shutil
import stat
import subprocess
import sys
import tarfile
import time
import urllib.parse
import zipfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path, PurePosixPath
from types import ModuleType
from typing import Final, cast

MAX_PLAN_BYTES: Final = 1_048_576
MAX_AUTHORIZATION_BYTES: Final = 65_536
MAX_UPLOAD_BUNDLE_BYTES: Final = 8_388_608
MAX_UPLOAD_BUNDLE_FILES: Final = 36
MAX_COMMAND_OUTPUT_BYTES: Final = 33_554_432
MAX_COMMAND_CALLS: Final = 128
CLEANUP_RESERVED_CALLS: Final = 48
CLEANUP_RESERVED_OUTPUT_BYTES: Final = 8_388_608
MAX_DOWNLOAD_BYTES: Final = 2_147_483_648
MAX_EVIDENCE_BYTES: Final = 268_435_456
MAX_FAILURE_EVIDENCE_BYTES: Final = 268_435_456
MAX_EARLY_FAILURE_EVIDENCE_BYTES: Final = 1_048_576
MAX_EVIDENCE_FILES: Final = 4_096
MAX_ATTEMPT_PAYLOAD_BYTES: Final = 67_108_864
MAX_RUNTIME_DISK_INCREMENT_BYTES: Final = 17_179_869_184
MIN_REMOTE_FREE_BYTES: Final = 34_359_738_368
HARD_PROVIDER_WALL_SECONDS: Final = 3_600
TERMINATION_HEADROOM_SECONDS: Final = 300
SCHEMA_VERSION: Final = "0.1.0"
PLAN_ID: Final = "PLAN-T07-BOUNDED-SIRA-SMOKE-V2"
HOST_RUN_ID: Final = "RUN-T07-BOUNDED-HOST-0002"
BRANCH: Final = "phase-1/sira-smoke-bounded"
REACTIVE_RUN_ID: Final = "RUN-T07-BOUNDED-SIRA-REACTIVE-0002"
SIMULATIVE_RUN_ID: Final = "RUN-T07-BOUNDED-SIRA-SIMULATIVE-0002"
MODEL: Final = "gpt-4o-2024-11-20"
SELECTED_IMAGE_ALIAS: Final = "img-0032"
SELECTED_IMAGE_FAMILY: Final = "lambda-stack-22-04"
SELECTED_IMAGE_VERSION: Final = "22.4.5-2141"
LIMITS_SHA256: Final = "316ae4bbd6ac83ac78cf54cef29763cf5d9aac716631b149ab1c7ceb8b0a8703"
REMOTE_BOOTSTRAP_FILE: Final = Path("/home/ubuntu/t07-bounded-bootstrap.py")
REMOTE_BUNDLE_ARCHIVE: Final = Path("/home/ubuntu/t07-bounded-repository.tar")
REMOTE_BUNDLE_ROOT: Final = Path("/home/ubuntu/t07-bounded-bundle")
REMOTE_PLAN_FILE: Final = REMOTE_BUNDLE_ROOT / (
    "containers/sira-smoke/bounded/bounded-smoke-plan-v2.json"
)
REMOTE_CONTRACT_FILE: Final = REMOTE_BUNDLE_ROOT / "src/giclab/harness/t07_bounded_smoke.py"
REMOTE_AUTHORIZATION_FILE: Final = Path("/home/ubuntu/t07-bounded-authorization.json")
REMOTE_RELEASE_FILE: Final = Path("/home/ubuntu/t07-bounded-bootstrap-release.json")
REMOTE_SECRET_FILE: Final = Path("/home/ubuntu/.config/giclab/sira_api_key")
REMOTE_OUTPUT_ROOT: Final = Path("/home/ubuntu/t07-bounded-output-0002")
UPLOAD_MANIFEST_NAME: Final = "BUNDLE_MANIFEST.json"
PRESECRET_FAILURE_STAGES: Final = frozenset(
    {
        "run_identity_reservation",
        "inherited_environment_guard",
        "invocation_validation",
        "authorization_validation",
        "release_validation",
        "bootstrap_hash_validation",
        "archive_validation",
        "manifest_validation",
        "plan_validation",
        "bundle_extraction",
        "contract_hash_validation",
        "contract_import",
        "contract_validation",
        "secret_target_validation",
        "normal_failure_packaging",
    }
)
EXECUTION_FAILURE_STAGES: Final = frozenset(
    {
        "host_environment",
        "secret_read",
        "build_context",
        "image_build",
        "browser_preflight",
        "model_preflight",
        "reactive_condition",
        "simulative_condition",
        "pair_validation",
        "evidence_packaging",
    }
)
FAILURE_CODES: Final = frozenset(
    {
        "bootstrap_contract_rejected",
        "command_nonzero_exit",
        "command_start_failure",
        "command_timeout",
        "command_supervision_failure",
        "command_output_cap",
        "credential_material_detected",
        "filesystem_io_failure",
        "unexpected_internal_failure",
    }
)
_HEX40 = re.compile(r"^[a-f0-9]{40}$")
_HEX64 = re.compile(r"^[a-f0-9]{64}$")
_IMAGE_ID = re.compile(r"^sha256:[a-f0-9]{64}$")
_AUTHORIZATION = re.compile(r"^AUTH-T07-BOUNDED-SIRA-SMOKE-V2-[A-Z0-9._-]{3,80}$")
_SECRET_SHAPES: Final = (
    re.compile(rb"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(
        rb"(?im)^[ \t]*[A-Z0-9_]*(?:API_"
        rb"KEY|TO"
        rb"KEN|SE"
        rb"CRET)[ \t]*=[^\r\n]+$"
    ),
    re.compile(
        rb"""(?ix)["']?(?:(?:api|access|private)[ _-]?key|"""
        rb"""token|secret|password|cookie|credential)"""
        rb"""["']?\s*[:=]\s*["']?[a-z0-9._~+/=-]{8,}"""
    ),
    re.compile(
        rb"""(?isx)["']?(?:key|label|name|type)["']?\s*:\s*"""
        rb"""["']?(?:(?:api|access|private)[ _-]?key|token|secret|password|cookie|"""
        rb"""credential|authorization)"""
        rb"""["']?[\s\S]{0,256}?["']?value["']?\s*:\s*"""
        rb"""["']?[a-z0-9._~+/=-]{8,}"""
    ),
    re.compile(
        rb"""(?isx)["']?value["']?\s*:\s*["']?"""
        rb"""[a-z0-9._~+/=-]{8,}["']?[\s\S]{0,256}?"""
        rb"""["']?(?:key|label|name|type)["']?\s*:\s*"""
        rb"""["']?(?:(?:api|access|private)[ _-]?key|token|secret|password|cookie|"""
        rb"""credential|authorization)"""
    ),
)


def _artifact_sensitive_key(name: str) -> bool:
    normalized = re.sub(r"[^a-z0-9]+", "_", name.casefold()).strip("_")
    if normalized in {
        "api_key",
        "access_key",
        "private_key",
        "token",
        "password",
        "cookie",
        "credential",
        "secret",
        "authorization",
    }:
        return True
    return any(
        normalized.endswith("_" + suffix)
        for suffix in (
            "api_key",
            "access_key",
            "private_key",
            "token",
            "password",
            "cookie",
            "credential",
            "secret",
            "authorization",
        )
    )


def _json_contains_artifact_secret(value: object) -> bool:
    if isinstance(value, Mapping):
        discriminator_sensitive = any(
            isinstance(key, str)
            and key.casefold() in {"key", "label", "name", "type"}
            and isinstance(child, str)
            and _artifact_sensitive_key(child)
            for key, child in value.items()
        )
        candidate = value.get("value")
        if (
            discriminator_sensitive
            and isinstance(candidate, str)
            and len(candidate) >= 8
            and _AUTHORIZATION.fullmatch(candidate) is None
        ):
            return True
        for key, child in value.items():
            if (
                isinstance(key, str)
                and _artifact_sensitive_key(key)
                and isinstance(child, str)
                and len(child) >= 8
                and not (
                    key.casefold().endswith("authorization")
                    and _AUTHORIZATION.fullmatch(child) is not None
                )
            ):
                return True
            if _json_contains_artifact_secret(child):
                return True
        return False
    if isinstance(value, list):
        return any(_json_contains_artifact_secret(item) for item in value)
    return False


def _contains_artifact_secret(encoded: bytes) -> bool:
    if any(pattern.search(encoded) for pattern in _SECRET_SHAPES):
        return True
    if len(encoded) > 16_777_216:
        return False
    try:
        document = json.loads(encoded)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return False
    return _json_contains_artifact_secret(document)


def _secret_derivatives(secret_value: bytes) -> tuple[bytes, ...]:
    """Return exact deterministic representations forbidden from retained evidence."""

    if not secret_value:
        raise BootstrapError("secret derivative scan requires a nonempty secret")
    digest = hashlib.sha256(secret_value).digest()
    standard_base64 = base64.b64encode(secret_value)
    urlsafe_base64 = base64.urlsafe_b64encode(secret_value)
    markers = {
        secret_value,
        secret_value.hex().encode("ascii"),
        secret_value.hex().upper().encode("ascii"),
        standard_base64,
        standard_base64.rstrip(b"="),
        urlsafe_base64,
        urlsafe_base64.rstrip(b"="),
        digest,
        digest.hex().encode("ascii"),
        digest.hex().upper().encode("ascii"),
    }
    return tuple(sorted(markers, key=lambda value: (len(value), value), reverse=True))


def _contains_secret_derivative(encoded: bytes, secret_value: bytes) -> bool:
    return any(marker in encoded for marker in _secret_derivatives(secret_value))


class BootstrapError(RuntimeError):
    """The one-shot bounded bootstrap failed closed with a secret-safe code."""

    def __init__(
        self,
        message: str,
        *,
        failure_code: str = "bootstrap_contract_rejected",
    ) -> None:
        if failure_code not in FAILURE_CODES:
            raise ValueError("bootstrap failure code is outside the closed taxonomy")
        super().__init__(message)
        self.failure_code = failure_code


def _sanitized_failure_code(exc: BaseException) -> str:
    if isinstance(exc, BootstrapError):
        return exc.failure_code
    if isinstance(exc, OSError):
        return "filesystem_io_failure"
    return "unexpected_internal_failure"


@dataclass(frozen=True, slots=True)
class CommandResult:
    argv: tuple[str, ...]
    returncode: int
    stdout: bytes
    stderr: bytes
    elapsed_seconds: float


@dataclass(slots=True)
class CommandMeter:
    """Aggregate meter with a non-borrowable cleanup reserve and durable ledger."""

    max_calls: int
    output_cap: int
    cleanup_reserved_calls: int = CLEANUP_RESERVED_CALLS
    cleanup_reserved_output_bytes: int = CLEANUP_RESERVED_OUTPUT_BYTES
    ledger_path: Path | None = None
    call_count: int = 0
    output_bytes: int = 0
    work_call_count: int = 0
    cleanup_call_count: int = 0
    work_output_bytes: int = 0
    cleanup_output_bytes: int = 0
    event_count: int = 0

    def __post_init__(self) -> None:
        if (
            not 0 < self.cleanup_reserved_calls < self.max_calls
            or not 0 < self.cleanup_reserved_output_bytes < self.output_cap
        ):
            raise BootstrapError("cleanup command reserve is invalid")
        if self.ledger_path is not None:
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
            descriptor = os.open(self.ledger_path, flags, 0o600)
            os.close(descriptor)
            self._append(
                "meter_started",
                scope=None,
                argv_sha256=None,
                returncode=None,
                stdout_bytes=None,
                stderr_bytes=None,
                elapsed_ms=None,
                failure_code=None,
            )

    def _append(
        self,
        event_type: str,
        *,
        scope: str | None,
        argv_sha256: str | None,
        returncode: int | None,
        stdout_bytes: int | None,
        stderr_bytes: int | None,
        elapsed_ms: int | None,
        failure_code: str | None,
    ) -> None:
        if self.ledger_path is None:
            return
        self.event_count += 1
        event = {
            "schema_version": "0.1.0",
            "event_sequence": self.event_count,
            "event_type": event_type,
            "scope": scope,
            "argv_sha256": argv_sha256,
            "returncode": returncode,
            "stdout_bytes": stdout_bytes,
            "stderr_bytes": stderr_bytes,
            "elapsed_ms": elapsed_ms,
            "failure_code": failure_code,
            "aggregate_call_count": self.call_count,
            "aggregate_output_bytes": self.output_bytes,
            "work_call_count": self.work_call_count,
            "work_output_bytes": self.work_output_bytes,
            "cleanup_call_count": self.cleanup_call_count,
            "cleanup_output_bytes": self.cleanup_output_bytes,
            "aggregate_call_cap": self.max_calls,
            "aggregate_output_cap_bytes": self.output_cap,
            "cleanup_reserved_calls": self.cleanup_reserved_calls,
            "cleanup_reserved_output_bytes": self.cleanup_reserved_output_bytes,
        }
        encoded = json.dumps(event, allow_nan=False, separators=(",", ":"), sort_keys=True).encode()
        encoded += b"\n"
        descriptor = os.open(
            self.ledger_path,
            os.O_WRONLY | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0),
        )
        try:
            written = os.write(descriptor, encoded)
            if written != len(encoded):
                raise BootstrapError("command meter append was incomplete")
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def begin_call(self, scope: str, argv_sha256: str) -> None:
        if scope not in {"work", "cleanup"}:
            raise BootstrapError("command budget scope is invalid")
        if self.call_count >= self.max_calls:
            raise BootstrapError("bounded command call cap is exhausted")
        if scope == "work" and self.work_call_count >= self.max_calls - self.cleanup_reserved_calls:
            raise BootstrapError("bounded work command call cap preserves cleanup reserve")
        if scope == "cleanup" and self.cleanup_call_count >= self.cleanup_reserved_calls:
            raise BootstrapError("bounded cleanup command call cap is exhausted")
        self.call_count += 1
        if scope == "work":
            self.work_call_count += 1
        else:
            self.cleanup_call_count += 1
        self._append(
            "command_started",
            scope=scope,
            argv_sha256=argv_sha256,
            returncode=None,
            stdout_bytes=None,
            stderr_bytes=None,
            elapsed_ms=None,
            failure_code=None,
        )

    def add_output(self, scope: str, count: int) -> None:
        self.output_bytes += count
        if scope == "work":
            self.work_output_bytes += count
        else:
            self.cleanup_output_bytes += count
        if self.output_bytes > self.output_cap:
            raise BootstrapError(
                "bounded command output exceeded its aggregate cap",
                failure_code="command_output_cap",
            )
        if (
            scope == "work"
            and self.work_output_bytes > self.output_cap - self.cleanup_reserved_output_bytes
        ):
            raise BootstrapError(
                "bounded work output cap preserves cleanup reserve",
                failure_code="command_output_cap",
            )
        if scope == "cleanup" and self.cleanup_output_bytes > self.cleanup_reserved_output_bytes:
            raise BootstrapError(
                "bounded cleanup command output cap is exhausted",
                failure_code="command_output_cap",
            )

    def finish_call(
        self,
        scope: str,
        argv_sha256: str,
        result: CommandResult | None,
        *,
        failure_code: str | None,
    ) -> None:
        returncode = result.returncode if result is not None else None
        failed = result is None or failure_code is not None
        if failed != (failure_code is not None) or (
            failure_code is not None and failure_code not in FAILURE_CODES
        ):
            raise BootstrapError("command failure receipt classification drifted")
        self._append(
            "command_failed" if failed else "command_completed",
            scope=scope,
            argv_sha256=argv_sha256,
            returncode=returncode,
            stdout_bytes=len(result.stdout) if result is not None else None,
            stderr_bytes=len(result.stderr) if result is not None else None,
            elapsed_ms=(
                max(0, math.ceil(result.elapsed_seconds * 1_000)) if result is not None else None
            ),
            failure_code=failure_code,
        )


class CommandRunner:
    """Shell-free subprocess runner with one monotonic deadline and output cap."""

    def __init__(
        self,
        *,
        deadline: float,
        output_cap: int = MAX_COMMAND_OUTPUT_BYTES,
        max_calls: int = 128,
        meter: CommandMeter | None = None,
        scope: str = "work",
    ) -> None:
        self.deadline = deadline
        self.meter = meter or CommandMeter(max_calls=max_calls, output_cap=output_cap)
        if scope not in {"work", "cleanup"}:
            raise BootstrapError("command runner scope is invalid")
        self.scope = scope

    @property
    def call_count(self) -> int:
        return self.meter.call_count

    @property
    def output_bytes(self) -> int:
        return self.meter.output_bytes

    def remaining(self) -> float:
        value = self.deadline - time.monotonic()
        if value <= 0:
            raise BootstrapError("bootstrap deadline is exhausted")
        return value

    def run(
        self,
        argv: Sequence[str],
        *,
        cwd: Path,
        timeout: float | None = None,
        check: bool = True,
    ) -> CommandResult:
        command = tuple(argv)
        if not command or any(not isinstance(item, str) or not item for item in command):
            raise BootstrapError("command array is invalid")
        argv_sha256 = _sha256(json.dumps(list(command), separators=(",", ":")).encode())
        self.meter.begin_call(self.scope, argv_sha256)
        try:
            result = self._run_started(
                command,
                cwd=cwd,
                timeout=timeout,
            )
        except BaseException as exc:
            self.meter.finish_call(
                self.scope,
                argv_sha256,
                None,
                failure_code=_sanitized_failure_code(exc),
            )
            raise
        failure_code = "command_nonzero_exit" if check and result.returncode != 0 else None
        self.meter.finish_call(
            self.scope,
            argv_sha256,
            result,
            failure_code=failure_code,
        )
        if check and result.returncode != 0:
            raise BootstrapError(
                "bounded command returned failure",
                failure_code="command_nonzero_exit",
            )
        return result

    def _run_started(
        self,
        command: tuple[str, ...],
        *,
        cwd: Path,
        timeout: float | None,
    ) -> CommandResult:
        allowed = self.remaining()
        if timeout is not None:
            if not isinstance(timeout, (int, float)) or timeout <= 0:
                raise BootstrapError("command timeout is outside the remaining deadline")
            allowed = min(float(timeout), allowed)
        environment = {
            "HOME": str(cwd),
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
            "PYTHONDONTWRITEBYTECODE": "1",
        }
        started = time.monotonic()
        try:
            process = subprocess.Popen(
                command,
                cwd=cwd,
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=False,
            )
        except OSError:
            raise BootstrapError(
                "bounded command could not start",
                failure_code="command_start_failure",
            ) from None
        selector = selectors.DefaultSelector()
        if process.stdout is None or process.stderr is None:
            process.kill()
            process.wait()
            selector.close()
            raise BootstrapError("bounded command pipes are unavailable")
        selector.register(process.stdout, selectors.EVENT_READ, "stdout")
        selector.register(process.stderr, selectors.EVENT_READ, "stderr")
        output = {"stdout": bytearray(), "stderr": bytearray()}
        try:
            while selector.get_map():
                elapsed = time.monotonic() - started
                if elapsed >= allowed:
                    process.kill()
                    raise BootstrapError(
                        "bounded command exceeded its wall limit",
                        failure_code="command_timeout",
                    )
                for key, _ in selector.select(min(0.1, allowed - elapsed)):
                    chunk = os.read(key.fd, 65_536)
                    if not chunk:
                        selector.unregister(key.fileobj)
                        continue
                    output[key.data].extend(chunk)
                    try:
                        self.meter.add_output(self.scope, len(chunk))
                    except BootstrapError:
                        process.kill()
                        raise
            returncode = process.wait(timeout=max(0.1, allowed - (time.monotonic() - started)))
        except BootstrapError:
            process.kill()
            process.wait()
            raise
        except (OSError, subprocess.SubprocessError):
            process.kill()
            process.wait()
            raise BootstrapError(
                "bounded command supervision failed",
                failure_code="command_supervision_failure",
            ) from None
        finally:
            selector.close()
        result = CommandResult(
            command,
            returncode,
            bytes(output["stdout"]),
            bytes(output["stderr"]),
            time.monotonic() - started,
        )
        return result


def _load_contract(path: Path, encoded: bytes) -> ModuleType:
    """Execute the exact contract bytes already held and hash-verified by the caller."""

    resolved = path.resolve(strict=True)
    module = ModuleType("t07_bounded_contract")
    module.__file__ = str(resolved)
    module.__package__ = ""
    sys.modules[module.__name__] = module
    try:
        code = compile(encoded, str(resolved), "exec", dont_inherit=True)
        exec(code, module.__dict__)
    except BaseException:
        sys.modules.pop(module.__name__, None)
        raise
    return module


def _strict_json(encoded: bytes, *, context: str) -> dict[str, object]:
    def pairs(items: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in items:
            if key in result:
                raise BootstrapError(f"{context} contains a duplicate key")
            result[key] = value
        return result

    try:
        value = json.loads(encoded, object_pairs_hook=pairs)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise BootstrapError(f"{context} is not strict JSON") from None
    if not isinstance(value, dict):
        raise BootstrapError(f"{context} must be an object")
    return value


def _read_regular(path: Path, *, max_bytes: int) -> bytes:
    try:
        linked = path.lstat()
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except OSError:
        raise BootstrapError("required bootstrap input is unavailable") from None
    try:
        opened = os.fstat(descriptor)
        if (
            not stat.S_ISREG(linked.st_mode)
            or stat.S_ISLNK(linked.st_mode)
            or linked.st_nlink != 1
            or (linked.st_dev, linked.st_ino) != (opened.st_dev, opened.st_ino)
            or opened.st_size > max_bytes
        ):
            raise BootstrapError("required bootstrap input identity is unsafe")
        output = bytearray()
        while True:
            chunk = os.read(descriptor, min(65_536, max_bytes + 1 - len(output)))
            if not chunk:
                break
            output.extend(chunk)
            if len(output) > max_bytes:
                raise BootstrapError("required bootstrap input exceeds its cap")
        if len(output) != opened.st_size:
            raise BootstrapError("required bootstrap input changed while held")
        return bytes(output)
    finally:
        os.close(descriptor)


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _write_all(descriptor: int, encoded: bytes) -> None:
    view = memoryview(encoded)
    offset = 0
    while offset < len(view):
        written = os.write(descriptor, view[offset:])
        if written <= 0:
            raise BootstrapError(
                "bounded file write made no progress",
                failure_code="filesystem_io_failure",
            )
        offset += written


def _bounded_regular_files(root: Path, *, context: str) -> list[Path]:
    files: list[Path] = []
    entries = 0
    for path in root.rglob("*"):
        entries += 1
        if entries > MAX_EVIDENCE_FILES:
            raise BootstrapError(f"{context} exceeds the filesystem-entry cap")
        if path.is_symlink():
            raise BootstrapError(f"{context} contains a symlink")
        if not path.is_file():
            continue
        files.append(path)
    return sorted(files)


def _validate_invocation_paths(args: argparse.Namespace) -> None:
    expected = {
        "bundle_archive": REMOTE_BUNDLE_ARCHIVE,
        "plan": REMOTE_PLAN_FILE,
        "contract_file": REMOTE_CONTRACT_FILE,
        "authorization": REMOTE_AUTHORIZATION_FILE,
        "bootstrap_release": REMOTE_RELEASE_FILE,
        "bundle_root": REMOTE_BUNDLE_ROOT,
        "secret_file": REMOTE_SECRET_FILE,
        "output_root": REMOTE_OUTPUT_ROOT,
    }
    if any(Path(getattr(args, name)) != path for name, path in expected.items()):
        raise BootstrapError("remote bootstrap invocation path contract drifted")


def _validate_bootstrap_file(*, argv_sha256: str, release_sha256: object) -> None:
    source = Path(__file__)
    if source != REMOTE_BOOTSTRAP_FILE or source.resolve(strict=True) != source:
        raise BootstrapError("remote bootstrap file path is not exact and canonical")
    encoded = _read_regular(source, max_bytes=MAX_UPLOAD_BUNDLE_BYTES)
    if (
        not isinstance(release_sha256, str)
        or _HEX64.fullmatch(argv_sha256) is None
        or argv_sha256 != release_sha256
        or _sha256(encoded) != release_sha256
    ):
        raise BootstrapError("remote bootstrap file hash drifted")


def _safe_bundle_member_name(name: str) -> str:
    path = PurePosixPath(name)
    if (
        not name
        or "\\" in name
        or path.is_absolute()
        or path.as_posix() != name
        or any(
            part in {"", ".", "..", ".git", ".env", "artifacts", ".secrets"} for part in path.parts
        )
    ):
        raise BootstrapError("upload bundle member path is unsafe")
    return name


def _read_validated_upload_archive(
    args: argparse.Namespace,
    *,
    release_archive_sha256: object,
) -> dict[str, bytes]:
    archive_encoded = _read_regular(args.bundle_archive, max_bytes=MAX_UPLOAD_BUNDLE_BYTES)
    if (
        not isinstance(release_archive_sha256, str)
        or _HEX64.fullmatch(args.bundle_archive_sha256) is None
        or args.bundle_archive_sha256 != release_archive_sha256
        or _sha256(archive_encoded) != release_archive_sha256
    ):
        raise BootstrapError("upload bundle archive hash drifted")
    destination = Path(args.bundle_root)
    if destination.exists() or destination.is_symlink():
        raise BootstrapError("upload bundle extraction root is not fresh")
    try:
        with tarfile.open(fileobj=io.BytesIO(archive_encoded), mode="r:") as archive:
            members = archive.getmembers()
            if len(members) != MAX_UPLOAD_BUNDLE_FILES:
                raise BootstrapError("upload bundle member count drifted")
            captured: dict[str, bytes] = {}
            total = 0
            for member in members:
                name = _safe_bundle_member_name(member.name)
                if (
                    name in captured
                    or not member.isfile()
                    or member.size < 0
                    or member.mode != 0o444
                    or member.mtime != 0
                    or member.uid != 0
                    or member.gid != 0
                    or member.pax_headers
                ):
                    raise BootstrapError("upload bundle member metadata drifted")
                total += member.size
                if total > MAX_UPLOAD_BUNDLE_BYTES:
                    raise BootstrapError("upload bundle extracted bytes exceed their cap")
                reader = archive.extractfile(member)
                if reader is None:
                    raise BootstrapError("upload bundle member is unreadable")
                encoded = reader.read(MAX_UPLOAD_BUNDLE_BYTES + 1)
                if len(encoded) != member.size:
                    raise BootstrapError("upload bundle member size drifted")
                captured[name] = encoded
    except (tarfile.TarError, OSError):
        raise BootstrapError("upload bundle archive is invalid") from None
    return captured


def _validate_upload_manifest(
    args: argparse.Namespace,
    captured: Mapping[str, bytes],
    *,
    release_manifest_sha256: object,
    execution_commit: object,
) -> dict[str, object]:
    manifest_encoded = captured.get(UPLOAD_MANIFEST_NAME)
    if (
        manifest_encoded is None
        or not isinstance(release_manifest_sha256, str)
        or _HEX64.fullmatch(args.bundle_manifest_sha256) is None
        or args.bundle_manifest_sha256 != release_manifest_sha256
        or _sha256(manifest_encoded) != release_manifest_sha256
    ):
        raise BootstrapError("upload bundle manifest hash drifted")
    manifest = _strict_json(manifest_encoded, context="upload bundle manifest")
    raw_rows = manifest.get("files")
    if not isinstance(raw_rows, list):
        raise BootstrapError("upload bundle manifest files are invalid")
    expected_keys = {
        "schema_version",
        "plan_id",
        "host_run_id",
        "execution_commit",
        "plan_sha256",
        "files",
        "file_count",
        "archive_member_count",
        "payload_bytes",
        "tracked_files_only",
        "forbidden_untracked_inputs_absent",
    }
    rows: dict[str, tuple[int, str]] = {}
    payload_bytes = 0
    for raw in raw_rows:
        if not isinstance(raw, Mapping) or set(raw) != {"path", "bytes", "sha256"}:
            raise BootstrapError("upload bundle manifest row is invalid")
        name = _safe_bundle_member_name(str(raw.get("path")))
        byte_count = raw.get("bytes")
        sha256 = raw.get("sha256")
        if (
            name == UPLOAD_MANIFEST_NAME
            or name in rows
            or type(byte_count) is not int
            or byte_count < 0
            or not isinstance(sha256, str)
            or _HEX64.fullmatch(sha256) is None
        ):
            raise BootstrapError("upload bundle manifest row drifted")
        member_encoded = captured.get(name)
        if (
            member_encoded is None
            or len(member_encoded) != byte_count
            or _sha256(member_encoded) != sha256
        ):
            raise BootstrapError("upload bundle member differs from its manifest")
        rows[name] = (byte_count, sha256)
        payload_bytes += byte_count
    if (
        set(manifest) != expected_keys
        or manifest.get("schema_version") != "0.1.0"
        or manifest.get("plan_id") != "PLAN-T07-BOUNDED-SIRA-SMOKE-V2"
        or manifest.get("host_run_id") != "RUN-T07-BOUNDED-HOST-0002"
        or manifest.get("execution_commit") != execution_commit
        or manifest.get("plan_sha256") != args.plan_sha256
        or manifest.get("file_count") != len(rows)
        or manifest.get("archive_member_count") != len(captured)
        or manifest.get("payload_bytes") != payload_bytes
        or manifest.get("tracked_files_only") is not True
        or manifest.get("forbidden_untracked_inputs_absent") is not True
        or set(captured) != {UPLOAD_MANIFEST_NAME, *rows}
    ):
        raise BootstrapError("upload bundle manifest contract drifted")
    return manifest


def _validate_upload_bundle(
    args: argparse.Namespace,
    *,
    release_archive_sha256: object,
    release_manifest_sha256: object,
    execution_commit: object,
) -> tuple[dict[str, object], dict[str, bytes]]:
    """Validate both upload layers for direct unit callers.

    The executable path invokes the two helpers separately so its durable failure
    evidence distinguishes archive failures from manifest failures.
    """

    captured = _read_validated_upload_archive(
        args,
        release_archive_sha256=release_archive_sha256,
    )
    manifest = _validate_upload_manifest(
        args,
        captured,
        release_manifest_sha256=release_manifest_sha256,
        execution_commit=execution_commit,
    )
    return manifest, captured


def _extract_validated_bundle(captured: Mapping[str, bytes]) -> None:
    destination = REMOTE_BUNDLE_ROOT
    if destination.exists() or destination.is_symlink():
        raise BootstrapError("upload bundle extraction root is not fresh")
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    destination.mkdir(mode=0o700, exist_ok=False)
    for name, encoded in captured.items():
        target = destination / name
        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        _write_bytes(target, encoded, cap=MAX_UPLOAD_BUNDLE_BYTES)


def _validate_bundle_against_plan(
    manifest: Mapping[str, object],
    captured: Mapping[str, bytes],
    *,
    plan: Mapping[str, object],
    plan_sha256: str,
    execution_commit: object,
) -> None:
    raw_rows = manifest.get("files")
    if not isinstance(raw_rows, list):
        raise BootstrapError("upload bundle manifest files are unavailable")
    observed = {
        str(row["path"]): {"bytes": row["bytes"], "sha256": row["sha256"]}
        for row in raw_rows
        if isinstance(row, Mapping) and set(row) == {"path", "bytes", "sha256"}
    }
    implementation = plan.get("implementation")
    if not isinstance(implementation, Mapping):
        raise BootstrapError("plan implementation binding is unavailable")
    artifacts = implementation.get("artifacts")
    if not isinstance(artifacts, list):
        raise BootstrapError("plan artifact binding is unavailable")
    expected = {
        str(row["path"]): {"bytes": row["bytes"], "sha256": row["sha256"]}
        for row in artifacts
        if isinstance(row, Mapping) and set(row) == {"path", "bytes", "sha256"}
    }
    plan_encoded = captured.get("containers/sira-smoke/bounded/bounded-smoke-plan-v2.json")
    if plan_encoded is None or len(plan_encoded) > MAX_PLAN_BYTES:
        raise BootstrapError("upload bundle has no bounded plan")
    expected["containers/sira-smoke/bounded/bounded-smoke-plan-v2.json"] = {
        "bytes": len(plan_encoded),
        "sha256": plan_sha256,
    }
    if (
        observed != expected
        or manifest.get("execution_commit") != execution_commit
        or set(captured) != {UPLOAD_MANIFEST_NAME, *expected}
    ):
        raise BootstrapError("extracted upload bundle differs from the reviewed plan")


def _parse_utc(value: object, *, context: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise BootstrapError(f"{context} is not an exact UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        raise BootstrapError(f"{context} is malformed") from None
    return parsed


def validate_authorization(
    encoded: bytes,
    *,
    expected_sha256: str,
    plan_sha256: str,
) -> dict[str, object]:
    if _HEX64.fullmatch(expected_sha256) is None or _sha256(encoded) != expected_sha256:
        raise BootstrapError("authorization file hash differs from the supplied binding")
    document = _strict_json(encoded, context="authorization")
    expected_keys = {
        "schema_version",
        "authorized",
        "authorization_reference",
        "execution_commit",
        "branch",
        "plan_id",
        "plan_sha256",
        "host_run_id",
        "condition_run_ids",
        "supervised_wall_started_at_utc",
        "expires_at_utc",
        "private_binding_sha256",
        "limits_sha256",
        "pricing",
        "permissions",
        "user_present",
        "manual_termination_path_confirmed",
    }
    reference = document.get("authorization_reference")
    pricing = document.get("pricing")
    permissions = document.get("permissions")
    if (
        set(document) != expected_keys
        or document.get("schema_version") != "0.1.0"
        or document.get("authorized") is not True
        or not isinstance(reference, str)
        or _AUTHORIZATION.fullmatch(reference) is None
        or reference.endswith("-PENDING")
        or document.get("branch") != BRANCH
        or document.get("plan_id") != PLAN_ID
        or document.get("host_run_id") != HOST_RUN_ID
        or document.get("plan_sha256") != plan_sha256
        or document.get("condition_run_ids") != [REACTIVE_RUN_ID, SIMULATIVE_RUN_ID]
        or not isinstance(document.get("private_binding_sha256"), str)
        or _HEX64.fullmatch(str(document["private_binding_sha256"])) is None
        or document.get("limits_sha256") != LIMITS_SHA256
        or not isinstance(document.get("execution_commit"), str)
        or _HEX40.fullmatch(str(document["execution_commit"])) is None
        or document.get("user_present") is not True
        or document.get("manual_termination_path_confirmed") is not True
        or pricing
        != {
            "model": MODEL,
            "api_request_service_tier": "default",
            "pricing_class": "standard",
            "input_usd_per_million": 2.5,
            "cached_input_usd_per_million": 1.25,
            "output_usd_per_million": 10.0,
            "lambda_cents_per_hour": 129,
        }
        or permissions
        != {
            "lambda_read_only_gets": 13,
            "user_cloud_mutations": True,
            "paid_compute": True,
            "prototype_execution": True,
            "scientific_interpretation": False,
            "training": False,
            "pilot": False,
            "ssh": False,
        }
    ):
        raise BootstrapError("authorization contract is incomplete or drifted")
    now = datetime.now(UTC)
    launch = _parse_utc(
        document.get("supervised_wall_started_at_utc"), context="supervised wall start"
    )
    expiry = _parse_utc(document.get("expires_at_utc"), context="authorization expiry")
    elapsed = (now - launch).total_seconds()
    if (
        expiry - launch != timedelta(seconds=HARD_PROVIDER_WALL_SECONDS)
        or not 0 <= elapsed < HARD_PROVIDER_WALL_SECONDS
        or now >= expiry
    ):
        raise BootstrapError("authorization or provider wall is expired")
    if HARD_PROVIDER_WALL_SECONDS - elapsed <= TERMINATION_HEADROOM_SECONDS:
        raise BootstrapError("provider termination headroom is exhausted")
    return document


def validate_bootstrap_release(
    encoded: bytes,
    *,
    expected_sha256: str,
    plan_sha256: str,
    authorization_sha256: str,
    authorization: Mapping[str, object],
) -> dict[str, object]:
    if _HEX64.fullmatch(expected_sha256) is None or _sha256(encoded) != expected_sha256:
        raise BootstrapError("bootstrap release hash differs from its supplied binding")
    document = _strict_json(encoded, context="bootstrap release")
    required = {
        "schema_version",
        "plan_id",
        "host_run_id",
        "authorization_reference",
        "execution_commit",
        "plan_sha256",
        "authorization_sha256",
        "private_binding_sha256",
        "observer_state_sha256",
        "post_launch_report_sha256",
        "provider_active_observed_at_utc",
        "selected_provider_image",
        "bundle_archive_sha256",
        "bundle_manifest_sha256",
        "bootstrap_file_sha256",
        "issued_at_utc",
        "bootstrap_release",
        "single_use_output_root",
    }
    observed_active = _parse_utc(
        document.get("provider_active_observed_at_utc"), context="provider active observation"
    )
    issued = _parse_utc(document.get("issued_at_utc"), context="bootstrap release time")
    authorized_start = _parse_utc(
        authorization.get("supervised_wall_started_at_utc"), context="supervised wall start"
    )
    expires = _parse_utc(authorization.get("expires_at_utc"), context="authorization expiry")
    selected_provider_image = document.get("selected_provider_image")
    if (
        set(document) != required
        or document.get("schema_version") != SCHEMA_VERSION
        or document.get("plan_id") != PLAN_ID
        or document.get("host_run_id") != HOST_RUN_ID
        or document.get("authorization_reference") != authorization.get("authorization_reference")
        or document.get("execution_commit") != authorization.get("execution_commit")
        or document.get("plan_sha256") != plan_sha256
        or document.get("authorization_sha256") != authorization_sha256
        or document.get("private_binding_sha256") != authorization.get("private_binding_sha256")
        or any(
            not isinstance(document.get(field), str)
            or _HEX64.fullmatch(str(document[field])) is None
            for field in (
                "observer_state_sha256",
                "post_launch_report_sha256",
                "bundle_archive_sha256",
                "bundle_manifest_sha256",
                "bootstrap_file_sha256",
            )
        )
        or document.get("bootstrap_release") is not True
        or document.get("single_use_output_root") != "/home/ubuntu/t07-bounded-output-0002"
        or selected_provider_image
        != {
            "alias": SELECTED_IMAGE_ALIAS,
            "family": SELECTED_IMAGE_FAMILY,
            "version": SELECTED_IMAGE_VERSION,
            "attestation": "confirmed-in-provider-console",
            "binding_basis": "prelaunch-offered-plus-user-console-attestation",
            "post_launch_api_image_observation_available": False,
        }
        or not authorized_start <= observed_active <= issued < expires
    ):
        raise BootstrapError("bootstrap release contract is incomplete or drifted")
    return document


@dataclass(slots=True)
class SecretLease:
    """Held no-follow identity for the uploaded secret across the whole bootstrap."""

    path: Path
    descriptor: int
    parent_descriptor: int
    device: int
    inode: int
    size: int
    value_read: bool = False
    destroyed: bool = False

    def mount_path(self) -> str:
        try:
            current = os.stat(
                self.path.name,
                dir_fd=self.parent_descriptor,
                follow_symlinks=False,
            )
        except OSError:
            raise BootstrapError("SIRA secret path identity is unavailable") from None
        if (current.st_dev, current.st_ino) != (self.device, self.inode):
            raise BootstrapError("SIRA secret path identity changed")
        return str(self.path)

    def read_value(self) -> bytes:
        opened = os.fstat(self.descriptor)
        if (
            self.destroyed
            or (opened.st_dev, opened.st_ino) != (self.device, self.inode)
            or opened.st_size != self.size
        ):
            raise BootstrapError("SIRA secret held identity drifted before read")
        raw = os.pread(self.descriptor, self.size + 1, 0)
        value = raw.rstrip(b"\r\n")
        if len(raw) != self.size or not value or b"\x00" in value:
            raise BootstrapError("SIRA secret file contract failed")
        try:
            value.decode("utf-8")
        except UnicodeDecodeError:
            raise BootstrapError("SIRA secret file contract failed") from None
        self.value_read = True
        return value

    def destroy(self, receipt_path: Path) -> dict[str, object]:
        if self.destroyed:
            raise BootstrapError("secret cleanup cannot be repeated")
        try:
            current = os.stat(
                self.path.name,
                dir_fd=self.parent_descriptor,
                follow_symlinks=False,
            )
            current_matches = (current.st_dev, current.st_ino) == (self.device, self.inode)
        except FileNotFoundError:
            current_matches = False
        os.ftruncate(self.descriptor, 0)
        os.fsync(self.descriptor)
        unlinked = False
        if current_matches:
            os.unlink(self.path.name, dir_fd=self.parent_descriptor)
            os.fsync(self.parent_descriptor)
            unlinked = True
        try:
            remaining = os.stat(
                self.path.name,
                dir_fd=self.parent_descriptor,
                follow_symlinks=False,
            )
        except FileNotFoundError:
            absent = True
        else:
            absent = False
            if (remaining.st_dev, remaining.st_ino) == (self.device, self.inode):
                raise BootstrapError("secret cleanup left the held identity reachable")
        self.destroyed = True
        record = {
            "schema_version": "0.1.0",
            "secret_variable_name": "SIRA_API_KEY",
            "secret_file_basename": "sira_api_key",
            "held_identity_established_before_preflight": True,
            "truncated_before_unlink": True,
            "unlinked": unlinked,
            "absence_verified": absent,
            "path_identity_replaced": not current_matches and not absent,
            "value_or_hash_retained": False,
            "manual_fallback_deletion_required": not (unlinked and absent),
        }
        _write_json(receipt_path, record)
        if not unlinked or not absent:
            raise BootstrapError("secret cleanup requires manual delete and credential rotation")
        return record

    def close(self) -> None:
        with contextlib.suppress(OSError):
            os.close(self.descriptor)
        with contextlib.suppress(OSError):
            os.close(self.parent_descriptor)


def acquire_secret_lease(path: Path, *, forbidden_roots: Sequence[Path]) -> SecretLease:
    try:
        linked = path.lstat()
        descriptor = os.open(path, os.O_RDWR | getattr(os, "O_NOFOLLOW", 0))
    except OSError:
        raise BootstrapError("SIRA secret file is unavailable") from None
    parent_descriptor = -1
    try:
        opened = os.fstat(descriptor)
        resolved = path.resolve(strict=True)
        if (
            not stat.S_ISREG(linked.st_mode)
            or stat.S_ISLNK(linked.st_mode)
            or linked.st_nlink != 1
            or (linked.st_dev, linked.st_ino) != (opened.st_dev, opened.st_ino)
            or not 0 < opened.st_size <= 16_384
            or stat.S_IMODE(opened.st_mode) & 0o077
            or any(root == resolved or root in resolved.parents for root in forbidden_roots)
        ):
            raise BootstrapError("SIRA secret file contract failed")
        parent_descriptor = os.open(
            path.parent,
            os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
        )
        return SecretLease(
            path=path,
            descriptor=descriptor,
            parent_descriptor=parent_descriptor,
            device=opened.st_dev,
            inode=opened.st_ino,
            size=opened.st_size,
        )
    except BaseException:
        os.close(descriptor)
        if parent_descriptor >= 0:
            os.close(parent_descriptor)
        raise


def _assert_secret_absent(
    root: Path,
    secret_value: bytes,
    *,
    captured: Sequence[tuple[Path, bytes]] | None = None,
) -> None:
    evidence = (
        list(captured)
        if captured is not None
        else [
            (path, _read_regular(path, max_bytes=MAX_EVIDENCE_BYTES))
            for path in _bounded_regular_files(root, context="evidence")
        ]
    )
    for path, encoded in evidence:
        relative = path.relative_to(root).as_posix().encode("utf-8")
        if _contains_secret_derivative(relative, secret_value) or any(
            pattern.search(relative) for pattern in _SECRET_SHAPES
        ):
            raise BootstrapError(
                "evidence path contains the supplied secret value",
                failure_code="credential_material_detected",
            )
        if _contains_secret_derivative(encoded, secret_value) or _contains_artifact_secret(encoded):
            raise BootstrapError(
                "evidence contains the supplied secret value",
                failure_code="credential_material_detected",
            )


def _download_exact(url: str, destination: Path, *, size: int, sha256: str) -> None:
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.query or parsed.fragment:
        raise BootstrapError("download URL is outside the HTTPS artifact contract")
    connection = http.client.HTTPSConnection(parsed.hostname, timeout=60)
    try:
        target = urllib.parse.urlunsplit(("", "", parsed.path, "", ""))
        connection.request(
            "GET",
            target,
            headers={"Accept": "application/octet-stream", "User-Agent": "gic-lab-t07/1"},
        )
        response = connection.getresponse()
        if response.status != 200 or response.getheader("Location") is not None:
            raise BootstrapError("artifact download did not return an exact 200 response")
        digest = hashlib.sha256()
        written = 0
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(destination, flags, 0o400)
        try:
            while chunk := response.read(65_536):
                written += len(chunk)
                if written > size or written > MAX_DOWNLOAD_BYTES:
                    raise BootstrapError("artifact download exceeded its exact byte contract")
                digest.update(chunk)
                _write_all(descriptor, chunk)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    finally:
        connection.close()
    persisted = _read_regular(destination, max_bytes=MAX_DOWNLOAD_BYTES)
    if (
        written != size
        or digest.hexdigest() != sha256
        or len(persisted) != size
        or _sha256(persisted) != sha256
    ):
        raise BootstrapError("artifact download identity drifted")


def _copy_exact(source: Path, destination: Path, *, sha256: str) -> None:
    encoded = _read_regular(source, max_bytes=4_194_304)
    if _sha256(encoded) != sha256:
        raise BootstrapError("bundle input hash drifted")
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(destination, flags, 0o400)
    try:
        _write_all(descriptor, encoded)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _extract_git_archive(archive: Path, destination: Path) -> None:
    destination.mkdir(mode=0o700, exist_ok=False)
    with tarfile.open(archive, "r:") as source:
        members = source.getmembers()
        for member in members:
            candidate = (destination / member.name).resolve(strict=False)
            if (
                destination.resolve() not in candidate.parents
                or member.issym()
                or member.islnk()
                or member.isdev()
                or member.isfifo()
            ):
                raise BootstrapError("SiRA archive contains an unsafe member")
        source.extractall(destination)


def _write_json(path: Path, value: object) -> None:
    encoded = json.dumps(value, allow_nan=False, indent=2, sort_keys=True).encode() + b"\n"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o600)
    try:
        _write_all(descriptor, encoded)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_bytes(path: Path, encoded: bytes, *, cap: int = MAX_COMMAND_OUTPUT_BYTES) -> None:
    if len(encoded) > cap:
        raise BootstrapError("bounded evidence output exceeds its file cap")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o600)
    try:
        _write_all(descriptor, encoded)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _assert_remote_capacity(root: Path) -> None:
    free = shutil.disk_usage(root.parent).free
    if free < MIN_REMOTE_FREE_BYTES:
        raise BootstrapError("remote root has insufficient free space")


def _assert_runtime_disk_increment(root: Path, *, starting_free_bytes: int) -> None:
    current_free = shutil.disk_usage(root.parent).free
    if starting_free_bytes - current_free > MAX_RUNTIME_DISK_INCREMENT_BYTES:
        raise BootstrapError("runtime disk increment exceeded its cap")


def _command_observation(result: CommandResult) -> dict[str, object]:
    return {
        "argv": list(result.argv),
        "argv_sha256": _sha256(json.dumps(list(result.argv), separators=(",", ":")).encode()),
        "returncode": result.returncode,
        "stdout_bytes": len(result.stdout),
        "stderr_bytes": len(result.stderr),
        "elapsed_seconds": result.elapsed_seconds,
    }


def _os_release() -> dict[str, str]:
    encoded = _read_regular(Path("/etc/os-release"), max_bytes=65_536)
    values: dict[str, str] = {}
    for raw_line in encoded.decode("utf-8", "strict").splitlines():
        if not raw_line or raw_line.startswith("#") or "=" not in raw_line:
            continue
        key, value = raw_line.split("=", 1)
        if key in {"ID", "VERSION_ID", "PRETTY_NAME"}:
            values[key] = value.strip().strip('"')
    if set(values) != {"ID", "VERSION_ID", "PRETTY_NAME"}:
        raise BootstrapError("host OS release identity is incomplete")
    return values


def capture_host_environment(
    *,
    evidence_root: Path,
    runner: CommandRunner,
    bootstrap_release: Mapping[str, object],
    contract: ModuleType,
) -> dict[str, object]:
    """Capture a bounded, nonsecret host/runtime fingerprint before image build."""

    version_argv = ("/usr/bin/docker", "version", "--format", "{{json .}}")
    info_format = (
        '{"driver":{{json .Driver}},"root":{{json .DockerRootDir}},'
        '"operating_system":{{json .OperatingSystem}},"os_type":{{json .OSType}},'
        '"architecture":{{json .Architecture}},"cgroup_driver":{{json .CgroupDriver}},'
        '"cgroup_version":{{json .CgroupVersion}},'
        '"security_options":{{json .SecurityOptions}}}'
    )
    info_argv = ("/usr/bin/docker", "info", "--format", info_format)
    gpu_argv = (
        "/usr/bin/nvidia-smi",
        "--query-gpu=name,uuid,driver_version",
        "--format=csv,noheader,nounits",
    )
    version_result = runner.run(
        version_argv, cwd=evidence_root, timeout=min(30, runner.remaining())
    )
    info_result = runner.run(info_argv, cwd=evidence_root, timeout=min(30, runner.remaining()))
    gpu_result = runner.run(gpu_argv, cwd=evidence_root, timeout=min(30, runner.remaining()))
    docker_version = _strict_json(version_result.stdout, context="Docker version")
    docker_info = _strict_json(info_result.stdout, context="Docker info")
    client = docker_version.get("Client")
    server = docker_version.get("Server")
    if not isinstance(client, Mapping) or not isinstance(server, Mapping):
        raise BootstrapError("Docker client/server identity is incomplete")
    security_options = docker_info.get("security_options")
    if not isinstance(security_options, list) or any(
        not isinstance(value, str) for value in security_options
    ):
        raise BootstrapError("Docker security-option identity is incomplete")
    docker_root = docker_info.get("root")
    if not isinstance(docker_root, str) or not docker_root.startswith("/"):
        raise BootstrapError("Docker root identity is unavailable")
    gpu_rows: list[dict[str, str]] = []
    for line in gpu_result.stdout.decode("utf-8", "strict").splitlines():
        parts = [value.strip() for value in line.split(",", 2)]
        if len(parts) != 3 or not all(parts):
            raise BootstrapError("GPU identity output is malformed")
        gpu_rows.append(
            {
                "name": parts[0],
                "uuid_sha256": _sha256(parts[1].encode()),
                "driver_version": parts[2],
            }
        )
    if len(gpu_rows) != 1 or "A10" not in gpu_rows[0]["name"]:
        raise BootstrapError("host GPU identity is not the selected one-A10 substrate")
    release_image = bootstrap_release.get("selected_provider_image")
    expected_image = {
        "alias": contract.SELECTED_IMAGE_ALIAS,
        "family": contract.SELECTED_IMAGE_FAMILY,
        "version": contract.SELECTED_IMAGE_VERSION,
        "attestation": "confirmed-in-provider-console",
        "binding_basis": "prelaunch-offered-plus-user-console-attestation",
        "post_launch_api_image_observation_available": False,
    }
    if release_image != expected_image:
        raise BootstrapError("provider image attestation drifted before host capture")
    os_release = _os_release()
    if (
        os_release.get("ID") != "ubuntu"
        or os_release.get("VERSION_ID") != "22.04"
        or platform.system() != "Linux"
        or platform.machine() not in {"x86_64", "amd64"}
        or client.get("Os") != "linux"
        or client.get("Arch") not in {"amd64", "x86_64"}
        or server.get("Os") != "linux"
        or server.get("Arch") not in {"amd64", "x86_64"}
        or docker_info.get("os_type") != "linux"
        or docker_info.get("architecture") not in {"amd64", "x86_64"}
    ):
        raise BootstrapError("host OS or Docker architecture differs from the x86_64 plan")
    record = {
        "schema_version": contract.SCHEMA_VERSION,
        "captured_before_image_build": True,
        "provider_image": expected_image,
        "provider_image_identity_basis": "user-attested-not-postlaunch-api-observed",
        "os_release": {
            "id": os_release["ID"],
            "version_id": os_release["VERSION_ID"],
            "pretty_name": os_release["PRETTY_NAME"],
        },
        "kernel": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
        },
        "bootstrap_python": {
            "executable": sys.executable,
            "version": platform.python_version(),
        },
        "docker": {
            "client_version": client.get("Version"),
            "client_os": client.get("Os"),
            "client_arch": client.get("Arch"),
            "server_version": server.get("Version"),
            "server_os": server.get("Os"),
            "server_arch": server.get("Arch"),
            "storage_driver": docker_info.get("driver"),
            "root_dir_sha256": _sha256(docker_root.encode()),
            "operating_system": docker_info.get("operating_system"),
            "os_type": docker_info.get("os_type"),
            "architecture": docker_info.get("architecture"),
            "cgroup_driver": docker_info.get("cgroup_driver"),
            "cgroup_version": docker_info.get("cgroup_version"),
            "security_options": security_options,
        },
        "gpus": gpu_rows,
        "commands": [
            _command_observation(version_result),
            _command_observation(info_result),
            _command_observation(gpu_result),
        ],
        "secret_values_retained": False,
    }
    _write_json(evidence_root / "host-environment.json", record)
    return record


def _artifact_map(plan: Mapping[str, object]) -> dict[str, tuple[int, str]]:
    implementation = plan.get("implementation")
    if not isinstance(implementation, Mapping):
        raise BootstrapError("plan implementation binding is unavailable")
    artifacts = implementation.get("artifacts")
    if not isinstance(artifacts, list):
        raise BootstrapError("plan implementation artifacts are unavailable")
    output: dict[str, tuple[int, str]] = {}
    for raw in artifacts:
        if not isinstance(raw, Mapping):
            raise BootstrapError("plan implementation artifact is invalid")
        path, size, digest = raw.get("path"), raw.get("bytes"), raw.get("sha256")
        if (
            not isinstance(path, str)
            or not isinstance(size, int)
            or not isinstance(digest, str)
            or _HEX64.fullmatch(digest) is None
        ):
            raise BootstrapError("plan implementation artifact identity is invalid")
        output[path] = (size, digest)
    return output


def prepare_build_context(
    *,
    bundle_root: Path,
    work_root: Path,
    plan: Mapping[str, object],
    contract: ModuleType,
    runner: CommandRunner,
) -> Path:
    source_checkout = work_root / "source-checkout"
    runner.run(
        (
            "/usr/bin/git",
            "clone",
            "--no-checkout",
            "https://github.com/sailing-lab/sira.git",
            str(source_checkout),
        ),
        cwd=work_root,
        timeout=min(600, runner.remaining()),
    )
    runner.run(
        (
            "/usr/bin/git",
            "-C",
            str(source_checkout),
            "checkout",
            "--detach",
            contract.UPSTREAM_COMMIT,
        ),
        cwd=work_root,
        timeout=min(120, runner.remaining()),
    )
    head = (
        runner.run(
            ("/usr/bin/git", "-C", str(source_checkout), "rev-parse", "HEAD"),
            cwd=work_root,
            timeout=min(30, runner.remaining()),
        )
        .stdout.decode()
        .strip()
    )
    tree = (
        runner.run(
            ("/usr/bin/git", "-C", str(source_checkout), "rev-parse", "HEAD^{tree}"),
            cwd=work_root,
            timeout=min(30, runner.remaining()),
        )
        .stdout.decode()
        .strip()
    )
    status = runner.run(
        (
            "/usr/bin/git",
            "-C",
            str(source_checkout),
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
        ),
        cwd=work_root,
        timeout=min(30, runner.remaining()),
    ).stdout
    if head != contract.UPSTREAM_COMMIT or tree != contract.UPSTREAM_TREE or status:
        raise BootstrapError("cloned SiRA identity is dirty or drifted")

    context = work_root / "build-context"
    context.mkdir(mode=0o700, exist_ok=False)
    archive = work_root / "upstream.tar"
    runner.run(
        (
            "/usr/bin/git",
            "-C",
            str(source_checkout),
            "archive",
            "--format=tar",
            f"--output={archive}",
            contract.UPSTREAM_COMMIT,
        ),
        cwd=work_root,
        timeout=min(120, runner.remaining()),
    )
    _extract_git_archive(archive, context / "upstream")

    bindings = _artifact_map(plan)
    copies = {
        "containers/sira-smoke/bounded/Containerfile.amd64": "Containerfile.amd64",
        "containers/sira-smoke/bounded/.dockerignore": ".dockerignore",
        "containers/sira-smoke/sira-immutable-model-routing.patch": (
            "sira-immutable-model-routing.patch"
        ),
        "containers/sira-smoke/container_entrypoint.py": "container_entrypoint.py",
        "containers/sira-smoke/bounded/model_preflight.py": "model_preflight.py",
        "containers/sira-smoke/bounded/browser_preflight.py": "browser_preflight.py",
        "containers/sira-smoke/fixtures/static.html": "static.html",
        "src/giclab/__init__.py": "giclab/__init__.py",
        "src/giclab/registry.py": "giclab/registry.py",
        "containers/sira-smoke/bounded/harness_init.py": "giclab/harness/__init__.py",
        "src/giclab/harness/sira_gate_a.py": "giclab/harness/sira_gate_a.py",
        "src/giclab/harness/sira_gate_a_runtime.py": ("giclab/harness/sira_gate_a_runtime.py"),
    }
    for source_relative, destination_relative in copies.items():
        binding = bindings.get(source_relative)
        if binding is None:
            raise BootstrapError("build input is absent from plan bindings")
        source = bundle_root / source_relative
        if source.stat().st_size != binding[0]:
            raise BootstrapError("build input byte identity drifted")
        _copy_exact(source, context / destination_relative, sha256=binding[1])
    vendor = context / "vendor"
    vendor.mkdir(mode=0o700)
    _download_exact(
        contract.UV_WHEEL_URL,
        vendor / contract.UV_WHEEL,
        size=contract.UV_WHEEL_BYTES,
        sha256=contract.UV_WHEEL_SHA256,
    )
    return context


def build_image(
    *,
    context: Path,
    execution_commit: str,
    authorization_reference: str,
    runner: CommandRunner,
    contract: ModuleType,
    evidence_root: Path,
) -> str:
    runner.run(
        (
            "/usr/bin/docker",
            "image",
            "pull",
            "--platform",
            "linux/amd64",
            contract.BASE_IMAGE_INDEX,
        ),
        cwd=context,
        timeout=min(600, runner.remaining()),
    )
    base = runner.run(
        (
            "/usr/bin/docker",
            "image",
            "inspect",
            "--format",
            "{{.Id}}",
            contract.BASE_IMAGE_INDEX,
        ),
        cwd=context,
        timeout=min(30, runner.remaining()),
    )
    if base.stdout.decode("utf-8", "strict").strip() != contract.BASE_IMAGE_AMD64_CONFIG:
        raise BootstrapError("pulled base image config differs from the pinned amd64 identity")
    tag = "giclab/sira-smoke:t07-bounded-v1"
    runner.run(
        (
            "/usr/bin/docker",
            "build",
            "--pull=false",
            "--no-cache",
            "--network=default",
            "--platform",
            "linux/amd64",
            "--file",
            str(context / "Containerfile.amd64"),
            "--tag",
            tag,
            "--label",
            f"org.giclab.t07.repository-commit={execution_commit}",
            "--label",
            f"org.giclab.t07.source-commit={contract.UPSTREAM_COMMIT}",
            "--label",
            f"org.giclab.t07.authorization={authorization_reference}",
            str(context),
        ),
        cwd=context,
        timeout=min(1_800, runner.remaining()),
    )
    result = runner.run(
        ("/usr/bin/docker", "image", "inspect", "--format", "{{.Id}}", tag),
        cwd=context,
        timeout=min(30, runner.remaining()),
    )
    image_id = result.stdout.decode("utf-8", "strict").strip()
    if _IMAGE_ID.fullmatch(image_id) is None:
        raise BootstrapError("built image ID is not immutable")
    inspect = runner.run(
        ("/usr/bin/docker", "image", "inspect", image_id),
        cwd=context,
        timeout=min(30, runner.remaining()),
    )
    _write_bytes(evidence_root / "image-inspect.json", inspect.stdout)
    return image_id


def _capture_json_output(path: Path, result: CommandResult) -> None:
    _write_json(
        path,
        {
            "argv_sha256": _sha256(json.dumps(list(result.argv), separators=(",", ":")).encode()),
            "returncode": result.returncode,
            "stdout_bytes": len(result.stdout),
            "stdout_sha256": _sha256(result.stdout),
            "stderr_bytes": len(result.stderr),
            "stderr_sha256": _sha256(result.stderr),
            "elapsed_seconds": result.elapsed_seconds,
        },
    )


def _render_lifecycle(
    plan: Mapping[str, object],
    contract: ModuleType,
    action: str,
    substitutions: Mapping[str, str],
) -> tuple[str, ...]:
    lifecycle = plan.get("container_lifecycle")
    if not isinstance(lifecycle, Mapping):
        raise BootstrapError("container lifecycle plan is unavailable")
    template = lifecycle.get(action)
    if not isinstance(template, list) or any(not isinstance(item, str) for item in template):
        raise BootstrapError("container lifecycle command is invalid")
    needed = {
        match.group(0) for item in template for match in re.finditer(r"\$\{[A-Z][A-Z0-9_]*\}", item)
    }
    selected = {key: value for key, value in substitutions.items() if key in needed}
    return cast(tuple[str, ...], contract.materialize_argv(template, selected))


def _line_count(encoded: bytes) -> int:
    return len([line for line in encoded.splitlines() if line.strip()])


def _running_container_observed(encoded: bytes) -> bool:
    try:
        document = json.loads(encoded)
        return (
            isinstance(document, list)
            and len(document) == 1
            and isinstance(document[0], dict)
            and isinstance(document[0].get("State"), dict)
            and document[0]["State"].get("Running") is True
        )
    except (AttributeError, json.JSONDecodeError, TypeError):
        return False


def _process_snapshot_count(encoded: bytes) -> int:
    lines = [line for line in encoded.splitlines() if line.strip()]
    return max(0, len(lines) - 1)


def _regular_tree_bytes(root: Path) -> int:
    total = 0
    for path in _bounded_regular_files(root, context="attempt evidence"):
        total += path.stat(follow_symlinks=False).st_size
        if total > MAX_EVIDENCE_BYTES:
            raise BootstrapError("attempt evidence exceeds the aggregate cap")
    return total


def _copy_container_payload(
    *,
    container_id: str,
    run_id: str,
    phase: str,
    plan: Mapping[str, object],
    contract: ModuleType,
    runner: CommandRunner,
    evidence_root: Path,
) -> tuple[bool, int]:
    if phase not in {"prestop", "poststop"}:
        raise BootstrapError("container copy-out phase is invalid")
    target = evidence_root / f"payload-{phase}"
    target.mkdir(mode=0o700, exist_ok=False)
    substitutions = {
        "${CONTAINER_ID}": container_id,
        "${RUN_ID}": run_id,
        "${HOST_ATTEMPT_ROOT}": str(target),
    }
    copied = runner.run(
        _render_lifecycle(plan, contract, "copy_out", substitutions),
        cwd=evidence_root,
        timeout=min(60, runner.remaining()),
        check=False,
    )
    _capture_json_output(evidence_root / f"container-copy-out-{phase}.json", copied)
    payload_bytes = _regular_tree_bytes(target)
    within = payload_bytes <= MAX_ATTEMPT_PAYLOAD_BYTES
    complete = copied.returncode == 0 and within
    _write_json(
        evidence_root / f"container-copy-out-{phase}-budget.json",
        {
            "phase": phase,
            "payload_bytes": payload_bytes,
            "payload_cap_bytes": MAX_ATTEMPT_PAYLOAD_BYTES,
            "within_cap": within,
            "copy_complete": complete,
        },
    )
    if complete:
        os.rename(target, evidence_root / "payload")
        return True, payload_bytes
    return False, payload_bytes


def _cleanup_container(
    *,
    container_id: str,
    run_id: str,
    condition: str,
    plan: Mapping[str, object],
    contract: ModuleType,
    cleanup_runner: CommandRunner,
    evidence_root: Path,
    payload_captured: bool,
    payload_bytes: int,
    payload_phase: str | None,
) -> None:
    substitutions = {"${CONTAINER_ID}": container_id, "${RUN_ID}": run_id}
    stop = cleanup_runner.run(
        _render_lifecycle(plan, contract, "stop", substitutions),
        cwd=evidence_root,
        timeout=min(15, cleanup_runner.remaining()),
        check=False,
    )
    _capture_json_output(evidence_root / "container-stop.json", stop)
    kill = cleanup_runner.run(
        _render_lifecycle(plan, contract, "kill", substitutions),
        cwd=evidence_root,
        timeout=min(15, cleanup_runner.remaining()),
        check=False,
    )
    _capture_json_output(evidence_root / "container-kill.json", kill)
    terminal = cleanup_runner.run(
        _render_lifecycle(plan, contract, "inspect", substitutions),
        cwd=evidence_root,
        timeout=min(15, cleanup_runner.remaining()),
        check=False,
    )
    _capture_json_output(evidence_root / "container-terminal-inspect-command.json", terminal)
    _write_bytes(evidence_root / "container-terminal-inspect.json", terminal.stdout)
    terminal_state_observed = False
    if terminal.returncode == 0:
        try:
            inspected = json.loads(terminal.stdout)
            state = inspected[0]["State"]
            terminal_state_observed = state.get("Running") is False and state.get("Status") in {
                "created",
                "exited",
                "dead",
            }
        except (IndexError, KeyError, TypeError, json.JSONDecodeError):
            terminal_state_observed = False
    if not payload_captured:
        try:
            payload_captured, payload_bytes = _copy_container_payload(
                container_id=container_id,
                run_id=run_id,
                phase="poststop",
                plan=plan,
                contract=contract,
                runner=cleanup_runner,
                evidence_root=evidence_root,
            )
            if payload_captured:
                payload_phase = "poststop"
        except BaseException:
            payload_captured = False
    removed = cleanup_runner.run(
        _render_lifecycle(plan, contract, "remove", substitutions),
        cwd=evidence_root,
        timeout=min(30, cleanup_runner.remaining()),
        check=False,
    )
    _capture_json_output(evidence_root / "container-remove.json", removed)
    removal_probe = cleanup_runner.run(
        _render_lifecycle(plan, contract, "inspect", substitutions),
        cwd=evidence_root,
        timeout=min(15, cleanup_runner.remaining()),
        check=False,
    )
    _capture_json_output(evidence_root / "container-removal-proof.json", removal_probe)
    residue: dict[str, int] = {}
    for kind, action in (
        ("owned_container_residue_count", "container_residue"),
        ("owned_network_residue_count", "network_residue"),
        ("owned_volume_residue_count", "volume_residue"),
    ):
        observed = cleanup_runner.run(
            _render_lifecycle(plan, contract, action, substitutions),
            cwd=evidence_root,
            timeout=min(30, cleanup_runner.remaining()),
        )
        receipt_name = {
            "container_residue": "container-residue-containers.json",
            "network_residue": "container-residue-networks.json",
            "volume_residue": "container-residue-volumes.json",
        }[action]
        _capture_json_output(evidence_root / receipt_name, observed)
        residue[kind] = _line_count(observed.stdout)
    record = {
        "schema_version": contract.SCHEMA_VERSION,
        "condition": condition,
        "container_id_sha256": _sha256(container_id.encode()),
        "terminal_state_observed": terminal_state_observed,
        "removed": removed.returncode == 0 and removal_probe.returncode != 0,
        **residue,
        "browser_process_residue_count": residue["owned_container_residue_count"],
        "process_evidence_captured_before_removal": False,
        "payload_capture_complete_before_removal": payload_captured,
        "payload_capture_phase": payload_phase,
        "payload_bytes": payload_bytes,
        "pre_stop_running_state_observed": False,
        "pre_stop_process_capture_succeeded": False,
        "pre_stop_process_count": 0,
    }
    pre_stop_inspect = evidence_root / "container-inspect-before-stop.json"
    pre_stop_processes = evidence_root / "container-processes-before-stop.txt"
    if pre_stop_inspect.is_file() and pre_stop_processes.is_file():
        running = _running_container_observed(_read_regular(pre_stop_inspect, max_bytes=1_048_576))
        process_count = _process_snapshot_count(
            _read_regular(pre_stop_processes, max_bytes=1_048_576)
        )
        record.update(
            {
                "process_evidence_captured_before_removal": running and process_count > 0,
                "pre_stop_running_state_observed": running,
                "pre_stop_process_capture_succeeded": process_count > 0,
                "pre_stop_process_count": process_count,
            }
        )
    _write_json(
        evidence_root / "container-payload-capture.json",
        {
            "schema_version": contract.SCHEMA_VERSION,
            "condition": condition,
            "copy_complete": payload_captured,
            "selected_phase": payload_phase,
            "payload_root": "payload" if payload_captured else None,
            "payload_bytes": payload_bytes,
            "payload_cap_bytes": MAX_ATTEMPT_PAYLOAD_BYTES,
            "captured_before_removal": payload_captured,
        },
    )
    _write_json(evidence_root / "container-cleanup.json", record)
    contract.validate_container_cleanup(record)


def run_owned_container(
    *,
    condition: str,
    run_id: str,
    create_template: Sequence[str],
    substitutions: Mapping[str, str],
    plan: Mapping[str, object],
    contract: ModuleType,
    work_runner: CommandRunner,
    cleanup_runner: CommandRunner,
    evidence_root: Path,
    attached: bool,
    wall_seconds: int,
    readiness_container_path: str | None = None,
) -> CommandResult:
    needed = {
        match.group(0)
        for item in create_template
        for match in re.finditer(r"\$\{[A-Z][A-Z0-9_]*\}", item)
    }
    create_substitutions = {key: value for key, value in substitutions.items() if key in needed}
    argv = contract.materialize_argv(create_template, create_substitutions)
    created = work_runner.run(
        argv,
        cwd=evidence_root,
        timeout=min(60, work_runner.remaining()),
    )
    _capture_json_output(evidence_root / "container-create.json", created)
    container_id = created.stdout.decode("utf-8", "strict").strip()
    if re.fullmatch(r"[a-f0-9]{64}", container_id) is None:
        raise BootstrapError("Docker create did not return an immutable container ID")
    lifecycle_substitutions = {"${CONTAINER_ID}": container_id, "${RUN_ID}": run_id}
    primary_error: BaseException | None = None
    result: CommandResult | None = None
    payload_captured = False
    payload_bytes = 0
    payload_phase: str | None = None
    try:
        _write_bytes(evidence_root / "container-id.txt", container_id.encode() + b"\n", cap=128)
        started = work_runner.run(
            _render_lifecycle(plan, contract, "start_detached", lifecycle_substitutions),
            cwd=evidence_root,
            timeout=min(30, work_runner.remaining()),
        )
        _capture_json_output(evidence_root / "container-start.json", started)
        required_readiness = (
            readiness_container_path
            if readiness_container_path is not None
            else "/giclab/attempt/.giclab-entrypoint-ready"
        )
        if attached or readiness_container_path is not None:
            readiness_deadline = min(time.monotonic() + 45, work_runner.deadline)
            while True:
                readiness = work_runner.run(
                    _render_lifecycle(
                        plan,
                        contract,
                        "readiness",
                        {
                            **lifecycle_substitutions,
                            "${READINESS_PATH}": required_readiness,
                        },
                    ),
                    cwd=evidence_root,
                    timeout=min(5, work_runner.remaining()),
                    check=False,
                )
                if readiness.returncode == 0:
                    break
                if time.monotonic() >= readiness_deadline:
                    raise BootstrapError("container readiness evidence was not produced")
                time.sleep(1)
            _capture_json_output(evidence_root / "container-readiness.json", readiness)
        inspect = work_runner.run(
            _render_lifecycle(plan, contract, "inspect", lifecycle_substitutions),
            cwd=evidence_root,
            timeout=min(30, work_runner.remaining()),
        )
        _capture_json_output(evidence_root / "container-inspect-before-stop-command.json", inspect)
        _write_bytes(evidence_root / "container-inspect-before-stop.json", inspect.stdout)
        if not _running_container_observed(inspect.stdout):
            raise BootstrapError("container was not running for the pre-stop inspection")
        try:
            inspected = json.loads(inspect.stdout)
            if (
                not isinstance(inspected, list)
                or len(inspected) != 1
                or not isinstance(inspected[0], dict)
            ):
                raise BootstrapError("container inspect response is incomplete")
            contract.validate_container_inspect(
                inspected[0],
                create_argv=list(argv),
                container_id=container_id,
                image_id=str(substitutions["${IMAGE_ID}"]),
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            raise BootstrapError("container inspect policy could not be validated") from None
        top = work_runner.run(
            _render_lifecycle(plan, contract, "top", lifecycle_substitutions),
            cwd=evidence_root,
            timeout=min(30, work_runner.remaining()),
            check=False,
        )
        _capture_json_output(evidence_root / "container-top-before-stop-command.json", top)
        _write_bytes(evidence_root / "container-processes-before-stop.txt", top.stdout)
        if top.returncode != 0 or _process_snapshot_count(top.stdout) < 1:
            raise BootstrapError("container process evidence is empty or unavailable")
        if attached:
            released = work_runner.run(
                _render_lifecycle(plan, contract, "release", lifecycle_substitutions),
                cwd=evidence_root,
                timeout=min(15, work_runner.remaining()),
            )
            _capture_json_output(evidence_root / "container-release.json", released)
            waited = work_runner.run(
                _render_lifecycle(plan, contract, "wait", lifecycle_substitutions),
                cwd=evidence_root,
                timeout=min(wall_seconds, work_runner.remaining()),
                check=False,
            )
            _capture_json_output(evidence_root / "container-wait.json", waited)
            try:
                exit_code = int(waited.stdout.decode("ascii", "strict").strip())
            except (UnicodeDecodeError, ValueError):
                raise BootstrapError("container wait returned an invalid exit status") from None
            if waited.returncode != 0 or not 0 <= exit_code <= 255:
                raise BootstrapError("container wait failed")
            logs = work_runner.run(
                _render_lifecycle(plan, contract, "logs", lifecycle_substitutions),
                cwd=evidence_root,
                timeout=min(30, work_runner.remaining()),
                check=False,
            )
            if logs.returncode != 0:
                raise BootstrapError("container logs were unavailable")
            _capture_json_output(evidence_root / "container-logs.json", logs)
            result = CommandResult(
                waited.argv,
                exit_code,
                logs.stdout,
                logs.stderr,
                waited.elapsed_seconds,
            )
        else:
            result = started
        if attached:
            _capture_json_output(evidence_root / "container-workload-result.json", result)
        _write_bytes(evidence_root / "stdout.log", result.stdout)
        _write_bytes(evidence_root / "stderr.log", result.stderr)
        if attached and result.returncode != 0:
            raise BootstrapError("owned container workload returned failure")
    except BaseException as exc:
        primary_error = exc
    try:
        payload_captured, payload_bytes = _copy_container_payload(
            container_id=container_id,
            run_id=run_id,
            phase="prestop",
            plan=plan,
            contract=contract,
            runner=cleanup_runner,
            evidence_root=evidence_root,
        )
        if payload_captured:
            payload_phase = "prestop"
        elif primary_error is None:
            primary_error = BootstrapError("container payload copy-out failed")
    except BaseException as exc:
        if primary_error is None:
            primary_error = exc
    cleanup_error: BaseException | None = None
    try:
        _cleanup_container(
            container_id=container_id,
            run_id=run_id,
            condition=condition,
            plan=plan,
            contract=contract,
            cleanup_runner=cleanup_runner,
            evidence_root=evidence_root,
            payload_captured=payload_captured,
            payload_bytes=payload_bytes,
            payload_phase=payload_phase,
        )
    except BaseException as exc:
        cleanup_error = exc
    if primary_error is not None:
        raise primary_error
    if cleanup_error is not None:
        raise cleanup_error
    if result is None:
        raise BootstrapError("owned container produced no command result")
    return result


def initialize_normalized_event_ledger(evidence_root: Path) -> None:
    path = evidence_root / "normalized-events.jsonl"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o600)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _append_normalized_event(path: Path, event: Mapping[str, object]) -> None:
    encoded = json.dumps(event, allow_nan=False, separators=(",", ":"), sort_keys=True).encode()
    encoded += b"\n"
    if len(encoded) > 16_384:
        raise BootstrapError("normalized event exceeds its cap")
    descriptor = os.open(path, os.O_WRONLY | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0))
    try:
        _write_all(descriptor, encoded)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _condition_configuration_refs(condition: str, mode: str) -> list[str]:
    filename = "smoke-reactive.yaml" if condition == "SIRA-REACTIVE" else "smoke-simulative.yaml"
    return [
        "containers/sira-smoke/bounded/bounded-smoke-plan-v2.json",
        "experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/conditions/" + filename,
        f"{mode}/resolved-command.json",
    ]


def _condition_field_provenance() -> dict[str, str]:
    return {
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


def run_condition(
    *,
    condition: str,
    plan: Mapping[str, object],
    contract: ModuleType,
    work_runner: CommandRunner,
    cleanup_runner: CommandRunner,
    image_id: str,
    evidence_root: Path,
    secret_file: Path,
    authorization: Mapping[str, object],
) -> None:
    index = list(contract.CONDITION_ORDER).index(condition)
    conditions = plan.get("conditions")
    if not isinstance(conditions, list) or not isinstance(conditions[index], Mapping):
        raise BootstrapError("condition plan is unavailable")
    template = conditions[index].get("container_create_argv_template")
    if not isinstance(template, list) or any(not isinstance(item, str) for item in template):
        raise BootstrapError("condition command template is invalid")
    condition_root = evidence_root / contract.MODE_VALUES[condition]
    condition_root.mkdir(mode=0o700, exist_ok=False)
    substitutions = {
        "${SIRA_SECRET_FILE}": str(secret_file),
        "${EXECUTION_COMMIT}": str(authorization["execution_commit"]),
        "${AUTHORIZATION_REFERENCE}": str(authorization["authorization_reference"]),
        "${IMAGE_ID}": image_id,
    }
    create_argv = contract.materialize_argv(template, substitutions)
    inner_argv = contract.condition_inner_argv(condition)
    configuration_refs = _condition_configuration_refs(condition, contract.MODE_VALUES[condition])
    _write_json(
        condition_root / "resolved-command.json",
        {
            "schema_version": contract.SCHEMA_VERSION,
            "condition": condition,
            "run_id": contract.RUN_IDS[condition],
            "container_create_argv": list(create_argv),
            "container_create_argv_sha256": contract.template_sha256(create_argv),
            "inner_argv": list(inner_argv),
            "inner_argv_sha256": contract.template_sha256(inner_argv),
            "configuration_refs": configuration_refs,
        },
    )
    decision = {
        "schema_version": contract.SCHEMA_VERSION,
        "plan_id": contract.PLAN_ID,
        "host_run_id": contract.HOST_RUN_ID,
        "run_id": contract.RUN_IDS[condition],
        "condition": condition,
        "source_kind": "experiment_assignment",
        "selected_mode": contract.MODE_VALUES[condition],
        "assignment_policy_sha256": _condition_plan_sha256(contract, condition),
        "resolved_configuration_refs": configuration_refs,
        "raw_artifact_roots": [
            f"{contract.MODE_VALUES[condition]}/payload/sira-output",
            f"{contract.MODE_VALUES[condition]}/payload/source-logs",
        ],
        "field_level_provenance": _condition_field_provenance(),
        "confidence": None,
        "override": None,
        "fallback": None,
        "critic": None,
        "configurator": None,
        "per_step_planning": None,
        "interpretation_allowed": False,
    }
    _write_json(condition_root / "regulation-decision.json", decision)
    index = list(contract.CONDITION_ORDER).index(condition)
    event_path = evidence_root / "normalized-events.jsonl"
    _append_normalized_event(
        event_path,
        {
            "schema_version": contract.SCHEMA_VERSION,
            "plan_id": contract.PLAN_ID,
            "host_run_id": contract.HOST_RUN_ID,
            "run_id": contract.RUN_IDS[condition],
            "event_sequence": index * 2 + 1,
            "event_type": "condition_assignment_bound",
            "condition": condition,
            "source_kind": "experiment_assignment",
            "evidence_reference": f"{contract.MODE_VALUES[condition]}/regulation-decision.json",
            "raw_artifact_refs": [],
            "resolved_configuration_refs": configuration_refs,
            "field_level_provenance": _condition_field_provenance(),
            "monotonic_timestamp_ns": time.monotonic_ns(),
            "wall_timestamp_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "interpretation_allowed": False,
        },
    )
    run_owned_container(
        condition=condition,
        run_id=contract.RUN_IDS[condition],
        create_template=template,
        substitutions=substitutions,
        plan=plan,
        contract=contract,
        work_runner=work_runner,
        cleanup_runner=cleanup_runner,
        evidence_root=condition_root,
        attached=True,
        wall_seconds=120,
    )
    payload = condition_root / "payload"
    artifact_paths = [
        path
        for path in _bounded_regular_files(payload, context="condition payload")
        if (
            path.parent == payload / "sira-output"
            or payload / "source-logs" in path.parents
            or path.name
            in {"provider-budget.json", "runtime-environment.json", "runtime-cleanup.json"}
        )
    ]
    raw_rows = []
    for path in artifact_paths:
        encoded = _read_regular(path, max_bytes=MAX_ATTEMPT_PAYLOAD_BYTES)
        raw_rows.append(
            {
                "path": path.relative_to(evidence_root).as_posix(),
                "bytes": len(encoded),
                "sha256": _sha256(encoded),
            }
        )
    session_rows = [
        row
        for row in raw_rows
        if str(row["path"]).endswith(".json") and "/sira-output/" in str(row["path"])
    ]
    log_rows = [row for row in raw_rows if "/source-logs/" in str(row["path"])]
    if len(session_rows) != 1 or not log_rows:
        raise BootstrapError("condition raw session or source-log evidence is incomplete")
    completion = {
        "schema_version": contract.SCHEMA_VERSION,
        "plan_id": contract.PLAN_ID,
        "host_run_id": contract.HOST_RUN_ID,
        "run_id": contract.RUN_IDS[condition],
        "condition": condition,
        "raw_artifacts": raw_rows,
        "raw_session_refs": [row["path"] for row in session_rows],
        "source_log_refs": [row["path"] for row in log_rows],
        "resolved_configuration_refs": configuration_refs,
        "field_level_provenance": {
            "raw_artifacts": "observed_file_bytes",
            "runtime": "observed_container_output",
            "accounting": "observed_provider_budget_boundary",
            "cleanup": "observed_runtime_close_record",
        },
        "interpretation_allowed": False,
    }
    _write_json(condition_root / "condition-completion.json", completion)
    _append_normalized_event(
        event_path,
        {
            "schema_version": contract.SCHEMA_VERSION,
            "plan_id": contract.PLAN_ID,
            "host_run_id": contract.HOST_RUN_ID,
            "run_id": contract.RUN_IDS[condition],
            "event_sequence": index * 2 + 2,
            "event_type": "condition_execution_completed",
            "condition": condition,
            "source_kind": "experiment_assignment",
            "evidence_reference": f"{contract.MODE_VALUES[condition]}/condition-completion.json",
            "raw_artifact_refs": [row["path"] for row in raw_rows],
            "resolved_configuration_refs": configuration_refs,
            "field_level_provenance": completion["field_level_provenance"],
            "monotonic_timestamp_ns": time.monotonic_ns(),
            "wall_timestamp_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "interpretation_allowed": False,
        },
    )


def package_evidence(
    evidence_root: Path,
    contract: ModuleType,
    *,
    secret_value: bytes,
) -> Path:
    captured = [
        (path, _read_regular(path, max_bytes=MAX_EVIDENCE_BYTES))
        for path in _bounded_regular_files(evidence_root, context="success evidence")
    ]
    _assert_secret_absent(evidence_root, secret_value, captured=captured)
    rows = [
        {
            "path": path.relative_to(evidence_root).as_posix(),
            "bytes": len(encoded),
            "sha256": _sha256(encoded),
        }
        for path, encoded in captured
        if path.name != "EVIDENCE_MANIFEST.json"
    ]
    total = sum(len(encoded) for path, encoded in captured if path.name != "EVIDENCE_MANIFEST.json")
    if len(rows) > MAX_EVIDENCE_FILES or total > MAX_EVIDENCE_BYTES:
        raise BootstrapError("success evidence exceeds its file or byte cap")
    manifest = {
        "schema_version": contract.SCHEMA_VERSION,
        "plan_id": contract.PLAN_ID,
        "host_run_id": contract.HOST_RUN_ID,
        "files": rows,
        "file_count": len(rows),
        "total_bytes": total,
    }
    contract.validate_evidence_manifest(manifest)
    manifest_path = evidence_root / "EVIDENCE_MANIFEST.json"
    _write_json(manifest_path, manifest)
    manifest_encoded = _read_regular(manifest_path, max_bytes=1_048_576)
    archive = evidence_root.parent / "t07-bounded-evidence.zip"
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_STORED) as output:
        for path, encoded in [*captured, (manifest_path, manifest_encoded)]:
            output.writestr(path.relative_to(evidence_root).as_posix(), encoded)
    if archive.stat().st_size > MAX_EVIDENCE_BYTES:
        raise BootstrapError("sealed evidence archive exceeds its cap")
    archive_descriptor = os.open(archive, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        os.fsync(archive_descriptor)
    finally:
        os.close(archive_descriptor)
    archive_digest = hashlib.sha256()
    with archive.open("rb") as source:
        while chunk := source.read(1_048_576):
            archive_digest.update(chunk)
    _write_json(
        evidence_root.parent / "ARCHIVE_IDENTITY.json",
        {
            "archive": archive.name,
            "bytes": archive.stat().st_size,
            "sha256": archive_digest.hexdigest(),
            "source_retained": True,
        },
    )
    return archive


def package_failure_evidence(
    output_root: Path,
    evidence_root: Path,
    contract: ModuleType,
    *,
    secret_value: bytes | None = None,
) -> Path:
    """Create a bounded secret-scanned archive after any post-root bootstrap failure."""

    archive = output_root / "t07-bounded-failure-evidence.zip"
    optional_candidates = _bounded_regular_files(evidence_root, context="failure evidence")
    incident = output_root / "TERMINATE_REQUIRED.json"
    if not incident.is_file() or incident.is_symlink():
        raise BootstrapError("failure evidence termination incident is unavailable")
    cleanup = evidence_root / "secret-cleanup.json"
    authority = evidence_root / "bootstrap-authority.json"
    mandatory_candidates = [incident]
    command_meter = evidence_root / "command-meter.jsonl"
    if command_meter.exists():
        if not command_meter.is_file() or command_meter.is_symlink():
            raise BootstrapError("failure evidence command meter is unsafe")
        mandatory_candidates.append(command_meter)
        optional_candidates.remove(command_meter)
    if authority.exists():
        if not authority.is_file() or authority.is_symlink():
            raise BootstrapError("failure evidence bootstrap authority is unsafe")
        mandatory_candidates.append(authority)
        optional_candidates.remove(authority)
    if cleanup.exists():
        if not cleanup.is_file() or cleanup.is_symlink():
            raise BootstrapError("failure evidence secret cleanup receipt is unsafe")
        mandatory_candidates.append(cleanup)
        optional_candidates.remove(cleanup)
    rows: list[dict[str, object]] = []
    retained: list[tuple[str, bytes]] = []
    skipped_sensitive = 0
    actual_secret_derivative_detected = False
    skipped_cap = 0
    payload_bytes = 0
    payload_limit = MAX_FAILURE_EVIDENCE_BYTES - 1_048_576

    def retain(path: Path, *, mandatory: bool) -> bool:
        nonlocal actual_secret_derivative_detected, payload_bytes, skipped_cap, skipped_sensitive
        relative = path.relative_to(output_root).as_posix()
        relative_encoded = relative.encode("utf-8")
        path_has_credential_material = secret_value is not None and _contains_secret_derivative(
            relative_encoded, secret_value
        )
        if (
            any(pattern.search(relative_encoded) for pattern in _SECRET_SHAPES)
            or path_has_credential_material
        ):
            if mandatory:
                raise BootstrapError(
                    "mandatory failure evidence has a secret-shaped path",
                    failure_code=(
                        "credential_material_detected"
                        if path_has_credential_material
                        else "bootstrap_contract_rejected"
                    ),
                )
            actual_secret_derivative_detected |= path_has_credential_material
            skipped_sensitive += 1
            return False
        try:
            encoded = _read_regular(path, max_bytes=MAX_EVIDENCE_BYTES)
        except BootstrapError:
            if mandatory:
                raise
            skipped_cap += 1
            return False
        content_has_credential_material = secret_value is not None and _contains_secret_derivative(
            encoded, secret_value
        )
        if _contains_artifact_secret(encoded) or content_has_credential_material:
            if mandatory:
                raise BootstrapError(
                    "mandatory failure evidence contains secret-shaped bytes",
                    failure_code=(
                        "credential_material_detected"
                        if content_has_credential_material
                        else "bootstrap_contract_rejected"
                    ),
                )
            actual_secret_derivative_detected |= content_has_credential_material
            skipped_sensitive += 1
            return False
        if payload_bytes + len(encoded) > payload_limit:
            if mandatory:
                raise BootstrapError("mandatory failure evidence exceeds its payload cap")
            skipped_cap += 1
            return False
        retained.append((relative, encoded))
        payload_bytes += len(encoded)
        rows.append({"path": relative, "bytes": len(encoded), "sha256": _sha256(encoded)})
        return True

    if len(mandatory_candidates) > MAX_EVIDENCE_FILES:
        raise BootstrapError("mandatory failure evidence exceeds its file cap")
    for path in mandatory_candidates:
        retain(path, mandatory=True)
    optional_slots = MAX_EVIDENCE_FILES - len(mandatory_candidates)
    for path in optional_candidates[:optional_slots]:
        retain(path, mandatory=False)
    if actual_secret_derivative_detected:
        incident_record = _strict_json(
            _read_regular(incident, max_bytes=65_536), context="termination incident"
        )
        incident_record["failure_stage"] = "evidence_packaging"
        incident_record["failure_class"] = "credential_material_detected"
        incident_record["manual_credential_rotation_required"] = True
        incident.unlink()
        _write_json(incident, incident_record)
        incident_relative = incident.relative_to(output_root).as_posix()
        retained = [row for row in retained if row[0] != incident_relative]
        rows = [row for row in rows if row["path"] != incident_relative]
        payload_bytes = sum(len(encoded) for _, encoded in retained)
        retain(incident, mandatory=True)
    manifest = {
        "schema_version": contract.SCHEMA_VERSION,
        "plan_id": contract.PLAN_ID,
        "host_run_id": contract.HOST_RUN_ID,
        "disposition": "bootstrap_failed",
        "files": rows,
        "file_count": len(rows),
        "payload_bytes": payload_bytes,
        "skipped_secret_shaped_file_count": skipped_sensitive,
        "skipped_cap_or_unsafe_file_count": skipped_cap
        + max(0, len(optional_candidates) - optional_slots),
        "secret_values_retained": False,
        "source_retained": True,
    }
    manifest_encoded = (
        json.dumps(manifest, allow_nan=False, indent=2, sort_keys=True).encode() + b"\n"
    )
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_STORED) as output:
        output.writestr("FAILURE_EVIDENCE_MANIFEST.json", manifest_encoded)
        for relative, encoded in retained:
            output.writestr(relative, encoded)
    archive_size = archive.stat(follow_symlinks=False).st_size
    if archive_size > MAX_FAILURE_EVIDENCE_BYTES:
        archive.unlink()
        raise BootstrapError("failure evidence archive exceeds its cap")
    archive_encoded = _read_regular(archive, max_bytes=MAX_FAILURE_EVIDENCE_BYTES)
    identity = {
        "schema_version": contract.SCHEMA_VERSION,
        "archive": archive.name,
        "bytes": archive_size,
        "sha256": _sha256(archive_encoded),
        "manifest_sha256": _sha256(manifest_encoded),
        "secret_scan_passed": True,
        "source_retained": True,
    }
    _write_json(output_root / "FAILURE_ARCHIVE_IDENTITY.json", identity)
    if evidence_root != output_root / "evidence":
        raise BootstrapError("failure evidence root identity drifted")
    return archive


def _create_early_failure_root(output_root: Path) -> tuple[Path, Path]:
    output = output_root.absolute()
    if output.resolve(strict=False) != output or output.parent.is_symlink():
        raise BootstrapError("early-failure output identity is unsafe")
    parent = output.parent.resolve(strict=True)
    if parent != output.parent or not parent.is_dir():
        raise BootstrapError("early-failure output parent is unsafe")
    root = parent / f"{output.name}-early-failure"
    root.mkdir(mode=0o700, exist_ok=False)
    evidence = root / "evidence"
    evidence.mkdir(mode=0o700)
    return root, evidence


def _use_reserved_early_failure_root(output_root: Path) -> tuple[Path, Path]:
    root = output_root.absolute()
    evidence = root / "evidence"
    if (
        root != REMOTE_OUTPUT_ROOT
        or root.resolve(strict=True) != root
        or root.is_symlink()
        or not root.is_dir()
        or evidence.resolve(strict=True) != evidence
        or evidence.is_symlink()
        or not evidence.is_dir()
        or {path.name for path in root.iterdir()} != {"evidence"}
        or any(evidence.iterdir())
    ):
        raise BootstrapError("reserved early-failure output root is not pristine")
    return root, evidence


def package_early_failure_evidence(
    output_root: Path,
    *,
    failure_stage: str,
    failure_code: str = "bootstrap_contract_rejected",
    secret_target_identity_established: bool,
    secret_cleanup_verified: bool,
    secret_value_read: bool,
    secret_cleanup_source: Path | None = None,
    reserved_output_root: bool = False,
) -> Path:
    """Seal a predictable minimal failure set when normal output setup never completed."""

    if failure_stage not in PRESECRET_FAILURE_STAGES:
        raise BootstrapError("early-failure stage is invalid")
    if failure_code not in FAILURE_CODES:
        raise BootstrapError("early-failure code is invalid")
    if secret_cleanup_verified != (secret_cleanup_source is not None):
        raise BootstrapError("early-failure cleanup receipt presence drifted")
    root, evidence = (
        _use_reserved_early_failure_root(output_root)
        if reserved_output_root
        else _create_early_failure_root(output_root)
    )
    disposition = {
        "schema_version": "0.1.0",
        "plan_id": "PLAN-T07-BOUNDED-SIRA-SMOKE-V2",
        "host_run_id": "RUN-T07-BOUNDED-HOST-0002",
        "failure_stage": failure_stage,
        "failure_code": failure_code,
        "message_retained": False,
        "secret_target_identity_established": secret_target_identity_established,
        "secret_cleanup_verified": secret_cleanup_verified,
        "manual_secret_deletion_and_rotation_required": not secret_cleanup_verified,
        "secret_value_read": secret_value_read,
        "value_or_hash_retained": False,
    }
    _write_json(evidence / "early-failure-disposition.json", disposition)
    if secret_cleanup_source is not None:
        cleanup = _read_regular(secret_cleanup_source, max_bytes=65_536)
        if _contains_artifact_secret(cleanup):
            raise BootstrapError("early-failure cleanup receipt is not secret-safe")
        cleanup_record = _strict_json(cleanup, context="early-failure secret cleanup")
        if cleanup_record != {
            "schema_version": "0.1.0",
            "secret_variable_name": "SIRA_API_KEY",
            "secret_file_basename": "sira_api_key",
            "held_identity_established_before_preflight": True,
            "truncated_before_unlink": True,
            "unlinked": True,
            "absence_verified": True,
            "path_identity_replaced": False,
            "value_or_hash_retained": False,
            "manual_fallback_deletion_required": False,
        }:
            raise BootstrapError("early-failure cleanup receipt is incomplete")
        _write_bytes(evidence / "secret-cleanup.json", cleanup, cap=65_536)
    incident = {
        "schema_version": "0.1.0",
        "provider_termination_required": True,
        "failure_stage": failure_stage,
        "failure_class": failure_code,
        "message_retained": False,
        "secret_cleanup_verified": secret_cleanup_verified,
        "manual_secret_deletion_required": not secret_cleanup_verified,
        "manual_credential_rotation_required": (
            not secret_cleanup_verified or failure_code == "credential_material_detected"
        ),
        "secret_target_validation_completed": secret_target_identity_established,
        "secret_value_read": secret_value_read,
    }
    _write_json(root / "TERMINATE_REQUIRED.json", incident)
    candidates = [
        evidence / "early-failure-disposition.json",
        *([evidence / "secret-cleanup.json"] if secret_cleanup_source is not None else []),
        root / "TERMINATE_REQUIRED.json",
    ]
    retained: list[tuple[str, bytes]] = []
    rows: list[dict[str, object]] = []
    payload_bytes = 0
    for path in candidates:
        relative = path.relative_to(root).as_posix()
        encoded = _read_regular(path, max_bytes=65_536)
        if any(
            pattern.search(relative.encode("utf-8")) for pattern in _SECRET_SHAPES
        ) or _contains_artifact_secret(encoded):
            raise BootstrapError("early-failure evidence is not secret-safe")
        payload_bytes += len(encoded)
        retained.append((relative, encoded))
        rows.append({"path": relative, "bytes": len(encoded), "sha256": _sha256(encoded)})
    manifest = {
        "schema_version": "0.1.0",
        "plan_id": "PLAN-T07-BOUNDED-SIRA-SMOKE-V2",
        "host_run_id": "RUN-T07-BOUNDED-HOST-0002",
        "disposition": "bootstrap_failed",
        "files": rows,
        "file_count": len(rows),
        "payload_bytes": payload_bytes,
        "skipped_secret_shaped_file_count": 0,
        "skipped_cap_or_unsafe_file_count": 0,
        "secret_values_retained": False,
        "source_retained": True,
    }
    manifest_encoded = (
        json.dumps(manifest, allow_nan=False, indent=2, sort_keys=True).encode() + b"\n"
    )
    archive = root / "t07-bounded-early-failure-evidence.zip"
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_STORED) as output:
        output.writestr("FAILURE_EVIDENCE_MANIFEST.json", manifest_encoded)
        for relative, encoded in retained:
            output.writestr(relative, encoded)
    archive_encoded = _read_regular(archive, max_bytes=MAX_EARLY_FAILURE_EVIDENCE_BYTES)
    identity = {
        "schema_version": "0.1.0",
        "archive": archive.name,
        "bytes": len(archive_encoded),
        "sha256": _sha256(archive_encoded),
        "manifest_sha256": _sha256(manifest_encoded),
        "secret_scan_passed": True,
        "source_retained": True,
    }
    _write_json(root / "EARLY_FAILURE_ARCHIVE_IDENTITY.json", identity)
    return archive


def validate_pair_evidence(evidence_root: Path, contract: ModuleType) -> None:
    usages: list[object] = []
    records: list[dict[str, object]] = []
    for condition in contract.CONDITION_ORDER:
        mode = contract.MODE_VALUES[condition]
        root = evidence_root / mode
        payload = root / "payload"
        budget = _strict_json(
            _read_regular(payload / "provider-budget.json", max_bytes=65_536),
            context=f"{mode} provider budget",
        )
        runtime = _strict_json(
            _read_regular(payload / "runtime-environment.json", max_bytes=65_536),
            context=f"{mode} runtime environment",
        )
        cleanup = _strict_json(
            _read_regular(payload / "runtime-cleanup.json", max_bytes=65_536),
            context=f"{mode} runtime cleanup",
        )
        command = _strict_json(
            _read_regular(root / "container-workload-result.json", max_bytes=65_536),
            context=f"{mode} command result",
        )
        if (
            budget.get("model_revision") != contract.MODEL
            or budget.get("request_service_tier") != "default"
            or budget.get("observed_response_service_tiers") != ["default"]
            or budget.get("default_service_tier_response_count")
            != budget.get("model_call_attempts")
            or budget.get("unreconciled_provider_attempts") != 0
            or runtime.get("routing_sha256") != contract.ROUTING_SHA256
            or cleanup.get("all_environment_closes_succeeded") is not True
        ):
            raise BootstrapError("condition accounting, routing, or browser cleanup drifted")
        output_bytes = sum(
            path.stat().st_size
            for path in _bounded_regular_files(root, context="condition evidence")
        )
        usage = contract.BudgetUsage(
            condition=condition,
            cost_usd=budget.get("cost_usd"),
            input_tokens=budget.get("input_tokens"),
            cached_input_tokens=budget.get("cached_input_tokens"),
            output_tokens=budget.get("output_tokens"),
            model_call_attempts=budget.get("model_call_attempts"),
            browser_actions=budget.get("browser_actions"),
            wall_seconds=command.get("elapsed_seconds"),
            output_bytes=output_bytes,
        )
        usages.append(usage)
        records.append(
            {
                "condition": condition,
                "run_id": contract.RUN_IDS[condition],
                "cost_usd": usage.cost_usd,
                "model_tokens": usage.total_tokens,
                "model_call_attempts": usage.model_call_attempts,
                "browser_actions": usage.browser_actions,
                "wall_seconds": usage.wall_seconds,
                "output_bytes": usage.output_bytes,
            }
        )
    contract.validate_pair_budget(usages)
    _write_json(
        evidence_root / "pair-budget.json",
        {
            "schema_version": contract.SCHEMA_VERSION,
            "plan_id": contract.PLAN_ID,
            "host_run_id": contract.HOST_RUN_ID,
            "condition_order": list(contract.CONDITION_ORDER),
            "conditions": records,
            "within_all_caps": True,
        },
    )


def _condition_plan_sha256(contract: ModuleType, condition: str) -> str:
    suffix = "smoke-reactive.yaml" if condition == "SIRA-REACTIVE" else "smoke-simulative.yaml"
    matches = [
        digest for path, digest in contract.SCIENTIFIC_HASHES.items() if str(path).endswith(suffix)
    ]
    if len(matches) != 1:
        raise BootstrapError("condition plan identity is unavailable")
    return str(matches[0])


def write_reconstruction_records(
    evidence_root: Path,
    *,
    contract: ModuleType,
) -> None:
    event_bytes = _read_regular(evidence_root / "normalized-events.jsonl", max_bytes=65_536)
    if len([line for line in event_bytes.splitlines() if line]) != 4:
        raise BootstrapError("normalized event ledger is incomplete")
    reactive = contract.container_create_argv("SIRA-REACTIVE")
    simulative = contract.container_create_argv("SIRA-SIMULATIVE")
    contract.assert_pair_command_contract(reactive, simulative)
    differences = [
        {"index": index, "reactive": left, "simulative": right}
        for index, (left, right) in enumerate(zip(reactive, simulative, strict=True))
        if left != right
    ]
    _write_json(
        evidence_root / "pair-equivalence.json",
        {
            "schema_version": contract.SCHEMA_VERSION,
            "plan_id": contract.PLAN_ID,
            "host_run_id": contract.HOST_RUN_ID,
            "condition_order": list(contract.CONDITION_ORDER),
            "reactive_command_sha256": contract.template_sha256(reactive),
            "simulative_command_sha256": contract.template_sha256(simulative),
            "difference_count": len(differences),
            "differences": differences,
            "canonical_condition_diff_only": True,
            "trace_instrumentation_changed_contrast": False,
            "interpretation_allowed": False,
        },
    )


def write_bootstrap_execution(
    evidence_root: Path,
    *,
    contract: ModuleType,
    status: str,
    started_at: datetime,
    ended_at: datetime | None = None,
) -> dict[str, object]:
    if status not in {"completed", "failed"}:
        raise BootstrapError("bootstrap execution status is invalid")
    started = started_at.astimezone(UTC)
    ended = datetime.now(UTC) if ended_at is None else ended_at.astimezone(UTC)
    elapsed = (ended - started).total_seconds()
    if not math.isfinite(elapsed) or elapsed < 0:
        raise BootstrapError("bootstrap execution wall interval is invalid")
    record = {
        "schema_version": contract.SCHEMA_VERSION,
        "plan_id": contract.PLAN_ID,
        "run_id": contract.HOST_RUN_ID,
        "record_kind": "remote_bootstrap_execution_interval",
        "started_at_utc": started.isoformat().replace("+00:00", "Z"),
        "ended_at_utc": ended.isoformat().replace("+00:00", "Z"),
        "wall_clock_seconds": elapsed,
        "status": status,
        "provider_allocation_accounting": False,
        "cost_accounting_authority": "local-post-termination-compute-closeout",
    }
    _write_json(evidence_root / "bootstrap-execution.json", record)
    return record


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bootstrap-file-sha256", required=True)
    parser.add_argument("--bundle-archive", type=Path, required=True)
    parser.add_argument("--bundle-archive-sha256", required=True)
    parser.add_argument("--bundle-manifest-sha256", required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--plan-sha256", required=True)
    parser.add_argument("--contract-file", type=Path, required=True)
    parser.add_argument("--contract-sha256", required=True)
    parser.add_argument("--authorization", type=Path, required=True)
    parser.add_argument("--authorization-sha256", required=True)
    parser.add_argument("--bootstrap-release", type=Path, required=True)
    parser.add_argument("--bootstrap-release-sha256", required=True)
    parser.add_argument("--bundle-root", type=Path, required=True)
    parser.add_argument("--secret-file", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    return parser


def _execute(
    args: argparse.Namespace,
    secret_lease: SecretLease,
    *,
    contract: ModuleType,
    plan: Mapping[str, object],
    authorization: Mapping[str, object],
    bootstrap_release: Mapping[str, object],
    starting_free_bytes: int,
) -> int:
    if "OPENAI_API_KEY" in os.environ or "SIRA_API_KEY" in os.environ:
        raise BootstrapError("credentials must not be inherited by the bootstrap")
    output_root = args.output_root.absolute()
    bundle_root = args.bundle_root.resolve(strict=True)
    evidence_root = output_root / "evidence"
    if (
        output_root != REMOTE_OUTPUT_ROOT
        or not output_root.is_dir()
        or output_root.is_symlink()
        or not evidence_root.is_dir()
        or evidence_root.is_symlink()
    ):
        raise BootstrapError("reserved remote output root identity drifted")
    _write_json(
        evidence_root / "bootstrap-authority.json",
        {
            "schema_version": contract.SCHEMA_VERSION,
            "plan_id": contract.PLAN_ID,
            "host_run_id": contract.HOST_RUN_ID,
            "authorization_reference": bootstrap_release["authorization_reference"],
            "execution_commit": bootstrap_release["execution_commit"],
            "plan_sha256": args.plan_sha256,
            "contract_sha256": args.contract_sha256,
            "authorization_sha256": args.authorization_sha256,
            "private_binding_sha256": bootstrap_release["private_binding_sha256"],
            "bootstrap_release_sha256": args.bootstrap_release_sha256,
            "bundle_archive_sha256": args.bundle_archive_sha256,
            "bundle_manifest_sha256": args.bundle_manifest_sha256,
            "bootstrap_file_sha256": args.bootstrap_file_sha256,
            "observer_state_sha256": bootstrap_release["observer_state_sha256"],
            "post_launch_report_sha256": bootstrap_release["post_launch_report_sha256"],
            "provider_active_observed_at_utc": bootstrap_release["provider_active_observed_at_utc"],
            "selected_provider_image": bootstrap_release["selected_provider_image"],
            "authority_validation_complete": True,
            "secret_value_or_hash_retained": False,
        },
    )
    bootstrap_started_at = datetime.now(UTC)
    incident = output_root / "TERMINATE_REQUIRED.json"
    launch = _parse_utc(
        authorization["supervised_wall_started_at_utc"], context="supervised wall start"
    )
    remaining = HARD_PROVIDER_WALL_SECONDS - (datetime.now(UTC) - launch).total_seconds()
    now_monotonic = time.monotonic()
    cleanup_reserve = int(contract.LIMITS["container_cleanup_reserve_seconds"])
    command_meter = CommandMeter(
        max_calls=int(contract.LIMITS["docker_lifecycle_calls"]),
        output_cap=int(contract.LIMITS["docker_control_output_bytes"]),
        cleanup_reserved_calls=int(contract.LIMITS["docker_cleanup_reserved_calls"]),
        cleanup_reserved_output_bytes=int(contract.LIMITS["docker_cleanup_reserved_output_bytes"]),
        ledger_path=evidence_root / "command-meter.jsonl",
    )
    work_runner = CommandRunner(
        deadline=now_monotonic + remaining - TERMINATION_HEADROOM_SECONDS - cleanup_reserve,
        meter=command_meter,
        scope="work",
    )
    cleanup_runner = CommandRunner(
        deadline=now_monotonic + remaining - TERMINATION_HEADROOM_SECONDS,
        meter=command_meter,
        scope="cleanup",
    )
    secret_value: bytes | None = None
    secret_cleanup_complete = False
    execution_stage = "host_environment"
    try:
        # The guarded failure path begins before the first byte of the real secret
        # is read.  If validation cannot prove an exact safe file identity, the
        # incident explicitly requires manual deletion rather than touching an
        # untrusted target.
        capture_host_environment(
            evidence_root=evidence_root,
            runner=work_runner,
            bootstrap_release=bootstrap_release,
            contract=contract,
        )
        execution_stage = "secret_read"
        secret_value = secret_lease.read_value()
        execution_stage = "build_context"
        context = prepare_build_context(
            bundle_root=bundle_root,
            work_root=output_root,
            plan=plan,
            contract=contract,
            runner=work_runner,
        )
        execution_stage = "image_build"
        image_id = build_image(
            context=context,
            execution_commit=str(authorization["execution_commit"]),
            authorization_reference=str(authorization["authorization_reference"]),
            runner=work_runner,
            contract=contract,
            evidence_root=evidence_root,
        )
        _assert_runtime_disk_increment(output_root, starting_free_bytes=starting_free_bytes)
        preflights = plan.get("preflights")
        if not isinstance(preflights, Mapping):
            raise BootstrapError("preflight plan is unavailable")
        browser_plan = preflights.get("browser")
        model_plan = preflights.get("model")
        if not isinstance(browser_plan, Mapping) or not isinstance(model_plan, Mapping):
            raise BootstrapError("preflight command binding is unavailable")
        browser_template = browser_plan.get("container_create_argv_template")
        model_template = model_plan.get("container_create_argv_template")
        if not isinstance(browser_template, list) or not isinstance(model_template, list):
            raise BootstrapError("preflight command template is unavailable")
        execution_stage = "browser_preflight"
        browser_root = evidence_root / "browser-preflight"
        browser_root.mkdir(mode=0o700)
        run_owned_container(
            condition="BROWSER-PREFLIGHT",
            run_id=contract.BROWSER_PREFLIGHT_RUN_ID,
            create_template=browser_template,
            substitutions={
                "${EXECUTION_COMMIT}": str(authorization["execution_commit"]),
                "${AUTHORIZATION_REFERENCE}": str(authorization["authorization_reference"]),
                "${IMAGE_ID}": image_id,
            },
            plan=plan,
            contract=contract,
            work_runner=work_runner,
            cleanup_runner=cleanup_runner,
            evidence_root=browser_root,
            attached=False,
            wall_seconds=60,
            readiness_container_path="/giclab/attempt/browser-preflight.json",
        )
        browser_payload = browser_root / "payload"
        browser_record = _strict_json(
            _read_regular(browser_payload / "browser-preflight.json", max_bytes=65_536),
            context="browser preflight",
        )
        if (
            browser_record.get("network_mode") != "none"
            or browser_record.get("browser_actions") != 1
            or browser_record.get("browser_running_before_container_stop") is not True
            or browser_record.get("browser_closed_by_fixture") is not False
            or browser_record.get("playwright_version") != contract.PLAYWRIGHT_VERSION
            or browser_record.get("chromium_revision") != contract.CHROMIUM_REVISION
            or b"chrom"
            not in (browser_root / "container-processes-before-stop.txt").read_bytes().lower()
        ):
            raise BootstrapError("browser preflight identity or cleanup drifted")
        _assert_runtime_disk_increment(output_root, starting_free_bytes=starting_free_bytes)
        _write_json(
            evidence_root / "image-provenance.json",
            {
                "schema_version": contract.SCHEMA_VERSION,
                "base_image": contract.BASE_IMAGE_INDEX,
                "base_image_index_digest": contract.BASE_IMAGE_INDEX_DIGEST,
                "base_image_amd64_manifest": contract.BASE_IMAGE_AMD64_MANIFEST,
                "base_image_amd64_config": contract.BASE_IMAGE_AMD64_CONFIG,
                "source_commit": contract.UPSTREAM_COMMIT,
                "source_tree": contract.UPSTREAM_TREE,
                "uv_lock_sha256": contract.UPSTREAM_LOCK_SHA256,
                "routing_patch_sha256": contract.ROUTING_PATCH_SHA256,
                "runtime_adaptation_sha256": contract.RUNTIME_ADAPTATION_SHA256,
                "playwright_version": browser_record["playwright_version"],
                "chromium_revision": browser_record["chromium_revision"],
                "chromium_version": browser_record["chromium_browser_version"],
                "chromium_executable_sha256": browser_record["chromium_executable_sha256"],
                "installed_package_manifest_sha256": browser_record[
                    "installed_package_manifest_sha256"
                ],
                "image_id": image_id,
                "platform": "linux/amd64",
            },
        )
        execution_stage = "model_preflight"
        model_root = evidence_root / "model-preflight"
        model_root.mkdir(mode=0o700)
        run_owned_container(
            condition="MODEL-PREFLIGHT",
            run_id=contract.MODEL_PREFLIGHT_RUN_ID,
            create_template=model_template,
            substitutions={
                "${SIRA_SECRET_FILE}": secret_lease.mount_path(),
                "${EXECUTION_COMMIT}": str(authorization["execution_commit"]),
                "${AUTHORIZATION_REFERENCE}": str(authorization["authorization_reference"]),
                "${IMAGE_ID}": image_id,
            },
            plan=plan,
            contract=contract,
            work_runner=work_runner,
            cleanup_runner=cleanup_runner,
            evidence_root=model_root,
            attached=True,
            wall_seconds=60,
        )
        model_record = _strict_json(
            _read_regular(model_root / "payload/model-availability.json", max_bytes=65_536),
            context="model availability",
        )
        if model_record != {
            "schema_version": contract.SCHEMA_VERSION,
            "method": "GET",
            "scheme": "https",
            "host": "api.openai.com",
            "path": f"/v1/models/{contract.MODEL}",
            "http_status": 200,
            "response_bytes": model_record.get("response_bytes"),
            "model": contract.MODEL,
            "available": True,
            "retry_count": 0,
            "redirect_follow_count": 0,
        } or not isinstance(model_record.get("response_bytes"), int):
            raise BootstrapError("model availability evidence drifted")
        _assert_runtime_disk_increment(output_root, starting_free_bytes=starting_free_bytes)
        initialize_normalized_event_ledger(evidence_root)
        execution_stage = "reactive_condition"
        run_condition(
            condition="SIRA-REACTIVE",
            plan=plan,
            contract=contract,
            work_runner=work_runner,
            cleanup_runner=cleanup_runner,
            image_id=image_id,
            evidence_root=evidence_root,
            secret_file=Path(secret_lease.mount_path()),
            authorization=authorization,
        )
        _assert_runtime_disk_increment(output_root, starting_free_bytes=starting_free_bytes)
        execution_stage = "simulative_condition"
        run_condition(
            condition="SIRA-SIMULATIVE",
            plan=plan,
            contract=contract,
            work_runner=work_runner,
            cleanup_runner=cleanup_runner,
            image_id=image_id,
            evidence_root=evidence_root,
            secret_file=Path(secret_lease.mount_path()),
            authorization=authorization,
        )
        _assert_runtime_disk_increment(output_root, starting_free_bytes=starting_free_bytes)
        execution_stage = "pair_validation"
        validate_pair_evidence(evidence_root, contract)
        write_reconstruction_records(evidence_root, contract=contract)
        write_bootstrap_execution(
            evidence_root,
            contract=contract,
            status="completed",
            started_at=bootstrap_started_at,
        )
        execution_stage = "evidence_packaging"
        secret_lease.destroy(evidence_root / "secret-cleanup.json")
        secret_cleanup_complete = True
        package_evidence(evidence_root, contract, secret_value=secret_value)
        _assert_runtime_disk_increment(output_root, starting_free_bytes=starting_free_bytes)
    except BaseException as exc:
        primary_failure_code = _sanitized_failure_code(exc)
        if not secret_cleanup_complete:
            try:
                secret_lease.destroy(evidence_root / "secret-cleanup.json")
                secret_cleanup_complete = True
            except BaseException:
                secret_cleanup_complete = False
        if not (evidence_root / "bootstrap-execution.json").exists():
            with contextlib.suppress(BaseException):
                write_bootstrap_execution(
                    evidence_root,
                    contract=contract,
                    status="failed",
                    started_at=bootstrap_started_at,
                )
        _write_json(
            incident,
            {
                "schema_version": "0.1.0",
                "provider_termination_required": True,
                "failure_stage": execution_stage,
                "failure_class": primary_failure_code,
                "message_retained": False,
                "secret_cleanup_verified": secret_cleanup_complete,
                "manual_secret_deletion_required": not secret_cleanup_complete,
                "manual_credential_rotation_required": (
                    not secret_cleanup_complete
                    or primary_failure_code == "credential_material_detected"
                ),
                "secret_target_validation_completed": True,
                "secret_value_read": secret_value is not None,
            },
        )
        try:
            package_failure_evidence(
                output_root,
                evidence_root,
                contract,
                secret_value=secret_value,
            )
        except BaseException as packaging_exc:
            if _sanitized_failure_code(packaging_exc) == "credential_material_detected":
                with contextlib.suppress(BaseException):
                    existing = _strict_json(
                        _read_regular(incident, max_bytes=65_536),
                        context="termination incident",
                    )
                    existing["failure_stage"] = "evidence_packaging"
                    existing["failure_class"] = "credential_material_detected"
                    existing["manual_credential_rotation_required"] = True
                    incident.unlink()
                    _write_json(incident, existing)
            with contextlib.suppress(BaseException):
                _write_json(
                    output_root / "FAILURE_ARCHIVE_ERROR.json",
                    {
                        "schema_version": "0.1.0",
                        "failure_archive_complete": False,
                        "failure_class": "failure_archive_unavailable",
                        "message_retained": False,
                        "provider_termination_required": True,
                    },
                )
        raise
    _write_json(
        incident,
        {
            "schema_version": "0.1.0",
            "provider_termination_required": True,
            "bootstrap_complete": True,
            "message_retained": False,
            "secret_cleanup_verified": True,
            "manual_secret_deletion_required": False,
            "manual_credential_rotation_required": False,
        },
    )
    return 0


def _reserve_single_use_output_root() -> int:
    output_root = REMOTE_OUTPUT_ROOT
    parent = output_root.parent
    if (
        output_root != output_root.absolute()
        or output_root.resolve(strict=False) != output_root
        or parent.resolve(strict=True) != parent
        or output_root.exists()
        or output_root.is_symlink()
    ):
        raise BootstrapError("remote output root is not fresh and canonical")
    os.mkdir(output_root, mode=0o700)
    parent_descriptor = os.open(
        parent,
        os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
    )
    try:
        os.fsync(parent_descriptor)
    finally:
        os.close(parent_descriptor)
    evidence_root = output_root / "evidence"
    evidence_root.mkdir(mode=0o700)
    output_descriptor = os.open(
        output_root,
        os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
    )
    try:
        os.fsync(output_descriptor)
    finally:
        os.close(output_descriptor)
    starting_free_bytes = shutil.disk_usage(parent).free
    _assert_remote_capacity(output_root)
    return starting_free_bytes


def _record_presecret_failure(*, failure_stage: str, failure_code: str) -> None:
    with contextlib.suppress(BaseException):
        package_early_failure_evidence(
            REMOTE_OUTPUT_ROOT,
            failure_stage=failure_stage,
            failure_code=failure_code,
            secret_target_identity_established=False,
            secret_cleanup_verified=False,
            secret_value_read=False,
            reserved_output_root=True,
        )


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    presecret_stage = "run_identity_reservation"
    attempt_claimed = False
    try:
        # The fixed output root is the authoritative one-shot run claim.  It is
        # reserved before any fallible authority, archive, plan, or contract
        # validation so every terminal pre-secret failure burns this run identity.
        starting_free_bytes = _reserve_single_use_output_root()
        attempt_claimed = True
        presecret_stage = "inherited_environment_guard"
        if "OPENAI_API_KEY" in os.environ or "SIRA_API_KEY" in os.environ:
            raise BootstrapError("credentials must not be inherited by the bootstrap")
        presecret_stage = "invocation_validation"
        _validate_invocation_paths(args)
        presecret_stage = "authorization_validation"
        authorization = validate_authorization(
            _read_regular(args.authorization, max_bytes=MAX_AUTHORIZATION_BYTES),
            expected_sha256=args.authorization_sha256,
            plan_sha256=args.plan_sha256,
        )
        presecret_stage = "release_validation"
        bootstrap_release = validate_bootstrap_release(
            _read_regular(args.bootstrap_release, max_bytes=MAX_AUTHORIZATION_BYTES),
            expected_sha256=args.bootstrap_release_sha256,
            plan_sha256=args.plan_sha256,
            authorization_sha256=args.authorization_sha256,
            authorization=authorization,
        )
        presecret_stage = "bootstrap_hash_validation"
        _validate_bootstrap_file(
            argv_sha256=args.bootstrap_file_sha256,
            release_sha256=bootstrap_release.get("bootstrap_file_sha256"),
        )
        presecret_stage = "archive_validation"
        captured = _read_validated_upload_archive(
            args,
            release_archive_sha256=bootstrap_release.get("bundle_archive_sha256"),
        )
        presecret_stage = "manifest_validation"
        bundle_manifest = _validate_upload_manifest(
            args,
            captured,
            release_manifest_sha256=bootstrap_release.get("bundle_manifest_sha256"),
            execution_commit=bootstrap_release.get("execution_commit"),
        )
        presecret_stage = "plan_validation"
        plan_bytes = captured.get("containers/sira-smoke/bounded/bounded-smoke-plan-v2.json")
        if (
            plan_bytes is None
            or _HEX64.fullmatch(args.plan_sha256) is None
            or _sha256(plan_bytes) != args.plan_sha256
        ):
            raise BootstrapError("bounded plan hash drifted")
        plan = _strict_json(plan_bytes, context="bounded plan")
        _validate_bundle_against_plan(
            bundle_manifest,
            captured,
            plan=plan,
            plan_sha256=args.plan_sha256,
            execution_commit=bootstrap_release["execution_commit"],
        )
        presecret_stage = "bundle_extraction"
        _extract_validated_bundle(captured)
        presecret_stage = "contract_hash_validation"
        contract_bytes = _read_regular(args.contract_file, max_bytes=1_048_576)
        if (
            _HEX64.fullmatch(args.contract_sha256) is None
            or _sha256(contract_bytes) != args.contract_sha256
        ):
            raise BootstrapError("bounded contract module hash drifted")
        presecret_stage = "contract_import"
        contract = _load_contract(args.contract_file, contract_bytes)
        presecret_stage = "contract_validation"
        contract.validate_plan(plan, repository_root=args.bundle_root)
        if (
            contract.SCHEMA_VERSION != SCHEMA_VERSION
            or contract.PLAN_ID != PLAN_ID
            or contract.HOST_RUN_ID != HOST_RUN_ID
            or contract.BRANCH != BRANCH
            or contract.REACTIVE_RUN_ID != REACTIVE_RUN_ID
            or contract.SIMULATIVE_RUN_ID != SIMULATIVE_RUN_ID
            or contract.MODEL != MODEL
            or contract.SELECTED_IMAGE_ALIAS != SELECTED_IMAGE_ALIAS
            or contract.SELECTED_IMAGE_FAMILY != SELECTED_IMAGE_FAMILY
            or contract.SELECTED_IMAGE_VERSION != SELECTED_IMAGE_VERSION
            or _sha256(contract.canonical_json_bytes(dict(contract.LIMITS))) != LIMITS_SHA256
        ):
            raise BootstrapError("reviewed contract differs from bootstrap trust anchors")
    except BaseException as exc:
        if attempt_claimed or REMOTE_OUTPUT_ROOT.is_dir():
            _record_presecret_failure(
                failure_stage=presecret_stage,
                failure_code=_sanitized_failure_code(exc),
            )
        raise
    forbidden_roots = (
        args.bundle_root.resolve(strict=False),
        args.output_root.absolute(),
    )
    try:
        secret_lease = acquire_secret_lease(
            args.secret_file.absolute(), forbidden_roots=forbidden_roots
        )
    except BaseException as exc:
        with contextlib.suppress(BaseException):
            package_early_failure_evidence(
                args.output_root,
                failure_stage="secret_target_validation",
                failure_code=_sanitized_failure_code(exc),
                secret_target_identity_established=False,
                secret_cleanup_verified=False,
                secret_value_read=False,
                reserved_output_root=True,
            )
        raise
    try:
        return _execute(
            args,
            secret_lease,
            contract=contract,
            plan=plan,
            authorization=authorization,
            bootstrap_release=bootstrap_release,
            starting_free_bytes=starting_free_bytes,
        )
    except BaseException as exc:
        cleanup_source = args.output_root.absolute() / "evidence/secret-cleanup.json"
        if not secret_lease.destroyed:
            try:
                early_cleanup = args.secret_file.parent / "t07-bounded-secret-cleanup-0002.json"
                secret_lease.destroy(early_cleanup)
                cleanup_verified = True
                cleanup_source = early_cleanup
            except BaseException:
                cleanup_verified = False
        else:
            cleanup_verified = cleanup_source.is_file() and not cleanup_source.is_symlink()
        normal_identity = args.output_root.absolute() / "FAILURE_ARCHIVE_IDENTITY.json"
        if not normal_identity.is_file() or normal_identity.is_symlink():
            with contextlib.suppress(BaseException):
                package_early_failure_evidence(
                    args.output_root,
                    failure_stage="normal_failure_packaging",
                    failure_code=_sanitized_failure_code(exc),
                    secret_target_identity_established=True,
                    secret_cleanup_verified=cleanup_verified,
                    secret_value_read=secret_lease.value_read,
                    secret_cleanup_source=cleanup_source if cleanup_verified else None,
                )
        raise
    finally:
        secret_lease.close()


if __name__ == "__main__":
    raise SystemExit(main())
