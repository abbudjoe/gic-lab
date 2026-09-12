"""Versioned provider-namespace cleanup observations, reconciled by the controller.

This is a source/transport trust boundary, not remote kernel attestation. Only
the observer opens remote names. The authority receives metadata and delegates
every capacity decision to the controller's existing cleanup reserve.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import stat
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import PurePosixPath
from typing import Any

from giclab.harness.campaign_output import CampaignWriterRole, CleanupOutputChannel

PROTOCOL = "cross-host-cleanup/1.0.0"
MAX_ENTRIES = 4096
MAX_DEPTH = 16
MAX_EVENTS = 16384
MAX_TRANSCRIPT_BYTES = 64 * 1024 * 1024


def digest(value: object) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def member(value: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or "\x00" in value
        or len(value.encode()) > 4096
        or any(x in {"", ".", ".."} for x in value.split("/"))
        or PurePosixPath(value).is_absolute()
        or len(value.split("/")) > MAX_DEPTH
    ):
        raise RuntimeError("noncanonical remote member")
    return value


@dataclass(frozen=True)
class RemoteRoot:
    """A POSIX namespace identity, never a controller-local Path."""

    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str) or not self.value.startswith("/"):
            raise RuntimeError("remote root must be absolute")
        member(self.value[1:])


@dataclass(frozen=True)
class RemoteCleanupBinding:
    provider_contract_version: str
    plan_id: str
    host_run_id: str
    source_commit: str
    source_tree: str
    candidate_sha256: str | None
    provider_identity: str
    launch_ordinal: int
    transfer_sha256: str
    entry_sha256: str
    root: RemoteRoot
    root_semantic_sha256: str
    handoff_sha256: str
    attempt: int
    deadline: float
    remaining_at_issue: float
    nonce: str
    helper_sha256: str
    phase: str = "host-cleanup"
    protocol: str = PROTOCOL

    def validate(self) -> None:
        if (
            self.protocol != PROTOCOL
            or self.phase != "host-cleanup"
            or not isinstance(self.root, RemoteRoot)
            or not all(
                isinstance(x, str) and x
                for x in (
                    self.provider_contract_version,
                    self.plan_id,
                    self.host_run_id,
                    self.provider_identity,
                    self.nonce,
                )
            )
            or type(self.launch_ordinal) is not int
            or self.launch_ordinal < 1
            or type(self.attempt) is not int
            or self.attempt < 1
            or type(self.deadline) not in {int, float}
            or not math.isfinite(self.deadline)
            or self.deadline <= 0
            or type(self.remaining_at_issue) not in {int, float}
            or not math.isfinite(self.remaining_at_issue)
            or self.remaining_at_issue <= 0
            or re.fullmatch(r"[A-Za-z0-9_-]{1,64}", self.nonce) is None
        ):
            raise RuntimeError("invalid remote cleanup binding")
        for value, length in (
            (self.source_commit, 40),
            (self.source_tree, 40),
            (self.transfer_sha256, 64),
            (self.entry_sha256, 64),
            (self.root_semantic_sha256, 64),
            (self.handoff_sha256, 64),
            (self.helper_sha256, 64),
            *(([(self.candidate_sha256, 64)]) if self.candidate_sha256 is not None else []),
        ):
            if (
                not isinstance(value, str)
                or len(value) != length
                or any(c not in "0123456789abcdef" for c in value)
            ):
                raise RuntimeError("invalid remote source identity")

    def document(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def identity(self) -> str:
        return digest(self.document())

    @classmethod
    def from_document(cls, value: dict[str, Any]) -> RemoteCleanupBinding:
        value = dict(value)
        value["root"] = RemoteRoot(**value["root"])
        result = cls(**value)
        result.validate()
        return result


@dataclass(frozen=True)
class Metadata:
    device: int
    inode: int
    uid: int
    mode: int
    links: int
    size: int
    mtime_ns: int
    ctime_ns: int

    @classmethod
    def observed(cls, value: os.stat_result) -> Metadata:
        return cls(
            value.st_dev,
            value.st_ino,
            value.st_uid,
            value.st_mode,
            value.st_nlink,
            value.st_size,
            value.st_mtime_ns,
            value.st_ctime_ns,
        )

    @property
    def runtime_identity(self) -> tuple[int, int, int, int]:
        return self.device, self.inode, self.uid, self.mode

    def validate(self, root: Metadata, *, directory: bool = False) -> None:
        if (
            any(type(x) is not int or x < 0 for x in asdict(self).values())
            or self.device != root.device
            or self.uid != root.uid
            or self.mode & 0o022
            or not (stat.S_ISDIR(self.mode) if directory else stat.S_ISREG(self.mode))
            or (not directory and self.links != 1)
        ):
            raise RuntimeError("unsafe remote metadata owner/mode/device/type/link")


class Operation(StrEnum):
    CREATE = "create"
    APPEND = "append"
    REPLACE = "replace"
    REMOVE = "remove"


class Phase(StrEnum):
    HELLO = "hello"
    BEFORE_START = "before-start"
    BEFORE = "before"
    WRITES = "writes"
    AFTER = "after"
    CLOSE = "close"
    ACK = "ack"
    DONE = "done"


class Disposition(StrEnum):
    OPEN = "open"
    UNRESOLVED = "unresolved"
    RECONCILED = "reconciled"


@dataclass
class RemoteLease:
    sequence: int
    path: str
    role: CampaignWriterRole
    operation: Operation
    granted: int
    initial: Metadata | None
    actual: int = 0
    temporary: str | None = None
    temporary_identity: Metadata | None = None
    opened: Metadata | None = None
    final: Metadata | None = None
    retired: int = 0
    baseline_removed: int = 0
    verified: bool = False


class RemoteCleanupAuthority:
    """Controller-owned causal state; no independent policy cap or refunds."""

    def __init__(
        self,
        binding: RemoteCleanupBinding,
        *,
        reserve: Callable[[int], None],
        observe: Callable[[int], None],
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        binding.validate()
        self.binding = binding
        self.reserve = reserve
        self.observe = observe
        self.monotonic = monotonic
        self.sequence = 0
        self.phase = Phase.HELLO
        self.disposition = Disposition.OPEN
        self.root: Metadata | None = None
        self.before: dict[str, Metadata] | None = None
        self.expected: dict[str, Metadata] = {}
        self.live_baseline: set[str] = set()
        self.leases: dict[int, RemoteLease] = {}
        self.snapshots: dict[str, dict[str, Metadata]] = {}
        self.result: dict[str, Any] | None = None
        self.events: list[dict[str, Any]] = []
        self.transcript_bytes = 0

    def remaining(self) -> float:
        remaining = self.binding.deadline - self.monotonic()
        if self.disposition != Disposition.OPEN or remaining <= 0:
            raise RuntimeError("remote cleanup unresolved/closed/original deadline expired")
        return remaining

    def accept(self, frame: dict[str, Any]) -> dict[str, Any]:
        try:
            self.remaining()
            if (
                set(frame) != {"binding", "sequence", "operation", "payload"}
                or canonical(frame["binding"]) != canonical(self.binding.document())
                or type(frame["sequence"]) is not int
                or frame["sequence"] != self.sequence + 1
                or self.sequence >= MAX_EVENTS
                or not isinstance(frame["payload"], dict)
            ):
                raise RuntimeError("remote cleanup binding/sequence replay")
            size = len(canonical(frame))
            if (
                size > CleanupOutputChannel.MAX_FRAME
                or self.transcript_bytes + size > MAX_TRANSCRIPT_BYTES
            ):
                raise RuntimeError("remote cleanup frame/transcript cap")
            self.sequence += 1
            op, payload = frame["operation"], frame["payload"]
            allowed = {
                Phase.HELLO: {"hello"},
                Phase.BEFORE_START: {"snapshot-start"},
                Phase.BEFORE: {"snapshot-member", "snapshot-end"},
                Phase.WRITES: {
                    "grant",
                    "opened",
                    "temporary",
                    "observe",
                    "verify",
                    "snapshot-start",
                },
                Phase.AFTER: {"snapshot-member", "snapshot-end"},
                Phase.CLOSE: {"close"},
                Phase.ACK: {"acknowledged"},
                Phase.DONE: set(),
            }
            if op not in allowed[self.phase]:
                raise RuntimeError("remote cleanup event outside typed phase")
            answer = self._event(op, payload)
            if self.monotonic() >= self.binding.deadline:
                raise RuntimeError("remote event crossed original deadline")
            self.transcript_bytes += size
            self.events.append(frame)
            return {
                "binding": self.binding.identity,
                "sequence": self.sequence,
                "accepted": True,
                "result": answer,
                "remaining_seconds": max(0.0, self.binding.deadline - self.monotonic()),
            }
        except BaseException:
            self.disposition = Disposition.UNRESOLVED
            raise

    def _event(self, op: str, p: dict[str, Any]) -> dict[str, Any]:
        if self.sequence == 1:
            if op != "hello" or set(p) != {"root"}:
                raise RuntimeError("remote cleanup requires exact handshake")
            root = Metadata(**p["root"])
            root.validate(root, directory=True)
            self.root = root
            self.phase = Phase.BEFORE_START
            return {}
        if self.root is None:
            raise RuntimeError("remote root absent")
        if op == "snapshot-start" and set(p) == {"kind", "root"}:
            kind = p["kind"]
            if kind != ("before" if self.phase == Phase.BEFORE_START else "after"):
                raise RuntimeError("remote snapshot phase substitution")
            if kind not in {"before", "after"} or kind in self.snapshots:
                raise RuntimeError("duplicate remote snapshot")
            if Metadata(**p["root"]).runtime_identity != self.root.runtime_identity:
                raise RuntimeError("remote root runtime drift")
            if kind == "after" and (
                self.before is None or any(not x.verified for x in self.leases.values())
            ):
                raise RuntimeError("remote publications unresolved")
            self.snapshots[kind] = {}
            self.phase = Phase.BEFORE if kind == "before" else Phase.AFTER
            return {}
        if op == "snapshot-member" and set(p) == {"kind", "path", "metadata"}:
            if p["kind"] != self.phase.value:
                raise RuntimeError("remote census phase substitution")
            inventory = self.snapshots[p["kind"]]
            path = member(p["path"])
            if (
                path in inventory
                or len(inventory) >= MAX_ENTRIES
                or (inventory and path <= max(inventory))
            ):
                raise RuntimeError("remote census duplicate/order/entry cap")
            value = Metadata(**p["metadata"])
            value.validate(self.root)
            if any((x.device, x.inode) == (value.device, value.inode) for x in inventory.values()):
                raise RuntimeError("remote census repeats an occupied inode")
            inventory[path] = value
            return {}
        if op == "snapshot-end" and set(p) == {"kind", "count", "bytes", "digest", "complete"}:
            kind = p["kind"]
            if kind != self.phase.value:
                raise RuntimeError("remote census phase substitution")
            inventory = self.snapshots[kind]
            if (
                p["complete"] is not True
                or type(p["count"]) is not int
                or p["count"] != len(inventory)
                or type(p["bytes"]) is not int
                or p["bytes"] != sum(x.size for x in inventory.values())
                or p["digest"] != digest({k: asdict(v) for k, v in inventory.items()})
            ):
                raise RuntimeError("remote census incomplete/count/bytes/digest mismatch")
            if kind == "before":
                if self.before is not None or self.leases:
                    raise RuntimeError("replayed remote baseline")
                self.before = dict(inventory)
                self.expected = dict(inventory)
                self.live_baseline = set(inventory)
                self.phase = Phase.WRITES
            else:
                if self.before is None or inventory != self.expected:
                    raise RuntimeError("remote census uncovered/omitted/changed publication")
                writes = sum(x.actual for x in self.leases.values())
                retired = sum(x.retired for x in self.leases.values())
                delta = sum(x.size for x in inventory.values()) - sum(
                    x.size for x in self.before.values()
                )
                if delta != writes - retired:
                    raise RuntimeError("remote census unexplained occupancy delta")
                self.phase = Phase.CLOSE
                self.result = {
                    "binding": self.binding.identity,
                    "complete": True,
                    "root_runtime_identity": list(self.root.runtime_identity),
                    "before_files": len(self.before),
                    "after_files": len(inventory),
                    "before_bytes": sum(x.size for x in self.before.values()),
                    "after_bytes": sum(x.size for x in inventory.values()),
                    "before": digest({k: asdict(v) for k, v in self.before.items()}),
                    "after": p["digest"],
                    "actual_writes": writes,
                    "exact_retirements": retired,
                    "occupancy_delta": delta,
                    "unreconciled_bytes": 0,
                    "uncovered_writes": [],
                    "observation_prefix_sequence": self.sequence - 1,
                    "observation_prefix_digest": digest(self.events),
                    "added": sorted(set(inventory) - set(self.before)),
                    "removed": sorted(set(self.before) - set(inventory)),
                    "changed": sorted(
                        k for k in inventory if k in self.before and inventory[k] != self.before[k]
                    ),
                    "baseline_removal_bytes": sum(x.baseline_removed for x in self.leases.values()),
                    "total_removed_bytes": sum(
                        x.retired for x in self.leases.values() if x.operation == Operation.REMOVE
                    ),
                    "replacement_retired_bytes": sum(
                        x.retired for x in self.leases.values() if x.operation == Operation.REPLACE
                    ),
                }
            return {}
        if self.before is None or "after" in self.snapshots:
            if op == "close" and not p and self.result is not None:
                self.phase = Phase.ACK
                return {"reconciliation": digest(self.result)}
            if (
                op == "acknowledged"
                and p == {"reconciliation": digest(self.result)}
                and self.result is not None
            ):
                self.phase = Phase.DONE
                self.disposition = Disposition.RECONCILED
                return {}
            raise RuntimeError("remote operation outside census lifecycle")
        if op == "grant" and set(p) == {"path", "role", "operation", "bytes", "initial"}:
            path = member(p["path"])
            operation = Operation(p["operation"])
            role = CampaignWriterRole(p["role"])
            size = p["bytes"]
            initial = None if p["initial"] is None else Metadata(**p["initial"])
            if (
                type(size) is not int
                or size < 0
                or initial != self.expected.get(path)
                or any(not x.verified for x in self.leases.values())
                or (operation == Operation.CREATE and initial is not None)
                or (operation != Operation.CREATE and initial is None)
                or (operation == Operation.REMOVE and size != 0)
            ):
                raise RuntimeError("remote grant operation/initial state mismatch")
            self.reserve(size)
            self.leases[self.sequence] = RemoteLease(
                self.sequence, path, role, operation, size, initial
            )
            return {"lease": self.sequence, "bytes": size, "deadline": self.binding.deadline}
        if op in {"opened", "temporary", "observe", "verify"}:
            lease = self.leases[p["lease"]]
            if type(p["lease"]) is not int or lease.verified:
                raise RuntimeError("remote lease replay")
            if op == "opened" and set(p) == {"lease", "metadata"}:
                opened = Metadata(**p["metadata"])
                opened.validate(self.root)
                if (
                    lease.operation != Operation.CREATE
                    or lease.opened is not None
                    or opened.size != 0
                ):
                    raise RuntimeError("remote create inode not fresh")
                if any(
                    (x.device, x.inode) == (opened.device, opened.inode)
                    for x in self.expected.values()
                ):
                    raise RuntimeError("remote fresh inode is already occupied")
                lease.opened = opened
            elif op == "temporary" and set(p) == {"lease", "path", "metadata"}:
                path = member(p["path"])
                identity = Metadata(**p["metadata"])
                identity.validate(self.root)
                if (
                    lease.operation != Operation.REPLACE
                    or lease.temporary is not None
                    or path in self.expected
                    or path == lease.path
                    or identity.size != 0
                ):
                    raise RuntimeError("remote temporary not fresh")
                if any(
                    (x.device, x.inode) == (identity.device, identity.inode)
                    for x in self.expected.values()
                ):
                    raise RuntimeError("remote temporary inode is already occupied")
                lease.temporary, lease.temporary_identity = path, identity
            elif op == "observe" and set(p) == {"lease", "bytes"}:
                count = p["bytes"]
                if (
                    type(count) is not int
                    or count < 0
                    or lease.actual + count > lease.granted
                    or (lease.operation == Operation.REPLACE and lease.temporary is None)
                    or (lease.operation == Operation.CREATE and lease.opened is None)
                ):
                    raise RuntimeError("remote write exceeds finite grant")
                self.observe(count)
                lease.actual += count
            elif op == "verify" and set(p) == {
                "lease",
                "final",
                "retired",
                "retired_identity",
                "time",
            }:
                final = None if p["final"] is None else Metadata(**p["final"])
                if (
                    type(p["time"]) not in {int, float}
                    or not math.isfinite(p["time"])
                    or p["time"] <= 0
                ):
                    raise RuntimeError("remote publication after original deadline")
                initial = lease.initial
                retired = (
                    initial.size
                    if initial and lease.operation in {Operation.REMOVE, Operation.REPLACE}
                    else 0
                )
                retired_identity = (
                    initial if lease.operation in {Operation.REMOVE, Operation.REPLACE} else None
                )
                if (
                    p["retired_identity"]
                    != (asdict(retired_identity) if retired_identity else None)
                    or type(p["retired"]) is not int
                    or p["retired"] != retired
                ):
                    raise RuntimeError("remote retirement mismatch")
                if lease.operation == Operation.REMOVE:
                    if final is not None or lease.actual:
                        raise RuntimeError("remote removal mismatch")
                    del self.expected[lease.path]
                else:
                    if final is None:
                        raise RuntimeError("remote publication absent")
                    final.validate(self.root)
                    origin = (
                        initial
                        if lease.operation == Operation.APPEND
                        else lease.opened
                        if lease.operation == Operation.CREATE
                        else lease.temporary_identity
                    )
                    if origin is None:
                        raise RuntimeError("remote publication lacks admitted open inode")
                    if origin and final.runtime_identity != origin.runtime_identity:
                        raise RuntimeError("remote publication inode changed")
                    expected_size = lease.actual + (
                        initial.size if initial and lease.operation == Operation.APPEND else 0
                    )
                    if final.size != expected_size:
                        raise RuntimeError("remote publication occupancy mismatch")
                    self.expected[lease.path] = final
                if (
                    lease.operation in {Operation.REMOVE, Operation.REPLACE}
                    and lease.path in self.live_baseline
                ):
                    if lease.operation == Operation.REMOVE:
                        lease.baseline_removed = self.before[lease.path].size
                    self.live_baseline.remove(lease.path)
                lease.final, lease.retired, lease.verified = final, retired, True
            else:
                raise RuntimeError("noncanonical remote lease event")
            return {}
        raise RuntimeError("unsupported remote cleanup event")

    def require_reconciled(self) -> str:
        if self.disposition != Disposition.RECONCILED or self.result is None:
            raise RuntimeError("remote cleanup unresolved; no refund or success")
        return digest(self.result)


class RemoteCleanupChannel(CleanupOutputChannel):
    """Explicit versioned extension using the existing deadline-safe pipe framing."""

    MAX_EVENTS = MAX_EVENTS

    @classmethod
    def for_provider(
        cls, fd: int, binding: RemoteCleanupBinding, *, write_fd: int | None = None
    ) -> RemoteCleanupChannel:
        # No shared monotonic epoch is assumed. The first authenticated response
        # clamps this finite transport window before any admitted file write.
        return cls(fd, binding, time.monotonic() + binding.remaining_at_issue, write_fd=write_fd)

    def exchange(self, operation: str, /, **payload: object) -> dict[str, Any]:
        if self.sequence >= self.MAX_EVENTS:
            raise RuntimeError("remote cleanup event limit")
        self.sequence += 1
        request_started = time.monotonic()
        self.send(
            {
                "binding": self.binding.document(),
                "sequence": self.sequence,
                "operation": operation,
                "payload": payload,
            }
        )
        response = self.receive()
        if (
            set(response) != {"binding", "sequence", "accepted", "result", "remaining_seconds"}
            or response["binding"] != digest(self.binding.document())
            or type(response["sequence"]) is not int
            or response["sequence"] != self.sequence
            or response["accepted"] is not True
        ):
            raise RuntimeError("remote cleanup grant denied or protocol mismatch")
        duration = response["remaining_seconds"]
        if (
            not isinstance(duration, (int, float))
            or isinstance(duration, bool)
            or not math.isfinite(duration)
            or duration <= 0
        ):
            raise RuntimeError("remote cleanup response deadline expired")
        self.deadline = min(self.deadline, request_started + duration)
        self.remaining()
        result = response["result"]
        if not isinstance(result, dict):
            raise RuntimeError("remote response result is not an object")
        return result

    def serve_remote(self, authority: RemoteCleanupAuthority) -> None:
        try:
            while authority.disposition == Disposition.OPEN:
                frame = self.receive()
                try:
                    response = authority.accept(frame)
                except Exception:
                    self.send(
                        {
                            "binding": authority.binding.identity,
                            "sequence": authority.sequence,
                            "accepted": False,
                            "result": {"reason": "aborted-unresolved"},
                            "remaining_seconds": 0,
                        }
                    )
                    raise
                self.send(response)
        except BaseException:
            authority.disposition = Disposition.UNRESOLVED
            raise
        finally:
            self.closed = True


class RemotePublicationObserver:
    """Exact helper-side namespace access. No capacity or policy is owned here."""

    def __init__(self, binding: RemoteCleanupBinding, channel: RemoteCleanupChannel):
        binding.validate()
        source = os.open(__file__, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            metadata = os.fstat(source)
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > 1_000_000:
                raise RuntimeError("remote helper source is not bounded regular source")
            payload = os.read(source, metadata.st_size + 1)
            if (
                len(payload) != metadata.st_size
                or hashlib.sha256(payload).hexdigest() != binding.helper_sha256
            ):
                raise RuntimeError("remote helper source binding mismatch")
        finally:
            os.close(source)
        if channel.binding != binding:
            raise RuntimeError("remote observer channel binding mismatch")
        self.binding, self.channel = binding, channel
        self.fd = -1
        self.closed = False
        fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            for component in binding.root.value[1:].split("/"):
                child = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                os.close(fd)
                fd = child
            self.root = Metadata.observed(os.fstat(fd))
            self.root.validate(self.root, directory=True)
            if self.root.uid != os.getuid():
                raise RuntimeError("remote root belongs to another user")
            self.fd, fd = fd, -1
            self.channel.exchange("hello", root=asdict(self.root))
            self.snapshot("before")
        except BaseException:
            self.close()
            raise
        finally:
            if fd >= 0:
                os.close(fd)

    def check_root(self) -> None:
        self.channel.remaining()
        if (
            self.closed
            or Metadata.observed(os.fstat(self.fd)).runtime_identity != self.root.runtime_identity
        ):
            raise RuntimeError("remote root descriptor changed")
        # Root path resolution is helper-local and no-follow at every component.
        fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            for component in self.binding.root.value[1:].split("/"):
                child = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                os.close(fd)
                fd = child
            if Metadata.observed(os.fstat(fd)).runtime_identity != self.root.runtime_identity:
                raise RuntimeError("remote root name/descriptor mismatch")
        finally:
            os.close(fd)

    def parent(self, path: str) -> tuple[int, str]:
        self.check_root()
        parts = member(path).split("/")
        fd = os.dup(self.fd)
        try:
            for component in parts[:-1]:
                child = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                try:
                    value = Metadata.observed(os.fstat(child))
                    value.validate(self.root, directory=True)
                    if value != Metadata.observed(
                        os.stat(component, dir_fd=fd, follow_symlinks=False)
                    ):
                        raise RuntimeError("remote parent descriptor/path mismatch")
                except BaseException:
                    os.close(child)
                    raise
                os.close(fd)
                fd = child
            return fd, parts[-1]
        except BaseException:
            os.close(fd)
            raise

    def revalidate_parent(self, path: str, held: int) -> None:
        current, _ = self.parent(path)
        try:
            if (
                Metadata.observed(os.fstat(current)).runtime_identity
                != Metadata.observed(os.fstat(held)).runtime_identity
            ):
                raise RuntimeError("remote held parent escaped its namespace")
        finally:
            os.close(current)

    def metadata(self, path: str) -> Metadata | None:
        fd, name = self.parent(path)
        opened = -1
        try:
            try:
                named = Metadata.observed(os.stat(name, dir_fd=fd, follow_symlinks=False))
            except FileNotFoundError:
                return None
            named.validate(self.root)
            opened = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
            held = Metadata.observed(os.fstat(opened))
            held.validate(self.root)
            if held != named or held != Metadata.observed(
                os.stat(name, dir_fd=fd, follow_symlinks=False)
            ):
                raise RuntimeError("remote file descriptor/path mismatch")
            return held
        finally:
            if opened >= 0:
                os.close(opened)
            os.close(fd)

    def inventory(self) -> dict[str, Metadata]:
        self.check_root()
        result: dict[str, Metadata] = {}
        entries_seen = 0

        def visit(fd: int, prefix: str, depth: int) -> None:
            nonlocal entries_seen
            self.channel.remaining()
            if depth > MAX_DEPTH:
                raise RuntimeError("remote census depth cap")
            # Bound allocation while enumerating, before sorting.
            names: list[str] = []
            with os.scandir(fd) as entries:
                for entry in entries:
                    self.channel.remaining()
                    entries_seen += 1
                    if entries_seen > MAX_ENTRIES:
                        raise RuntimeError("remote census entry cap")
                    names.append(entry.name)
            for name in sorted(names):
                self.channel.remaining()
                path = member(prefix + name)
                value = Metadata.observed(os.stat(name, dir_fd=fd, follow_symlinks=False))
                if stat.S_ISDIR(value.mode):
                    value.validate(self.root, directory=True)
                    child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                    try:
                        if value != Metadata.observed(os.fstat(child)):
                            raise RuntimeError("remote census directory drift")
                        visit(child, path + "/", depth + 1)
                        if value != Metadata.observed(
                            os.fstat(child)
                        ) or value != Metadata.observed(
                            os.stat(name, dir_fd=fd, follow_symlinks=False)
                        ):
                            raise RuntimeError("remote census directory changed during traversal")
                    finally:
                        os.close(child)
                else:
                    value.validate(self.root)
                    if value != self.metadata(path):
                        raise RuntimeError("remote census file drift")
                    result[path] = value

        before = Metadata.observed(os.fstat(self.fd))
        visit(self.fd, "", 1)
        self.check_root()
        if before != Metadata.observed(os.fstat(self.fd)):
            raise RuntimeError("remote census root changed during traversal")
        return dict(sorted(result.items()))

    def snapshot(self, kind: str) -> dict[str, Metadata]:
        inventory = self.inventory()
        self.channel.exchange("snapshot-start", kind=kind, root=asdict(self.root))
        for path, value in inventory.items():
            self.channel.exchange("snapshot-member", kind=kind, path=path, metadata=asdict(value))
        document = {k: asdict(v) for k, v in inventory.items()}
        self.channel.exchange(
            "snapshot-end",
            kind=kind,
            count=len(inventory),
            bytes=sum(x.size for x in inventory.values()),
            digest=digest(document),
            complete=True,
        )
        return inventory

    def publish(
        self,
        path: str,
        data: bytes,
        operation: Operation,
        role: CampaignWriterRole = CampaignWriterRole.CLEANUP_RECEIPT,
        *,
        maximum_bytes: int | None = None,
    ) -> None:
        """Grant first; open/write only after the bound finite response arrives."""
        path = member(path)
        maximum = len(data) if maximum_bytes is None else maximum_bytes
        if type(maximum) is not int or maximum < len(data):
            raise RuntimeError("remote payload exceeds requested finite grant")
        initial = self.metadata(path)
        if operation == Operation.REMOVE and data:
            raise RuntimeError("removal carries no write payload")
        grant = self.channel.exchange(
            "grant",
            path=path,
            role=role.value,
            operation=operation.value,
            bytes=maximum,
            initial=None if initial is None else asdict(initial),
        )
        lease = grant["lease"]
        if grant != {
            "lease": self.channel.sequence,
            "bytes": maximum,
            "deadline": self.binding.deadline,
        }:
            raise RuntimeError("remote grant carrier substitution")
        parent, name = self.parent(path)
        fd = -1
        try:
            self.revalidate_parent(path, parent)
            if self.metadata(path) != initial:
                raise RuntimeError("remote target changed after grant")
            target = name
            temporary = None
            if operation == Operation.REMOVE:
                os.unlink(name, dir_fd=parent)
            else:
                flags = os.O_WRONLY | os.O_NOFOLLOW | os.O_NONBLOCK
                if operation == Operation.REPLACE:
                    temporary = path + ".cleanup-" + self.binding.nonce + "-" + str(lease)
                    member(temporary)
                    target = temporary.rsplit("/", 1)[-1]
                flags |= os.O_APPEND if operation == Operation.APPEND else os.O_CREAT | os.O_EXCL
                fd = os.open(target, flags, 0o600, dir_fd=parent)
                opened = Metadata.observed(os.fstat(fd))
                opened.validate(self.root)
                if operation == Operation.APPEND and opened != initial:
                    raise RuntimeError("remote append inode drift")
                if operation == Operation.CREATE:
                    self.channel.exchange("opened", lease=lease, metadata=asdict(opened))
                if temporary is not None:
                    self.channel.exchange(
                        "temporary", lease=lease, path=temporary, metadata=asdict(opened)
                    )
                offset = 0
                while offset < len(data):
                    self.revalidate_parent(path, parent)
                    count = os.write(fd, memoryview(data)[offset : offset + 65536])
                    if count <= 0:
                        raise OSError("remote write made no progress")
                    offset += count
                    self.channel.exchange("observe", lease=lease, bytes=count)
                os.fsync(fd)
                held = Metadata.observed(os.fstat(fd))
                held.validate(self.root)
                if held.runtime_identity != opened.runtime_identity or held != Metadata.observed(
                    os.stat(target, dir_fd=parent, follow_symlinks=False)
                ):
                    raise RuntimeError("remote publication descriptor/path mismatch")
                if temporary is not None:
                    if self.metadata(path) != initial:
                        raise RuntimeError("remote retirement inode changed")
                    os.replace(target, name, src_dir_fd=parent, dst_dir_fd=parent)
            final = self.metadata(path)
            if fd >= 0 and final != Metadata.observed(os.fstat(fd)):
                raise RuntimeError("remote published inode changed")
            retired = (
                initial.size
                if initial and operation in {Operation.REMOVE, Operation.REPLACE}
                else 0
            )
            self.channel.exchange(
                "verify",
                lease=lease,
                final=None if final is None else asdict(final),
                retired=retired,
                retired_identity=asdict(initial)
                if initial and operation in {Operation.REMOVE, Operation.REPLACE}
                else None,
                time=time.monotonic(),
            )
        finally:
            if fd >= 0:
                os.close(fd)
            os.close(parent)

    def finish(self) -> str:
        try:
            self.snapshot("after")
            result = self.channel.exchange("close")
            identity = result["reconciliation"]
            if not isinstance(identity, str) or re.fullmatch(r"[a-f0-9]{64}", identity) is None:
                raise RuntimeError("invalid remote reconciliation identity")
            self.channel.exchange("acknowledged", reconciliation=identity)
            return identity
        finally:
            self.close()

    def close(self) -> None:
        if self.fd >= 0:
            os.close(self.fd)
            self.fd = -1
        self.closed = True
