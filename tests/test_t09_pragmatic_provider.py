from __future__ import annotations

import inspect
import json
import subprocess
from pathlib import Path

import pytest

from giclab.harness import t09_pragmatic_provider as provider
from giclab.harness.t09_cleanup_state import EarlyCleanupJournal
from giclab.harness.t09_provider_contracts import (
    PROVIDER_CONTRACTS,
    V3_PROVIDER_CONTRACT,
    V4_PROVIDER_CONTRACT,
    V5_PROVIDER_CONTRACT,
    V6_PROVIDER_CONTRACT,
    V7_PROVIDER_CONTRACT,
    V8_PROVIDER_CONTRACT,
    V9_PROVIDER_CONTRACT,
    V10_PROVIDER_CONTRACT,
    V11_PROVIDER_CONTRACT,
    V13_PROVIDER_CONTRACT,
    V14_PROVIDER_CONTRACT,
    V15_PROVIDER_CONTRACT,
    T09ProviderContract,
    T09ProviderContractError,
    load_provider_plan,
    load_provider_profile,
    provider_contract,
    provider_contract_for_plan_id,
    render_provider_entry_command,
)

ROOT = Path(__file__).resolve().parents[1]


def _entry_command(version: str, *, launch_slot: int = 1) -> tuple[str, ...]:
    return render_provider_entry_command(
        provider_contract(version),
        interpreter="/public/python3.11",
        repository="/public/gic-lab",
        package_commit="a" * 40,
        authorization_ledger="/private/authorization.json",
        dotenv="/private/provider.env",
        private_root=f"/private/{version.lower()}-attempt",
        public_ipv4_file="/private/public-ipv4.txt",
        ssh_public_key_file="/private/id_ed25519.pub",
        launch_slot=launch_slot,
        model_metadata_receipt=(
            "/private/model-metadata-receipt.json"
            if version in {"V12", "V13", "V14", "V15"}
            else None
        ),
    )


def test_every_retained_provider_version_has_one_frozen_contract() -> None:
    assert tuple(PROVIDER_CONTRACTS) == (
        "V3",
        "V4",
        "V5",
        "V6",
        "V7",
        "V8",
        "V9",
        "V10",
        "V11",
        "V12",
        "V13",
        "V14",
        "V15",
    )
    assert len({contract.plan_id for contract in PROVIDER_CONTRACTS.values()}) == 13
    assert len({contract.host_run_id for contract in PROVIDER_CONTRACTS.values()}) == 13
    assert len({contract.instance_name for contract in PROVIDER_CONTRACTS.values()}) == 13


def test_v13_contract_exposes_the_fresh_explicit_pilot_identity_bundle() -> None:
    assert V13_PROVIDER_CONTRACT.plan_id == "PLAN-EXP0001-PILOT-V13"
    assert V13_PROVIDER_CONTRACT.host_run_id == "RUN-T09-PILOT-HOST-AUTONOMOUS-0006"
    assert V13_PROVIDER_CONTRACT.attempt_order == (
        "RUN-T09-TASK-A-REACTIVE-AUTONOMOUS-0006",
        "RUN-T09-TASK-A-SIMULATIVE-AUTONOMOUS-0006",
        "RUN-T09-TASK-B-SIMULATIVE-AUTONOMOUS-0006",
        "RUN-T09-TASK-B-REACTIVE-AUTONOMOUS-0006",
    )
    assert V13_PROVIDER_CONTRACT.evaluator_run_ids == tuple(
        run_id.replace("RUN-T09-TASK-", "RUN-T09-EVAL-TASK-", 1)
        for run_id in V13_PROVIDER_CONTRACT.attempt_order
    )
    assert V13_PROVIDER_CONTRACT.active_image_qualification_id == (
        "QUAL-T09-PILOT-V13-IMAGE-AUTONOMOUS-0006"
    )
    assert V13_PROVIDER_CONTRACT.local_finalizer_qualification_id == (
        "QUAL-T09-PILOT-V13-LOCAL-FINALIZER-AUTONOMOUS-0006"
    )
    assert V13_PROVIDER_CONTRACT.frozen_run_manifest_id == (
        "RUN-MANIFEST-EXP0001-PILOT-V13-AUTONOMOUS-0006"
    )


