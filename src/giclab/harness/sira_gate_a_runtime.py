"""Repository-owned runtime adaptation for the pinned SiRA smoke.

The adapter is executed by the already-installed, external SiRA environment.  It
does not modify the upstream checkout.  It replaces only the provider construction,
log destinations, and environment cleanup surfaces before calling the pinned runner.
"""

from __future__ import annotations

import argparse
import builtins
import codecs
import contextlib
import copy
import importlib.util
import io
import json
import locale
import os
import platform
import resource
import stat
import sys
import threading
import time
from collections.abc import Callable, Iterator, Mapping, Sequence
from pathlib import Path
from types import ModuleType
from typing import Any

from giclab.control.remote_bridge import ConditionSessionBinding
from giclab.harness import t09_sira_pilot as t09_pilot
from giclab.harness.safety import CredentialExposureError, ExactCredentialScrubber
from giclab.harness.sira_gate_a import (
    SIRA_API_BASE_URL,
    SIRA_MODEL_REVISION,
    SIRA_SECRET_VARIABLE,
    SIRA_SERVICE_TIER,
    GateAContractError,
    ImmutableModelRouting,
    ModelRole,
    ProviderBudgetBoundary,
    ProviderBudgetUsage,
    ProviderCallTerminalState,
    ProviderFailureDisposition,
    ProviderRequest,
    ProviderResponseReceiptError,
    ProviderResponseUsage,
    aggregate_caps,
    condition_caps,
    file_sha256,
    validate_sira_secret_names,
)
from giclab.harness.t09_provider_contracts import provider_contract
from giclab.harness.t09_runtime_admission import (
    InProcessBoundaryPort,
    RuntimeAdmissionPort,
    build_private_socket_supervisor_port,
)
from giclab.harness.t09_sira_pilot import (
    EventWriter,
    PilotExecutionContract,
    ResourceGuard,
    T09PilotError,
    confirm_supervised_empirical_entry,
    load_aggregate_observed_usage,
    load_aggregate_usage,
    load_execution_contract,
    pilot_state_time_origins,
    usage_from_document,
    write_aggregate_usage,
)

SIRA_MAX_OUTPUT_TOKENS_PER_CHOICE = 4_096
MAX_RUNTIME_CORE_SCAN_ENTRIES = 100_000


