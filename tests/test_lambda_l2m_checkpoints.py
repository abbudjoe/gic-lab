from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from giclab.harness.lambda_l2m_checkpoints import (
    CHECKPOINT_TYPES,
    CheckpointBinding,
    CheckpointConsumptionOutcomeUnknown,
    CheckpointContractError,
    PrivateCheckpointReader,
    VerifiedCheckpoint,
    launch_checkpoint_proves_provider_launch,
    validate_human_decision,
)

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas/t07-lambda-l2m-checkpoint.schema.json"
DECISION_SCHEMA = ROOT / "schemas/t07-lambda-l2m-human-decision.schema.json"
TEMPLATE = ROOT / "containers/sira-smoke/lambda/manual-console/T07_L2M_HUMAN_DECISION_TEMPLATE.json"


def binding() -> CheckpointBinding:
    return CheckpointBinding(
        run_id="RUN-T07-L2M-HOST-QUALIFICATION-0001",
        decision_alias="l2m-decision-0123456789ab",
        marker_alias="l2m-marker-0123456789ab",
    )


def checkpoint(kind: str, observed: dt.datetime) -> dict[str, object]:
    details: dict[str, object] = {kind: True}
    if kind == "launch_wizard_image_offered":
        details.update(
            {
                "selected_instance_type": "gpu_1x_a10",
                "selected_region": "us-east-1",
                "selected_image_alias": "img-0032",
                "selected_image_version": "22.4.5-2141",
            }
        )
    elif kind == "launch_configuration_selected":
        details["launch_configuration_sha256"] = "5" * 64
    elif kind == "launch_clicked_once":
        details["launch_configuration_sha256"] = "5" * 64
        details["approved_image_offered_for_selected_type_region"] = True
    elif kind == "instance_bound":
        details["instance_binding_sha256"] = "2" * 64
    elif kind == "qualification_bundle_downloaded":
        details["qualification_archive_sha256"] = "3" * 64
    elif kind == "qualification_bundle_uploaded":
        details["qualification_bundle_manifest_sha256"] = (
            "dc9824649f97fab6cfd105b5fc0d0c6c1c5ff513fa25f70e0d517afa623cc261"
        )
    elif kind == "instance_terminal_verified":
        details["terminal_or_absent"] = True
        details["launch_identity_state"] = "exact_one_bound"
    elif kind == "regional_ruleset_deleted":
        details["regional_ruleset_absent"] = True
    elif kind == "global_firewall_restored":
        details["global_firewall_semantic_sha256"] = "4" * 64
    return {
        "schema_version": "0.1.0",
        "checkpoint_id": "CHECKPOINT-T07-L2M-FIXTURE-0001",
        "checkpoint_type": kind,
        "checkpoint_nonce": "1" * 64,
        "run_id": binding().run_id,
        "decision_alias": binding().decision_alias,
        "marker_alias": binding().marker_alias,
        "observed_at_utc": observed.isoformat().replace("+00:00", "Z"),
        "actor": "user",
        "action_confirmed": True,
        "details": details,
    }


def write_private(path: Path, document: dict[str, object]) -> None:
    path.write_text(json.dumps(document), encoding="utf-8")
    path.chmod(0o600)


def test_checkpoint_is_mode_bound_fresh_single_use_and_launch_is_not_provider_proof(
    tmp_path: Path,
) -> None:
    now = dt.datetime.now(dt.UTC)
    path = tmp_path / "checkpoint.json"
    write_private(path, checkpoint("launch_clicked_once", now))
    consumption = tmp_path / "consumption.jsonl"
    reader = PrivateCheckpointReader.from_schema_path(
        SCHEMA, binding=binding(), consumption_path=consumption
    )
    verified = reader.read_once(
        path,
        expected_type="launch_clicked_once",
        expected_nonce="1" * 64,
        not_before=now - dt.timedelta(seconds=1),
        not_after=now + dt.timedelta(seconds=1),
    )
    assert verified.launch_clicked_once
    assert verified.details == {
        "launch_clicked_once": True,
        "approved_image_offered_for_selected_type_region": True,
        "launch_configuration_sha256": "5" * 64,
    }
    assert launch_checkpoint_proves_provider_launch(verified) is False
    with pytest.raises(CheckpointContractError, match="already consumed"):
        reader.read_once(
            path,
            expected_type="launch_clicked_once",
            expected_nonce="1" * 64,
            not_before=now - dt.timedelta(seconds=1),
            not_after=now + dt.timedelta(seconds=1),
        )
    reader.close()
    restarted = PrivateCheckpointReader.from_schema_path(
        SCHEMA, binding=binding(), consumption_path=consumption
    )
    with pytest.raises(CheckpointContractError, match="already consumed"):
        restarted.read_once(
            path,
            expected_type="launch_clicked_once",
            expected_nonce="1" * 64,
            not_before=now - dt.timedelta(seconds=1),
            not_after=now + dt.timedelta(seconds=1),
        )
    restarted.close()