def test_v14_contract_exposes_a_fresh_nonreplayable_identity_bundle() -> None:
    assert V14_PROVIDER_CONTRACT.plan_id == "PLAN-EXP0001-PILOT-V14"
    assert V14_PROVIDER_CONTRACT.host_run_id == "RUN-T09-PILOT-HOST-AUTONOMOUS-0007"
    assert V14_PROVIDER_CONTRACT.authorization_prefix == "AUTH-T09-V14-"
    assert V14_PROVIDER_CONTRACT.attempt_order == (
        "RUN-T09-TASK-A-REACTIVE-AUTONOMOUS-0007",
        "RUN-T09-TASK-A-SIMULATIVE-AUTONOMOUS-0007",
        "RUN-T09-TASK-B-SIMULATIVE-AUTONOMOUS-0007",
        "RUN-T09-TASK-B-REACTIVE-AUTONOMOUS-0007",
    )
    assert V14_PROVIDER_CONTRACT.evaluator_run_ids == tuple(
        run_id.replace("RUN-T09-TASK-", "RUN-T09-EVAL-TASK-", 1)
        for run_id in V14_PROVIDER_CONTRACT.attempt_order
    )
    assert V14_PROVIDER_CONTRACT.active_image_qualification_id == (
        "QUAL-T09-PILOT-V14-IMAGE-AUTONOMOUS-0007"
    )
    assert V14_PROVIDER_CONTRACT.local_finalizer_qualification_id == (
        "QUAL-T09-PILOT-V14-LOCAL-FINALIZER-AUTONOMOUS-0007"
    )
    assert V14_PROVIDER_CONTRACT.frozen_run_manifest_id == (
        "RUN-MANIFEST-EXP0001-PILOT-V14-AUTONOMOUS-0007"
    )
    assert set(V14_PROVIDER_CONTRACT.attempt_order).isdisjoint(V13_PROVIDER_CONTRACT.attempt_order)


def test_v15_contract_exposes_a_fresh_nonreplayable_identity_bundle() -> None:
    assert V15_PROVIDER_CONTRACT.plan_id == "PLAN-EXP0001-PILOT-V15"
    assert V15_PROVIDER_CONTRACT.host_run_id == "RUN-T09-PILOT-HOST-AUTONOMOUS-0008"
    assert V15_PROVIDER_CONTRACT.authorization_prefix == "AUTH-T09-V15-"
    assert V15_PROVIDER_CONTRACT.attempt_order == (
        "RUN-T09-TASK-A-REACTIVE-AUTONOMOUS-0008",
        "RUN-T09-TASK-A-SIMULATIVE-AUTONOMOUS-0008",
        "RUN-T09-TASK-B-SIMULATIVE-AUTONOMOUS-0008",
        "RUN-T09-TASK-B-REACTIVE-AUTONOMOUS-0008",
    )
    assert V15_PROVIDER_CONTRACT.evaluator_run_ids == tuple(
        run_id.replace("RUN-T09-TASK-", "RUN-T09-EVAL-TASK-", 1)
        for run_id in V15_PROVIDER_CONTRACT.attempt_order
    )
    assert V15_PROVIDER_CONTRACT.active_image_qualification_id == (
        "QUAL-T09-PILOT-V15-IMAGE-AUTONOMOUS-0008"
    )
    assert V15_PROVIDER_CONTRACT.local_finalizer_qualification_id == (
        "QUAL-T09-PILOT-V15-LOCAL-FINALIZER-AUTONOMOUS-0008"
    )
    assert V15_PROVIDER_CONTRACT.frozen_run_manifest_id == (
        "RUN-MANIFEST-EXP0001-PILOT-V15-AUTONOMOUS-0008"
    )
    assert set(V15_PROVIDER_CONTRACT.attempt_order).isdisjoint(V14_PROVIDER_CONTRACT.attempt_order)


@pytest.mark.parametrize("contract", tuple(PROVIDER_CONTRACTS.values()))
def test_versioned_provider_plan_and_profile_bytes_are_exact(
    contract: T09ProviderContract,
) -> None:
    selected = provider_contract(contract.version)
    assert load_provider_plan(ROOT, selected)["plan_id"] == selected.plan_id
    assert load_provider_profile(ROOT, selected)["plan_id"] == selected.provider_profile_id


def test_v3_entry_command_uses_harness_cli_and_authority() -> None:
    command = _entry_command("V3")
    assert command[:5] == (
        "/public/python3.11",
        "-m",
        "giclab.harness.t09_pragmatic_provider",
        "--provider-contract",
        "V3",
    )
    V3_PROVIDER_CONTRACT.validate_authority(
        "AUTH-T09-PRAGMATIC-PILOT-2026-08-13",
        "1f8285ea3fc52f4084a945f1712870203463cb7fb92cc61ac2eeae47d119e4c7",
    )