def _attempt_root_matches_raw_binding(attempt_root: Path, raw_output_root: str) -> bool:
    """Match the runtime-owned raw root, not its parent logical attempt root."""

    expected_suffix = Path(raw_output_root).parts
    return (
        bool(expected_suffix)
        and len(attempt_root.parts) >= len(expected_suffix)
        and attempt_root.parts[-len(expected_suffix) :] == expected_suffix
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--gate-upstream-runner", type=Path, required=True)
    parser.add_argument("--gate-attempt-root", type=Path, required=True)
    parser.add_argument("--gate-mode", choices=("reactive", "simulative"), required=True)
    parser.add_argument("--gate-adaptation-sha256", required=True)
    parser.add_argument("--gate-pilot-contract", type=Path)
    parser.add_argument("--gate-pilot-contract-sha256")
    parser.add_argument("--gate-pilot-library-sha256")
    parser.add_argument("--gate-pilot-attempt-id")
    parser.add_argument("--gate-condition-plan", type=Path)
    parser.add_argument("--gate-aggregate-ledger", type=Path)
    parser.add_argument("--gate-pilot-state", type=Path)
    parser.add_argument(
        "--gate-admission-mode",
        choices=("historical-in-process", "duplex-supervisor"),
        default="historical-in-process",
    )
    parser.add_argument("--gate-duplex-binding", type=Path)
    parser.add_argument("--gate-duplex-session-id")
    parser.add_argument("--gate-duplex-frozen-manifest-sha256")
    parser.add_argument("--gate-duplex-transaction-root-identity")
    parser.add_argument("upstream_argv", nargs=argparse.REMAINDER)
    return parser


def _usage(response: Any) -> ProviderResponseUsage:
    service_tier = (
        response.get("service_tier")
        if isinstance(response, Mapping)
        else getattr(response, "service_tier", None)
    )
    if service_tier != SIRA_SERVICE_TIER:
        raise GateAContractError("provider response service_tier must be exactly default")
    raw = (
        response.get("usage") if isinstance(response, Mapping) else getattr(response, "usage", None)
    )
    if raw is None:
        raise GateAContractError("provider response omitted required usage accounting")

    def value(*names: str) -> int:
        for name in names:
            candidate = raw.get(name) if isinstance(raw, Mapping) else getattr(raw, name, None)
            if candidate is not None:
                if type(candidate) is not int or candidate < 0:
                    raise GateAContractError(f"provider usage {name} is invalid")
                return candidate
        raise GateAContractError(f"provider response omitted usage field {names[0]}")

    input_tokens = value("prompt_tokens", "input_tokens")
    output_tokens = value("completion_tokens", "output_tokens")
    details = (
        raw.get("prompt_tokens_details")
        if isinstance(raw, Mapping)
        else getattr(raw, "prompt_tokens_details", None)
    )
    cached_tokens = 0
    if details is not None:
        cached = (
            details.get("cached_tokens")
            if isinstance(details, Mapping)
            else getattr(details, "cached_tokens", 0)
        )
        if cached is not None:
            if type(cached) is not int or cached < 0:
                raise GateAContractError("provider cached-token usage is invalid")
            cached_tokens = cached
    return ProviderResponseUsage(
        input_tokens=input_tokens,
        cached_input_tokens=cached_tokens,
        output_tokens=output_tokens,
        service_tier=service_tier,
    )


_KNOWN_PROVIDER_ERROR_TYPES = frozenset(
    {
        "APIError",
        "AuthenticationError",
        "BadRequestError",
        "ContentPolicyViolationError",
        "ContextWindowExceededError",
        "NotFoundError",
        "PermissionDeniedError",
        "RateLimitError",
        "ServiceUnavailableError",
        "UnprocessableEntityError",
    }
)


def _classify_provider_failure(exc: BaseException) -> ProviderFailureDisposition:
    """Classify only explicit provider responses; ambiguity remains charged unknown."""

    if type(exc).__name__ in _KNOWN_PROVIDER_ERROR_TYPES:
        return ProviderFailureDisposition.PROVIDER_ERROR
    return ProviderFailureDisposition.OUTCOME_UNKNOWN


_LEDGER_WRITE_LOCK = threading.Lock()


class _PilotLineage(threading.local):
    parent_event_id: str | None = None
    action_event_id: str | None = None


def _json_safe(value: object) -> object:
    """Convert post-action provider objects to retained JSON without value inference."""

    def fallback(item: object) -> object:
        scalar = getattr(item, "item", None)
        if callable(scalar):
            try:
                return scalar()
            except (TypeError, ValueError):
                pass
        return {"unavailable_type": type(item).__name__}

    return json.loads(json.dumps(value, default=fallback))


def _ledger_document(
    usage: ProviderBudgetUsage,
    unreconciled_provider_attempts: int,
) -> dict[str, object]:
    return {
        "schema_version": "0.1.0",
        "model_revision": SIRA_MODEL_REVISION,
        "request_service_tier": SIRA_SERVICE_TIER,
        "observed_response_service_tiers": (
            [SIRA_SERVICE_TIER] if usage.default_service_tier_responses > 0 else []
        ),
        "default_service_tier_response_count": usage.default_service_tier_responses,
        "cost_usd": usage.cost_usd,
        "input_tokens": usage.input_tokens,
        "cached_input_tokens": usage.cached_input_tokens,
        "output_tokens": usage.output_tokens,
        "total_tokens": usage.total_tokens,
        "model_call_attempts": usage.model_call_attempts,
        "unreconciled_provider_attempts": unreconciled_provider_attempts,
        "browser_actions": usage.browser_actions,
        "output_bytes": usage.output_bytes,
    }


def _write_ledger(path: Path, boundary: ProviderBudgetBoundary) -> None:
    _write_usage_ledger(
        path,
        boundary.condition_usage,
        boundary.unreconciled_provider_attempts,
    )


def _write_usage_ledger(
    path: Path,
    usage: ProviderBudgetUsage,
    unreconciled_provider_attempts: int,
    *,
    reserve_temporary_bytes: Callable[[int], None] | None = None,
    require_output_admission: bool = False,
) -> None:
    with _LEDGER_WRITE_LOCK:
        _publish_json_evidence(
            path,
            _ledger_document(usage, unreconciled_provider_attempts),
            temporary=path.with_suffix(f".{threading.get_ident()}.tmp"),
            reserve_temporary_bytes=reserve_temporary_bytes,
            require_output_admission=require_output_admission,
        )


def _session_path(upstream_argv: Sequence[str]) -> Path:
    indexes = [index for index, value in enumerate(upstream_argv) if value == "--output_dir"]
    if len(indexes) != 1 or indexes[0] + 1 >= len(upstream_argv):
        raise GateAContractError("upstream output directory is unavailable for reconciliation")
    output_directory = Path(upstream_argv[indexes[0] + 1]).resolve(strict=True)
    sessions = sorted(
        path
        for path in output_directory.glob("*.json")
        if path.name != "output.jsonl" and path.is_file() and not path.is_symlink()
    )
    if len(sessions) != 1:
        raise GateAContractError("browser-action reconciliation requires one session JSON")
    return sessions[0]


def _session_history(upstream_argv: Sequence[str]) -> list[object]:
    session = json.loads(_session_path(upstream_argv).read_text(encoding="utf-8"))
    history = session.get("history") if isinstance(session, Mapping) else None
    if not isinstance(history, list):
        raise GateAContractError("session history is unavailable for browser-action accounting")
    return history


def _write_json_evidence(
    path: Path,
    value: object,
    *,
    reserve_temporary_bytes: Callable[[int], None] | None = None,
    require_output_admission: bool = False,
) -> None:
    """Atomically fsync one value-only evidence record."""

    _publish_json_evidence(
        path,
        value,
        temporary=path.with_suffix(f".{os.getpid()}.tmp"),
        reserve_temporary_bytes=reserve_temporary_bytes,
        require_output_admission=require_output_admission,
    )


def _publish_json_evidence(
    path: Path,
    value: object,
    *,
    temporary: Path,
    reserve_temporary_bytes: Callable[[int], None] | None,
    require_output_admission: bool,
) -> None:
    """Expose the atomic writer's full temporary growth before any mutation.

    The caller owns admission. This writer cannot issue, extend or release an
    allowance, and does not confuse a replacement's full temporary allocation
    with its net published growth. In particular it must not subtract the old
    file size: both files exist until replacement. Observed scope totals and
    unused capacity remain the caller's responsibility, including on failure.

    Existing callers retain their historical behavior when admission is not
    required. Remote scope allocation must explicitly supply this boundary;
    adding the callback alone does not establish admission for those callers.
    """
    if require_output_admission and reserve_temporary_bytes is None:
        raise GateAContractError("JSON evidence writer has no bound output admission")
    encoded = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")
    if reserve_temporary_bytes is not None:
        reserve_temporary_bytes(len(encoded))
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    # Exclusive creation preserves a stale/replacement temporary record. A
    # failed write retains the exact created prefix rather than removing
    # evidence or implicitly returning its reservation to the allocator.
    with temporary.open("xb", buffering=0) as handle:
        offset = 0
        while offset < len(encoded):
            count = handle.write(encoded[offset:])
            if count is None or count <= 0:
                raise OSError("JSON evidence write made no progress")
            offset += count
        os.fsync(handle.fileno())
    os.replace(temporary, path)
    directory = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


class _AdmittedPublicationAllowance:
    """A consumption-only view of one already admitted output reservation."""

    def __init__(self, capacity: int) -> None:
        if type(capacity) is not int or capacity < 0:
            raise GateAContractError("runtime publication allowance capacity is malformed")
        self._remaining = capacity
        self._denied = False
        self._lock = threading.Lock()

    @property
    def remaining(self) -> int:
        with self._lock:
            return self._remaining

    def require_no_denial(self) -> None:
        with self._lock:
            if self._denied:
                raise GateAContractError("runtime publication allowance has a retained denial")

    def __call__(self, count: int) -> None:
        with self._lock:
            if self._denied or type(count) is not int or not 0 <= count <= self._remaining:
                self._denied = True
                raise GateAContractError("runtime publication allowance exhausted")
            self._remaining -= count


def _reserve_terminal_publications(
    admission_port: RuntimeAdmissionPort, *, capacity: int = 64 * 1024
) -> _AdmittedPublicationAllowance:
    """Prefund full terminal JSON temporaries before reservations can be denied.

    The shared accountant admits the unchanged condition/campaign bounds. This
    consumption mirror cannot enlarge capacity, claim observations, or free a
    retained failed prefix. Unconsumed capacity remains unavailable to a census
    of other writers and is explicitly carried in the output observation.
    """
    if type(capacity) is not int or not 0 < capacity <= 64 * 1024:
        raise GateAContractError("runtime terminal publication allocation is invalid")
    admission_port.reserve_output_growth(capacity)
    return _AdmittedPublicationAllowance(capacity)


class _AdmittedSourceStream:
    """Lazy stream for the retained Python session/logger writers only.

    Admit the encoded bytes before opening/truncating or writing. No descriptor
    or raw-buffer escape is exposed. This is a writer boundary, not a sandbox
    for arbitrary native code; attach streams and other roles have separate
    retained writers and must be admitted separately.
    """

    def __init__(self, opener: Callable[[], Any], consume: Callable[[int], None], *, binary: bool):
        self._opener = opener
        self._consume = consume
        self._binary = binary
        self._stream: Any = None
        self._closed = False
        self._lock = threading.RLock()

    def write(self, value: Any) -> int:
        with self._lock:
            if self._closed:
                raise ValueError("source stream is closed")
            if self._binary:
                if not isinstance(value, (bytes, bytearray, memoryview)):
                    raise TypeError("binary source stream requires bytes")
                size = len(bytes(value))
            else:
                if not isinstance(value, str):
                    raise TypeError("text source stream requires text")
                size = len(value.encode("utf-8"))
            self._consume(size)
            if self._stream is None:
                self._stream = self._opener()
            return int(self._stream.write(value))

    def writelines(self, values: Any) -> None:
        for value in values:
            self.write(value)

    def flush(self) -> None:
        with self._lock:
            if self._stream is not None:
                self._stream.flush()

    def close(self) -> None:
        with self._lock:
            if self._stream is not None:
                self._stream.close()
            self._closed = True

    @property
    def closed(self) -> bool:
        return self._closed

    @property
    def encoding(self) -> str | None:
        return None if self._binary else "utf-8"

    def __enter__(self) -> _AdmittedSourceStream:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


@contextlib.contextmanager
def _admit_source_writers(
    attempt_root: Path, allowance: _AdmittedPublicationAllowance
) -> Iterator[None]:
    """Bind Python open/Path.open at the two retained upstream output roles."""
    roots = (attempt_root / "sira-output", attempt_root / "source-logs")
    original_open, original_io_open = builtins.open, io.open
    streams: list[_AdmittedSourceStream] = []

    def guarded_open(file: Any, mode: str = "r", *args: Any, **kwargs: Any) -> Any:
        if not isinstance(file, (str, bytes, os.PathLike)) or not any(c in mode for c in "wax+"):
            return original_open(file, mode, *args, **kwargs)
        path = Path(os.fsdecode(file)).absolute()
        if not any(path.is_relative_to(root) for root in roots):
            return original_open(file, mode, *args, **kwargs)
        if ".." in path.parts or any(parent.is_symlink() for parent in (path, *path.parents)):
            raise GateAContractError("source output path is unsafe")
        names = ("buffering", "encoding", "errors", "newline", "closefd", "opener")
        if len(args) > len(names) or any(name in kwargs for name in names[: len(args)]):
            raise TypeError("source writer has duplicate or excessive open arguments")
        kwargs = {**dict(zip(names, args, strict=False)), **kwargs}
        if (
            mode not in {"w", "a", "x", "wb", "ab", "xb", "wt", "at", "xt"}
            or kwargs.get("opener") is not None
            or kwargs.get("closefd") is False
        ):
            raise GateAContractError("source writer requires its bound simple output mode")
        if "b" not in mode:
            encoding = kwargs.get("encoding")
            if encoding in (None, "locale"):
                encoding = locale.getencoding()
            if (
                not isinstance(encoding, str)
                or codecs.lookup(encoding).name != "utf-8"
                or kwargs.get("newline") not in (None, "", "\n")
                or kwargs.get("errors") not in (None, "strict")
            ):
                raise GateAContractError("source writer requires exact UTF-8 byte accounting")
            kwargs = {**kwargs, "encoding": "utf-8"}

        def open_bound() -> Any:
            # Resolve every directory with no-follow descriptors, then inspect
            # the opened target before truncation. A hard link or nonregular
            # replacement cannot turn output admission into write authority.
            directories: list[tuple[Path, int]] = []
            descriptor: int | None = None
            try:
                parent_fd = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY)
                directories.append((Path(path.anchor), parent_fd))
                current = Path(path.anchor)
                for part in path.parts[1:-1]:
                    current /= part
                    parent_fd = os.open(
                        part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd
                    )
                    directories.append((current, parent_fd))
                for directory, held_fd in directories:
                    if directory.lstat() != os.fstat(held_fd):
                        raise GateAContractError("source output directory changed")
                flags = os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK
                if "x" in mode:
                    flags |= os.O_EXCL
                if "a" in mode:
                    flags |= os.O_APPEND
                descriptor = os.open(path.name, flags, 0o600, dir_fd=parent_fd)
                metadata = os.fstat(descriptor)
                if (
                    not stat.S_ISREG(metadata.st_mode)
                    or metadata.st_nlink != 1
                    or metadata.st_uid != os.geteuid()
                    or path.lstat() != metadata
                ):
                    raise GateAContractError("source output file identity is unsafe")
                if "w" in mode:
                    os.ftruncate(descriptor, 0)
                opened = original_open(descriptor, mode, **kwargs)
                descriptor = None
                return opened
            finally:
                if descriptor is not None:
                    os.close(descriptor)
                for _, held_fd in reversed(directories):
                    os.close(held_fd)

        stream = _AdmittedSourceStream(open_bound, allowance, binary="b" in mode)
        streams.append(stream)
        return stream

    builtins.open = guarded_open
    io.open = guarded_open
    try:
        yield
    finally:
        builtins.open, io.open = original_open, original_io_open
        for stream in streams:
            stream.close()
    # Logging handlers may catch write exceptions. A caught admission denial
    # remains fatal for this runtime; it cannot silently become a valid answer.
    allowance.require_no_denial()