def test_checkpoint_rejects_mode_symlink_nonce_and_stale_time(tmp_path: Path) -> None:
    now = dt.datetime.now(dt.UTC)
    target = tmp_path / "target.json"
    write_private(target, checkpoint("global_firewall_restricted", now))
    target.chmod(0o644)
    reader = PrivateCheckpointReader.from_schema_path(
        SCHEMA,
        binding=binding(),
        consumption_path=tmp_path / "consumption.jsonl",
    )
    with pytest.raises(CheckpointContractError, match="mode"):
        reader.read_once(
            target,
            expected_type="global_firewall_restricted",
            expected_nonce="1" * 64,
            not_before=now - dt.timedelta(seconds=1),
            not_after=now + dt.timedelta(seconds=1),
        )
    target.chmod(0o600)
    link = tmp_path / "link.json"
    link.symlink_to(target)
    with pytest.raises(CheckpointContractError, match="unsafe"):
        reader.read_once(
            link,
            expected_type="global_firewall_restricted",
            expected_nonce="1" * 64,
            not_before=now - dt.timedelta(seconds=1),
            not_after=now + dt.timedelta(seconds=1),
        )
    with pytest.raises(CheckpointContractError, match="binding"):
        reader.read_once(
            target,
            expected_type="global_firewall_restricted",
            expected_nonce="2" * 64,
            not_before=now - dt.timedelta(seconds=1),
            not_after=now + dt.timedelta(seconds=1),
        )
    with pytest.raises(CheckpointContractError, match="time window"):
        reader.read_once(
            target,
            expected_type="global_firewall_restricted",
            expected_nonce="1" * 64,
            not_before=now + dt.timedelta(seconds=2),
            not_after=now + dt.timedelta(seconds=3),
        )
    with pytest.raises(CheckpointContractError, match="time window"):
        reader.read_once(
            target,
            expected_type="global_firewall_restricted",
            expected_nonce="1" * 64,
            not_before=now - dt.timedelta(seconds=301),
            not_after=now,
        )
    old = now - dt.timedelta(days=7)
    old_path = tmp_path / "expired-narrow-window.json"
    write_private(old_path, checkpoint("global_firewall_restricted", old))
    with pytest.raises(CheckpointContractError, match="time window"):
        reader.read_once(
            old_path,
            expected_type="global_firewall_restricted",
            expected_nonce="1" * 64,
            not_before=old - dt.timedelta(seconds=1),
            not_after=old + dt.timedelta(seconds=1),
        )
    reader.close()