def test_v3_plan_defines_remote_image_and_provider_qualification_caps() -> None:
    lifecycle = provider.load_campaign_lifecycle(ROOT, contract=V3_PROVIDER_CONTRACT)
    assert lifecycle.contract is V3_PROVIDER_CONTRACT
    assert lifecycle.wall_seconds == 14_400
    assert lifecycle.cleanup_reserve_seconds == 900
    assert lifecycle.termination_cutoff_seconds == 13_500
    assert lifecycle.max_instances == 1
    assert lifecycle.max_launches == 1


def test_v4_cleanup_targets_exact_bound_instance_and_security() -> None:
    V4_PROVIDER_CONTRACT.validate_owner(
        plan_id="PLAN-EXP0001-PILOT-V4",
        host_run_id="RUN-T09-PILOT-HOST-0002",
        instance_name="giclab-t09-pilot-v4-0002",
    )


def test_v5_entry_plan_allows_fresh_archive_path() -> None:
    command = _entry_command("V5", launch_slot=2)
    assert command[command.index("--private-root") + 1] == "/private/v5-attempt"
    assert command[-2:] == ("--launch-slot", "2")


def test_slot2_image_import_command_enforces_hold_boundary() -> None:
    assert V5_PROVIDER_CONTRACT.max_launch_count == 2
    with pytest.raises(T09ProviderContractError, match="launch slot"):
        _entry_command("V5", launch_slot=3)


def test_slot2_entry_command_uses_fresh_image_qualification_identity() -> None:
    V5_PROVIDER_CONTRACT.validate_image_qualification(
        plan_id=V5_PROVIDER_CONTRACT.plan_id,
        host_run_id=V5_PROVIDER_CONTRACT.host_run_id,
        qualification_id="QUAL-T09-PILOT-V5-IMAGE-0002",
    )


def test_slot2_image_spec_uses_v5_profile_path() -> None:
    assert V5_PROVIDER_CONTRACT.provider_profile_path.endswith("PLAN-EXP0001-PILOT-V5.yaml")
    assert "V10" not in V5_PROVIDER_CONTRACT.provider_profile_path


def test_v5_preflight_entry_plan_values_have_fresh_identities() -> None:
    assert V5_PROVIDER_CONTRACT.plan_id == "PLAN-EXP0001-PILOT-V5"
    assert V5_PROVIDER_CONTRACT.host_run_id == "RUN-T09-PILOT-HOST-0003"
    assert V5_PROVIDER_CONTRACT.instance_name == "giclab-t09-pilot-v5-0003"


def test_v5_image_identity_plan_values_have_fresh_identities() -> None:
    assert V5_PROVIDER_CONTRACT.image_qualification_ids == (
        "QUAL-T09-PILOT-V5-IMAGE-0001",
        "QUAL-T09-PILOT-V5-IMAGE-0002",
    )


def test_v6_entry_command_uses_harness_cli_and_authority() -> None:
    assert _entry_command("V6")[4] == "V6"
    V6_PROVIDER_CONTRACT.validate_authority(
        "AUTH-T09-PRAGMATIC-RETRY4-2026-08-14",
        "e3222d38c9b21091a51839122d42594d691577716bc87fd3e09296c6b766df51",
    )


def test_retained_autonomous_contracts_remain_distinct() -> None:
    assert (
        V7_PROVIDER_CONTRACT.host_run_id,
        V8_PROVIDER_CONTRACT.host_run_id,
        V9_PROVIDER_CONTRACT.host_run_id,
        V10_PROVIDER_CONTRACT.host_run_id,
        V11_PROVIDER_CONTRACT.host_run_id,
    ) == (
        "RUN-T09-PILOT-HOST-0005",
        "RUN-T09-PILOT-HOST-AUTONOMOUS-0001",
        "RUN-T09-PILOT-HOST-AUTONOMOUS-0002",
        "RUN-T09-PILOT-HOST-AUTONOMOUS-0003",
        "RUN-T09-PILOT-HOST-AUTONOMOUS-0004",
    )
    assert V8_PROVIDER_CONTRACT.frozen_run_manifest_id != (
        V10_PROVIDER_CONTRACT.frozen_run_manifest_id
    )
    assert V8_PROVIDER_CONTRACT.local_finalizer_qualification_id != (
        V10_PROVIDER_CONTRACT.local_finalizer_qualification_id
    )
    assert V10_PROVIDER_CONTRACT.frozen_run_manifest_id != (
        V11_PROVIDER_CONTRACT.frozen_run_manifest_id
    )


