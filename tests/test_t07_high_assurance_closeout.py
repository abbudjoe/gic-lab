from __future__ import annotations

import hashlib
import json
import stat
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import pytest

import giclab.harness.lambda_firewall_baseline as firewall
import giclab.harness.t07_high_assurance_closeout as closeout
from giclab.harness.sira_storage import VolumeObservation

ROOT = Path(__file__).resolve().parents[1]


def rule(
    *,
    description: str = "synthetic exact description",
    source_network: str = "192.0.2.1/32",
) -> dict[str, object]:
    return {
        "description": description,
        "port_range": [443, 443],
        "protocol": "tcp",
        "source_network": source_network,
    }


def fixture_root(tmp_path: Path) -> Path:
    for relative in (
        firewall.BASELINE_SCHEMA_RELATIVE,
        firewall.CANONICAL_REPORT_SCHEMA_RELATIVE,
        firewall.PUBLIC_STRUCTURAL_REPORT_SCHEMA_RELATIVE,
        firewall.RESTORATION_SCHEMA_RELATIVE,
        closeout.ADJUDICATION_SCHEMA_RELATIVE,
    ):
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((ROOT / relative).read_bytes())
    return tmp_path


def synthetic_documents(tmp_path: Path) -> closeout.AuthoritativeFirewallDocuments:
    private_workspace = "PRIVATE-WORKSPACE-CANARY"
    raw = firewall.canonical_json_bytes(
        {
            "data": {
                "id": "global",
                "name": "Synthetic",
                "rules": [rule(description=""), rule()],
                "workspace_id": private_workspace,
            }
        }
    )
    evidence = closeout.ImmutableCaptureEvidence(
        b"synthetic-ledger\n",
        raw,
        (),
        "AUTH-T07-GATE-L2M-FIREWALL-BASELINE-CAPTURE-V1-TEST",
        "2026-08-11T00:00:00Z",
        1,
    )
    documents = closeout.build_authoritative_documents(
        fixture_root(tmp_path),
        evidence,
        require_observed_workspace_extension=True,
    )
    assert private_workspace.encode() in documents.private_baseline
    assert private_workspace.encode() not in documents.canonical_report
    assert private_workspace.encode() not in documents.public_structural_report
    assert private_workspace.encode() not in documents.adjudication
    return documents


def test_additive_workspace_metadata_is_adjudicated_without_public_scalar() -> None:
    ruleset = {
        "id": "global",
        "name": "Synthetic",
        "rules": [rule()],
        "workspace_id": "PRIVATE-WORKSPACE-CANARY",
    }
    parsed = firewall.parse_global_firewall_response({"data": ruleset})
    private_report = firewall.complete_canonical_report(
        parsed.parsed_ruleset.baseline,
        envelope=parsed.envelope,
        ruleset=parsed.parsed_ruleset.ruleset,
    )
    report = firewall.render_public_structural_report(private_report, repository_root=ROOT)
    assert parsed.parsed_ruleset.extension_types == (("workspace_id", "string"),)
    assert report["compatible_top_level_extensions"] == [{"name": "workspace_id", "type": "string"}]
    assert private_report["protocol_classes"] == ["tcp"]
    assert report["protocol_class_count"] == 1
    assert "protocol_classes" not in report
    assert "PRIVATE-WORKSPACE-CANARY" not in json.dumps(report, sort_keys=True)


def test_private_baseline_and_restoration_preserve_exact_rule_semantics(tmp_path: Path) -> None:
    documents = synthetic_documents(tmp_path)
    baseline = json.loads(documents.private_baseline)
    payload = json.loads(documents.restoration_payload)
    report = json.loads(documents.canonical_report)
    assert baseline["global_ruleset"]["workspace_id"] == "PRIVATE-WORKSPACE-CANARY"
    assert payload == {"rules": baseline["global_ruleset"]["rules"]}
    assert "workspace_id" not in payload
    assert "id" not in payload and "name" not in payload
    assert [item["description"] for item in payload["rules"]] == [
        "",
        "synthetic exact description",
    ]
    assert report["empty_description_count"] == 1
    assert report["nonempty_description_count"] == 1


