"""Writer consumption of campaign capacity owned by the shared budget boundary.

This module makes no policy decisions. The production controller supplies the
admission callback; a writer receives only its finite, single-write allowance.
Historical standalone callers retain their explicit unbound context.
"""

from __future__ import annotations

import json
import math
import os
import stat
import struct
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path
from typing import Protocol


class CampaignWriterRole(StrEnum):
    PROVIDER_RECORD = "provider-record"
    PROVIDER_JOURNAL = "provider-journal"
    RETAINED_COPY = "retained-copy"
    CLEANUP_JOURNAL = "cleanup-journal"
    CLEANUP_RECEIPT = "cleanup-receipt"
    HOST_CONTROL = "host-control"
    PHASE_CONTROL = "phase-control"


@dataclass(frozen=True, slots=True)
class CampaignFileIdentity:
    device: int
    inode: int
    size: int
    mtime_ns: int
    ctime_ns: int


def _campaign_file_identity(path: Path) -> CampaignFileIdentity | None:
    """Hold every parent; do not dereference a replacement name or final link."""
    if not path.is_absolute() or ".." in path.parts:
        raise RuntimeError("campaign census path is not canonical")
    directory = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for component in path.parts[1:-1]:
            child = os.open(
                component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory
            )
            os.close(directory)
            directory = child
        named = os.stat(path.name, dir_fd=directory, follow_symlinks=False)
        if not stat.S_ISREG(named.st_mode) or named.st_nlink != 1 or named.st_uid != os.getuid():
            raise RuntimeError("campaign publication has unsafe ownership")
        descriptor = os.open(
            path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory
        )
        try:
            metadata = os.fstat(descriptor)
            named = os.stat(path.name, dir_fd=directory, follow_symlinks=False)
            if (metadata.st_dev, metadata.st_ino) != (named.st_dev, named.st_ino):
                raise RuntimeError("campaign file changed while held")
        finally:
            os.close(descriptor)
    except FileNotFoundError:
        return None
    finally:
        os.close(directory)
    if (
        not stat.S_ISREG(metadata.st_mode)
        or metadata.st_nlink != 1
        or metadata.st_uid != os.getuid()
    ):
        raise RuntimeError("campaign publication has unsafe ownership")
    return CampaignFileIdentity(
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    )


def _bind_campaign_initial(lease: CampaignWriteAllowance) -> None:
    lease.initial_identity = _campaign_file_identity(lease.path)
    if lease.role is CampaignWriterRole.PROVIDER_JOURNAL and lease.initial_identity is not None:
        lease.initial_bytes = lease.initial_identity.size


@dataclass
class CampaignWriteAllowance:
    path: Path
    role: CampaignWriterRole
    granted: int
    consume: Callable[[int], None]
    observed: int = 0
    cleanup: bool = False
    closed: bool = False
    verify: Callable[[Path, int], None] | None = None
    initial_bytes: int = 0
    initial_identity: CampaignFileIdentity | None = None
    final_identity: CampaignFileIdentity | None = None
    retired_bytes: int = 0
    temporary_path: Path | None = None
    register_temporary: Callable[[Path], None] | None = None

    def observe(self, count: int) -> None:
        if (
            self.closed
            or type(count) is not int
            or count < 0
            or self.observed + count > self.granted
        ):
            raise RuntimeError("campaign writer exceeded its own admitted allowance")
        self.consume(count)
        self.observed += count


class CampaignOutputAdmission(Protocol):
    def __call__(
        self, path: Path, size: int, role: CampaignWriterRole
    ) -> CampaignWriteAllowance: ...


_ADMISSION: ContextVar[CampaignOutputAdmission | None] = ContextVar(
    "gic_campaign_output_admission", default=None
)
_CLEANUP: ContextVar[bool] = ContextVar("gic_campaign_cleanup_output", default=False)


@contextmanager
def campaign_cleanup_scope() -> Iterator[None]:
    token = _CLEANUP.set(True)
    try:
        yield
    finally:
        _CLEANUP.reset(token)


def campaign_cleanup_active() -> bool:
    return _CLEANUP.get()


@contextmanager
def campaign_output_scope(admission: CampaignOutputAdmission) -> Iterator[None]:
    token = _ADMISSION.set(admission)
    try:
        yield
    finally:
        _ADMISSION.reset(token)


def admit_campaign_write(
    path: Path, size: int, role: CampaignWriterRole
) -> CampaignWriteAllowance | None:
    if type(size) is not int or size < 0:
        raise ValueError("campaign writer length must be a non-negative integer")
    admission = _ADMISSION.get()
    if admission is None:
        return None
    lease = admission(path, size, role)
    _bind_campaign_initial(lease)
    return lease