def _remove_secret_bearing_artifacts(
    root: Path,
    scrubber: ExactCredentialScrubber,
) -> list[str]:
    """Remove any retained file containing the exact injected credential."""

    removed: list[str] = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink() or not path.is_file():
            continue
        try:
            scrubber.assert_file(path, label="retained pilot artifact")
        except CredentialExposureError:
            removed.append(path.relative_to(root).as_posix())
            path.unlink()
    return removed


def _privacy_safe_runtime_secret_cleanup(
    *,
    attempt_root: Path,
    observed_credentials: Sequence[str],
    core_scan_integrity_failure: bool,
    core_destruction_verified: bool,
) -> tuple[dict[str, object], list[str]]:
    """Drop the credential without reading files unless core safety is proven."""

    cleanup: dict[str, object] = {
        "credential_observed": False,
        "credential_removed_from_environment": False,
        "content_scan_permitted": False,
        "secret_bearing_artifacts_removed": [],
        "remaining_exact_credential_matches": None,
    }
    errors: list[str] = []
    os.environ.pop(SIRA_SECRET_VARIABLE, None)
    cleanup["credential_removed_from_environment"] = True
    if len(observed_credentials) != 1:
        errors.append("CredentialObservationIncomplete")
        return cleanup, errors
    cleanup["credential_observed"] = True
    if core_scan_integrity_failure or not core_destruction_verified:
        errors.append("CredentialCleanupIntegrityUnknownDueToCoreSafety")
        return cleanup, errors
    cleanup["content_scan_permitted"] = True
    scrubber = ExactCredentialScrubber(observed_credentials)
    removed = _remove_secret_bearing_artifacts(attempt_root, scrubber)
    cleanup["secret_bearing_artifacts_removed"] = removed
    remaining_matches = 0
    for retained_path in sorted(attempt_root.rglob("*")):
        if retained_path.is_symlink() or not retained_path.is_file():
            continue
        try:
            scrubber.assert_file(retained_path, label="retained pilot artifact")
        except CredentialExposureError:
            remaining_matches += 1
    cleanup["remaining_exact_credential_matches"] = remaining_matches
    if remaining_matches:
        errors.append("CredentialExposureError")
    return cleanup, errors


def _elf_is_core(path: Path) -> bool:
    descriptor = os.open(
        path,
        os.O_RDONLY | os.O_NONBLOCK | getattr(os, "O_NOFOLLOW", 0),
    )
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            return False
        header = os.read(descriptor, 18)
    finally:
        os.close(descriptor)
    if len(header) < 18 or header[:4] != b"\x7fELF":
        return False
    if header[5] == 1:
        return int.from_bytes(header[16:18], "little") == 4
    if header[5] == 2:
        return int.from_bytes(header[16:18], "big") == 4
    return False


