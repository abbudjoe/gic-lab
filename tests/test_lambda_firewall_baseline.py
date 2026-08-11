from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest

import giclab.harness.lambda_firewall_baseline as baseline
from giclab.harness.lambda_firewall_baseline import (
    CANONICALIZATION_VERSION,
    CAPTURE_PLAN_ID,
    CAPTURE_RUN_ID,
    FirewallBaselineError,
    build_exact_restoration_payload,
    canonicalize_firewall_rules,
    verify_exact_firewall_baseline,
)
from giclab.harness.sira_storage import VolumeObservation

ROOT = Path(__file__).resolve().parents[1]
V3_PLAN = (
    ROOT / "containers/sira-smoke/lambda/manual-console/gate-l2m-host-qualification-plan-v3.json"
)
V4_PLAN = (
    ROOT / "containers/sira-smoke/lambda/manual-console/gate-l2m-host-qualification-plan-v4.json"
)


def rule(
    *,
    description: str = "synthetic rule",
    source: str = "192.0.2.1/32",
    protocol: str = "tcp",
    ports: list[int] | None = None,
) -> dict[str, object]:
    value: dict[str, object] = {
        "description": description,
        "protocol": protocol,
        "source_network": source,
    }
    if protocol != "icmp":
        value["port_range"] = [443, 443] if ports is None else ports
    return value


def test_description_is_authoritative_and_absence_is_not_empty() -> None:
    complete = canonicalize_firewall_rules([rule(description="")])
    changed = canonicalize_firewall_rules([rule(description="changed")])
    assert complete.semantic_sha256 != changed.semantic_sha256
    incomplete = rule(description="")
    incomplete.pop("description")
    with pytest.raises(FirewallBaselineError, match="required authoritative"):
        canonicalize_firewall_rules([incomplete])


def test_rule_order_is_ignored_but_duplicate_multiplicity_is_preserved() -> None:
    first = rule(description="first", ports=[80, 80])
    second = rule(description="second", protocol="udp", ports=[53, 53])
    ordered = canonicalize_firewall_rules([first, second])
    reordered = canonicalize_firewall_rules([second, first])
    duplicated = canonicalize_firewall_rules([second, first, first])
    assert ordered.semantic_sha256 == reordered.semantic_sha256
    assert ordered.semantic_sha256 != duplicated.semantic_sha256
    assert duplicated.duplicate_rule_count == 1


def test_cidr_semantics_and_port_contract_are_exact() -> None:
    host = canonicalize_firewall_rules([rule(source="192.0.2.1")])
    host_cidr = canonicalize_firewall_rules([rule(source="192.0.2.1/32")])
    assert host.semantic_sha256 == host_cidr.semantic_sha256
    network_variant = canonicalize_firewall_rules([rule(source="192.0.2.7/24")])
    canonical_network = canonicalize_firewall_rules([rule(source="192.0.2.0/24")])
    assert network_variant.semantic_sha256 == canonical_network.semantic_sha256
    with pytest.raises(FirewallBaselineError, match="port range"):
        canonicalize_firewall_rules([rule(ports=[444, 443])])
    with pytest.raises(FirewallBaselineError, match="omit port_range"):
        canonicalize_firewall_rules(
            [
                {
                    "description": "icmp",
                    "port_range": [1, 1],
                    "protocol": "icmp",
                    "source_network": "192.0.2.1/32",
                }
            ]
        )


def test_extra_or_missing_rule_and_unknown_material_field_fail() -> None:
    expected = canonicalize_firewall_rules([rule()])
    with pytest.raises(FirewallBaselineError, match="differs"):
        verify_exact_firewall_baseline(
            {"id": "global", "name": "Global", "rules": [rule(), rule()]},
            expected_ruleset_id="global",
            expected_ruleset_name="Global",
            expected_semantic_sha256=expected.semantic_sha256,
        )
    missing = rule()
    missing.pop("source_network")
    with pytest.raises(FirewallBaselineError, match="required authoritative"):
        canonicalize_firewall_rules([missing])
    extra = rule()
    extra["provider_extension"] = "not-authoritative"
    with pytest.raises(FirewallBaselineError, match="unknown additive"):
        canonicalize_firewall_rules([extra])