def observe_campaign_write(allowance: CampaignWriteAllowance | None, count: int) -> None:
    if allowance is not None:
        allowance.observe(count)


@dataclass(frozen=True, slots=True)
class CleanupOutputBinding:
    """Immutable campaign capability identity, deliberately without a condition."""

    plan_id: str
    host_run_id: str
    source_commit: str
    source_tree: str
    candidate_sha256: str | None
    transaction_root: str
    handoff_sha256: str
    attempt: int
    phase: str = "host-cleanup"
    output_roots: tuple[str, ...] = ()

    def document(self) -> dict[str, object]:
        return {**asdict(self), "output_roots": list(self.output_roots)}

    @classmethod
    def from_document(cls, document: dict[str, object]) -> CleanupOutputBinding:
        from typing import Any, cast

        values = dict(document)
        roots = values.get("output_roots")
        if not isinstance(roots, list) or not all(isinstance(x, str) for x in roots):
            raise RuntimeError("cleanup output roots are not explicitly bound")
        values["output_roots"] = tuple(roots)
        binding = cls(**cast(dict[str, Any], values))
        binding.validate()
        return binding

    def validate(self) -> None:
        root = Path(self.transaction_root)
        if (
            not self.plan_id
            or not self.host_run_id
            or self.phase != "host-cleanup"
            or type(self.attempt) is not int
            or self.attempt < 1
            or not root.is_absolute()
            or ".." in root.parts
            or root.as_posix() != self.transaction_root
        ):
            raise RuntimeError("invalid campaign cleanup binding")
        if (
            not isinstance(self.output_roots, tuple)
            or not self.output_roots
            or len(self.output_roots) > 32
            or len(set(self.output_roots)) != len(self.output_roots)
        ):
            raise RuntimeError("cleanup output roots are absent or ambiguous")
        for value in self.output_roots:
            path = Path(value)
            if not path.is_relative_to(root) or ".." in path.parts or path.as_posix() != value:
                raise RuntimeError("cleanup output root escaped the owned transaction")
        for value, size in (
            (self.source_commit, 40),
            (self.source_tree, 40),
            (self.handoff_sha256, 64),
        ):
            if (
                not isinstance(value, str)
                or len(value) != size
                or any(c not in "0123456789abcdef" for c in value)
            ):
                raise RuntimeError("invalid cleanup source/handoff identity")
        if self.candidate_sha256 is not None and (
            len(self.candidate_sha256) != 64
            or any(c not in "0123456789abcdef" for c in self.candidate_sha256)
        ):
            raise RuntimeError("invalid cleanup candidate identity")


class CleanupOutputAuthority:
    """Single-use transport access to the controller's existing cleanup reserve.

    Grants are never refunded by EOF, unused capacity or a failed acknowledgement.
    This object has no policy cap and cannot increase the shared allocation.
    """

    def __init__(
        self, binding: CleanupOutputBinding, *, deadline: float, monotonic: Callable[[], float]
    ) -> None:
        binding.validate()
        admission = _ADMISSION.get()
        if admission is None or not math.isfinite(deadline):
            raise RuntimeError("cleanup output capability lacks parent admission/deadline")
        self.binding = binding
        self.deadline = deadline
        self.monotonic = monotonic
        self.admission = admission
        self.claimed = False
        self.closed = False
        self.leases: list[CampaignWriteAllowance] = []
        self.events: list[dict[str, object]] = []

    def remaining(self) -> float:
        value = self.deadline - self.monotonic()
        if self.closed or value <= 0:
            raise TimeoutError("campaign cleanup output capability closed or expired")
        return value

    def claim(self, binding: dict[str, object]) -> None:
        self.remaining()
        if self.claimed or binding != self.binding.document():
            raise RuntimeError("campaign cleanup capability replay or identity mismatch")
        self.claimed = True

    def admit(self, path: Path, size: int, role: CampaignWriterRole) -> CampaignWriteAllowance:
        self.remaining()
        if not self.claimed or not any(
            path.is_relative_to(Path(root)) for root in self.binding.output_roots
        ):
            raise RuntimeError("cleanup child escaped its bound root or admission session")
        lease = self.admission(path, size, role)
        if not lease.cleanup:
            raise RuntimeError("cleanup child did not consume the prefunded reserve")
        _bind_campaign_initial(lease)
        self.leases.append(lease)
        return lease

    def close(self) -> None:
        self.closed = True
        for lease in self.leases:
            lease.closed = True


