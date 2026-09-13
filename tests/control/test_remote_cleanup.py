"""Offline separate-directory/retained-process proof; no remote host is claimed."""

from __future__ import annotations

import hashlib
import json
import os
import socket
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import asdict, replace
from pathlib import Path

import pytest

from giclab.harness import remote_cleanup as remote
from giclab.harness.campaign_output import (
    CampaignWriterRole,
    admit_campaign_write,
    verify_campaign_write,
)
from tests.control.test_remote_transaction_review import _campaign_writer_world

HELPER = """
import json,os,sys
from giclab.harness.remote_cleanup import *
b=RemoteCleanupBinding.from_document(json.loads(sys.argv[1]))
c=RemoteCleanupChannel.for_provider(int(sys.argv[2]),b)
o=RemotePublicationObserver(b,c)
try:
 for action in json.loads(sys.argv[3]):
  if action[0]=='unadmitted':
   fd=os.open(action[1],os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600,dir_fd=o.fd)
   os.write(fd,b'x');os.close(fd)
  elif action[0]=='stall':
   import time;time.sleep(float(action[1]))
  elif action[0]=='disconnect': os._exit(7)
  elif action[0]=='partial-disconnect':
   write=os.write
   def partial(fd,data):
    if stat.S_ISREG(os.fstat(fd).st_mode):
     write(fd,data[:1]);os._exit(7)
    return write(fd,data)
   os.write=partial
   o.publish(action[1],action[2].encode(),Operation(action[3]))
  else: o.publish(action[1],action[2].encode(),Operation(action[0]))
 o.finish()
finally: o.close()
"""


def binding(root):
    return remote.RemoteCleanupBinding(
        provider_contract_version="16.0.0",
        plan_id="offline-plan",
        host_run_id="offline-host",
        source_commit="1" * 40,
        source_tree="2" * 40,
        candidate_sha256="3" * 64,
        provider_identity="offline-provider",
        launch_ordinal=1,
        transfer_sha256="4" * 64,
        entry_sha256="5" * 64,
        root=remote.RemoteRoot(str(root)),
        root_semantic_sha256="6" * 64,
        handoff_sha256="7" * 64,
        attempt=1,
        deadline=time.monotonic() + 15,
        remaining_at_issue=15,
        nonce="offline-nonce",
        helper_sha256=hashlib.sha256(Path(remote.__file__).read_bytes()).hexdigest(),
    )


def run_remote(tmp_path, actions, *, reserve=None, seed=None, seconds=15):
    local, provider = tmp_path / "controller", tmp_path / "provider-fixture"
    local.mkdir(mode=0o700)
    provider.mkdir(mode=0o700)
    for name, data in (seed or {}).items():
        (provider / name).write_bytes(data)
    world, _ = _campaign_writer_world(local)
    accountant = world._campaign_accountant()
    if reserve is not None:
        world._campaign_cleanup_remaining = reserve
    original = world._campaign_cleanup_remaining
    bound = replace(
        binding(provider), deadline=time.monotonic() + seconds, remaining_at_issue=seconds
    )
    authority = remote.RemoteCleanupAuthority(
        bound,
        reserve=world._reserve_cleanup_publication,
        observe=accountant.observe_campaign_output_bytes,
    )
    independent, error = drive_authority(authority, actions)
    return world, authority, independent, original, error