def test_checkpoint_nonce_reuse_and_empty_action_details_fail_closed(tmp_path: Path) -> None:
    now = dt.datetime.now(dt.UTC)
    consumption = tmp_path / "consumption.jsonl"
    reader = PrivateCheckpointReader.from_schema_path(
        SCHEMA, binding=binding(), consumption_path=consumption
    )
    first = tmp_path / "first.json"
    write_private(first, checkpoint("global_firewall_restricted", now))
    reader.read_once(
        first,
        expected_type="global_firewall_restricted",
        expected_nonce="1" * 64,
        not_before=now - dt.timedelta(seconds=1),
        not_after=now + dt.timedelta(seconds=1),
    )
    second_document = checkpoint("regional_ruleset_created", now)
    second = tmp_path / "second.json"
    write_private(second, second_document)
    with pytest.raises(CheckpointContractError, match="nonce was already consumed"):
        reader.read_once(
            second,
            expected_type="regional_ruleset_created",
            expected_nonce="1" * 64,
            not_before=now - dt.timedelta(seconds=1),
            not_after=now + dt.timedelta(seconds=1),
        )
    empty = checkpoint("cloud_ide_opened", now)
    empty["checkpoint_nonce"] = "5" * 64
    empty["details"] = {}
    empty_path = tmp_path / "empty.json"
    write_private(empty_path, empty)
    with pytest.raises(CheckpointContractError, match="schema"):
        reader.read_once(
            empty_path,
            expected_type="cloud_ide_opened",
            expected_nonce="5" * 64,
            not_before=now - dt.timedelta(seconds=1),
            not_after=now + dt.timedelta(seconds=1),
        )
    reader.close()


def test_human_decision_requires_new_image_approval_and_public_ipv4_32() -> None:
    template = json.loads(TEMPLATE.read_bytes())
    schema = json.loads(DECISION_SCHEMA.read_bytes())
    with pytest.raises(CheckpointContractError, match="schema"):
        validate_human_decision(template, schema=schema, schema_path=DECISION_SCHEMA)
    valid = dict(template)
    valid.update(
        {
            "decision_id": "T07-L2M-FRESH-0001",
            "decision_nonce": "a" * 64,
            "source_ipv4_cidr": "8.8.8.8/32",
        }
    )
    for key in list(valid):
        if (
            key.startswith("approve_")
            or key.startswith("attest_")
            or key.startswith("acknowledge_")
        ):
            valid[key] = True
    validate_human_decision(valid, schema=schema, schema_path=DECISION_SCHEMA)
    with pytest.raises(CheckpointContractError, match="repository-bound"):
        validate_human_decision(valid, schema={}, schema_path=DECISION_SCHEMA)
    valid["source_ipv4_cidr"] = "10.0.0.1/32"
    with pytest.raises(CheckpointContractError, match="public IPv4"):
        validate_human_decision(valid, schema=schema, schema_path=DECISION_SCHEMA)
    for unsafe in ("0.0.0.0/0", "not-a-cidr", "2001:4860:4860::8888/128"):
        valid["source_ipv4_cidr"] = unsafe
        with pytest.raises(CheckpointContractError):
            validate_human_decision(valid, schema=schema, schema_path=DECISION_SCHEMA)


def test_checkpoint_schema_and_template_are_public_safe() -> None:
    combined = SCHEMA.read_text(encoding="utf-8") + TEMPLATE.read_text(encoding="utf-8")
    prohibited = (
        "jupyter_token",
        "jupyter_url",
        "authorization_header",
        "private_key_path",
        "OPENAI_API_KEY",
        "SIRA_API_KEY",
        "LAMBDA_API_KEY",
    )
    assert all(value not in combined for value in prohibited)
    assert os.path.expanduser("~") not in combined


@pytest.mark.parametrize("kind", CHECKPOINT_TYPES)
def test_every_checkpoint_type_has_one_exact_details_contract(kind: str) -> None:
    schema = json.loads(SCHEMA.read_bytes())
    document = checkpoint(kind, dt.datetime(2026, 8, 10, tzinfo=dt.UTC))
    assert not list(Draft202012Validator(schema).iter_errors(document))

    details = document["details"]
    assert isinstance(details, dict)
    details["cloud_ide_opened" if kind != "cloud_ide_opened" else "provider_instance_id"] = True
    assert list(Draft202012Validator(schema).iter_errors(document))


@pytest.mark.parametrize("raw_id_key", ["provider_instance_id", "provider_ruleset_id"])
def test_checkpoint_schema_rejects_raw_provider_identifiers(raw_id_key: str) -> None:
    schema = json.loads(SCHEMA.read_bytes())
    document = checkpoint("termination_confirmed_by_user", dt.datetime.now(dt.UTC))
    details = document["details"]
    assert isinstance(details, dict)
    details[raw_id_key] = "private-provider-id"
    assert list(Draft202012Validator(schema).iter_errors(document))