def verify_campaign_write(allowance: CampaignWriteAllowance | None, path: Path) -> None:
    """Reconcile an actual completed publication independently of byte observations.

    Atomic replacement reserves its full temporary footprint, and records its full
    write consumption. The final file is an independent occupancy observation;
    replacement does not refund old grants or pretend cumulative writes are net size.
    """
    if allowance is None:
        return
    if allowance.verify is not None:
        allowance.verify(path, allowance.observed)
        return
    if path != allowance.path or allowance.final_identity is not None:
        raise RuntimeError("campaign publication identity or single-use verification changed")
    metadata = _campaign_file_identity(path)
    if metadata is None or metadata.size != allowance.observed + allowance.initial_bytes:
        raise RuntimeError("campaign publication occupancy does not reconcile")
    initial = allowance.initial_identity
    if initial is not None:
        replaced = (initial.device, initial.inode) != (metadata.device, metadata.inode)
        if allowance.role is CampaignWriterRole.PROVIDER_JOURNAL:
            if replaced:
                raise RuntimeError("campaign append changed its owned inode")
        elif not replaced or allowance.temporary_path is None:
            raise RuntimeError("campaign replacement lacks its admitted temporary")
        else:
            allowance.retired_bytes = initial.size
    allowance.final_identity = metadata


def prepare_campaign_temporary(allowance: CampaignWriteAllowance | None, temporary: Path) -> None:
    """Bind a single fresh staging name before it can receive any granted byte."""
    if allowance is None:
        return
    if (
        allowance.closed
        or allowance.observed
        or allowance.temporary_path is not None
        or temporary == allowance.path
        or temporary.parent != allowance.path.parent
        or _campaign_file_identity(temporary) is not None
    ):
        raise RuntimeError("campaign temporary is not an exclusive admitted output")
    if allowance.register_temporary is not None:
        allowance.register_temporary(temporary)
    allowance.temporary_path = temporary


def replace_campaign_write(
    allowance: CampaignWriteAllowance | None, temporary: Path, path: Path
) -> None:
    """Check the exact retiring inode immediately before the real replacement.

    Neither replacement nor verification refunds any reservation. Interrupted
    staging remains an admitted, counted file and is never disguised as a commit.
    """
    if allowance is not None:
        if (
            allowance.closed
            or allowance.path != path
            or allowance.temporary_path != temporary
            or allowance.final_identity is not None
            or _campaign_file_identity(path) != allowance.initial_identity
        ):
            raise RuntimeError("campaign replacement retirement identity changed")
        staged = _campaign_file_identity(temporary)
        if staged is None or staged.size != allowance.observed:
            raise RuntimeError("campaign replacement staging bytes do not reconcile")
    os.replace(temporary, path)


