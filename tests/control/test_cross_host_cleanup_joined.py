"""Production cleanup from an accepted-transfer fixture boundary, offline only.

Provider entry/transfer and restoration are explicit low-level fixture state.
Grants, writes, inode verification, census and joined cleanup decisions are real.
Historical end-to-end local-carrier parameters remain separate evidence.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections import Counter
from dataclasses import asdict, replace
from types import SimpleNamespace

import pytest

from giclab.control.adapters import AdapterFailure, CleanupInterrupted
from giclab.control.effects import (
    CrossHostCleanupExecutionReceipt,
    CrossHostCleanupExecutionRequest,
    EffectExecutionMode,
    HostPackageTransferReceipt,
    HostTransferBinding,
    ProviderHandle,
    hold_transaction_root,
)
from giclab.harness.campaign_output import (
    CampaignWriterRole,
    admit_campaign_write,
    prepare_campaign_temporary,
    replace_campaign_write,
    verify_campaign_write,
)
from giclab.harness.remote_cleanup import Disposition, RemoteRoot
from giclab.harness.sira_gate_a import ProviderBudgetExceeded
from giclab.harness.t09_candidate_inputs import project_candidate_package
from tests.control.test_candidate_inputs import candidate as candidate
from tests.control.test_remote_cleanup import drive_authority
from tests.control.test_remote_transaction_review import _campaign_writer_world


@pytest.fixture
def joined(candidate, tmp_path):
    snapshot, _ = candidate
    package = tmp_path / "package"
    project_candidate_package(snapshot, package)
    local, provider = tmp_path / "controller", tmp_path / "provider-fixture"
    local.mkdir(mode=0o700)
    provider.mkdir(mode=0o700)
    world, _ = _campaign_writer_world(local)
    world.repository = package
    world.source_inputs = snapshot
    world.clock = SimpleNamespace(wall_time=time.time, monotonic=time.monotonic)
    held = hold_transaction_root(local)
    world.held_transaction_root = held
    world.authorization_context = SimpleNamespace(
        execution_mode=EffectExecutionMode.DETERMINISTIC_NO_NETWORK,
        transaction_root_identity=held.semantic_sha256,
        external_authorization_reference=None,
        external_authorization_source_sha256=None,
    )
    world.authority = None
    world._offline_provider_namespaces = {1: RemoteRoot(str(provider))}
    world._remote_cleanup_sessions = {}
    world._remote_cleanup_local_results = {}
    world._counts = Counter()
    world._calls = []
    world._primitive_calls = []
    world._undeclared_calls = []
    world._root_identity_mismatch = False
    world._execution_contract = None
    world._cleanup_calls = 0
    world._cleanup_original_deadline = None
    world._cleanup_handoff_bytes = None
    world._cleanup_receipt = None
    world._campaign_deadline_monotonic = time.monotonic() + 60
    world._dotenv = local / "absent-fixture-secret"
    commit, tree = world._source_identity()
    handle = ProviderHandle("offline-provider", 1)
    payload = b"accepted offline transfer fixture"
    (provider / "baseline").write_bytes(payload)
    sha = hashlib.sha256(payload).hexdigest()
    transfer_binding = HostTransferBinding(
        world.contract.version,
        world.contract.plan_id,
        world.contract.host_run_id,
        handle.opaque_identity,
        1,
        sha,
        sha,
        commit,
        tree,
        str(provider),
        snapshot.digest,
    )
    transfer = HostPackageTransferReceipt(
        transfer_binding,
        str(provider / "baseline"),
        str(provider / "baseline"),
        len(payload),
        sha,
        (),
        sha,
        sha,
        1,
        1,
        1,
        1,
        sha,
        (sha,) * 4,
        "",
    )
    world._host_transfers = {
        1: replace(transfer, receipt_sha256=world._transfer_receipt_identity(transfer))
    }
    controls = world.low_level_effects.campaign_low_level_controls()
    state = {
        "actions": [["create", "remote-receipt", "{}"]],
        "interrupt": False,
        "wrong_receipt": False,
        "unadmitted_local": False,
        "observed": None,
        "calls": 0,
        "ack_loss": False,
        "local_next": None,
        "interrupt_local": None,
    }

    def cleanup(request):
        assert isinstance(request, CrossHostCleanupExecutionRequest)
        state["calls"] += 1
        if state["interrupt"] and state["calls"] == 1:
            if state["interrupt_local"] is not None:
                interrupted_file = local / "before-resume"
                if state["interrupt_local"] == "admitted-partial":
                    lease = admit_campaign_write(
                        interrupted_file, 3, CampaignWriterRole.CLEANUP_RECEIPT
                    )
                    interrupted_file.write_bytes(b"x")
                    lease.observe(1)
                else:
                    interrupted_file.write_bytes(b"unadmitted")
            raise CleanupInterrupted("before remote handshake fixture interruption")
        authority = request.remote_output_authority
        if authority.disposition != Disposition.RECONCILED:
            inventory, error = drive_authority(
                authority, state["actions"], drop_terminal_ack=state["ack_loss"]
            )
            state["observed"] = inventory
            if error is not None:
                raise error
        local_file = local / "local-receipt"
        if not local_file.exists():
            lease = admit_campaign_write(local_file, 2, CampaignWriterRole.CLEANUP_RECEIPT)
            local_file.write_bytes(b"{}")
            lease.observe(2)
            verify_campaign_write(lease, local_file)
        if state["local_next"] is not None:
            operation = state["local_next"]
            role = (
                CampaignWriterRole.PROVIDER_JOURNAL
                if operation == "append"
                else CampaignWriterRole.CLEANUP_RECEIPT
            )
            lease = admit_campaign_write(local_file, 3, role)
            if operation == "append":
                with local_file.open("ab") as stream:
                    assert stream.write(b"abc") == 3
            else:
                temporary = local / "local-staging"
                prepare_campaign_temporary(lease, temporary)
                temporary.write_bytes(b"abc")
            lease.observe(3)
            if operation == "replace":
                replace_campaign_write(lease, temporary, local_file)
            verify_campaign_write(lease, local_file)
        if state["unadmitted_local"]:
            (local / "unadmitted").write_bytes(b"x")
        receipt = CrossHostCleanupExecutionReceipt(
            immutable_handoff_sha256=request.immutable_handoff_sha256,
            owned_containers_absent=True,  # No container exists in this offline provider fixture.
            exact_secret_matches=0,
            structural_privacy_findings=(),
            remote_secret_removed=not (provider / "secret").exists(),
            firewall_restored=not (provider / "firewall-change").exists(),
            rulesets_restored=not (provider / "ruleset-change").exists(),
            started_wall_time=request.started_wall_time,
            completed_wall_time=time.time(),
            started_monotonic=request.started_monotonic,
            completed_monotonic=time.monotonic(),
            remote_reconciliation_sha256=authority.require_reconciled(),
            receipt_sha256="",
        )
        if state["wrong_receipt"]:
            receipt = replace(receipt, remote_reconciliation_sha256="0" * 64)
        return replace(receipt, receipt_sha256=world._cleanup_receipt_identity(receipt))

    world.low_level_effects = SimpleNamespace(
        transaction_root=lambda: local,
        campaign_low_level_controls=lambda: controls,
        cleanup_transaction=cleanup,
    )
    try:
        yield world, handle, state, provider
    finally:
        (tmp_path / "joined-cleanup-evidence.json").write_text(
            json.dumps(
                {
                    "classification": "production-cleanup-from-accepted-transfer-offline-fixture",
                    "cleanup_calls": world._cleanup_calls,
                    "original_deadline": world._cleanup_original_deadline,
                    "receipt": asdict(world._cleanup_receipt)
                    if world._cleanup_receipt is not None
                    else None,
                    "local_reconciliation": world._remote_cleanup_local_results,
                    "remote_dispositions": {
                        str(k): v.disposition.value
                        for k, v in world._remote_cleanup_sessions.items()
                    },
                    "remaining_reserve": world._campaign_cleanup_remaining,
                    "accounting": world._campaign_accountant().accounting_document(),
                },
                sort_keys=True,
            )
            + "\n"
        )
        held.close()


def test_joined_controller_remote_and_local_publication_one_accountant(joined):
    world, handle, state, _ = joined
    world._campaign_accountant()
    before = world._campaign_cleanup_remaining
    receipt = world.cleanup(handle)
    assert receipt == world._cleanup_receipt.receipt_sha256
    assert world._campaign_cleanup_remaining == before - 4
    assert world._campaign_accountant().campaign_output_observed == 4
    authority = world._remote_cleanup_sessions[1]
    assert authority.require_reconciled() == world._cleanup_receipt.remote_reconciliation_sha256
    assert state["observed"] == authority.expected
    assert world._remote_cleanup_local_results[1]["unreconciled_bytes"] == 0
    projection = json.dumps(world.remote_cleanup_control_evidence())
    assert authority.binding.root.value not in projection
    assert "inode" not in projection and "device" not in projection


@pytest.mark.parametrize(
    "fault",
    [
        "denial",
        "disconnect",
        "unadmitted-remote",
        "wrong-root",
        "wrong-receipt",
        "unadmitted-local",
        "missing-proof",
        "ack-loss",
        "partial-disconnect",
    ],
)
def test_joined_controller_negative_paths_preserve_unresolved_authority(joined, fault):
    world, handle, state, provider = joined
    world._campaign_accountant()
    if fault == "denial":
        world._campaign_cleanup_remaining = 1
    elif fault == "disconnect":
        state["actions"].append(["disconnect"])
    elif fault == "unadmitted-remote":
        state["actions"].append(["unadmitted", "rogue"])
    elif fault == "ack-loss":
        state["ack_loss"] = True
    elif fault == "partial-disconnect":
        state["actions"] = [["partial-disconnect", "partial", "abc", "create"]]
    elif fault == "wrong-receipt":
        state["wrong_receipt"] = True
    elif fault == "unadmitted-local":
        state["unadmitted_local"] = True
    elif fault == "wrong-root":
        world._offline_provider_namespaces[1] = RemoteRoot(str(provider / "other"))
    else:
        old = world.low_level_effects.cleanup_transaction

        def missing(request):
            receipt = old(request)
            from giclab.control.effects import CleanupExecutionReceipt

            values = asdict(receipt)
            del values["cleanup_protocol"], values["remote_reconciliation_sha256"]
            receipt = CleanupExecutionReceipt(**values)
            return replace(receipt, receipt_sha256=world._cleanup_receipt_identity(receipt))

        world.low_level_effects.cleanup_transaction = missing
    with pytest.raises(AdapterFailure):
        world.cleanup(handle)
    assert world._cleanup_receipt is None
    if fault == "wrong-root":
        assert state["calls"] == 0
    else:
        assert world._remote_cleanup_sessions[1].disposition == Disposition.UNRESOLVED
    if fault == "denial":
        assert world._campaign_admission_blocked
        assert not (provider / "remote-receipt").exists()


def test_joined_cleanup_resume_reuses_original_deadline_binding_and_reserve(joined):
    world, handle, state, _ = joined
    state["interrupt"] = True
    with pytest.raises(CleanupInterrupted):
        world.cleanup(handle)
    original = world._remote_cleanup_sessions[1]
    deadline = world._cleanup_original_deadline
    remaining = world._campaign_cleanup_remaining
    world.cleanup(handle)
    assert world._remote_cleanup_sessions[1] is original
    assert world._cleanup_original_deadline == deadline
    assert original.binding.attempt == 1
    assert world._campaign_cleanup_remaining == remaining - 4


@pytest.mark.parametrize("operation", ["append", "replace"])
def test_joined_repeated_local_publication_validates_causal_chain(joined, operation):
    world, handle, state, _ = joined
    state["local_next"] = operation
    world.cleanup(handle)
    result = world._remote_cleanup_local_results[1]
    assert result["actual_written_bytes"] == 5
    assert result["exact_replaced_old_bytes"] == (2 if operation == "replace" else 0)
    assert result["unreconciled_bytes"] == 0
    assert world._campaign_accountant().campaign_output_observed == 7


def test_joined_controller_census_enforces_original_deadline(joined, monkeypatch):
    from giclab.control import production

    world, handle, _, _ = joined
    inventory = production.cleanup_output_inventory
    calls = 0

    def expires(root, *, check_deadline=None):
        nonlocal calls
        calls += 1
        if calls == 2:
            world.clock.monotonic = lambda: world._cleanup_original_deadline + 1
        return inventory(root, check_deadline=check_deadline)

    monkeypatch.setattr(production, "cleanup_output_inventory", expires)
    with pytest.raises(AdapterFailure, match="deadline"):
        world.cleanup(handle)
    assert world._cleanup_receipt is None
    assert world._remote_cleanup_sessions[1].disposition == Disposition.UNRESOLVED


def test_joined_partial_disconnect_cannot_resume_or_refund(joined):
    world, handle, state, provider = joined
    state["actions"] = [["partial-disconnect", "partial", "abc", "create"]]
    with pytest.raises(AdapterFailure):
        world.cleanup(handle)
    session = world._remote_cleanup_sessions[1]
    calls = state["calls"]
    remaining = world._campaign_cleanup_remaining
    actual = (provider / "partial").read_bytes()
    assert actual == b"a"
    state["actions"] = [["create", "later", "never"]]
    with pytest.raises(AdapterFailure):
        world.cleanup(handle)
    assert world._remote_cleanup_sessions[1] is session
    assert state["calls"] == calls
    assert session.disposition == Disposition.UNRESOLVED
    assert world._campaign_cleanup_remaining == remaining
    assert (provider / "partial").read_bytes() == actual
    assert not (provider / "later").exists()
    assert world._campaign_admission_blocked
    with pytest.raises(ProviderBudgetExceeded), world._campaign_writer_scope():
        admit_campaign_write(world.root / "later-local", 1, CampaignWriterRole.PROVIDER_RECORD)
    assert not (world.root / "later-local").exists()
    for run_id in ("new-condition", "cached-condition"):
        if run_id == "cached-condition":
            # Cache state is an explicit fixture; no condition is executed.
            world._condition_observers[run_id] = SimpleNamespace(_failure_output_remaining=1)
        with pytest.raises(ProviderBudgetExceeded, match="unresolved remote cleanup"):
            world._condition_accountant(run_id)
    assert world._campaign_cleanup_remaining == remaining


def test_joined_remote_denial_blocks_subsequent_noncleanup_writer(joined):
    world, handle, _, _ = joined
    world._campaign_accountant()
    world._campaign_cleanup_remaining = 1
    with pytest.raises(AdapterFailure):
        world.cleanup(handle)
    with (
        pytest.raises(ProviderBudgetExceeded, match="already blocked"),
        world._campaign_writer_scope(),
    ):
        admit_campaign_write(world.root / "later", 1, CampaignWriterRole.PROVIDER_RECORD)
    assert not (world.root / "later").exists()
    with pytest.raises(ProviderBudgetExceeded, match="condition entry"):
        world._condition_accountant("later-condition")


@pytest.mark.parametrize("publication", ["admitted-partial", "unadmitted"])
def test_joined_local_activity_before_handshake_cannot_become_resume_baseline(joined, publication):
    world, handle, state, provider = joined
    state["interrupt"] = True
    state["interrupt_local"] = publication
    with pytest.raises(CleanupInterrupted):
        world.cleanup(handle)
    session = world._remote_cleanup_sessions[1]
    assert session.sequence == 0 and session.disposition == Disposition.UNRESOLVED
    remaining = world._campaign_cleanup_remaining
    local_bytes = (world.root / "before-resume").read_bytes()
    with pytest.raises(AdapterFailure, match="remains unresolved"):
        world.cleanup(handle)
    assert state["calls"] == 1
    assert world._campaign_cleanup_remaining == remaining
    assert (world.root / "before-resume").read_bytes() == local_bytes
    assert not (provider / "remote-receipt").exists()
    assert not (world.root / "local-receipt").exists()
    assert world._cleanup_receipt is None
    assert world._campaign_admission_blocked