def test_historical_budget_contracts_do_not_inherit_v10_caps() -> None:
    assert V5_PROVIDER_CONTRACT.preflight_lambda_cost_cap_usd == 5.16
    assert V5_PROVIDER_CONTRACT.campaign_lambda_cost_cap_usd == 5.16
    assert V5_PROVIDER_CONTRACT.campaign_aggregate_cost_cap_usd == 45.16
    assert V6_PROVIDER_CONTRACT.preflight_lambda_cost_cap_usd == 8.0
    assert V8_PROVIDER_CONTRACT.preflight_lambda_cost_cap_usd == 20.0
    assert V10_PROVIDER_CONTRACT.preflight_lambda_cost_cap_usd == 10.0
    assert V11_PROVIDER_CONTRACT.preflight_lambda_cost_cap_usd == 10.0
    assert V11_PROVIDER_CONTRACT.prior_t09_cost_usd == 33.14878958732642


def test_v3_renderer_cannot_emit_v10_identity() -> None:
    command = _entry_command("V3")
    rendered = "\0".join(command)
    assert V3_PROVIDER_CONTRACT.plan_id not in rendered  # authority is selected, not duplicated
    assert V10_PROVIDER_CONTRACT.plan_id not in rendered
    assert V10_PROVIDER_CONTRACT.host_run_id not in rendered
    assert V10_PROVIDER_CONTRACT.instance_name not in rendered


def test_v10_renderer_rejects_v5_authority() -> None:
    with pytest.raises(T09ProviderContractError, match="another version"):
        V10_PROVIDER_CONTRACT.validate_authority(
            V5_PROVIDER_CONTRACT.authorization_id or "",
            V5_PROVIDER_CONTRACT.authorization_source_sha256 or "",
        )


def test_cleanup_rejects_cross_version_ownership() -> None:
    with pytest.raises(T09ProviderContractError, match="crosses versions"):
        V4_PROVIDER_CONTRACT.validate_owner(
            plan_id=V10_PROVIDER_CONTRACT.plan_id,
            host_run_id=V10_PROVIDER_CONTRACT.host_run_id,
            instance_name=V10_PROVIDER_CONTRACT.instance_name,
        )


def test_historical_cleanup_authority_is_version_bound_and_launch_inert(
    tmp_path: Path,
) -> None:
    package_commit = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    authority = tmp_path / "v5-cleanup-authority.json"
    authority.write_text(
        json.dumps(
            {
                "authorization_reference": V5_PROVIDER_CONTRACT.authorization_id,
                "authorization_source_sha256": (V5_PROVIDER_CONTRACT.authorization_source_sha256),
                "authorized": True,
                "single_use": True,
                "clean_package_commit": package_commit,
                "plan_id": V5_PROVIDER_CONTRACT.plan_id,
                "plan_sha256": provider.file_sha256(
                    ROOT / V5_PROVIDER_CONTRACT.provider_profile_path
                ),
                "max_lambda_instances": 1,
                "persistent_filesystems": 0,
            }
        ),
        encoding="utf-8",
    )
    authority.chmod(0o600)
    retained = provider.validate_cleanup_authority_ledger(
        authority,
        contract=V5_PROVIDER_CONTRACT,
        repository=ROOT,
        package_commit=package_commit,
    )
    assert retained["plan_id"] == V5_PROVIDER_CONTRACT.plan_id
    with pytest.raises(provider.T09ProviderError, match="crosses versions"):
        provider.validate_cleanup_authority_ledger(
            authority,
            contract=V4_PROVIDER_CONTRACT,
            repository=ROOT,
            package_commit=package_commit,
        )
    with pytest.raises(provider.T09ProviderError, match="cannot be replayed"):
        provider.validate_authorization_ledger(
            authority,
            contract=V5_PROVIDER_CONTRACT,
            repository=ROOT,
            package_commit=package_commit,
        )


def test_image_qualification_rejects_stale_contract() -> None:
    with pytest.raises(T09ProviderContractError, match="another version"):
        V10_PROVIDER_CONTRACT.validate_image_qualification(
            plan_id=V10_PROVIDER_CONTRACT.plan_id,
            host_run_id=V10_PROVIDER_CONTRACT.host_run_id,
            qualification_id="QUAL-T09-PILOT-V5-IMAGE-0002",
        )


def test_condition_run_rejects_cross_version_contract() -> None:
    with pytest.raises(T09ProviderContractError, match="another version"):
        V8_PROVIDER_CONTRACT.validate_run_id(V10_PROVIDER_CONTRACT.run_ids[0])
    V8_PROVIDER_CONTRACT.validate_run_id(V8_PROVIDER_CONTRACT.run_ids[0])