class CleanupOutputChannel:
    """Cleanup-specific messages over the existing nonblocking bridge I/O primitives.

    An inherited pipe pair is passed only to the exact retained child. There is no
    listener, daemon, condition session or additional budget owner here.
    """

    MAX_FRAME = 16384
    MAX_EVENTS = 4096

    def __init__(
        self,
        fd: int,
        binding: CleanupOutputBinding,
        deadline: float,
        *,
        write_fd: int | None = None,
    ):
        binding.validate()
        self.fd = fd
        self.write_fd = fd if write_fd is None else write_fd
        self.cancelled: Callable[[], bool] = lambda: False
        self.binding = binding
        self.deadline = deadline
        self.sequence = 0
        self.closed = False
        os.set_blocking(fd, False)
        os.set_blocking(self.write_fd, False)

    def remaining(self) -> float:
        remaining = self.deadline - time.monotonic()
        if self.closed or self.cancelled() or remaining <= 0:
            raise TimeoutError("cleanup bridge closed, cancelled or original deadline expired")
        return remaining

    def send(self, value: dict[str, object]) -> None:
        from giclab.control.remote_bridge import _write_deadline, canonical_bytes

        packet = canonical_bytes(value)
        if len(packet) > self.MAX_FRAME:
            raise RuntimeError("cleanup output frame limit")
        _write_deadline(self.write_fd, struct.pack("!I", len(packet)) + packet, self.remaining)

    def receive(self) -> dict[str, object]:
        from giclab.control.remote_bridge import _read_deadline, canonical_bytes

        size = struct.unpack("!I", _read_deadline(self.fd, 4, self.remaining))[0]
        if not 0 < size <= self.MAX_FRAME:
            raise RuntimeError("cleanup output frame limit")
        raw = _read_deadline(self.fd, size, self.remaining)
        value = json.loads(raw)
        if not isinstance(value, dict) or canonical_bytes(value) != raw:
            raise RuntimeError("cleanup output frame is not canonical")
        return value

    def request(self, operation: str, **payload: object) -> dict[str, object]:
        if self.sequence >= self.MAX_EVENTS:
            raise RuntimeError("cleanup output event limit")
        self.sequence += 1
        self.send(
            {
                "binding": self.binding.document(),
                "sequence": self.sequence,
                "operation": operation,
                "payload": payload,
            }
        )
        response = self.receive()
        if response != {"sequence": self.sequence, "accepted": True}:
            raise RuntimeError("cleanup output admission rejected")
        return response

    def connect(self) -> None:
        self.request("hello")

    def admit(self, path: Path, size: int, role: CampaignWriterRole) -> CampaignWriteAllowance:
        self.request("grant", path=str(path), size=size, role=role.value)
        lease_id = self.sequence

        def observe(count: int) -> None:
            self.request("observe", lease=lease_id, count=count)

        def verify(path: Path, count: int) -> None:
            self.request("verify", lease=lease_id, path=str(path), count=count)

        def temporary(value: Path) -> None:
            self.request("temporary", lease=lease_id, path=str(value))

        return CampaignWriteAllowance(
            path, role, size, observe, cleanup=True, verify=verify, register_temporary=temporary
        )

    def finish(self) -> None:
        self.request("close")
        self.closed = True

    def serve(self, authority: CleanupOutputAuthority) -> None:
        leases: dict[int, CampaignWriteAllowance] = {}
        verified: set[int] = set()
        transcript_bytes = 0
        try:
            for sequence in range(1, self.MAX_EVENTS + 1):
                frame = self.receive()
                if (
                    set(frame) != {"binding", "sequence", "operation", "payload"}
                    or frame["binding"] != authority.binding.document()
                    or type(frame["sequence"]) is not int
                    or frame["sequence"] != sequence
                    or not isinstance(frame["payload"], dict)
                ):
                    raise RuntimeError("cleanup output replay or binding mismatch")
                authority.remaining()
                operation, payload = frame["operation"], frame["payload"]
                if sequence == 1:
                    if operation != "hello" or payload:
                        raise RuntimeError("cleanup output requires a bound handshake")
                    authority.claim(frame["binding"])
                elif operation == "grant" and set(payload) == {"path", "size", "role"}:
                    if not isinstance(payload["path"], str):
                        raise RuntimeError("invalid cleanup output path")
                    leases[sequence] = authority.admit(
                        Path(payload["path"]), payload["size"], CampaignWriterRole(payload["role"])
                    )
                elif operation == "temporary" and set(payload) == {"lease", "path"}:
                    if (
                        type(payload["lease"]) is not int
                        or not isinstance(payload["path"], str)
                        or payload["lease"] in verified
                    ):
                        raise RuntimeError("invalid cleanup temporary binding")
                    prepare_campaign_temporary(leases[payload["lease"]], Path(payload["path"]))
                elif operation in {"observe", "verify"}:
                    expected = {"lease", "count"} | ({"path"} if operation == "verify" else set())
                    if (
                        set(payload) != expected
                        or type(payload["lease"]) is not int
                        or type(payload["count"]) is not int
                    ):
                        raise RuntimeError("invalid cleanup output consumption frame")
                    lease = leases[payload["lease"]]
                    if payload["lease"] in verified:
                        raise RuntimeError("cleanup output lease was already reconciled")
                    if operation == "observe":
                        lease.observe(payload["count"])
                    else:
                        if payload["path"] != str(lease.path) or payload["count"] != lease.observed:
                            raise RuntimeError("cleanup output census identity mismatch")
                        verify_campaign_write(lease, lease.path)
                        verified.add(payload["lease"])
                elif operation == "close" and not payload:
                    if set(leases) != verified:
                        raise RuntimeError("cleanup child has unreconciled publications")
                    self.send({"sequence": sequence, "accepted": True})
                    authority.events.append({"sequence": sequence, "operation": "close"})
                    return
                else:
                    raise RuntimeError("cleanup output operation is not admitted")
                event = {"sequence": sequence, "operation": operation, **payload}
                transcript_bytes += len(json.dumps(event).encode())
                if transcript_bytes > 1024 * 1024:
                    raise RuntimeError("cleanup output transcript limit")
                authority.events.append(event)
                self.send({"sequence": sequence, "accepted": True})
            raise RuntimeError("cleanup output event limit")
        finally:
            for lease in leases.values():
                lease.closed = True
            self.closed = True