def test_absent_description_blocks_while_empty_description_is_authoritative() -> None:
    empty = rule(description="")
    baseline = firewall.canonicalize_firewall_rules([empty])
    assert baseline.rules[0].description == ""
    missing = dict(empty)
    del missing["description"]
    with pytest.raises(firewall.FirewallBaselineError, match="required authoritative"):
        firewall.canonicalize_firewall_rules([missing])


def test_rule_order_is_equivalent_but_multiplicity_and_semantic_changes_fail() -> None:
    first = rule(description="first")
    second = rule(description="second", source_network="198.51.100.2/32")
    ordered = firewall.canonicalize_firewall_rules([first, second])
    reordered = firewall.canonicalize_firewall_rules([second, first])
    duplicate = firewall.canonicalize_firewall_rules([first, second, first])
    changed = firewall.canonicalize_firewall_rules(
        [first, rule(description="changed", source_network="198.51.100.2/32")]
    )
    assert ordered.semantic_sha256 == reordered.semantic_sha256
    assert ordered.semantic_sha256 != duplicate.semantic_sha256
    assert ordered.semantic_sha256 != changed.semantic_sha256
    with pytest.raises(firewall.FirewallBaselineError, match="differs"):
        firewall.verify_exact_firewall_baseline(
            {"id": "global", "name": "Synthetic", "rules": [first, first, second]},
            expected_ruleset_id="global",
            expected_ruleset_name="Synthetic",
            expected_semantic_sha256=ordered.semantic_sha256,
        )


def test_unknown_rule_field_still_blocks() -> None:
    value = rule()
    value["provider_extension"] = "PRIVATE-CANARY"
    with pytest.raises(firewall.FirewallBaselineError, match="unknown additive"):
        firewall.parse_global_firewall_response(
            {"data": {"id": "global", "name": "Synthetic", "rules": [value]}}
        )