def test_exact_restoration_payload_includes_description_and_excludes_response_metadata() -> None:
    document, encoded, digest = build_exact_restoration_payload(
        [rule(description="exact synthetic description")], repository_root=ROOT
    )
    assert document == {"rules": [rule(description="exact synthetic description")]}
    assert b'"description":"exact synthetic description"' in encoded
    assert b'"id"' not in encoded and b'"name"' not in encoded
    assert hashlib.sha256(encoded).hexdigest() == digest


def test_historical_projection_is_preserved_but_not_lossless() -> None:
    adjudication = baseline.adjudicate_historical_run(ROOT)
    assert adjudication.document["adjudicated_classification"] == (
        "incomplete_or_transformed_baseline"
    )
    assert adjudication.structural_report["all_current_required_fields_present"] is True
    assert adjudication.structural_report["raw_response_retained"] is False
    assert adjudication.structural_report["unknown_raw_key_structure_retained"] is False
    assert adjudication.document["next_required_state"] == (
        "fresh-readonly-firewall-baseline-required"
    )
    assert adjudication.document["run_replay_allowed"] is False


def test_committed_historical_reports_match_private_structural_analysis() -> None:
    adjudication = baseline.adjudicate_historical_run(ROOT)
    committed_adjudication = json.loads(
        (ROOT / baseline.HISTORICAL_ADJUDICATION_RELATIVE).read_bytes()
    )
    committed_report = json.loads(
        (ROOT / baseline.HISTORICAL_STRUCTURAL_REPORT_RELATIVE).read_bytes()
    )
    assert committed_adjudication == adjudication.document
    assert committed_report == adjudication.structural_report
    combined = json.dumps([committed_adjudication, committed_report], sort_keys=True)
    assert "192.0.2.1" not in combined
    assert "synthetic rule" not in combined


def test_fallback_plan_is_exactly_one_get_and_no_manual_v4_exists() -> None:
    plan = baseline.render_capture_plan(ROOT, reviewed_implementation_commit="a" * 40)
    baseline.validate_capture_plan(plan, repository_root=ROOT)
    assert plan["plan_id"] == CAPTURE_PLAN_ID
    assert plan["run_id"] == CAPTURE_RUN_ID
    assert plan["terminal_decision"] == "fresh-readonly-firewall-baseline-required"
    assert plan["request"] == {
        "ordinal": 1,
        "method": "GET",
        "scheme": "https",
        "host": "cloud.lambda.ai",
        "path": "/api/v1/firewall-rulesets/global",
        "query_key_names": [],
        "redirect_follows": 0,
        "pagination_requests": 0,
        "automatic_retries": 0,
    }
    assert plan["authorization"]["authorized"] is False
    assert plan["caps"]["cloud_mutations"] == 0
    assert plan["caps"]["paid_compute_cents"] == 0
    assert not V4_PLAN.exists()


def test_materialized_capture_plan_is_exact_and_unauthorized() -> None:
    path = ROOT / baseline.CAPTURE_PLAN_RELATIVE
    encoded = path.read_bytes()
    assert len(encoded) == 5_754
    assert hashlib.sha256(encoded).hexdigest() == (
        "0d353f1283e906c7d6fd02ed278e6546cfb4c64e19f64370afb2860aa67501e1"
    )
    plan = json.loads(encoded)
    baseline.validate_capture_plan(plan, repository_root=ROOT)
    assert plan == baseline.render_capture_plan(
        ROOT,
        reviewed_implementation_commit="a55d66a96a6fa4e722cf0d12c258ff15f9eab659",
    )
    assert plan["authorization"]["authorized"] is False


def test_historical_plan_and_run_are_immutable_and_old_v3_fails_closed() -> None:
    assert hashlib.sha256(V3_PLAN.read_bytes()).hexdigest() == baseline.HISTORICAL_PLAN_SHA256
    assert (
        hashlib.sha256((ROOT / baseline.HISTORICAL_JOURNAL_RELATIVE).read_bytes()).hexdigest()
        == baseline.HISTORICAL_JOURNAL_SHA256
    )
    plan = json.loads(V3_PLAN.read_bytes())
    observer_binding = next(
        item
        for item in plan["implementation_binding"]["artifacts"]
        if item["path"] == "src/giclab/harness/lambda_l2m_observer.py"
    )
    assert (
        observer_binding["sha256"]
        != hashlib.sha256((ROOT / observer_binding["path"]).read_bytes()).hexdigest()
    )


