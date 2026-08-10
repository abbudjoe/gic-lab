"""Privacy-separated local SSH public-key matching for T07 Gate L1A.

Only held, no-follow ``*.pub`` files are opened.  Same-stem non-``.pub`` objects are
observed through metadata and never opened.  Exact paths and fingerprints stay in
the ignored private manifest; the sanitized report carries only opaque aliases,
already-public account key names, match states, and the explicit approval boundary.
"""

from __future__ import annotations

import hashlib
import os
import pwd
import stat
from collections.abc import Callable, Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Final

from .lambda_ssh_key_fingerprint import (
    APPROVED_ACCOUNT_KEY_NAMES,
    FINGERPRINT_SCHEMA_RELATIVE_PATH,
    LOCAL_VERIFICATION_RELATIVE_PATH,
    MATCH_SCHEMA_RELATIVE_PATH,
    MAX_LOCAL_RAW_PRIVATE_EVIDENCE_BYTES,
    MAX_LOCAL_VERIFICATION_BYTES,
    MAX_PUBLIC_KEY_TEXT_BYTES,
    MAX_RESPONSE_BYTES,
    MAX_SANITIZED_MATCH_REPORT_BYTES,
    PLAN_ID,
    PRIVATE_MANIFEST_RELATIVE_PATH,
    PRIVATE_SEAL_RELATIVE_PATH,
    RAW_RESPONSE_RELATIVE_PATH,
    RUN_ID,
    RUN_ROOT_RELATIVE_PATH,
    SANITIZED_REPORT_RELATIVE_PATH,
    AccountKeyProjection,
    SSHKeyFingerprintError,
    canonical_json_bytes,
    parse_public_key,
    validate_document_against_schema,
)

MAX_LOCAL_PUBLIC_KEYS: Final = 128
MAX_LOCAL_PUBLIC_KEY_AGGREGATE_BYTES: Final = 131_072


class MatchState(StrEnum):
    UNIQUE_MATCH = "unique_match"
    NO_MATCH = "no_match"
    AMBIGUOUS_MATCH = "ambiguous_match"
    INVALID_EVIDENCE = "invalid_evidence"


@dataclass(frozen=True, slots=True)
class SameStemMetadata:
    present: bool
    owner_class: str | None
    mode: str | None
    regular_file: bool | None

    def __post_init__(self) -> None:
        if self.present:
            if (
                self.owner_class not in {"current-user", "different-user"}
                or self.mode is None
                or self.regular_file is None
            ):
                raise SSHKeyFingerprintError("same-stem metadata is incomplete")
        elif any(value is not None for value in (self.owner_class, self.mode, self.regular_file)):
            raise SSHKeyFingerprintError("absent same-stem metadata must be null")


@dataclass(frozen=True, slots=True)
class LocalPublicKeyRecord:
    local_key_alias: str
    basename: str
    exact_path: str
    algorithm: str
    fingerprint: str
    source_format: str
    owner_class: str
    mode: str
    same_stem: SameStemMetadata
    private_key_bytes_accessed: bool = False

    def __post_init__(self) -> None:
        if (
            not self.local_key_alias.startswith("local-key-")
            or not self.basename.endswith(".pub")
            or "/" in self.basename
            or not Path(self.exact_path).is_absolute()
            or self.algorithm not in {"ssh-ed25519", "ssh-rsa"}
            or not self.fingerprint.startswith("SHA256:")
            or self.owner_class != "current-user"
            or self.private_key_bytes_accessed
        ):
            raise SSHKeyFingerprintError("local public-key evidence is invalid")

    @property
    def usable_private_counterpart(self) -> bool:
        return bool(
            self.same_stem.present
            and self.same_stem.regular_file
            and self.same_stem.owner_class == "current-user"
        )

    def private_document(self) -> dict[str, object]:
        return {
            "local_key_alias": self.local_key_alias,
            "basename": self.basename,
            "exact_path": self.exact_path,
            "algorithm": self.algorithm,
            "fingerprint": self.fingerprint,
            "source_format": self.source_format,
            "owner_class": self.owner_class,
            "mode": self.mode,
            "same_stem_private_file": {
                "present": self.same_stem.present,
                "owner_class": self.same_stem.owner_class,
                "mode": self.same_stem.mode,
                "regular_file": self.same_stem.regular_file,
            },
            "private_key_bytes_accessed": False,
        }