def configure_synthetic_materialization(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> tuple[
    Path,
    Path,
    Callable[[], tuple[VolumeObservation, VolumeObservation]],
]:
    root = fixture_root(tmp_path / "repository")
    documents = synthetic_documents(tmp_path / "documents")
    for relative, encoded in (
        (closeout.PUBLIC_ADJUDICATION_RELATIVE, documents.adjudication),
        (closeout.PUBLIC_STRUCTURAL_REPORT_RELATIVE, documents.public_structural_report),
    ):
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(encoded)
    external = tmp_path / "external"
    system = tmp_path / "system"
    external.mkdir()
    system.mkdir()
    monkeypatch.setattr(closeout, "APPROVED_MOUNT", external)
    monkeypatch.setattr(closeout, "SYSTEM_DATA_MOUNT", system)
    monkeypatch.setattr(closeout, "adjudicate_capture_run", lambda _root: documents)
    monkeypatch.setattr(closeout, "verify_scientific_locks", lambda _root: None)
    synthetic_ledger = b"synthetic immutable ledger\n"
    synthetic_raw = b'{"data":{}}\n'
    ledger_path = root / firewall.CAPTURE_LEDGER_RELATIVE
    raw_path = root / firewall.CAPTURE_RUN_ROOT_RELATIVE / "raw-global-firewall-response.json"
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    ledger_path.write_bytes(synthetic_ledger)
    raw_path.write_bytes(synthetic_raw)
    monkeypatch.setattr(
        closeout, "CAPTURE_LEDGER_SHA256", hashlib.sha256(synthetic_ledger).hexdigest()
    )
    monkeypatch.setattr(closeout, "CAPTURE_RAW_SHA256", hashlib.sha256(synthetic_raw).hexdigest())
    monkeypatch.setattr(
        firewall,
        "_git",
        lambda _root, *args: {
            ("branch", "--show-current"): "phase-1/sira-smoke-lambda",
            ("rev-parse", "HEAD"): "a" * 40,
            ("status", "--short"): "",
        }[args],
    )
    monkeypatch.setattr(closeout, "_validate_external", lambda _value, incremental_bytes: 0)
    monkeypatch.setattr(closeout, "_validate_system", lambda _value, floor_bytes: None)
    real_open = closeout._HeldDirectory.open.__func__

    def fake_open(cls: type[closeout._HeldDirectory], path: Path) -> closeout._HeldDirectory:
        held = real_open(cls, path)
        if path == external:
            held.device += 100_000
        return held

    def fake_archive_root(
        held_external: closeout._HeldDirectory,
        archive_path: Path,
    ) -> closeout._HeldDirectory:
        archive_path.mkdir(parents=True, exist_ok=True)
        held = real_open(closeout._HeldDirectory, archive_path)
        held.device = held_external.device
        return held

    monkeypatch.setattr(closeout._HeldDirectory, "open", classmethod(fake_open))
    monkeypatch.setattr(closeout, "_open_or_create_archive_root", fake_archive_root)
    external_observation = VolumeObservation(
        external,
        "apfs",
        True,
        "8478609D-FA37-4ED5-875D-47AE912B9151",
        "7904A6F1-F483-4ED7-9E34-BFECAB31C63E",
        1_000_000_000,
        900_000_000,
        False,
        True,
        True,
        True,
        "synthetic-external",
        "Thunderbolt",
        "IODeviceTree:/synthetic/UTDM",
    )
    system_observation = VolumeObservation(
        system,
        "apfs",
        True,
        "00000000-0000-0000-0000-000000000001",
        None,
        1_000_000_000,
        900_000_000,
        True,
        True,
        True,
        True,
        "synthetic-system",
    )
    return (
        root,
        external / "GIC-Lab/t07/sealed-artifacts",
        lambda: (external_observation, system_observation),
    )


def test_authoritative_baseline_seals_and_copies_with_source_retained(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root, _archive_root, volume_observer = configure_synthetic_materialization(
        monkeypatch,
        tmp_path,
    )
    seal = closeout.materialize_authoritative_baseline(
        root,
        implementation_commit="a" * 40,
        volume_observer=volume_observer,
        entropy=lambda count: b"x" * count,
        utc_now=lambda: datetime(2026, 8, 11, tzinfo=UTC),
    )
    assert seal.destination_hashes_verified is True
    assert seal.source_retained is True
    assert (seal.local_root / "BASELINE_SEAL.json").is_file()
    assert stat.S_IMODE(seal.local_root.stat().st_mode) == 0o500
    assert (seal.external_root / "SEAL.json").is_file()
    assert hashlib.sha256((seal.external_root / "SEAL.json").read_bytes()).hexdigest() == (
        seal.external_seal_sha256
    )


def test_staging_readback_failure_cannot_publish_a_verified_bundle(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root, archive_root, volume_observer = configure_synthetic_materialization(
        monkeypatch,
        tmp_path,
    )
    real_read = closeout._read_regular_at

    def corrupt_one_staged_member(directory_fd: int, name: str, *, max_bytes: int) -> bytes:
        observed = real_read(directory_fd, name, max_bytes=max_bytes)
        if name == "canonical-report.json":
            return observed + b"corruption"
        return observed

    monkeypatch.setattr(closeout, "_read_regular_at", corrupt_one_staged_member)
    with pytest.raises(closeout.HighAssuranceCloseoutError, match="destination verification"):
        closeout.materialize_authoritative_baseline(
            root,
            implementation_commit="a" * 40,
            volume_observer=volume_observer,
            entropy=lambda count: b"y" * count,
            utc_now=lambda: datetime(2026, 8, 11, tzinfo=UTC),
        )
    children = tuple(archive_root.iterdir())
    assert children
    assert all(child.name.startswith(".") for child in children)
    assert all(not (child / "COPY_RECORD.json").exists() for child in children)
    assert all(not (child / "SEAL.json").exists() for child in children)


def test_burned_capture_and_scientific_inputs_remain_immutable() -> None:
    assert (
        hashlib.sha256((ROOT / firewall.CAPTURE_LEDGER_RELATIVE).read_bytes()).hexdigest()
        == closeout.CAPTURE_LEDGER_SHA256
    )
    assert (
        hashlib.sha256(
            (
                ROOT / firewall.CAPTURE_RUN_ROOT_RELATIVE / "raw-global-firewall-response.json"
            ).read_bytes()
        ).hexdigest()
        == closeout.CAPTURE_RAW_SHA256
    )
    closeout.verify_scientific_locks(ROOT)


def test_sealed_private_canonical_v1_remains_valid_under_its_unchanged_schema() -> None:
    assert (
        hashlib.sha256((ROOT / firewall.CANONICAL_REPORT_SCHEMA_RELATIVE).read_bytes()).hexdigest()
        == "3fad2ca8f48845fd7394cbd29357f47f9a6be2db90e740a5eb1faa915a8b9a22"
    )
    private_report = json.loads(
        (ROOT / closeout.LOCAL_ROOT_RELATIVE / "canonical-report.json").read_bytes()
    )
    firewall.validate_canonical_report(private_report, repository_root=ROOT)
    assert private_report["schema_version"] == "0.1.0"
    assert "protocol_classes" in private_report


def test_closeout_has_no_external_or_experimental_execution_surface() -> None:
    source = (ROOT / "src/giclab/harness/t07_high_assurance_closeout.py").read_text()
    for forbidden in (
        "LAMBDA_API_KEY",
        "SIRA_API_KEY",
        "OPENAI_API_KEY",
        "urllib.request",
        "requests.",
        "LambdaHttps",
        "subprocess",
    ):
        assert forbidden not in source
    assert not (
        ROOT
        / "containers/sira-smoke/lambda/manual-console/gate-l2m-host-qualification-plan-v4.json"
    ).exists()


def test_high_assurance_track_is_frozen_and_bounded_handoff_is_non_authorizing() -> None:
    state = (ROOT / "docs/PROJECT_STATE.yaml").read_text()
    assert "planned_execution_substrate: null" in state
    assert "historical_execution_substrate:" in state
    assert "decision_state: bounded-smoke-v3-ready-unauthorized" in state
    assert "gate_l2_decision_state: bounded-manual-console-plan-ready-unauthorized" in state
    for permission in (
        "paid_compute_allowed",
        "prototype_execution_allowed",
        "benchmark_execution_allowed",
        "training_allowed",
        "cloud_mutation_allowed",
    ):
        assert f"{permission}: false" in state

    closeout_document = (
        ROOT / "docs/harness/T07_HIGH_ASSURANCE_INFRASTRUCTURE_CLOSEOUT.md"
    ).read_text()
    residuals = (ROOT / "docs/harness/T07_HIGH_ASSURANCE_RESIDUAL_CONTROLS.md").read_text()
    handoff = (ROOT / "docs/harness/T07_BOUNDED_SMOKE_FORK_HANDOFF.md").read_text()
    assert "high-assurance-infrastructure-frozen" in closeout_document
    assert "A control is a bounded-smoke hard blocker only" in closeout_document
    assert "phase-1/sira-smoke-bounded" in handoff
    assert "execution unauthorized" in handoff
    for control in (
        "Kernel-proven descendant containment",
        "Independent watchdog",
        "Exactly-once cloud launch recovery",
        "Full runtime supply-chain attestation",
    ):
        assert control in residuals


def test_private_closeout_outputs_are_not_tracked() -> None:
    closeout.assert_private_output_not_tracked(ROOT)


def test_real_private_firewall_scalars_do_not_enter_public_closeout_surfaces() -> None:
    raw = json.loads(
        (
            ROOT / firewall.CAPTURE_RUN_ROOT_RELATIVE / "raw-global-firewall-response.json"
        ).read_bytes()
    )["data"]
    sensitive_values = [raw.get("workspace_id"), raw.get("name")]
    for private_rule in raw["rules"]:
        sensitive_values.extend(
            [private_rule.get("source_network"), private_rule.get("description")]
        )
    encoded_values = {
        value.encode() for value in sensitive_values if isinstance(value, str) and value
    }
    public_paths = firewall._git(ROOT, "ls-files", "-co", "--exclude-standard").splitlines()
    assert all(
        sensitive not in (ROOT / relative).read_bytes()
        for relative in public_paths
        if (ROOT / relative).is_file()
        for sensitive in encoded_values
    )
    structural_report = (ROOT / closeout.PUBLIC_STRUCTURAL_REPORT_RELATIVE).read_bytes()
    assert all(
        json.dumps(private_rule["protocol"]).encode() not in structural_report
        for private_rule in raw["rules"]
    )