def test_incident_bundle_seals_without_changing_historical_bytes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    adjudication = baseline.adjudicate_historical_run(ROOT)
    members = baseline._incident_members(ROOT, adjudication)
    historical_paths = (
        baseline.HISTORICAL_JOURNAL_RELATIVE,
        baseline.HISTORICAL_OBSERVATION_RELATIVE,
    )
    for relative, encoded in (
        (historical_paths[0], adjudication.original_journal),
        (historical_paths[1], adjudication.original_observation),
    ):
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(encoded)
    before = {
        relative: hashlib.sha256((tmp_path / relative).read_bytes()).hexdigest()
        for relative in historical_paths
    }
    external = tmp_path / "external"
    system = tmp_path / "system"
    external.mkdir()
    system.mkdir()
    monkeypatch.setattr(baseline, "APPROVED_MOUNT", external)
    monkeypatch.setattr(baseline, "SYSTEM_DATA_MOUNT", system)
    monkeypatch.setattr(baseline, "adjudicate_historical_run", lambda _root: adjudication)
    monkeypatch.setattr(baseline, "_incident_members", lambda _root, _value: members)
    monkeypatch.setattr(baseline, "_validate_external", lambda _value, incremental_bytes: 0)
    monkeypatch.setattr(baseline, "_validate_system", lambda _value, floor_bytes: None)

    real_open = baseline._HeldDirectory.open.__func__

    def fake_open(cls: type[baseline._HeldDirectory], path: Path) -> baseline._HeldDirectory:
        held = real_open(cls, path)
        if path == external:
            held.device += 100_000
        return held

    def fake_archive_root(
        held_external: baseline._HeldDirectory, archive_path: Path
    ) -> baseline._HeldDirectory:
        archive_path.mkdir(parents=True, exist_ok=True)
        held = real_open(baseline._HeldDirectory, archive_path)
        held.device = held_external.device
        return held

    monkeypatch.setattr(baseline._HeldDirectory, "open", classmethod(fake_open))
    monkeypatch.setattr(baseline, "_open_or_create_archive_root", fake_archive_root)
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
    seal = baseline.seal_run_0003_incident_bundle(
        tmp_path,
        volume_observer=lambda: (external_observation, system_observation),
        entropy=lambda count: b"x" * count,
    )
    assert seal.destination_hashes_verified is True
    assert seal.source_retained is True
    assert (seal.local_root / "INCIDENT_SEAL.json").is_file()
    assert (seal.external_root / "SEAL.json").is_file()
    assert before == {
        relative: hashlib.sha256((tmp_path / relative).read_bytes()).hexdigest()
        for relative in historical_paths
    }


class FakeCaptureTransport:
    def __init__(self, body: bytes) -> None:
        self.body = body
        self.calls = 0

    def fetch(
        self,
        *,
        credential: str,
        timeout_seconds: float,
        max_response_bytes: int,
    ) -> baseline.CaptureResponse:
        assert credential == "PUBLIC-DUMMY-CANARY-NOT-A-SECRET"
        assert timeout_seconds == baseline.MAX_CAPTURE_PROVIDER_WALL_SECONDS
        assert len(self.body) <= max_response_bytes
        self.calls += 1
        return baseline.CaptureResponse(200, "application/json", self.body, 1)


def capture_fixture_root(tmp_path: Path) -> Path:
    for relative in (
        baseline.BASELINE_SCHEMA_RELATIVE,
        baseline.CANONICAL_REPORT_SCHEMA_RELATIVE,
        baseline.RESTORATION_SCHEMA_RELATIVE,
        baseline.CAPTURE_LEDGER_SCHEMA_RELATIVE,
    ):
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((ROOT / relative).read_bytes())
    return tmp_path