def test_launch_checkpoint_requires_type_region_image_offeredness_attestation() -> None:
    schema = json.loads(SCHEMA.read_bytes())
    document = checkpoint("launch_clicked_once", dt.datetime.now(dt.UTC))
    details = document["details"]
    assert isinstance(details, dict)
    del details["approved_image_offered_for_selected_type_region"]
    assert list(Draft202012Validator(schema).iter_errors(document))


def test_checkpoint_schema_substitution_is_rejected_before_ledger_creation(
    tmp_path: Path,
) -> None:
    permissive = tmp_path / "permissive.schema.json"
    permissive.write_text("{}")
    consumption = tmp_path / "consumption.jsonl"
    with pytest.raises(CheckpointContractError, match="repository-bound"):
        PrivateCheckpointReader.from_schema_path(
            permissive,
            binding=binding(),
            consumption_path=consumption,
        )
    assert not consumption.exists()


@pytest.mark.parametrize(
    "kind",
    [
        "termination_confirmed_by_user",
        "instance_terminal_verified",
        "regional_ruleset_deleted",
        "global_firewall_restored",
    ],
)
def test_cleanup_checkpoint_partial_append_is_burned_and_recovered_exactly(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    kind: str,
) -> None:
    now = dt.datetime.now(dt.UTC)
    path = tmp_path / f"{kind}.json"
    write_private(path, checkpoint(kind, now))
    reader = PrivateCheckpointReader.from_schema_path(
        SCHEMA,
        binding=binding(),
        consumption_path=tmp_path / "consumption.jsonl",
    )
    original_write = os.write
    target = reader.consumption_descriptor
    writes = 0

    def partial_then_fail(descriptor: int, value: object) -> int:
        nonlocal writes
        if descriptor == target:
            writes += 1
            encoded = bytes(value)  # type: ignore[arg-type]
            if writes == 1:
                return original_write(descriptor, encoded[: max(1, len(encoded) // 2)])
            if writes == 2:
                raise OSError
        return original_write(descriptor, value)  # type: ignore[arg-type]

    monkeypatch.setattr(os, "write", partial_then_fail)
    with pytest.raises(CheckpointConsumptionOutcomeUnknown) as caught:
        reader.read_once(
            path,
            expected_type=kind,
            expected_nonce="1" * 64,
            not_before=now - dt.timedelta(seconds=1),
            not_after=now + dt.timedelta(seconds=1),
        )
    assert caught.value.checkpoint.checkpoint_type == kind
    assert caught.value.content_complete
    assert kind in reader.consumed_types
    monkeypatch.setattr(os, "write", original_write)
    reader.close()
    assert not reader.final_evidence.complete
    record = json.loads(reader.final_evidence.encoded)
    assert record["checkpoint_type"] == kind


def test_checkpoint_fsync_failure_burns_identity_but_preserves_structural_evidence(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    now = dt.datetime.now(dt.UTC)
    path = tmp_path / "termination_confirmed_by_user.json"
    write_private(path, checkpoint("termination_confirmed_by_user", now))
    reader = PrivateCheckpointReader.from_schema_path(
        SCHEMA,
        binding=binding(),
        consumption_path=tmp_path / "consumption.jsonl",
    )
    original_fsync = os.fsync
    target = reader.consumption_descriptor
    failed = False

    def fail_once(descriptor: int) -> None:
        nonlocal failed
        if descriptor == target and not failed:
            failed = True
            raise OSError
        original_fsync(descriptor)

    monkeypatch.setattr(os, "fsync", fail_once)
    with pytest.raises(CheckpointConsumptionOutcomeUnknown) as caught:
        reader.read_once(
            path,
            expected_type="termination_confirmed_by_user",
            expected_nonce="1" * 64,
            not_before=now - dt.timedelta(seconds=1),
            not_after=now + dt.timedelta(seconds=1),
        )
    assert caught.value.content_complete
    monkeypatch.setattr(os, "fsync", original_fsync)
    reader.close()
    assert not reader.final_evidence.complete


@pytest.mark.parametrize("failure_mode", ["partial_write_interrupt", "fsync_interrupt"])
def test_checkpoint_interrupt_burns_identity_and_retains_exact_record_prefix(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    failure_mode: str,
) -> None:
    now = dt.datetime.now(dt.UTC)
    kind = "cloud_ide_opened"
    path = tmp_path / f"{kind}.json"
    write_private(path, checkpoint(kind, now))
    reader = PrivateCheckpointReader.from_schema_path(
        SCHEMA,
        binding=binding(),
        consumption_path=tmp_path / "consumption.jsonl",
    )
    target = reader.consumption_descriptor
    original_write = os.write
    original_fsync = os.fsync
    faulted = False
    fsync_armed = False

    def write_with_interrupt(descriptor: int, value: object) -> int:
        nonlocal faulted, fsync_armed
        encoded = bytes(value)  # type: ignore[arg-type]
        if descriptor == target and not faulted:
            if failure_mode == "partial_write_interrupt":
                faulted = True
                original_write(descriptor, encoded[: max(1, len(encoded) // 2)])
                raise KeyboardInterrupt
            fsync_armed = True
        return original_write(descriptor, encoded)

    def fsync_with_interrupt(descriptor: int) -> None:
        nonlocal faulted, fsync_armed
        if descriptor == target and fsync_armed and not faulted:
            faulted = True
            fsync_armed = False
            raise SystemExit(19)
        original_fsync(descriptor)

    monkeypatch.setattr(os, "write", write_with_interrupt)
    monkeypatch.setattr(os, "fsync", fsync_with_interrupt)
    with pytest.raises(CheckpointConsumptionOutcomeUnknown) as caught:
        reader.read_once(
            path,
            expected_type=kind,
            expected_nonce="1" * 64,
            not_before=now - dt.timedelta(seconds=1),
            not_after=now + dt.timedelta(seconds=1),
        )
    assert caught.value.content_complete
    assert faulted and kind in reader.consumed_types
    with pytest.raises(CheckpointContractError, match="already consumed"):
        reader.read_once(
            path,
            expected_type=kind,
            expected_nonce="1" * 64,
            not_before=now - dt.timedelta(seconds=1),
            not_after=now + dt.timedelta(seconds=1),
        )
    monkeypatch.setattr(os, "write", original_write)
    monkeypatch.setattr(os, "fsync", original_fsync)
    reader.close()
    assert not reader.final_evidence.complete
    retained = reader.final_evidence.encoded
    assert retained.endswith(b"\n")
    assert json.loads(retained)["checkpoint_type"] == kind


def test_interrupt_after_consumption_returns_verified_burned_checkpoint(
    tmp_path: Path,
) -> None:
    now = dt.datetime.now(dt.UTC)
    kind = "termination_confirmed_by_user"
    path = tmp_path / f"{kind}.json"
    write_private(path, checkpoint(kind, now))
    reader = PrivateCheckpointReader.from_schema_path(
        SCHEMA,
        binding=binding(),
        consumption_path=tmp_path / "consumption.jsonl",
    )

    def interrupt_after_consumption(verified: VerifiedCheckpoint) -> None:
        assert verified.checkpoint_type == kind
        raise KeyboardInterrupt

    with pytest.raises(CheckpointConsumptionOutcomeUnknown) as outcome:
        reader.read_once(
            path,
            expected_type=kind,
            expected_nonce="1" * 64,
            not_before=now - dt.timedelta(seconds=1),
            not_after=now + dt.timedelta(seconds=1),
            on_consumed=interrupt_after_consumption,
        )
    assert outcome.value.checkpoint.checkpoint_type == kind
    assert outcome.value.content_complete is True
    assert isinstance(outcome.value.interruption, KeyboardInterrupt)
    with pytest.raises(CheckpointContractError, match="already consumed"):
        reader.read_once(
            path,
            expected_type=kind,
            expected_nonce="1" * 64,
            not_before=now - dt.timedelta(seconds=1),
            not_after=now + dt.timedelta(seconds=1),
        )
