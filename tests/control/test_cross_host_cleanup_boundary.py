"""Characterize the retained cleanup boundary; these preserve the historical local contract.

Use the actual production accountant and publication verifier. A temporary sibling
stands for a different host namespace; no provider or empirical runtime is used.
"""

from dataclasses import replace
from pathlib import Path

import pytest

from giclab.control.adapters import AdapterFailure
from giclab.harness.campaign_output import (
    CampaignWriterRole,
    CleanupOutputAuthority,
    admit_campaign_write,
    verify_campaign_write,
)
from tests.control.test_remote_transaction_review import (
    _campaign_writer_world,
    _cleanup_output_binding,
)


def test_retained_cleanup_rejects_provider_namespace_before_admission(tmp_path):
    world, _ = _campaign_writer_world(tmp_path)
    remote = Path(world.contract.remote_root) / "phases/cleanup-terminal.json"
    assert not remote.is_relative_to(tmp_path)
    with world._campaign_writer_scope(cleanup=True):
        authority = CleanupOutputAuthority(
            _cleanup_output_binding(tmp_path), deadline=10, monotonic=lambda: 5
        )
        authority.claim(authority.binding.document())
        remaining = world._campaign_cleanup_remaining
        with pytest.raises(RuntimeError, match="escaped its bound root"):
            authority.admit(remote, 1, CampaignWriterRole.CLEANUP_RECEIPT)
        assert authority.leases == []
        assert world._campaign_cleanup_remaining == remaining
        authority.close()


def test_retained_cleanup_binding_cannot_add_provider_namespace(tmp_path):
    world, _ = _campaign_writer_world(tmp_path)
    binding = replace(_cleanup_output_binding(tmp_path), output_roots=(world.contract.remote_root,))
    with pytest.raises(RuntimeError, match="escaped the owned transaction"):
        binding.validate()


def test_direct_parent_admission_also_rejects_provider_namespace(tmp_path):
    world, _ = _campaign_writer_world(tmp_path)
    remote = Path(world.contract.remote_root) / "phases/cleanup-terminal.json"
    with world._campaign_writer_scope(cleanup=True):
        remaining = world._campaign_cleanup_remaining
        with pytest.raises(AdapterFailure, match="outside its exact owned scope"):
            admit_campaign_write(remote, 1, CampaignWriterRole.CLEANUP_RECEIPT)
        assert world._campaign_writes == []
        assert world._campaign_cleanup_remaining == remaining


def test_shared_verifier_requires_actual_local_publication_not_remote_byte_report(tmp_path):
    local = tmp_path / "controller"
    remote = tmp_path / "provider-namespace"
    local.mkdir()
    remote.mkdir()
    world, _ = _campaign_writer_world(local)
    target = local / "cleanup-terminal.json"
    remote_target = remote / target.name
    with world._campaign_writer_scope(cleanup=True):
        authority = CleanupOutputAuthority(
            _cleanup_output_binding(local), deadline=10, monotonic=lambda: 5
        )
        authority.claim(authority.binding.document())
        lease = authority.admit(target, 1, CampaignWriterRole.CLEANUP_RECEIPT)
        remote_target.write_bytes(b"x")
        lease.observe(1)
        with pytest.raises(RuntimeError, match="occupancy does not reconcile"):
            verify_campaign_write(lease, target)
        assert lease.final_identity is None
        # Positive control: the existing verifier observes the controller inode.
        # This is a separate publication, not evidence about the provider inode.
        target.write_bytes(b"x")
        verify_campaign_write(lease, target)
        assert lease.final_identity.inode == target.stat().st_ino
        assert lease.final_identity.inode != remote_target.stat().st_ino
        assert world._campaign_accountant().campaign_output_observed == 1
        authority.close()
