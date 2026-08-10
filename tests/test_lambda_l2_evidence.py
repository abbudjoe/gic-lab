from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from giclab.harness.lambda_l2_evidence import (
    GateL2EvidenceWriter,
    L2EvidenceError,
    copy_sealed_evidence_bundle,
)

ROOT = Path(__file__).resolve().parents[1]


def test_one_way_transfer_seal_and_archive_are_hash_verified(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir(mode=0o700)
    writer = GateL2EvidenceWriter.create(repository)
    encoded = b'{"synthetic":"host observation"}\n'
    digest = hashlib.sha256(encoded).hexdigest()
    record = writer.write_transferred_record(
        name="0001-host.json",
        encoded=encoded,
        source_transport_sha256=digest,
    )
    assert record.sha256 == digest
    bundle = writer.seal()
    destination = tmp_path / "external"
    destination.mkdir(mode=0o700)
    archived = copy_sealed_evidence_bundle(
        bundle,
        destination_parent=destination,
        archive_id="RUN-T07-L2-LAMBDA-HOST-QUALIFICATION-0001-HOST-EVIDENCE",
        require_distinct_device=False,
    )
    assert archived.source_retained
    assert (bundle.root / "0001-host.json").read_bytes() == encoded
    assert (archived.destination / "0001-host.json").read_bytes() == encoded
    assert archived.total_bytes > len(encoded)
    writer.close()


def test_transfer_hash_mismatch_stops_before_write(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir(mode=0o700)
    writer = GateL2EvidenceWriter.create(repository)
    with pytest.raises(L2EvidenceError):
        writer.write_transferred_record(
            name="0001-host.json",
            encoded=b"synthetic\n",
            source_transport_sha256="0" * 64,
        )
    writer.close()


def test_l2_success_and_incident_schemas_are_coherent_with_caps() -> None:
    success_schema = json.loads(
        (ROOT / "schemas/t07-lambda-l2-host-evidence.schema.json").read_text()
    )
    incident_schema = json.loads((ROOT / "schemas/t07-lambda-l2-incident.schema.json").read_text())
    Draft202012Validator.check_schema(success_schema)
    Draft202012Validator.check_schema(incident_schema)
    incident = {
        "schema_version": "0.1.0",
        "plan_id": "PLAN-T07-GATE-L2-LAMBDA-HOST-QUALIFICATION-V1",
        "run_id": "RUN-T07-L2-LAMBDA-HOST-QUALIFICATION-0001",
        "authorization_reference": "AUTH-T07-L2-TEST-0001",
        "repository_commit": "a" * 40,
        "incident_phase": "termination",
        "sanitized_failure_class": "terminal_timeout",
        "provider_calls": 140,
        "provider_wall_seconds": 3600,
        "estimated_cost_cents": 129,
        "launch_requests": 1,
        "termination_requests": 1,
        "owned_instance_id_state": "bound",
        "provider_terminal_confirmed": False,
        "strict_global_firewall_preserved": True,
        "regional_cleanup_verified": False,
        "global_restored": False,
        "request_ledger_sha256": "b" * 64,
        "evidence_sealed": True,
        "scientific_boundary": {
            "model_calls": 0,
            "model_tokens": 0,
            "browser_actions": 0,
            "sira_executions": 0,
            "scientific_executions": 0,
            "interpretation_allowed": False,
        },
    }
    assert not list(Draft202012Validator(incident_schema).iter_errors(incident))
    incident["global_restored"] = True
    assert list(Draft202012Validator(incident_schema).iter_errors(incident))