def test_fake_capture_retains_complete_private_response_and_never_leaks_secret(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = capture_fixture_root(tmp_path)
    monkeypatch.setattr(baseline, "MIN_LOCAL_PREWRITE_FREE_BYTES", 0)
    body = baseline.canonical_json_bytes(
        {"data": {"id": "global", "name": "Synthetic", "rules": [rule()]}}
    )
    transport = FakeCaptureTransport(body)
    evidence = baseline.capture_with_fakeable_transport(
        root,
        authorization_reference="AUTH-T07-GATE-L2M-FIREWALL-BASELINE-CAPTURE-V1-TEST",
        credential_provider=lambda: "PUBLIC-DUMMY-CANARY-NOT-A-SECRET",
        transport=transport,
    )
    assert transport.calls == 1
    assert evidence.baseline_alias.startswith("l2m-firewall-baseline-")
    assert (evidence.root / "raw-global-firewall-response.json").read_bytes() == body
    retained = b"".join(path.read_bytes() for path in evidence.root.iterdir())
    assert b"PUBLIC-DUMMY-CANARY-NOT-A-SECRET" not in retained
    events = [
        json.loads(line)
        for line in (evidence.root / "request-ledger.jsonl").read_text().splitlines()
    ]
    assert [event["event_sequence"] for event in events] == list(range(1, len(events) + 1))
    assert events[-1]["event_type"] == "run_stopped"
    assert evidence.ledger_events == 12


def test_capture_missing_secret_stops_before_send(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = capture_fixture_root(tmp_path)
    monkeypatch.setattr(baseline, "MIN_LOCAL_PREWRITE_FREE_BYTES", 0)
    transport = FakeCaptureTransport(b"{}")
    with pytest.raises(FirewallBaselineError, match="secret presence"):
        baseline.capture_with_fakeable_transport(
            root,
            authorization_reference="AUTH-T07-GATE-L2M-FIREWALL-BASELINE-CAPTURE-V1-TEST",
            credential_provider=lambda: None,
            transport=transport,
        )
    assert transport.calls == 0
    events = [
        json.loads(line)
        for line in (root / baseline.CAPTURE_LEDGER_RELATIVE).read_text().splitlines()
    ]
    assert all(event["event_type"] != "request_send_started" for event in events)


def test_capture_schema_drift_stops_without_retry(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = capture_fixture_root(tmp_path)
    monkeypatch.setattr(baseline, "MIN_LOCAL_PREWRITE_FREE_BYTES", 0)
    body = baseline.canonical_json_bytes(
        {"data": {"id": "global", "name": "Synthetic", "rules": [{"protocol": "tcp"}]}}
    )
    transport = FakeCaptureTransport(body)
    with pytest.raises(FirewallBaselineError):
        baseline.capture_with_fakeable_transport(
            root,
            authorization_reference="AUTH-T07-GATE-L2M-FIREWALL-BASELINE-CAPTURE-V1-TEST",
            credential_provider=lambda: "PUBLIC-DUMMY-CANARY-NOT-A-SECRET",
            transport=transport,
        )
    assert transport.calls == 1
    assert (
        root / baseline.CAPTURE_RUN_ROOT_RELATIVE / "raw-global-firewall-response.json"
    ).read_bytes() == body
    events = [
        json.loads(line)
        for line in (root / baseline.CAPTURE_LEDGER_RELATIVE).read_text().splitlines()
    ]
    assert sum(event["event_type"] == "request_send_started" for event in events) == 1
    assert events[-1]["event_type"] == "run_stopped"
    partial = baseline._capture_local_members(
        root / baseline.CAPTURE_RUN_ROOT_RELATIVE,
        require_complete=False,
    )
    assert partial["raw-global-firewall-response.json"] == body
    with pytest.raises(FirewallBaselineError, match="member set"):
        baseline._capture_local_members(
            root / baseline.CAPTURE_RUN_ROOT_RELATIVE,
            require_complete=True,
        )


def test_capture_ledger_rejects_reuse_and_sequence_gap(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = capture_fixture_root(tmp_path)
    monkeypatch.setattr(baseline, "MIN_LOCAL_PREWRITE_FREE_BYTES", 0)
    ledger = baseline.CaptureLedger.create(
        root,
        authorization_reference="AUTH-T07-GATE-L2M-FIREWALL-BASELINE-CAPTURE-V1-TEST",
    )
    with pytest.raises(FirewallBaselineError, match="order"):
        ledger.append("request_intent_committed", request=True)
    ledger.close()
    with pytest.raises(FirewallBaselineError, match="not fresh"):
        baseline.CaptureLedger.create(
            root,
            authorization_reference="AUTH-T07-GATE-L2M-FIREWALL-BASELINE-CAPTURE-V1-TEST2",
        )


def test_capture_plan_caps_are_finite_and_science_is_locked() -> None:
    plan = baseline.render_capture_plan(ROOT, reviewed_implementation_commit="b" * 40)
    caps = plan["caps"]
    for name in (
        "account_gets",
        "raw_response_bytes",
        "request_ledger_bytes",
        "request_ledger_events",
        "request_ledger_event_bytes",
        "local_artifact_bytes",
        "external_archive_bytes",
        "provider_wall_seconds",
        "archive_wall_seconds",
        "total_wall_seconds",
    ):
        assert isinstance(caps[name], int) and caps[name] > 0
    for name in (
        "automatic_retries",
        "pagination_requests",
        "redirect_follows",
        "cloud_mutations",
        "paid_compute_cents",
        "ssh_operations",
        "jupyter_actions",
        "browser_actions",
        "container_actions",
        "model_calls",
        "model_tokens",
        "sira_executions",
    ):
        assert caps[name] == 0
    assert plan["scientific_lock"] == {
        "experiment": "EXP-0001",
        "profile": "PLAN-EXP0001-SMOKE",
        "condition_order": ["SIRA-REACTIVE", "SIRA-SIMULATIVE"],
        "pair": "PAIR-EXP0001-SMOKE-0000",
        "model": "gpt-4o-2024-11-20",
        "reproduction_level": "directional reproduction",
        "interpretation_allowed": False,
        "pilot_authorized": False,
        "training": False,
        "gate_scope": "read-only-firewall-baseline-capture-only",
    }


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ({"id": "not-global"}, "identity"),
        ({"name": "Drifted"}, "identity"),
        ({"rules": [rule(description="drifted")]}, "differs"),
    ],
)
def test_exact_ruleset_identity_and_post_restoration_equality(
    mutation: dict[str, object], message: str
) -> None:
    rules = [rule()]
    canonical = canonicalize_firewall_rules(rules)
    current: dict[str, object] = {"id": "global", "name": "Global", "rules": rules}
    current.update(mutation)
    with pytest.raises(FirewallBaselineError, match=message):
        verify_exact_firewall_baseline(
            current,
            expected_ruleset_id="global",
            expected_ruleset_name="Global",
            expected_semantic_sha256=canonical.semantic_sha256,
        )


def test_public_contract_and_schema_identities_are_current() -> None:
    contract = json.loads((ROOT / baseline.PUBLIC_CONTRACT_RELATIVE).read_bytes())
    assert contract["specification"]["sha256"] == baseline.OPENAPI_SHA256
    assert contract["specification"]["bytes"] == baseline.OPENAPI_BYTES
    assert contract["firewall_rule"]["required"] == [
        "protocol",
        "source_network",
        "description",
    ]
    assert contract["authenticated_request_made"] is False
    assert contract["cloud_mutation_performed"] is False
    assert baseline.CANONICALIZATION_VERSION == CANONICALIZATION_VERSION


def test_capture_authorization_rejects_pending_or_malformed_bindings() -> None:
    with pytest.raises(FirewallBaselineError, match="authorization"):
        baseline.CaptureAuthorization(
            "a" * 40,
            baseline.CAPTURE_AUTHORIZATION_PLACEHOLDER,
            "b" * 64,
        ).validate()
    with pytest.raises(FirewallBaselineError, match="authorization"):
        replace(
            baseline.CaptureAuthorization(
                "a" * 40,
                "AUTH-T07-GATE-L2M-FIREWALL-BASELINE-CAPTURE-V1-TEST",
                "b" * 64,
            ),
            expected_commit="not-a-commit",
        ).validate()


def test_no_live_http_or_mutation_surface_is_imported_by_capture_plan() -> None:
    source = (ROOT / "src/giclab/harness/lambda_firewall_baseline.py").read_text()
    assert "requests." not in source
    assert "urllib.request" not in source
    assert "curl" not in source
    assert (
        "PATCH"
        not in baseline.render_capture_plan(ROOT, reviewed_implementation_commit="c" * 40)[
            "capture_invocation"
        ]
    )
    assert "SIRA_API_KEY" not in source
    assert "OPENAI_API_KEY" not in source