def cleanup_output_inventory(root: Path) -> dict[str, tuple[int, ...]]:
    """Bounded metadata-only census of the exact owned cleanup transaction.

    Read no file payloads. In particular this is not a credential scan. Existing
    immutable inputs remain in the comparison; they are not silently dropped to
    make the writer sum agree. Never descend through links or another filesystem.
    """
    result: dict[str, tuple[int, ...]] = {}
    descriptor = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    device = os.fstat(descriptor).st_dev
    entries_seen = 0

    def visit(fd: int, prefix: str, depth: int) -> None:
        nonlocal entries_seen
        if depth > 16:
            raise RuntimeError("cleanup output census depth limit")
        with os.scandir(fd) as entries:
            for entry in entries:
                entries_seen += 1
                if entries_seen > 4096:
                    raise RuntimeError("cleanup output census entry limit")
                metadata = entry.stat(follow_symlinks=False)
                if metadata.st_uid != os.getuid() or metadata.st_dev != device:
                    raise RuntimeError("cleanup census crossed owned device/owner")
                relative = prefix + entry.name
                if stat.S_ISDIR(metadata.st_mode):
                    child = os.open(
                        entry.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd
                    )
                    try:
                        held = os.fstat(child)
                        if (held.st_dev, held.st_ino) != (metadata.st_dev, metadata.st_ino):
                            raise RuntimeError("cleanup census directory identity drift")
                        visit(child, relative + "/", depth + 1)
                    finally:
                        os.close(child)
                elif stat.S_ISREG(metadata.st_mode) and metadata.st_nlink == 1:
                    result[relative] = (
                        metadata.st_dev,
                        metadata.st_ino,
                        metadata.st_size,
                        metadata.st_mtime_ns,
                        metadata.st_ctime_ns,
                    )
                else:
                    raise RuntimeError("cleanup census unsafe retained member")

    try:
        visit(descriptor, "", 0)
    finally:
        os.close(descriptor)
    return result


def reconcile_cleanup_output(
    before: dict[str, tuple[int, ...]],
    after: dict[str, tuple[int, ...]],
    authority: CleanupOutputAuthority,
    *,
    parent_leases: tuple[CampaignWriteAllowance, ...] = (),
) -> dict[str, object]:
    """Independently detect writes that bypassed the admitted producer path."""
    root = Path(authority.binding.transaction_root)
    admitted = {
        str(path.relative_to(root))
        for lease in authority.leases
        for path in (lease.path, lease.temporary_path)
        if path is not None
    }
    parent = {str(lease.path.relative_to(root)) for lease in parent_leases}
    changed = {name for name in after if after[name] != before.get(name)}
    uncovered = changed - admitted - parent
    leases = (*authority.leases, *parent_leases)
    removed = set(before) - set(after)
    retired = sum(lease.retired_bytes for lease in leases)
    writes = sum(lease.observed for lease in leases)
    removed_bytes = sum(before[name][2] for name in removed)
    growth = sum(row[2] for row in after.values()) - sum(row[2] for row in before.values())
    discrepancy = growth - (writes - retired - removed_bytes)
    result: dict[str, object] = {
        "before_files": len(before),
        "after_files": len(after),
        "before_bytes": sum(row[2] for row in before.values()),
        "after_bytes": sum(row[2] for row in after.values()),
        "changed_files": sorted(changed),
        "uncovered_writes": sorted(uncovered),
        "removed_files": sorted(set(before) - set(after)),
        "parent_capture_paths": sorted(parent),
        "actual_written_bytes": writes,
        "exact_replaced_old_bytes": retired,
        "removed_baseline_bytes": removed_bytes,
        "occupancy_delta_bytes": growth,
        "unreconciled_bytes": discrepancy,
        "retirements": [
            {
                "path": str(lease.path.relative_to(root)),
                "old_bytes": lease.retired_bytes,
                "old": asdict(lease.initial_identity),
                "new": asdict(lease.final_identity),
            }
            for lease in leases
            if lease.retired_bytes
            and lease.initial_identity is not None
            and lease.final_identity is not None
        ],
        "interpretation": (
            "occupancy delta equals actual writes minus exact retirements "
            "and baseline deletions; no grant refund"
        ),
    }
    if uncovered:
        raise RuntimeError(
            "cleanup census found writes without prior admission: "
            + ", ".join(sorted(uncovered)[:8])
        )
    if discrepancy:
        raise RuntimeError(f"cleanup census byte equation differs by {discrepancy}")
    return result