def _runtime_core_census_roots(
    roots: Sequence[tuple[str, Path]],
) -> tuple[list[dict[str, object]], list[Path]]:
    """Census one explicit, validated set of condition-writable roots."""

    observed_entries: list[tuple[str, Path, os.stat_result, bool, bool]] = []
    core_inodes: set[tuple[int, int]] = set()
    inode_counts: dict[tuple[int, int], int] = {}
    observed = 0
    for label, root in roots:
        if not root.is_dir() or root.is_symlink():
            raise GateAContractError("condition writable-root core census root is unsafe")
        for path in sorted(root.rglob("*")):
            observed += 1
            if observed > MAX_RUNTIME_CORE_SCAN_ENTRIES:
                raise GateAContractError("condition writable-root core census exceeded its cap")
            metadata = path.lstat()
            lowered_name = path.name.lower()
            named = lowered_name == "core" or lowered_name.startswith("core.")
            elf_core = stat.S_ISREG(metadata.st_mode) and _elf_is_core(path)
            observed_entries.append((label, path, metadata, named, elf_core))
            if stat.S_ISREG(metadata.st_mode):
                identity = (metadata.st_dev, metadata.st_ino)
                inode_counts[identity] = inode_counts.get(identity, 0) + 1
                if named or elf_core:
                    core_inodes.add(identity)
    records: list[dict[str, object]] = []
    operational_paths: list[Path] = []
    for label, path, metadata, named, elf_core in observed_entries:
        regular = stat.S_ISREG(metadata.st_mode)
        record_identity = (metadata.st_dev, metadata.st_ino) if regular else None
        alias = record_identity in core_inodes if record_identity is not None else False
        if not named and not elf_core and not alias:
            continue
        operational_paths.append(path)
        classified_links = (
            inode_counts.get(record_identity, 0) if record_identity is not None else 0
        )
        records.append(
            {
                "artifact": f"<condition-core-artifact-{len(records) + 1:04d}>",
                "writable_root": label,
                "bytes": metadata.st_size,
                "known_core_filename": named,
                "elf_et_core": elf_core,
                "hardlink_alias_of_core_inode": alias and not named and not elf_core,
                "file_type": "regular" if regular else "non-regular",
                "filesystem_device": metadata.st_dev if regular else None,
                "filesystem_inode": metadata.st_ino if regular else None,
                "link_count": metadata.st_nlink,
                "classified_links_within_writable_roots": classified_links,
                "destruction_verifiable": (regular and metadata.st_nlink == classified_links),
                "content_or_hash_retained": False,
            }
        )
    return records, operational_paths


def _runtime_core_census(
    attempt_root: Path,
    *,
    runtime_budget_root: Path | None = None,
) -> tuple[list[dict[str, object]], list[Path]]:
    """Census every condition-writable mount before container teardown."""

    roots: list[tuple[str, Path]] = [
        ("attempt-root", attempt_root),
        ("/tmp", Path("/tmp")),
        ("/dev/shm", Path("/dev/shm")),
    ]
    if runtime_budget_root is not None:
        roots.append(("runtime-budget", runtime_budget_root))
    return _runtime_core_census_roots(roots)