def test_no_implicit_latest_provider_contract_fallback_exists() -> None:
    assert (
        inspect.signature(provider_contract).parameters["version"].default
        is inspect.Parameter.empty
    )
    assert (
        inspect.signature(render_provider_entry_command).parameters["contract"].default
        is inspect.Parameter.empty
    )
    assert (
        inspect.signature(provider.launch_campaign).parameters["contract"].default
        is inspect.Parameter.empty
    )
    assert (
        inspect.signature(provider.closeout_campaign).parameters["contract"].default
        is inspect.Parameter.empty
    )
    with pytest.raises(T09ProviderContractError, match="unsupported"):
        provider_contract("latest")
    with pytest.raises(T09ProviderContractError, match="unsupported"):
        provider_contract_for_plan_id("PLAN-EXP0001-PILOT-LATEST")


def test_v10_cannot_dispatch_historical_replacement_eligibility() -> None:
    unavailable = ROOT / "public-dummy-file-that-does-not-exist"
    with pytest.raises(provider.T09ProviderError, match="unsupported for the selected"):
        provider.derive_built_image_replacement_eligibility(
            contract=V10_PROVIDER_CONTRACT,
            repository=ROOT,
            package_commit="a" * 40,
            prior_private_root=unavailable,
            slot1_failure_archive=unavailable,
            slot1_image_archive=unavailable,
        )


def test_v10_replacement_launch_rejects_v5_receipt_before_capability_lookup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prior = tmp_path / "prior"
    prior.mkdir(mode=0o700)
    eligibility = prior / "replacement-launch-eligibility.json"
    eligibility.write_text(
        json.dumps(
            {
                "closed_launch_slot": 1,
                "eligibility_kind": provider.SLOT2_ELIGIBILITY_KIND,
            }
        ),
        encoding="utf-8",
    )
    eligibility.chmod(0o600)
    image = tmp_path / "public-dummy-image.tar"
    image.write_bytes(b"public-dummy-image")
    image.chmod(0o600)
    monkeypatch.setattr(provider, "_safe_regular_identity", lambda *_args, **_kwargs: None)

    with pytest.raises(provider.T09ProviderError, match="another provider contract"):
        provider._validate_replacement_launch_eligibility(
            prior,
            contract=V10_PROVIDER_CONTRACT,
            repository=ROOT,
            package_commit="a" * 40,
            slot1_image_archive=image,
        )


def test_initial_cleanup_launch_slot_is_bounded_by_selected_contract(tmp_path: Path) -> None:
    cleanup_root = tmp_path / "cleanup"
    instance_id = "public-dummy-instance"
    plan_sha256 = "a" * 64
    EarlyCleanupJournal.initialize(
        cleanup_root,
        plan_id=V3_PROVIDER_CONTRACT.plan_id,
        host_run_id=V3_PROVIDER_CONTRACT.host_run_id,
        package_commit="b" * 40,
        plan_sha256=plan_sha256,
        provider_instance_id=instance_id,
        provider_instance_identity_sha256=provider._instance_identity_sha256(instance_id),
        provider_started_at_epoch=1.0,
        launch_slot=2,
        replacement_eligibility_sha256=None,
        firewall_baseline_identity_sha256="c" * 64,
    )
    with pytest.raises(provider.T09ProviderError, match="cleanup identity drifted"):
        provider._validate_initial_preflight_cleanup_state(
            cleanup_root,
            contract=V3_PROVIDER_CONTRACT,
            package_commit="b" * 40,
            plan_sha256=plan_sha256,
        )


@pytest.mark.parametrize("contract", (V3_PROVIDER_CONTRACT, V4_PROVIDER_CONTRACT))
def test_single_launch_contracts_cannot_emit_provisional_replacement_authority(
    contract: T09ProviderContract,
) -> None:
    assert (
        provider._provisional_replacement_permitted(
            contract,
            launch_slot=1,
        )
        is False
    )


def test_provisional_replacement_authority_tracks_the_selected_launch_cap() -> None:
    assert provider._provisional_replacement_permitted(
        V5_PROVIDER_CONTRACT,
        launch_slot=1,
    )
    assert not provider._provisional_replacement_permitted(
        V5_PROVIDER_CONTRACT,
        launch_slot=2,
    )
    with pytest.raises(provider.T09ProviderError, match="escaped"):
        provider._provisional_replacement_permitted(
            V3_PROVIDER_CONTRACT,
            launch_slot=2,
        )