def drive_authority(authority, actions, *, drop_terminal_ack=False):
    bound = authority.binding
    provider = Path(bound.root.value)
    parent, child = socket.socketpair()
    process = None
    error = None
    try:
        process = subprocess.Popen(
            [
                sys.executable,
                "-B",
                "-c",
                HELPER,
                json.dumps(bound.document()),
                str(child.fileno()),
                json.dumps(actions),
            ],
            pass_fds=(child.fileno(),),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        child.close()
        channel = remote.RemoteCleanupChannel(parent.fileno(), bound, bound.deadline)
        if drop_terminal_ack:
            send = channel.send

            def faulted_send(value):
                if authority.disposition == remote.Disposition.RECONCILED:
                    raise OSError("offline terminal acknowledgement transport loss")
                send(value)

            channel.send = faulted_send
        try:
            channel.serve_remote(authority)
        except (RuntimeError, EOFError, OSError, TimeoutError) as exc:
            error = exc
        parent.close()
        if time.monotonic() >= bound.deadline and process.poll() is None:
            process.kill()
        try:
            stdout, stderr = process.communicate(
                timeout=max(0.01, min(1.0, bound.deadline - time.monotonic()))
            )
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate(timeout=1)
            if error is None:
                error = TimeoutError("retained helper did not terminate before deadline")
        process_closed_at = time.monotonic()
        assert not stdout
        if error is not None:
            error = RuntimeError(str(error) + " child: " + stderr.decode())
        if error is None:
            assert process.returncode == 0, stderr.decode()
        independent = {
            str(p.relative_to(provider)): remote.Metadata.observed(p.stat())
            for p in provider.rglob("*")
            if p.is_file()
        }
        (provider.parent / "remote-cleanup-evidence.json").write_text(
            json.dumps(
                {
                    "classification": "offline-separate-directory-retained-process",
                    "binding": bound.document(),
                    "disposition": authority.disposition.value,
                    "events": authority.events,
                    "leases": [asdict(x) for x in authority.leases.values()],
                    "snapshots": {
                        k: {name: asdict(v) for name, v in inventory.items()}
                        for k, inventory in authority.snapshots.items()
                    },
                    "independent_after": {name: asdict(v) for name, v in independent.items()},
                    "reconciliation": authority.result,
                    "process_exit": process.returncode,
                    "process_closed_at": process_closed_at,
                    "teardown_bound_seconds": 1,
                    "descriptors_closed": parent.fileno() == child.fileno() == -1,
                    "error": None if error is None else str(error),
                },
                sort_keys=True,
            )
            + "\n"
        )
        return independent, error
    finally:
        parent.close()
        child.close()
        if process is not None:
            if process.poll() is None:
                process.kill()
            process.communicate(timeout=5)


def test_actual_separate_process_create_append_replace_remove_and_census(tmp_path):
    world, a, inventory, original, error = run_remote(
        tmp_path,
        [
            ["create", "new", "abc"],
            ["append", "new", "d"],
            ["replace", "old", "xy"],
            ["remove", "gone", ""],
        ],
        seed={"old": b"12345", "gone": b"123"},
    )
    assert error is None
    assert a.require_reconciled()
    assert inventory == a.expected == a.snapshots["after"]
    assert a.result["actual_writes"] == 6
    assert a.result["exact_retirements"] == 8
    assert a.result["occupancy_delta"] == -2
    assert world._campaign_cleanup_remaining == original - 6
    assert world._campaign_accountant().campaign_output_observed == 6
    # A local publication consumes the very same reserve and local inode verifier.
    with world._campaign_writer_scope(cleanup=True):
        target = world.root / "local.json"
        lease = admit_campaign_write(target, 2, CampaignWriterRole.CLEANUP_RECEIPT)
        target.write_bytes(b"{}")
        lease.observe(2)
        verify_campaign_write(lease, target)
    assert world._campaign_cleanup_remaining == original - 8
    assert world._campaign_accountant().campaign_output_observed == 8


@pytest.mark.parametrize(
    "actions,reserve,expected_bytes",
    [
        ([["create", "denied", "abc"]], 2, 0),
        ([["create", "partial", "abc"], ["disconnect"]], 10, 3),
        ([["unadmitted", "rogue"]], 10, 1),
    ],
)
def test_fail_closed_denial_disconnect_unadmitted(tmp_path, actions, reserve, expected_bytes):
    world, a, inventory, original, error = run_remote(tmp_path, actions, reserve=reserve)
    assert error is not None
    assert a.disposition == remote.Disposition.UNRESOLVED
    with pytest.raises(RuntimeError, match="unresolved"):
        a.require_reconciled()
    assert sum(x.size for x in inventory.values()) == expected_bytes
    assert world._campaign_cleanup_remaining == original - sum(x.granted for x in a.leases.values())
    if actions[0][1] == "denied":
        assert world._campaign_admission_blocked


@pytest.mark.parametrize(
    "field,value",
    [
        ("provider_identity", "other"),
        ("launch_ordinal", 2),
        ("plan_id", "other"),
        ("host_run_id", "other"),
        ("transfer_sha256", "8" * 64),
        ("entry_sha256", "8" * 64),
        ("source_commit", "8" * 40),
        ("source_tree", "8" * 40),
        ("candidate_sha256", "8" * 64),
        ("root", remote.RemoteRoot("/other/root")),
        ("handoff_sha256", "8" * 64),
        ("attempt", 2),
        ("nonce", "other"),
        ("helper_sha256", "8" * 64),
        ("provider_contract_version", "other"),
        ("root_semantic_sha256", "8" * 64),
        ("deadline", 1.0),
    ],
)
def test_binding_substitution_before_effect(tmp_path, field, value):
    b = binding(tmp_path)
    calls = []
    a = remote.RemoteCleanupAuthority(b, reserve=calls.append, observe=calls.append)
    wrong = replace(b, **{field: value})
    with pytest.raises(RuntimeError, match="binding/sequence"):
        a.accept({"binding": wrong.document(), "sequence": 1, "operation": "hello", "payload": {}})
    assert not calls and not a.leases


@pytest.mark.parametrize(
    "value", ["/absolute", "../escape", "a/../b", "a//b", "", "a/./b", "a/", "//root"]
)
def test_remote_members_are_canonical_relative_posix(value):
    with pytest.raises(RuntimeError):
        remote.member(value)


@pytest.mark.parametrize("sequence", [0, 2, True, -1])
def test_wrong_initial_sequence(tmp_path, sequence):
    b = binding(tmp_path)
    a = remote.RemoteCleanupAuthority(
        b, reserve=lambda _: pytest.fail("unapproved grant"), observe=lambda _: None
    )
    with pytest.raises(RuntimeError, match="binding/sequence"):
        a.accept(
            {"binding": b.document(), "sequence": sequence, "operation": "hello", "payload": {}}
        )


def test_legacy_channel_protocol_is_separately_versioned():
    from giclab.control.effects import EFFECT_PROTOCOL_VERSION

    assert EFFECT_PROTOCOL_VERSION == "2.0.0"
    assert remote.PROTOCOL == "cross-host-cleanup/1.0.0"


class OfflineDuplex:
    """Explicit low-level transport double; real authority and actual files."""

    def __init__(self, authority):
        self.authority = authority
        self.binding = authority.binding
        self.deadline = self.binding.deadline
        self.sequence = 0
        self.frames = []
        self.mutate: Callable | None = None

    def remaining(self):
        return self.authority.remaining()

    def exchange(self, operation, /, **payload):
        self.sequence += 1
        frame = {
            "binding": self.binding.document(),
            "sequence": self.sequence,
            "operation": operation,
            "payload": payload,
        }
        if self.mutate is not None:
            frame = self.mutate(frame)
        self.frames.append(frame)
        return self.authority.accept(frame)["result"]


@pytest.fixture
def observed(tmp_path):
    local, provider = tmp_path / "controller", tmp_path / "provider"
    local.mkdir(mode=0o700)
    provider.mkdir(mode=0o700)
    (provider / "baseline").write_bytes(b"baseline")
    world, _ = _campaign_writer_world(local)
    accountant = world._campaign_accountant()
    authority = remote.RemoteCleanupAuthority(
        binding(provider),
        reserve=world._reserve_cleanup_publication,
        observe=accountant.observe_campaign_output_bytes,
    )
    channel = OfflineDuplex(authority)
    observer = remote.RemotePublicationObserver(authority.binding, channel)
    try:
        yield world, authority, channel, observer, provider
    finally:
        observer.close()


@pytest.mark.parametrize("operation", list(remote.Operation))
def test_zero_byte_operations_bind_real_inodes(observed, operation):
    _world, authority, _channel, observer, provider = observed
    path = "fresh" if operation == remote.Operation.CREATE else "baseline"
    observer.publish(path, b"", operation)
    observer.finish()
    assert authority.require_reconciled()
    lease = next(iter(authority.leases.values()))
    assert lease.actual == lease.granted == 0
    if operation == remote.Operation.CREATE:
        assert lease.opened is not None and lease.opened.inode == (provider / path).stat().st_ino
    if operation == remote.Operation.REPLACE:
        assert lease.temporary_identity is not None
        assert lease.final.inode == lease.temporary_identity.inode


@pytest.mark.parametrize(
    "fault",
    [
        "duplicate-before-end",
        "member-after-before-end",
        "after-before-grant",
        "ack-without-close",
        "duplicate-sequence",
    ],
)
def test_census_phase_replay_fails_closed(observed, fault):
    _, authority, channel, observer, _ = observed
    frame = dict(channel.frames[-1])
    frame["sequence"] = channel.sequence + 1
    if fault == "member-after-before-end":
        frame = {
            **frame,
            "operation": "snapshot-member",
            "payload": {
                "kind": "before",
                "path": "baseline",
                "metadata": asdict(authority.before["baseline"]),
            },
        }
    elif fault == "after-before-grant":
        frame = {
            **frame,
            "operation": "snapshot-member",
            "payload": {
                "kind": "after",
                "path": "baseline",
                "metadata": asdict(authority.before["baseline"]),
            },
        }
    elif fault == "ack-without-close":
        observer.snapshot("after")
        frame = {
            **frame,
            "sequence": channel.sequence + 1,
            "operation": "acknowledged",
            "payload": {"reconciliation": remote.digest(authority.result)},
        }
    elif fault == "duplicate-sequence":
        frame["sequence"] = channel.sequence
    with pytest.raises(RuntimeError):
        authority.accept(frame)
    assert authority.disposition == remote.Disposition.UNRESOLVED


@pytest.mark.parametrize(
    "fault",
    [
        "count",
        "bytes",
        "digest",
        "incomplete",
        "duplicate-member",
        "omitted-publication",
        "wrong-retirement",
        "wrong-inode",
    ],
)
def test_faulted_observations_do_not_reconcile(observed, fault):
    _, authority, channel, observer, _ = observed

    def mutate(frame):
        p = dict(frame["payload"])
        if frame["operation"] == "verify":
            if fault == "wrong-retirement":
                p["retired"] += 1
            if fault == "wrong-inode":
                p["final"] = {**p["final"], "inode": p["final"]["inode"] + 1}
        if frame["operation"] == "snapshot-end" and p["kind"] == "after":
            if fault in {"count", "bytes"}:
                p[fault] += 1
            if fault == "digest":
                p["digest"] = "0" * 64
            if fault == "incomplete":
                p["complete"] = False
        if frame["operation"] == "snapshot-member" and p["kind"] == "after":
            if fault == "duplicate-member":
                p["path"] = "baseline"
            if fault == "omitted-publication" and p["path"] == "fresh":
                p["path"] = "substitute"
        return {**frame, "payload": p}

    channel.mutate = mutate
    with pytest.raises(RuntimeError):
        observer.publish("fresh", b"abc", remote.Operation.CREATE)
        observer.finish()
    assert authority.disposition == remote.Disposition.UNRESOLVED


@pytest.mark.parametrize("fault", ["symlink", "hardlink", "fifo", "mode", "new", "changed"])
def test_actual_unsafe_or_unadmitted_files_fail_terminal_census(observed, fault):
    _, authority, _, observer, provider = observed
    path = provider / "unadmitted"
    if fault == "symlink":
        path.symlink_to(provider / "baseline")
    elif fault == "hardlink":
        os.link(provider / "baseline", path)
    elif fault == "fifo":
        os.mkfifo(path)
    elif fault == "mode":
        (provider / "baseline").chmod(0o666)
    elif fault == "new":
        path.write_bytes(b"rogue")
    else:
        (provider / "baseline").write_bytes(b"changed")
    with pytest.raises(RuntimeError):
        observer.finish()
    with pytest.raises(RuntimeError):
        authority.require_reconciled()


def test_actual_root_substitution_is_rejected(observed):
    _, _, _, observer, provider = observed
    provider.rename(provider.with_name("displaced"))
    provider.mkdir(mode=0o700)
    with pytest.raises(RuntimeError, match="root name/descriptor"):
        observer.publish("fresh", b"x", remote.Operation.CREATE)
    assert not list(provider.iterdir())


def test_actual_parent_rename_cannot_use_held_descriptor(observed):
    _, _, _, observer, provider = observed
    directory = provider / "nested"
    directory.mkdir(mode=0o700)
    fd, _ = observer.parent("nested/file")
    directory.rename(provider.parent / "escaped")
    directory.mkdir(mode=0o700)
    try:
        with pytest.raises(RuntimeError, match="held parent escaped"):
            observer.revalidate_parent("nested/file", fd)
    finally:
        os.close(fd)
    assert not list((provider.parent / "escaped").iterdir())


@pytest.mark.parametrize("field", ["uid", "device", "mode", "links"])
def test_unsafe_metadata_fault_injection_for_nonroot_properties(observed, field):
    _, authority, _, _, _ = observed
    value = authority.before["baseline"]
    wrong = replace(
        value, **{field: (value.mode | 0o022) if field == "mode" else getattr(value, field) + 1}
    )
    with pytest.raises(RuntimeError, match="unsafe remote metadata"):
        wrong.validate(authority.root)


def test_original_deadline_is_not_renewed(observed):
    _, authority, _, observer, provider = observed
    authority.monotonic = lambda: authority.binding.deadline + 1
    with pytest.raises(RuntimeError, match="deadline"):
        observer.publish("late", b"x", remote.Operation.CREATE)
    assert not (provider / "late").exists()


def test_remote_proof_and_local_export_are_separate_facts(observed):
    world, authority, _, observer, provider = observed
    observer.publish("evidence", b"selected evidence", remote.Operation.CREATE)
    observer.finish()
    assert authority.require_reconciled()
    assert not (world.root / "evidence").exists()
    with world._campaign_writer_scope(cleanup=True):
        data = (provider / "evidence").read_bytes()
        target = world.root / "evidence"
        lease = admit_campaign_write(target, len(data), CampaignWriterRole.RETAINED_COPY)
        target.write_bytes(data)
        lease.observe(len(data))
        verify_campaign_write(lease, target)
    assert target.read_bytes() == (provider / "evidence").read_bytes()
    assert target.stat().st_ino != (provider / "evidence").stat().st_ino


def test_successful_partial_admitted_write_never_refunds(observed):
    world, authority, _, observer, _ = observed
    before = world._campaign_cleanup_remaining
    observer.publish("partial", b"abc", remote.Operation.CREATE, maximum_bytes=10)
    observer.finish()
    assert authority.require_reconciled()
    lease = next(iter(authority.leases.values()))
    assert (lease.granted, lease.actual) == (10, 3)
    assert world._campaign_cleanup_remaining == before - 10


def test_payload_exceeding_requested_grant_is_rejected_before_open(observed):
    _, authority, _, observer, provider = observed
    with pytest.raises(RuntimeError, match="exceeds requested"):
        observer.publish("oversize", b"abc", remote.Operation.CREATE, maximum_bytes=2)
    assert not authority.leases and not (provider / "oversize").exists()


@pytest.mark.parametrize("operation", ["create", "replace"])
def test_actual_partial_write_disconnect_retains_grant_and_temporary(tmp_path, operation):
    seed = {"target": b"old"} if operation == "replace" else None
    world, authority, inventory, before, error = run_remote(
        tmp_path, [["partial-disconnect", "target", "abcdef", operation]], seed=seed
    )
    assert error is not None and authority.disposition == remote.Disposition.UNRESOLVED
    assert world._campaign_cleanup_remaining == before - 6
    lease = next(iter(authority.leases.values()))
    assert lease.actual == 0  # The acknowledgement was lost after the actual write.
    if operation == "replace":
        assert inventory["target"].size == 3
        assert inventory[lease.temporary].size == 1
    else:
        assert inventory["target"].size == 1


@pytest.mark.parametrize("replacement", [False, True])
def test_removal_provenance_distinguishes_baseline_from_new_bytes(observed, replacement):
    _, authority, _, observer, _ = observed
    if replacement:
        observer.publish("baseline", b"abc", remote.Operation.REPLACE)
        path = "baseline"
    else:
        observer.publish("fresh", b"abc", remote.Operation.CREATE)
        path = "fresh"
    observer.publish(path, b"", remote.Operation.REMOVE)
    observer.finish()
    assert authority.result["baseline_removal_bytes"] == 0
    assert authority.result["total_removed_bytes"] == 3


@pytest.mark.parametrize("cap", ["entries", "depth", "frame"])
def test_bounded_census_and_frame_fail_without_truncation(observed, monkeypatch, cap):
    _, authority, channel, observer, provider = observed
    if cap == "entries":
        monkeypatch.setattr(remote, "MAX_ENTRIES", 1)
        (provider / "second").write_bytes(b"x")
    elif cap == "depth":
        monkeypatch.setattr(remote, "MAX_DEPTH", 1)
        (provider / "nested").mkdir(mode=0o700)
    else:
        with pytest.raises(RuntimeError, match="frame"):
            channel.exchange("grant", junk="x" * 20000)
        return
    with pytest.raises(RuntimeError, match="cap"):
        observer.finish()
    with pytest.raises(RuntimeError):
        authority.require_reconciled()


def test_open_event_without_grant_is_rejected_before_effect(observed):
    _, authority, channel, _, provider = observed
    with pytest.raises(KeyError):
        channel.exchange("opened", lease=999, metadata=asdict(authority.before["baseline"]))
    assert not authority.leases
    assert sorted(p.name for p in provider.iterdir()) == ["baseline"]


@pytest.mark.parametrize("operation", [remote.Operation.APPEND, remote.Operation.REPLACE])
def test_actual_inode_substitution_after_grant_fails_before_write(observed, operation):
    world, authority, channel, observer, provider = observed
    before = world._campaign_cleanup_remaining
    request = channel.exchange

    def substituted(op, /, **payload):
        value = request(op, **payload)
        if op == "grant":
            (provider / "baseline").rename(provider / "old-inode")
            (provider / "baseline").write_bytes(b"replacement")
        return value

    channel.exchange = substituted
    with pytest.raises(RuntimeError, match="target changed after grant"):
        observer.publish("baseline", b"extra", operation)
    assert world._campaign_cleanup_remaining == before - 5
    assert (provider / "baseline").read_bytes() == b"replacement"
    assert next(iter(authority.leases.values())).actual == 0


@pytest.mark.parametrize("root_link", [True, False])
def test_actual_root_and_parent_symlinks_are_never_followed(observed, root_link):
    _, authority, _channel, observer, provider = observed
    (provider / "directory").mkdir(mode=0o700)
    link = provider / "link"
    link.symlink_to(provider / "directory", target_is_directory=True)
    if root_link:
        changed = replace(authority.binding, root=remote.RemoteRoot(str(link)))
        other = OfflineDuplex(
            remote.RemoteCleanupAuthority(
                changed, reserve=lambda _: pytest.fail("grant"), observe=lambda _: None
            )
        )
        with pytest.raises(OSError):
            remote.RemotePublicationObserver(changed, other)
    else:
        with pytest.raises(OSError):
            observer.publish("link/file", b"x", remote.Operation.CREATE)
    assert not list((provider / "directory").iterdir())
    assert not authority.leases


def test_actual_opened_descriptor_name_mismatch_is_rejected(observed, monkeypatch):
    _, authority, _, observer, provider = observed
    (provider / "replacement").write_bytes(b"new inode")
    real_open = os.open
    replaced = False

    def swapping_open(path, flags, *args, **kwargs):
        nonlocal replaced
        fd = real_open(path, flags, *args, **kwargs)
        if path == "baseline" and not replaced:
            replaced = True
            (provider / "baseline").rename(provider / "displaced")
            os.replace(provider / "replacement", provider / "baseline")
        return fd

    monkeypatch.setattr(os, "open", swapping_open)
    with pytest.raises(RuntimeError, match="descriptor/path mismatch"):
        observer.publish("baseline", b"x", remote.Operation.APPEND)
    assert not authority.leases


@pytest.mark.parametrize("operation", [remote.Operation.CREATE, remote.Operation.REPLACE])
def test_faulted_fresh_inode_cannot_reuse_occupied_member(observed, operation):
    _, authority, channel, observer, _ = observed

    def mutate(frame):
        if frame["operation"] in {"opened", "temporary"}:
            return {
                **frame,
                "payload": {
                    **frame["payload"],
                    "metadata": {**asdict(authority.before["baseline"]), "size": 0},
                },
            }
        return frame

    channel.mutate = mutate
    with pytest.raises(RuntimeError, match="already occupied"):
        observer.publish(
            "new" if operation == remote.Operation.CREATE else "baseline", b"x", operation
        )


@pytest.mark.parametrize("offset", [-1000000.0, 1000000.0])
def test_provider_clock_epoch_and_response_transit_do_not_extend_deadline(
    observed, monkeypatch, offset
):
    _, authority, _, _, _ = observed

    # The low-level transport response carries controller remaining duration.
    # Delay occurs after request-start, so the helper loses rather than regains time.
    class Channel(remote.RemoteCleanupChannel):
        def send(self, value):
            self.packet = value

        def receive(self):
            local[0] += 2
            return {
                "binding": authority.binding.identity,
                "sequence": self.sequence,
                "accepted": True,
                "result": {},
                "remaining_seconds": 5,
            }

    local = [time.monotonic() + offset]
    monkeypatch.setattr(remote.time, "monotonic", lambda: local[0])
    left, right = socket.socketpair()
    try:
        channel = Channel.for_provider(left.fileno(), authority.binding)
        start = local[0]
        channel.exchange("hello")
        assert channel.deadline == start + 5
        assert channel.remaining() == 3
        first = channel.deadline
        channel.exchange("hello")
        assert channel.deadline == first
    finally:
        left.close()
        right.close()


def test_largest_supported_complete_before_after_census(tmp_path):
    _, authority, inventory, _, error = run_remote(
        tmp_path, [], seed={f"member-{i:04d}": b"" for i in range(remote.MAX_ENTRIES)}, seconds=90
    )
    assert error is None
    assert len(inventory) == remote.MAX_ENTRIES
    assert authority.require_reconciled()
    assert authority.sequence < remote.MAX_EVENTS


def test_canonical_protocol_schema_validates_real_observations(observed):
    from jsonschema import Draft202012Validator

    _, authority, _, observer, _ = observed
    observer.publish("new", b"x", remote.Operation.CREATE)
    observer.publish("baseline", b"replacement", remote.Operation.REPLACE)
    observer.finish()
    schema = json.loads(
        (
            Path(__file__).resolve().parents[2] / "schemas/t09-remote-cleanup-protocol.schema.json"
        ).read_text()
    )
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    for frame in authority.events:
        validator.validate(frame)


def test_explicit_legacy_and_remote_cleanup_receipt_forms():
    from giclab.control.effects import CleanupExecutionReceipt, CrossHostCleanupExecutionReceipt

    legacy = CleanupExecutionReceipt("1" * 64, True, 0, (), True, True, True, 1, 2, 1, 2, "")
    assert set(asdict(legacy)) == {
        "immutable_handoff_sha256",
        "owned_containers_absent",
        "exact_secret_matches",
        "structural_privacy_findings",
        "remote_secret_removed",
        "firewall_restored",
        "rulesets_restored",
        "started_wall_time",
        "completed_wall_time",
        "started_monotonic",
        "completed_monotonic",
        "receipt_sha256",
    }
    extension = CrossHostCleanupExecutionReceipt(
        **asdict(legacy), remote_reconciliation_sha256="2" * 64
    )
    assert set(asdict(extension)) - set(asdict(legacy)) == {
        "cleanup_protocol",
        "remote_reconciliation_sha256",
    }
    assert extension.cleanup_protocol == remote.PROTOCOL


def test_actual_helper_deadline_expires_with_bounded_process_teardown(tmp_path):
    _, authority, inventory, _, error = run_remote(tmp_path, [["stall", "2"]], seconds=0.5)
    assert error is not None
    assert authority.disposition == remote.Disposition.UNRESOLVED
    assert inventory == {}
    evidence = json.loads((tmp_path / "remote-cleanup-evidence.json").read_text())
    assert evidence["process_closed_at"] <= authority.binding.deadline + 1
    assert evidence["process_exit"] is not None
    assert evidence["descriptors_closed"]


def test_omitted_baseline_with_consistent_forged_snapshot_totals_is_rejected(observed):
    _, authority, channel, observer, _ = observed
    channel.exchange("snapshot-start", kind="after", root=asdict(observer.root))
    with pytest.raises(RuntimeError):
        channel.exchange(
            "snapshot-end",
            kind="after",
            count=0,
            bytes=0,
            digest=remote.digest({}),
            complete=True,
        )
    assert authority.disposition == remote.Disposition.UNRESOLVED


@pytest.mark.parametrize("field,value", [("launch_ordinal", True), ("attempt", 1.0)])
def test_binding_numeric_aliases_cannot_bypass_canonical_identity(tmp_path, field, value):
    bound = binding(tmp_path)
    calls = []
    authority = remote.RemoteCleanupAuthority(bound, reserve=calls.append, observe=calls.append)
    document = bound.document()
    document[field] = value
    with pytest.raises(RuntimeError, match="binding/sequence"):
        authority.accept({"binding": document, "sequence": 1, "operation": "hello", "payload": {}})
    assert not calls and not authority.leases
    assert authority.disposition == remote.Disposition.UNRESOLVED


@pytest.mark.parametrize("sequence", [True, 1.0])
def test_response_sequence_requires_exact_integer_type(tmp_path, monkeypatch, sequence):
    bound = binding(tmp_path)
    parent, child = socket.socketpair()
    try:
        channel = remote.RemoteCleanupChannel(parent.fileno(), bound, bound.deadline)
        # Explicit transport fault, with no filesystem effect or invented grant.
        monkeypatch.setattr(channel, "send", lambda frame: None)
        monkeypatch.setattr(
            channel,
            "receive",
            lambda: {
                "binding": remote.digest(bound.document()),
                "sequence": sequence,
                "accepted": True,
                "result": {},
                "remaining_seconds": 1.0,
            },
        )
        with pytest.raises(RuntimeError, match="protocol mismatch"):
            channel.exchange("hello")
    finally:
        parent.close()
        child.close()