@dataclass(frozen=True, slots=True)
class MatchResult:
    private_manifest: Mapping[str, object]
    sanitized_report: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class EvidenceFileIdentity:
    relative_path: str
    bytes: int
    sha256: str


@dataclass(frozen=True, slots=True)
class LocalEvidenceBundle:
    raw_response: EvidenceFileIdentity
    private_manifest: EvidenceFileIdentity
    sanitized_report: EvidenceFileIdentity
    private_seal: EvidenceFileIdentity
    total_bytes: int


def _directory_flags() -> int:
    return os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)


def _open_directory_no_symlinks(path: Path) -> int:
    if not path.is_absolute() or ".." in path.parts:
        raise SSHKeyFingerprintError("directory path is not absolute and confined")
    descriptor = os.open("/", _directory_flags())
    try:
        for component in path.parts[1:]:
            child = os.open(component, _directory_flags(), dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
    except OSError:
        with suppress(OSError):
            os.close(descriptor)
        raise SSHKeyFingerprintError("directory path is missing or unsafe") from None
    return descriptor


def _read_public_file(descriptor: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        remaining = MAX_PUBLIC_KEY_TEXT_BYTES + 1 - total
        if remaining <= 0:
            raise SSHKeyFingerprintError("local public-key file exceeds its byte cap")
        chunk = os.read(descriptor, min(8_192, remaining))
        if not chunk:
            break
        chunks.append(chunk)
        total += len(chunk)
        if total > MAX_PUBLIC_KEY_TEXT_BYTES:
            raise SSHKeyFingerprintError("local public-key file exceeds its byte cap")
    return b"".join(chunks)


def discover_local_public_keys(
    *,
    home_directory: Path | None = None,
    expected_owner_uid: int | None = None,
    pre_open_hook: Callable[[str], None] | None = None,
) -> tuple[LocalPublicKeyRecord, ...]:
    """Read only the current user's held, no-follow ``~/.ssh/*.pub`` scope.

    ``home_directory`` is an explicit local-fixture seam.  Production callers omit
    it, which binds discovery to the passwd database entry for the current UID
    instead of trusting ``HOME`` or an arbitrary caller-supplied SSH directory.
    Even fixtures can select only the ``.ssh`` child of the injected home.
    """

    owner_uid = os.getuid() if expected_owner_uid is None else expected_owner_uid
    if home_directory is None:
        try:
            home = Path(pwd.getpwuid(owner_uid).pw_dir)
        except (KeyError, OSError):
            raise SSHKeyFingerprintError("current-user home identity is unavailable") from None
    else:
        home = home_directory
    if not home.is_absolute() or ".." in home.parts:
        raise SSHKeyFingerprintError("current-user home identity is unsafe")
    root = home / ".ssh"
    descriptor = _open_directory_no_symlinks(root)
    records: list[LocalPublicKeyRecord] = []
    aggregate = 0
    try:
        names = sorted(name for name in os.listdir(descriptor) if name.endswith(".pub"))
        if len(names) > MAX_LOCAL_PUBLIC_KEYS:
            raise SSHKeyFingerprintError("local public-key count exceeds its cap")
        for ordinal, name in enumerate(names, start=1):
            try:
                observed = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
            except OSError:
                raise SSHKeyFingerprintError("local public-key metadata is unavailable") from None
            if (
                stat.S_ISLNK(observed.st_mode)
                or not stat.S_ISREG(observed.st_mode)
                or observed.st_nlink != 1
                or observed.st_uid != owner_uid
            ):
                raise SSHKeyFingerprintError(
                    "local public key must be a current-user single-link regular file"
                )
            if pre_open_hook is not None:
                pre_open_hook(name)
            flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
            try:
                public_descriptor = os.open(name, flags, dir_fd=descriptor)
            except OSError:
                raise SSHKeyFingerprintError("local public-key open rejected path drift") from None
            try:
                opened = os.fstat(public_descriptor)
                if (
                    not stat.S_ISREG(opened.st_mode)
                    or opened.st_nlink != 1
                    or opened.st_uid != owner_uid
                    or (opened.st_dev, opened.st_ino) != (observed.st_dev, observed.st_ino)
                ):
                    raise SSHKeyFingerprintError("local public-key identity changed before open")
                encoded = _read_public_file(public_descriptor)
            finally:
                os.close(public_descriptor)
            aggregate += len(encoded)
            if aggregate > MAX_LOCAL_PUBLIC_KEY_AGGREGATE_BYTES:
                raise SSHKeyFingerprintError("local public-key aggregate exceeds its cap")
            try:
                text = encoded.decode("utf-8")
            except UnicodeDecodeError:
                raise SSHKeyFingerprintError("local public-key file is not UTF-8") from None
            parsed = parse_public_key(text)

            private_name = name.removesuffix(".pub")
            try:
                private_metadata = os.stat(
                    private_name,
                    dir_fd=descriptor,
                    follow_symlinks=False,
                )
            except FileNotFoundError:
                same_stem = SameStemMetadata(False, None, None, None)
            except OSError:
                raise SSHKeyFingerprintError("same-stem metadata inspection failed") from None
            else:
                same_stem = SameStemMetadata(
                    present=True,
                    owner_class=(
                        "current-user" if private_metadata.st_uid == owner_uid else "different-user"
                    ),
                    mode=f"{stat.S_IMODE(private_metadata.st_mode):04o}",
                    regular_file=stat.S_ISREG(private_metadata.st_mode),
                )
            records.append(
                LocalPublicKeyRecord(
                    local_key_alias=f"local-key-{ordinal:04d}",
                    basename=name,
                    exact_path=str(root / name),
                    algorithm=parsed.algorithm,
                    fingerprint=parsed.fingerprint,
                    source_format=parsed.source_format.value,
                    owner_class="current-user",
                    mode=f"{stat.S_IMODE(opened.st_mode):04o}",
                    same_stem=same_stem,
                )
            )
    finally:
        os.close(descriptor)
    return tuple(records)


def match_account_to_local_keys(
    projection: AccountKeyProjection,
    local_keys: Sequence[LocalPublicKeyRecord],
) -> MatchResult:
    """Build separate private and sanitized one-to-one match documents."""

    account_by_fingerprint: dict[str, list[str]] = {}
    local_by_fingerprint: dict[str, list[LocalPublicKeyRecord]] = {}
    for account_record in projection.records:
        account_by_fingerprint.setdefault(account_record.fingerprint, []).append(
            account_record.account_alias
        )
    for local_record in local_keys:
        local_by_fingerprint.setdefault(local_record.fingerprint, []).append(local_record)

    public_rows: list[dict[str, object]] = []
    private_rows: list[dict[str, object]] = []
    approvable: list[str] = []
    for account in projection.records:
        locals_for_key = local_by_fingerprint.get(account.fingerprint, [])
        accounts_for_key = account_by_fingerprint[account.fingerprint]
        if not locals_for_key:
            state = MatchState.NO_MATCH
            public_local: LocalPublicKeyRecord | None = None
        elif len(locals_for_key) == 1 and len(accounts_for_key) == 1:
            state = MatchState.UNIQUE_MATCH
            public_local = locals_for_key[0]
            if public_local.usable_private_counterpart:
                approvable.append(account.name)
        else:
            state = MatchState.AMBIGUOUS_MATCH
            public_local = None
        public_rows.append(
            {
                "account_key_name": account.name,
                "account_key_alias": account.account_alias,
                "match_status": state.value,
                "local_key_alias": (
                    public_local.local_key_alias if public_local is not None else None
                ),
                "local_public_key_basename": (
                    public_local.basename if public_local is not None else None
                ),
                "same_stem_private_file_present": (
                    public_local.same_stem.present if public_local is not None else None
                ),
                "private_key_bytes_accessed": False,
            }
        )
        private_rows.append(
            {
                "account_key_alias": account.account_alias,
                "raw_api_key_id": account.raw_api_key_id,
                "account_key_name": account.name,
                "algorithm": account.algorithm,
                "fingerprint": account.fingerprint,
                "matching_local_key_aliases": [item.local_key_alias for item in locals_for_key],
                "match_status": state.value,
            }
        )

    unique_rows = [
        row for row in public_rows if row["match_status"] == MatchState.UNIQUE_MATCH.value
    ]
    recommended = approvable[0] if len(unique_rows) == 1 and len(approvable) == 1 else None
    sanitized: dict[str, object] = {
        "schema_version": "0.1.0",
        "plan_id": PLAN_ID,
        "run_id": RUN_ID,
        "evidence_state": "complete-valid",
        "account_key_matches": public_rows,
        "recommended_account_key_name": recommended,
        "selection_state": (
            "unique-match-awaiting-user-approval" if recommended is not None else "blocked"
        ),
        "selection_authorized": False,
        "private_key_bytes_accessed": False,
        "ssh_agent_used": False,
        "ssh_invoked": False,
        "raw_public_key_bodies_retained": False,
        "raw_api_key_ids_retained": False,
        "exact_fingerprints_retained": False,
        "exact_home_paths_retained": False,
    }
    private_manifest = projection.private_manifest_document()
    private_manifest = {
        **private_manifest,
        "local_public_keys": [item.private_document() for item in local_keys],
        "account_to_local_matches": private_rows,
        "sanitized_report_relative_path": SANITIZED_REPORT_RELATIVE_PATH,
        "selection_authorized": False,
        "private_key_bytes_accessed": False,
        "ssh_invoked": False,
    }
    return MatchResult(private_manifest=private_manifest, sanitized_report=sanitized)


def invalid_evidence_report(account_key_names: Sequence[str]) -> dict[str, object]:
    """Create a value-free public failure report after invalid private evidence."""

    return {
        "schema_version": "0.1.0",
        "plan_id": PLAN_ID,
        "run_id": RUN_ID,
        "evidence_state": "invalid",
        "account_key_matches": [
            {
                "account_key_name": name,
                "account_key_alias": f"account-key-{ordinal:04d}",
                "match_status": MatchState.INVALID_EVIDENCE.value,
                "local_key_alias": None,
                "local_public_key_basename": None,
                "same_stem_private_file_present": None,
                "private_key_bytes_accessed": False,
            }
            for ordinal, name in enumerate(account_key_names, start=1)
        ],
        "recommended_account_key_name": None,
        "selection_state": "blocked",
        "selection_authorized": False,
        "private_key_bytes_accessed": False,
        "ssh_agent_used": False,
        "ssh_invoked": False,
        "raw_public_key_bodies_retained": False,
        "raw_api_key_ids_retained": False,
        "exact_fingerprints_retained": False,
        "exact_home_paths_retained": False,
    }


def _write_exclusive_file(directory_fd: int, name: str, encoded: bytes) -> EvidenceFileIdentity:
    if not name or "/" in name or not encoded:
        raise SSHKeyFingerprintError("evidence filename or content is invalid")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    descriptor = -1
    try:
        descriptor = os.open(name, flags, 0o600, dir_fd=directory_fd)
        offset = 0
        while offset < len(encoded):
            written = os.write(descriptor, encoded[offset:])
            if written < 1:
                raise OSError
            offset += written
        os.fsync(descriptor)
        os.fchmod(descriptor, 0o400)
        observed = os.fstat(descriptor)
        if (
            not stat.S_ISREG(observed.st_mode)
            or observed.st_nlink != 1
            or observed.st_size != len(encoded)
        ):
            raise OSError
        os.close(descriptor)
        descriptor = -1
        os.fsync(directory_fd)
        read_descriptor = os.open(
            name,
            os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=directory_fd,
        )
        try:
            readback = b""
            while len(readback) <= len(encoded):
                chunk = os.read(read_descriptor, len(encoded) + 1 - len(readback))
                if not chunk:
                    break
                readback += chunk
        finally:
            os.close(read_descriptor)
        if readback != encoded:
            raise OSError
    except OSError:
        if descriptor >= 0:
            with suppress(OSError):
                os.close(descriptor)
        raise SSHKeyFingerprintError("exclusive evidence write failed") from None
    return EvidenceFileIdentity(
        relative_path=f"{RUN_ROOT_RELATIVE_PATH}/{name}",
        bytes=len(encoded),
        sha256=hashlib.sha256(encoded).hexdigest(),
    )


def write_local_evidence_bundle(
    repository_root: Path,
    *,
    raw_response: bytes,
    result: MatchResult,
) -> LocalEvidenceBundle:
    """Write a sealed ignored bundle into an already-fresh run root.

    The request ledger owns creation of the fresh run root.  This writer holds that
    exact directory and exclusively creates the four evidence files; it never
    replaces, truncates, follows, or cleans up an existing object.
    """

    root = repository_root.resolve(strict=True)
    if root != repository_root.absolute():
        raise SSHKeyFingerprintError("repository root identity is unsafe")
    run_root = root / RUN_ROOT_RELATIVE_PATH
    try:
        run_root.relative_to(root)
    except ValueError:
        raise SSHKeyFingerprintError("run root escaped the repository") from None
    if not raw_response or len(raw_response) > MAX_RESPONSE_BYTES:
        raise SSHKeyFingerprintError("raw response violates its byte cap")
    validate_document_against_schema(
        result.private_manifest,
        repository_root=root,
        schema_relative_path=FINGERPRINT_SCHEMA_RELATIVE_PATH,
    )
    validate_sanitized_report(result.sanitized_report, repository_root=root)
    private_bytes = canonical_json_bytes(
        result.private_manifest,
        max_bytes=MAX_LOCAL_RAW_PRIVATE_EVIDENCE_BYTES,
    )
    report_bytes = canonical_json_bytes(
        result.sanitized_report,
        max_bytes=MAX_SANITIZED_MATCH_REPORT_BYTES,
    )

    def identity(relative_path: str, encoded: bytes) -> EvidenceFileIdentity:
        return EvidenceFileIdentity(
            relative_path=relative_path,
            bytes=len(encoded),
            sha256=hashlib.sha256(encoded).hexdigest(),
        )

    raw_identity = identity(RAW_RESPONSE_RELATIVE_PATH, raw_response)
    private_identity = identity(PRIVATE_MANIFEST_RELATIVE_PATH, private_bytes)
    report_identity = identity(SANITIZED_REPORT_RELATIVE_PATH, report_bytes)
    seal_document: dict[str, object] = {
        "schema_version": "0.1.0",
        "plan_id": PLAN_ID,
        "run_id": RUN_ID,
        "files": [
            {
                "relative_path": item.relative_path,
                "bytes": item.bytes,
                "sha256": item.sha256,
            }
            for item in (raw_identity, private_identity, report_identity)
        ],
        "private_key_bytes_accessed": False,
        "source_retained": True,
    }
    seal_bytes = canonical_json_bytes(
        seal_document,
        max_bytes=MAX_LOCAL_VERIFICATION_BYTES,
    )
    seal_identity = identity(PRIVATE_SEAL_RELATIVE_PATH, seal_bytes)
    total = sum(
        item.bytes for item in (raw_identity, private_identity, report_identity, seal_identity)
    )
    if total > (
        MAX_RESPONSE_BYTES
        + MAX_LOCAL_RAW_PRIVATE_EVIDENCE_BYTES
        + MAX_SANITIZED_MATCH_REPORT_BYTES
        + MAX_LOCAL_VERIFICATION_BYTES
    ):
        raise SSHKeyFingerprintError("local evidence bundle exceeds its aggregate cap")

    descriptor = _open_directory_no_symlinks(run_root)
    try:
        written = (
            _write_exclusive_file(
                descriptor,
                Path(RAW_RESPONSE_RELATIVE_PATH).name,
                raw_response,
            ),
            _write_exclusive_file(
                descriptor,
                Path(PRIVATE_MANIFEST_RELATIVE_PATH).name,
                private_bytes,
            ),
            _write_exclusive_file(
                descriptor,
                Path(SANITIZED_REPORT_RELATIVE_PATH).name,
                report_bytes,
            ),
            _write_exclusive_file(
                descriptor,
                Path(PRIVATE_SEAL_RELATIVE_PATH).name,
                seal_bytes,
            ),
        )
    finally:
        os.close(descriptor)
    if written != (raw_identity, private_identity, report_identity, seal_identity):
        raise SSHKeyFingerprintError("local evidence identity changed during write")
    return LocalEvidenceBundle(
        raw_response=raw_identity,
        private_manifest=private_identity,
        sanitized_report=report_identity,
        private_seal=seal_identity,
        total_bytes=total,
    )


def write_local_verification_record(
    repository_root: Path,
    encoded: bytes,
) -> EvidenceFileIdentity:
    """Exclusively retain the bounded post-archive verification record."""

    if not encoded or len(encoded) > MAX_LOCAL_VERIFICATION_BYTES:
        raise SSHKeyFingerprintError("local verification violates its byte cap")
    root = repository_root.resolve(strict=True)
    if root != repository_root.absolute():
        raise SSHKeyFingerprintError("repository root identity is unsafe")
    descriptor = _open_directory_no_symlinks(root / RUN_ROOT_RELATIVE_PATH)
    try:
        return _write_exclusive_file(
            descriptor,
            Path(LOCAL_VERIFICATION_RELATIVE_PATH).name,
            encoded,
        )
    finally:
        os.close(descriptor)


def validate_sanitized_report(
    document: Mapping[str, object],
    *,
    repository_root: Path,
) -> None:
    validate_document_against_schema(
        document,
        repository_root=repository_root,
        schema_relative_path=MATCH_SCHEMA_RELATIVE_PATH,
    )
    rows = document.get("account_key_matches")
    if not isinstance(rows, list) or len(rows) != len(APPROVED_ACCOUNT_KEY_NAMES):
        raise SSHKeyFingerprintError("sanitized match cardinality drifted")
    if any(not isinstance(row, Mapping) for row in rows):
        raise SSHKeyFingerprintError("sanitized match row is invalid")
    names = [row.get("account_key_name") for row in rows]
    aliases = [row.get("account_key_alias") for row in rows]
    if set(names) != set(APPROVED_ACCOUNT_KEY_NAMES) or len(set(aliases)) != len(aliases):
        raise SSHKeyFingerprintError("sanitized match identity drifted")
    evidence_state = document.get("evidence_state")
    unique_rows: list[Mapping[str, object]] = []
    for row in rows:
        state = row.get("match_status")
        local_values = (
            row.get("local_key_alias"),
            row.get("local_public_key_basename"),
            row.get("same_stem_private_file_present"),
        )
        if state == MatchState.UNIQUE_MATCH.value:
            if evidence_state != "complete-valid" or any(value is None for value in local_values):
                raise SSHKeyFingerprintError("unique sanitized match lacks local evidence")
            unique_rows.append(row)
        elif state in {
            MatchState.NO_MATCH.value,
            MatchState.AMBIGUOUS_MATCH.value,
            MatchState.INVALID_EVIDENCE.value,
        }:
            if any(value is not None for value in local_values):
                raise SSHKeyFingerprintError("blocked sanitized match exposes local evidence")
            if state == MatchState.INVALID_EVIDENCE.value and evidence_state != "invalid":
                raise SSHKeyFingerprintError("invalid sanitized evidence state drifted")
            if state != MatchState.INVALID_EVIDENCE.value and evidence_state != "complete-valid":
                raise SSHKeyFingerprintError("complete sanitized evidence state drifted")
        else:
            raise SSHKeyFingerprintError("sanitized match state drifted")
    recommended = document.get("recommended_account_key_name")
    selection_state = document.get("selection_state")
    if recommended is None:
        if selection_state != "blocked":
            raise SSHKeyFingerprintError("blocked sanitized selection state drifted")
    elif (
        selection_state != "unique-match-awaiting-user-approval"
        or len(unique_rows) != 1
        or unique_rows[0].get("account_key_name") != recommended
        or unique_rows[0].get("same_stem_private_file_present") is not True
    ):
        raise SSHKeyFingerprintError("sanitized recommendation lacks one unique match")