def _remove_runtime_core_artifacts(
    attempt_root: Path,
    paths: Sequence[Path],
    records: Sequence[Mapping[str, object]],
    *,
    runtime_budget_root: Path | None = None,
) -> bool:
    """Identity-check, unlink, and then recensus every condition-writable root."""

    if len(paths) != len(records) or not all(
        record.get("destruction_verifiable") is True for record in records
    ):
        return False
    validated: list[tuple[Path, os.stat_result]] = []
    for path, record in zip(paths, records, strict=True):
        try:
            metadata = path.lstat()
        except FileNotFoundError:
            return False
        except OSError:
            return False
        if (
            record.get("file_type") != "regular"
            or not stat.S_ISREG(metadata.st_mode)
            or metadata.st_dev != record.get("filesystem_device")
            or metadata.st_ino != record.get("filesystem_inode")
            or metadata.st_nlink != record.get("link_count")
        ):
            return False
        validated.append((path, metadata))
    synced_parents: set[Path] = set()
    try:
        for path, _ in validated:
            path.unlink()
            synced_parents.add(path.parent)
        for parent in sorted(synced_parents):
            directory = os.open(parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        if any(os.path.lexists(path) for path, _ in validated):
            return False
        residual_records, _ = _runtime_core_census(
            attempt_root,
            runtime_budget_root=runtime_budget_root,
        )
    except (OSError, GateAContractError):
        return False
    return not residual_records


def _reconcile_browser_actions(
    upstream_argv: Sequence[str],
    admission_port: RuntimeAdmissionPort,
) -> None:
    for index, _ in enumerate(_session_history(upstream_argv), start=1):
        admission_port.browser_action(
            action_id=f"HISTORICAL-ACTION-{index:08d}",
            perform=lambda: None,
        )


def _load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise GateAContractError(f"cannot load pinned runtime module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _install_locked_llm_factory(
    runner: ModuleType,
    *,
    admission_port: RuntimeAdmissionPort,
    llm_timeout_seconds: int,
    ledger_path: Path,
    pilot_events: EventWriter | None = None,
    pilot_lineage: _PilotLineage | None = None,
    before_empirical_operation: Callable[[], None] | None = None,
    resource_guard: ResourceGuard | None = None,
    observe_credential: Callable[[str], None] | None = None,
) -> None:
    del ledger_path
    if pilot_events is not None:
        pilot_events.bind_output_admission(
            reserve_growth=admission_port.reserve_output_growth,
            observe_growth=lambda count: admission_port.output_bytes(
                total_bytes=admission_port.condition_usage.output_bytes + count
            ),
        )
    upstream_llm_module = importlib.import_module("sira.web.utils.llm")
    upstream_llm = upstream_llm_module.LLM
    call_identity_lock = threading.Lock()
    call_identity_sequence = 0

    def next_call_id() -> str:
        nonlocal call_identity_sequence
        with call_identity_lock:
            call_identity_sequence += 1
            return admission_port.call_identity(call_identity_sequence)

    class BudgetedLLM(upstream_llm):  # type: ignore[misc, valid-type]
        def __init__(self, *, role: ModelRole, credential: str) -> None:
            self._gate_role = role
            credential_option = {"api_key": credential}
            super().__init__(
                model=SIRA_MODEL_REVISION,
                base_url=SIRA_API_BASE_URL,
                custom_llm_provider="openai",
                num_retries=0,
                llm_timeout=llm_timeout_seconds,
                **credential_option,
            )
            self_any: Any = self
            unbudgeted_completion: Any = self_any._completion

            def completion_once(*args: Any, **kwargs: Any) -> Any:
                if resource_guard is not None:
                    resource_guard.check()
                messages = kwargs.get("messages")
                if messages is None and len(args) > 1:
                    messages = args[1]
                if messages is None:
                    raise GateAContractError("provider request omitted messages")
                input_tokens = self.get_token_count(messages)
                declared_per_choice = kwargs.get("max_completion_tokens", self.max_output_tokens)
                if type(declared_per_choice) is not int or declared_per_choice < 0:
                    raise GateAContractError("provider output maximum is unavailable")
                per_choice = min(declared_per_choice, SIRA_MAX_OUTPUT_TOKENS_PER_CHOICE)
                sample_count = kwargs.get("n", 1)
                if type(sample_count) is not int or sample_count < 1:
                    raise GateAContractError("provider sample count must be a positive integer")
                kwargs["max_completion_tokens"] = per_choice
                requested_tier = kwargs.get("service_tier", SIRA_SERVICE_TIER)
                if requested_tier != SIRA_SERVICE_TIER:
                    raise GateAContractError(
                        "provider request service_tier must be exactly default"
                    )
                kwargs["service_tier"] = SIRA_SERVICE_TIER
                request = ProviderRequest(
                    role=self._gate_role,
                    model=self.model_name,
                    input_tokens=input_tokens,
                    max_output_tokens=per_choice * sample_count,
                    service_tier=SIRA_SERVICE_TIER,
                    implicit_transport_retries=0,
                )
                call_id = next_call_id()
                parent = pilot_lineage.parent_event_id if pilot_lineage is not None else None

                def send(_: ProviderRequest) -> tuple[Any, ProviderResponseUsage]:
                    response = unbudgeted_completion(*args, **kwargs)
                    try:
                        observed_usage = _usage(response)
                    except Exception as exc:
                        raise ProviderResponseReceiptError(
                            "provider response usage receipt was invalid"
                        ) from exc
                    return response, observed_usage

                try:
                    result = admission_port.model_call(
                        request,
                        send,
                        before_send=before_empirical_operation,
                        call_id=call_id,
                        logical_call_id=call_id,
                        classify_failure=_classify_provider_failure,
                    )
                except Exception as exc:
                    try:
                        record = admission_port.terminal_call_state(call_id)
                    except KeyError:
                        # Admission can fail before a remote terminal receipt is
                        # available. Preserve that original failure, not a lookup
                        # error or an invented zero-activity terminal record.
                        raise exc from None
                    if pilot_events is not None:
                        pilot_events.append(
                            "provider-call-failed",
                            {
                                "call_id": call_id,
                                "role": self._gate_role.value,
                                "model": self.model_name,
                                "requested_service_tier": SIRA_SERVICE_TIER,
                                "exception_type": type(exc).__name__,
                                "terminal_accounting_state": (record.terminal_state),
                                "retry": "forbidden",
                            },
                            parent_event_id=parent,
                        )
                    raise
                record = admission_port.terminal_call_state(call_id)
                observed_usage = record.actual_usage
                if (
                    observed_usage is None
                    or record.terminal_state != ProviderCallTerminalState.RESPONSE_RECONCILED.value
                ):
                    raise GateAContractError("provider response lacks terminal accounting")
                if pilot_events is not None:
                    response_id = (
                        result.get("id")
                        if isinstance(result, Mapping)
                        else getattr(result, "id", None)
                    )
                    system_fingerprint = (
                        result.get("system_fingerprint")
                        if isinstance(result, Mapping)
                        else getattr(result, "system_fingerprint", None)
                    )
                    try:
                        pilot_events.append(
                            "provider-call-receipt",
                            {
                                "call_id": call_id,
                                "role": self._gate_role.value,
                                "model": self.model_name,
                                "requested_service_tier": SIRA_SERVICE_TIER,
                                "returned_service_tier": observed_usage.service_tier,
                                "provider_response_id": response_id,
                                "system_fingerprint": system_fingerprint,
                                "usage": {
                                    "input_tokens": observed_usage.input_tokens,
                                    "cached_input_tokens": observed_usage.cached_input_tokens,
                                    "output_tokens": observed_usage.output_tokens,
                                    "total_tokens": (
                                        observed_usage.input_tokens + observed_usage.output_tokens
                                    ),
                                },
                                "terminal_accounting_state": record.terminal_state,
                                "retry": "none",
                            },
                            parent_event_id=parent,
                        )
                    except Exception as exc:
                        raise ProviderResponseReceiptError(
                            "provider response was reconciled before event persistence failed"
                        ) from exc
                if resource_guard is not None:
                    resource_guard.check()
                return result

            self._completion = completion_once

    def make_llm(model: str, credential: str) -> dict[str, Any]:
        if model != SIRA_MODEL_REVISION:
            raise GateAContractError("upstream command requested an unapproved model alias")
        if observe_credential is not None:
            observe_credential(credential)
        return {role.value: BudgetedLLM(role=role, credential=credential) for role in ModelRole}

    runner_any: Any = runner
    runner_any.make_llm = make_llm


def run(argv: Sequence[str] | None = None) -> int:
    core_limits = resource.getrlimit(resource.RLIMIT_CORE)
    if core_limits != (0, 0):
        raise GateAContractError("condition process-tree core limit is not exactly zero")
    args = _parser().parse_args(argv)
    if not args.upstream_argv or args.upstream_argv[0] != "--":
        raise GateAContractError("upstream argv must follow a -- boundary")
    pilot_values = (
        args.gate_pilot_contract,
        args.gate_pilot_contract_sha256,
        args.gate_pilot_library_sha256,
        args.gate_pilot_attempt_id,
        args.gate_condition_plan,
        args.gate_aggregate_ledger,
        args.gate_pilot_state,
    )
    if any(value is not None for value in pilot_values) and not all(
        value is not None for value in pilot_values
    ):
        raise GateAContractError("T09 pilot runtime arguments must be supplied together")
    pilot_enabled = all(value is not None for value in pilot_values)
    duplex_values = (
        args.gate_duplex_binding,
        args.gate_duplex_session_id,
        args.gate_duplex_frozen_manifest_sha256,
        args.gate_duplex_transaction_root_identity,
    )
    if args.gate_admission_mode == "duplex-supervisor":
        if not pilot_enabled or not all(value is not None for value in duplex_values):
            raise GateAContractError(
                "duplex admission requires the complete pilot and private bridge binding"
            )
    elif any(value is not None for value in duplex_values):
        raise GateAContractError(
            "historical in-process admission rejects duplex-only runtime inputs"
        )
    runner_path = args.gate_upstream_runner.resolve(strict=True)
    attempt_root = args.gate_attempt_root.resolve(strict=True)
    pilot_contract: PilotExecutionContract | None = None
    condition_plan_path: Path | None = None
    pilot_state_path: Path | None = None
    aggregate_ledger_path: Path | None = None
    resource_guard: ResourceGuard | None = None
    pilot_events: EventWriter | None = None
    pilot_lineage: _PilotLineage | None = None
    empirical_entered = False
    attempt: t09_pilot.AttemptBinding | None = None
    if pilot_enabled:
        assert isinstance(args.gate_pilot_contract, Path)
        assert isinstance(args.gate_pilot_contract_sha256, str)
        assert isinstance(args.gate_pilot_library_sha256, str)
        assert isinstance(args.gate_pilot_attempt_id, str)
        assert isinstance(args.gate_condition_plan, Path)
        assert isinstance(args.gate_aggregate_ledger, Path)
        assert isinstance(args.gate_pilot_state, Path)
        pilot_contract = load_execution_contract(
            args.gate_pilot_contract.resolve(strict=True),
            expected_sha256=args.gate_pilot_contract_sha256,
        )
        pilot_library_path = Path(t09_pilot.__file__).resolve(strict=True)
        if file_sha256(pilot_library_path) != args.gate_pilot_library_sha256:
            raise GateAContractError("repository-owned T09 pilot library hash changed")
        attempt = pilot_contract.attempt(args.gate_pilot_attempt_id)
        condition_plan_path = args.gate_condition_plan.resolve(strict=True)
        if (
            condition_plan_path.name != Path(attempt.condition_plan_path).name
            or file_sha256(condition_plan_path) != attempt.condition_plan_sha256
        ):
            raise GateAContractError("pilot condition plan changed from its frozen binding")
        if attempt.condition != args.gate_mode:
            raise GateAContractError("pilot attempt mode does not match its frozen condition")
        if attempt.upstream_argv != tuple(args.upstream_argv[1:]):
            raise GateAContractError("pilot upstream argv drifted from the execution contract")
        if not _attempt_root_matches_raw_binding(attempt_root, attempt.raw_output_root):
            raise GateAContractError("pilot attempt root drifted from the execution contract")
        pilot_state_path = args.gate_pilot_state.resolve(strict=True)
        aggregate_ledger_path = args.gate_aggregate_ledger.resolve(strict=False)
    if attempt_root in runner_path.parents:
        raise GateAContractError("upstream runner must remain outside the attempt root")
    if file_sha256(Path(__file__).resolve(strict=True)) != args.gate_adaptation_sha256:
        raise GateAContractError("repository-owned runtime adaptation hash changed")
    validate_sira_secret_names(
        requested=(SIRA_SECRET_VARIABLE,),
        inherited=tuple(name for name in os.environ if name == "OPENAI_API_KEY"),
    )
    os.environ.pop("OPENAI_API_KEY", None)
    os.environ["DEBUG_LOG_FOLDER"] = str(attempt_root / "source-logs" / "debug")
    runtime_cwd = attempt_root / "source-runtime"
    runtime_cwd.mkdir(mode=0o700, exist_ok=False)
    (attempt_root / "source-logs" / "debug").mkdir(parents=True, mode=0o700)
    (attempt_root / "source-logs" / "agent").mkdir(mode=0o700)
    os.chdir(runtime_cwd)

    routing = ImmutableModelRouting.locked()
    ledger_path = attempt_root / "provider-budget.json"
    lifecycle_path = attempt_root / "provider-call-lifecycle.json"
    initial_aggregate_usage = ProviderBudgetUsage()
    initial_aggregate_observed_usage = ProviderBudgetUsage()
    condition_budget_caps = condition_caps(args.gate_mode)
    aggregate_budget_caps = aggregate_caps()
    if pilot_contract is not None:
        assert aggregate_ledger_path is not None
        assert pilot_state_path is not None
        initial_aggregate_usage = load_aggregate_usage(
            aggregate_ledger_path,
            contract_sha256=pilot_contract.sha256,
            plan_id=pilot_contract.plan_id,
        )
        initial_aggregate_observed_usage = load_aggregate_observed_usage(
            aggregate_ledger_path,
            contract_sha256=pilot_contract.sha256,
            plan_id=pilot_contract.plan_id,
        )
        condition_budget_caps = pilot_contract.limits.condition_provider_caps()
        aggregate_budget_caps = pilot_contract.limits.aggregate_provider_caps()

        condition_started = time.monotonic()
        time_origins = pilot_state_time_origins(
            pilot_state_path,
            execution_contract_sha256=pilot_contract.sha256,
            run_id=args.gate_pilot_attempt_id,
        )
        pilot_control_root = pilot_state_path.parent
        pilot_root = pilot_control_root.parent
        expected_control_root = provider_contract(
            pilot_contract.provider_contract_version
        ).control_root_name
        if (
            pilot_control_root.name != expected_control_root
            or aggregate_ledger_path.parent.name != "runtime-budget"
            or aggregate_ledger_path.parent.parent != pilot_control_root
            or pilot_root not in attempt_root.parents
        ):
            raise GateAContractError("pilot state, aggregate ledger, and attempt roots disagree")
        resource_guard = ResourceGuard(
            pilot_contract.limits,
            attempt_root=attempt_root,
            pilot_root=pilot_root,
            condition_started=condition_started,
            pair_started=time_origins.pair_started,
            campaign_started=time_origins.campaign_started,
            owned_lambda_started=time_origins.owned_lambda_started,
            prior_lambda_duration_seconds=time_origins.prior_lambda_duration_seconds,
            prior_lambda_cost_usd=time_origins.prior_lambda_cost_usd,
        )
        resource_guard.check()
        pilot_events = EventWriter(
            attempt_root / "normalized-events.jsonl",
            require_output_admission=args.gate_admission_mode == "duplex-supervisor",
        )
        pilot_lineage = _PilotLineage()
        if args.gate_admission_mode == "historical-in-process":
            assert attempt is not None
            pilot_events.append(
                "regulation-decision-assignment",
                {
                    "source_kind": "experiment_assignment",
                    "condition": attempt.condition,
                    "scientific_effect_on_h2k": "none",
                },
            )

    def before_empirical_operation() -> None:
        nonlocal empirical_entered
        if pilot_contract is None:
            return
        assert pilot_state_path is not None
        assert resource_guard is not None
        resource_guard.check()
        if not empirical_entered:
            confirm_supervised_empirical_entry(
                pilot_state_path,
                execution_contract_sha256=pilot_contract.sha256,
                run_id=args.gate_pilot_attempt_id,
                supervised_release_receipt=(
                    attempt_root / ".giclab-supervisor/supervised-release.json"
                ),
            )
            empirical_entered = True

    def persist_complete_accounting(document: Mapping[str, object]) -> None:
        _write_json_evidence(lifecycle_path, document)
        if pilot_contract is None:
            return
        assert aggregate_ledger_path is not None
        observed_bounds = document.get("observed_lower_bound")
        reserved_bounds = document.get("reserved_upper_bound")
        if not isinstance(observed_bounds, Mapping) or not isinstance(reserved_bounds, Mapping):
            raise GateAContractError("provider accounting bounds are malformed")
        unreconciled = document.get("unreconciled_provider_attempts")
        unknown = document.get("unknown_outcomes")
        if type(unreconciled) is not int or type(unknown) is not int:
            raise GateAContractError("provider accounting outcome counts are malformed")
        write_aggregate_usage(
            aggregate_ledger_path,
            contract_sha256=pilot_contract.sha256,
            plan_id=pilot_contract.plan_id,
            usage=usage_from_document(reserved_bounds.get("aggregate")),
            observed_usage=usage_from_document(observed_bounds.get("aggregate")),
            unreconciled_provider_attempts=unreconciled,
            unknown_outcomes=unknown,
        )

    if args.gate_admission_mode == "historical-in-process":
        boundary = ProviderBudgetBoundary(
            routing=routing,
            aggregate_caps=aggregate_budget_caps,
            condition_caps=condition_budget_caps,
            persist=lambda usage, unreconciled: _write_usage_ledger(
                ledger_path, usage, unreconciled
            ),
            initial_aggregate_usage=initial_aggregate_usage,
            initial_aggregate_observed_usage=initial_aggregate_observed_usage,
            persist_accounting=persist_complete_accounting,
        )
        admission_port: RuntimeAdmissionPort = InProcessBoundaryPort(boundary)
    else:
        assert pilot_contract is not None
        assert attempt is not None
        assert isinstance(args.gate_duplex_binding, Path)
        assert isinstance(args.gate_duplex_session_id, str)
        assert isinstance(args.gate_duplex_frozen_manifest_sha256, str)
        assert isinstance(args.gate_duplex_transaction_root_identity, str)
        selected_contract = provider_contract(pilot_contract.provider_contract_version)
        attempt_index = selected_contract.run_ids.index(attempt.run_id)
        expected_binding = ConditionSessionBinding(
            session_id=args.gate_duplex_session_id,
            provider_contract_version=selected_contract.version,
            plan_id=pilot_contract.plan_id,
            host_run_id=selected_contract.host_run_id,
            condition_run_id=attempt.run_id,
            evaluator_run_id=selected_contract.evaluator_run_ids[attempt_index],
            frozen_manifest_sha256=args.gate_duplex_frozen_manifest_sha256,
        )
        admission_port = build_private_socket_supervisor_port(
            manifest_path=args.gate_duplex_binding,
            attempt_root=attempt_root,
            expected_binding=expected_binding,
            expected_transaction_root_identity=(args.gate_duplex_transaction_root_identity),
        )
    try:
        # Shared capacity and observed bytes are different quantities. Atomic
        # publications reserve their full temporary file before creation; the final
        # retained scope census is still independently checked, never replaced with
        # a sum of these reservations.
        remote_output = args.gate_admission_mode == "duplex-supervisor"
        # Pre-admit a finite terminal publication allowance while the channel is
        # still open to reservations. Once output is denied or the runtime detaches,
        # terminal writers may consume this allowance but cannot request more.
        finalizing_runtime = False
        consume_terminal_publication = (
            _reserve_terminal_publications(admission_port) if remote_output else None
        )

        def reserve_runtime_publication(count: int) -> None:
            if finalizing_runtime:
                assert consume_terminal_publication is not None
                consume_terminal_publication(count)
            else:
                admission_port.reserve_output_growth(count)

        def write_runtime_evidence(path: Path, value: object) -> None:
            _write_json_evidence(
                path,
                value,
                reserve_temporary_bytes=reserve_runtime_publication if remote_output else None,
                require_output_admission=remote_output,
            )

        def write_runtime_ledger() -> None:
            _write_usage_ledger(
                ledger_path,
                admission_port.condition_usage,
                admission_port.unreconciled_provider_attempts,
                reserve_temporary_bytes=reserve_runtime_publication if remote_output else None,
                require_output_admission=remote_output,
            )

        write_runtime_ledger()
        write_runtime_evidence(lifecycle_path, admission_port.accounting_document())
        write_runtime_evidence(
            attempt_root / "runtime-environment.json",
            {
                "schema_version": "0.1.0",
                "python_executable": sys.executable,
                "python_version": platform.python_version(),
                "os": platform.system(),
                "architecture": platform.machine(),
                "upstream_runner": str(runner_path),
                "runtime_adaptation_sha256": args.gate_adaptation_sha256,
                "routing_sha256": routing.sha256(),
                "pilot_execution_contract_sha256": (
                    pilot_contract.sha256 if pilot_contract is not None else None
                ),
                "pilot_attempt_id": args.gate_pilot_attempt_id,
                "admission_mode": args.gate_admission_mode,
                "authoritative_accounting_location": (
                    "condition-process"
                    if args.gate_admission_mode == "historical-in-process"
                    else "shared-controller"
                ),
                "core_soft_limit": core_limits[0],
                "core_hard_limit": core_limits[1],
                "gpu_accounting": {
                    "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES"),
                    "gpu_use_claimed": False,
                    "visibility_interpretation": "visible-or-disabled-but-unused",
                    "scientific_variable": False,
                },
                "environment_variable_names": sorted(
                    {
                        "DEBUG_LOG_FOLDER",
                        "PLAYWRIGHT_BROWSERS_PATH",
                        "PYTHONDONTWRITEBYTECODE",
                        "PYTHONPATH",
                        SIRA_SECRET_VARIABLE,
                        "UV_CACHE_DIR",
                        "UV_PROJECT_ENVIRONMENT",
                    }
                ),
                "secret_variable_names": [SIRA_SECRET_VARIABLE],
            },
        )

        source_publications = None
        if remote_output:
            admission_port.reserve_output_growth(4 * 1024 * 1024)
            source_publications = _AdmittedPublicationAllowance(4 * 1024 * 1024)
        with (
            _admit_source_writers(attempt_root, source_publications)
            if source_publications is not None
            else contextlib.nullcontext()
        ):
            runner = _load_module(runner_path, "giclab_t07_pinned_sira_runner")
            observed_credentials: list[str] = []

            def observe_credential(value: str) -> None:
                if observed_credentials and observed_credentials[0] != value:
                    raise GateAContractError(
                        "more than one provider credential reached the runtime"
                    )
                if not observed_credentials:
                    observed_credentials.append(value)

            _install_locked_llm_factory(
                runner,
                admission_port=admission_port,
                llm_timeout_seconds=condition_budget_caps.max_wall_seconds,
                ledger_path=ledger_path,
                pilot_events=pilot_events,
                pilot_lineage=pilot_lineage,
                before_empirical_operation=before_empirical_operation if pilot_contract else None,
                resource_guard=resource_guard,
                observe_credential=observe_credential if pilot_contract else None,
            )
            if pilot_events is not None and args.gate_admission_mode == "duplex-supervisor":
                assert attempt is not None
                pilot_events.append(
                    "regulation-decision-assignment",
                    {
                        "source_kind": "experiment_assignment",
                        "condition": attempt.condition,
                        "scientific_effect_on_h2k": "none",
                    },
                )
            if pilot_events is not None and pilot_lineage is not None:
                original_make_agent = runner.make_agent

                def instrumented_make_agent(*agent_args: Any, **agent_kwargs: Any) -> Any:
                    agent = original_make_agent(*agent_args, **agent_kwargs)
                    original_step = agent.step

                    def instrumented_agent_step(raw_observation: Any) -> Any:
                        step_event_id = pilot_events.append(
                            "agent-step-started",
                            {"observation_available": raw_observation is not None},
                        )
                        pilot_lineage.parent_event_id = step_event_id
                        try:
                            action, thoughts = original_step(raw_observation)
                        finally:
                            pilot_lineage.parent_event_id = None
                        action_event_id = pilot_events.append(
                            "requested-browser-action",
                            {"requested_action": action, "agent_step_info": _json_safe(thoughts)},
                            parent_event_id=step_event_id,
                        )
                        pilot_lineage.action_event_id = action_event_id
                        return action, thoughts

                    agent.step = instrumented_agent_step
                    return agent

                runner_any_for_agent: Any = runner
                runner_any_for_agent.make_agent = instrumented_make_agent
            logger_module = importlib.import_module("sira.web.utils.logger")
            original_agent_logger = logger_module.get_agent_logger

            def owned_agent_logger(
                log_file: str = "default_log.log", log_dir: str | None = None
            ) -> Any:
                del log_dir
                return original_agent_logger(
                    log_file=log_file,
                    log_dir=str(attempt_root / "source-logs" / "agent"),
                )

            runner_any: Any = runner
            logger_any: Any = logger_module
            runner_any.get_agent_logger = owned_agent_logger
            logger_any.get_agent_logger = owned_agent_logger

            opened_environments: list[Any] = []
            original_gym_make = runner.gym.make

            def tracked_gym_make(*make_args: Any, **make_kwargs: Any) -> Any:
                created = original_gym_make(*make_args, **make_kwargs)
                current = created
                seen: set[int] = set()
                while hasattr(current, "env") and id(current) not in seen:
                    seen.add(id(current))
                    current = current.env
                opened_environments.append(current)
                if pilot_events is not None and pilot_lineage is not None:
                    original_environment_step = current.step

                    def instrumented_environment_step(action: str) -> Any:
                        if resource_guard is not None:
                            resource_guard.check()
                        action_event_id = pilot_lineage.action_event_id
                        if action_event_id is None:
                            action_event_id = pilot_events.append(
                                "requested-browser-action",
                                {"requested_action": action, "agent_step_info": None},
                            )

                        def perform_browser_action() -> Any:
                            before_empirical_operation()
                            return original_environment_step(action)

                        try:
                            result = admission_port.browser_action(
                                action_id=action_event_id,
                                perform=perform_browser_action,
                            )
                        except Exception as exc:
                            pilot_events.append(
                                "post-action-result",
                                {
                                    "requested_action": action,
                                    "result_available": False,
                                    "exception_type": type(exc).__name__,
                                },
                                parent_event_id=action_event_id,
                            )
                            pilot_lineage.action_event_id = None
                            raise
                        if not isinstance(result, tuple) or len(result) != 5:
                            raise GateAContractError(
                                "browser step returned an unexpected result shape"
                            )
                        observation, reward, terminated, truncated, info = result
                        serializable_observation = runner.get_serializable_obs(
                            current,
                            copy.deepcopy(observation),
                        )
                        pilot_events.append(
                            "post-action-result",
                            {
                                "requested_action": action,
                                "result_available": True,
                                "observation": _json_safe(serializable_observation),
                                "reward": _json_safe(reward),
                                "terminated": _json_safe(terminated),
                                "truncated": _json_safe(truncated),
                                "info": _json_safe(info),
                            },
                            parent_event_id=action_event_id,
                        )
                        pilot_lineage.action_event_id = None
                        if resource_guard is not None:
                            resource_guard.check()
                        return result

                    current.step = instrumented_environment_step
                return created

            runner.gym.make = tracked_gym_make
            sys.argv = [str(runner_path), *args.upstream_argv[1:]]
            cleanup_path = attempt_root / "runtime-cleanup.json"
            close_errors: list[str] = []
            secret_cleanup = {
                "credential_observed": False,
                "credential_removed_from_environment": False,
                "content_scan_permitted": False,
                "secret_bearing_artifacts_removed": [],
                "remaining_exact_credential_matches": None,
            }
            runtime_core_cleanup: dict[str, object] = {
                "core_artifacts_detected": [],
                "core_artifact_count": 0,
                "core_scan_integrity_failure": False,
                "destruction_verified": True,
                "credential_rotation_required_due_to_core_handling": False,
                "core_content_or_hash_retained": False,
                "core_detection_receipt_sha256": None,
            }
            runner_succeeded = False
            runtime_terminalized = False
            try:
                runner.main()
                if source_publications is not None:
                    source_publications.require_no_denial()
                runner_succeeded = True
            finally:
                finalizing_runtime = True
                try:
                    admission_port.close_in_flight(grace_seconds=5.0, sleeper=time.sleep)
                except Exception as exc:
                    close_errors.append(type(exc).__name__)
                for environment in opened_environments:
                    try:
                        environment.close()
                    except Exception as exc:  # cleanup evidence must survive a source close failure
                        close_errors.append(type(exc).__name__)
                runtime_core_records: list[dict[str, object]] = []
                runtime_core_paths: list[Path] = []
                runtime_core_scan_failure = False
                try:
                    runtime_core_records, runtime_core_paths = _runtime_core_census(
                        attempt_root,
                        runtime_budget_root=(
                            aggregate_ledger_path.parent
                            if aggregate_ledger_path is not None
                            else None
                        ),
                    )
                except (OSError, GateAContractError):
                    runtime_core_scan_failure = True
                core_detection_path = attempt_root / "runtime-core-detection.json"
                write_runtime_evidence(
                    core_detection_path,
                    {
                        "schema_version": "0.1.0",
                        "scope": "condition-container-writable-roots-before-teardown",
                        "core_artifacts_detected": runtime_core_records,
                        "core_artifact_count": len(runtime_core_records),
                        "core_scan_integrity_failure": runtime_core_scan_failure,
                        "core_content_or_hash_retained": False,
                        "destructive_cleanup_not_yet_claimed": True,
                    },
                )
                runtime_core_destruction_verified = (
                    _remove_runtime_core_artifacts(
                        attempt_root,
                        runtime_core_paths,
                        runtime_core_records,
                        runtime_budget_root=(
                            aggregate_ledger_path.parent
                            if aggregate_ledger_path is not None
                            else None
                        ),
                    )
                    if not runtime_core_scan_failure
                    else False
                )
                if runtime_core_records:
                    close_errors.append("CoreArtifactDetected")
                if runtime_core_scan_failure:
                    close_errors.append("CoreScanIntegrityFailure")
                runtime_core_cleanup = {
                    "core_artifacts_detected": runtime_core_records,
                    "core_artifact_count": len(runtime_core_records),
                    "core_scan_integrity_failure": runtime_core_scan_failure,
                    "destruction_verified": runtime_core_destruction_verified,
                    "credential_rotation_required_due_to_core_handling": (
                        runtime_core_scan_failure
                        or (bool(runtime_core_records) and not runtime_core_destruction_verified)
                    ),
                    "core_content_or_hash_retained": False,
                    "core_detection_receipt_sha256": file_sha256(core_detection_path),
                }
                if pilot_contract is not None:
                    secret_cleanup, credential_cleanup_errors = (
                        _privacy_safe_runtime_secret_cleanup(
                            attempt_root=attempt_root,
                            observed_credentials=tuple(observed_credentials),
                            core_scan_integrity_failure=runtime_core_scan_failure,
                            core_destruction_verified=runtime_core_destruction_verified,
                        )
                    )
                    close_errors.extend(credential_cleanup_errors)
                write_runtime_evidence(
                    cleanup_path,
                    {
                        "schema_version": "0.1.0",
                        "tracked_browser_environments": len(opened_environments),
                        "close_error_types": close_errors,
                        "all_environment_closes_succeeded": not close_errors,
                        "pilot_attempt_id": args.gate_pilot_attempt_id,
                        "empirical_entry_crossed": empirical_entered,
                        "secret_cleanup": secret_cleanup,
                        "core_cleanup": runtime_core_cleanup,
                    },
                )
                try:
                    if runner_succeeded:
                        if pilot_contract is None:
                            _reconcile_browser_actions(args.upstream_argv[1:], admission_port)
                        else:
                            if not empirical_entered:
                                raise T09PilotError(
                                    "a successful pilot condition had no empirical operation"
                                )
                            if close_errors:
                                raise T09PilotError("pilot browser cleanup did not complete")
                            history = _session_history(args.upstream_argv[1:])
                            if len(history) != admission_port.condition_usage.browser_actions:
                                raise T09PilotError(
                                    "pre-action browser counter and retained session "
                                    "history disagree"
                                )
                            assert resource_guard is not None
                            snapshot = resource_guard.check()
                            admission_port.output_bytes(
                                total_bytes=snapshot.attempt_output_bytes,
                                retained_output_bytes=(
                                    (
                                        consume_terminal_publication.remaining
                                        if consume_terminal_publication is not None
                                        else 0
                                    )
                                    + (
                                        source_publications.remaining
                                        if source_publications is not None
                                        else 0
                                    )
                                ),
                            )
                            if pilot_events is not None:
                                pilot_events.append(
                                    "cleanup-receipt",
                                    {
                                        "tracked_browser_environments": len(opened_environments),
                                        "all_environment_closes_succeeded": not close_errors,
                                        "attempt_output_bytes": snapshot.attempt_output_bytes,
                                        "pilot_disk_bytes": snapshot.pilot_disk_bytes,
                                        "gpu_use_claimed": False,
                                    },
                                )
                finally:
                    try:
                        write_runtime_ledger()
                        write_runtime_evidence(lifecycle_path, admission_port.accounting_document())
                        if args.gate_admission_mode == "duplex-supervisor":
                            # Process outcome, final answer, and raw seal identities are
                            # host-derived. The container detaches after its last runtime
                            # event; the transparent host relay appends that exact evidence
                            # before the sole shared terminal acknowledgement.
                            write_runtime_evidence(
                                attempt_root / "duplex-runtime-detached.json",
                                admission_port.detach_runtime(),
                            )
                            runtime_terminalized = True
                    finally:
                        admission_port.close()
            if args.gate_admission_mode == "duplex-supervisor" and not runtime_terminalized:
                raise GateAContractError("duplex runtime session did not terminalize")
            return 0
    finally:
        admission_port.close()


if __name__ == "__main__":
    raise SystemExit(run())
