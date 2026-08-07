from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from giclab.registry import load_json, load_yaml
from giclab.validation import (
    ROOT,
    run_all,
    validate_episode_order,
    validate_experiment_protocol,
    validate_instance,
    validate_project_state,
    validate_site_output,
    validate_transition_record,
)


def _valid_transition() -> dict[str, Any]:
    return {
        "schema_version": "0.1.0",
        "transition_id": "TRN-episode-1-step-0",
        "experiment_id": "EXP-0001",
        "episode_id": "episode-1",
        "step_index": 0,
        "timestamp": "2026-07-15T12:00:00Z",
        "goal": {"text": "test"},
        "observation_before": {"text": "before"},
        "belief_before": {"text": "belief"},
        "configurator_decision": {"mode": "plan", "budget": {"horizon": 1}},
        "candidate_actions": [
            {"candidate_action_id": "A-1", "action": {"kind": "noop"}},
        ],
        "predicted_futures": [
            {
                "prediction_id": "P-1",
                "candidate_action_id": "A-1",
                "horizon": 1,
                "predicted_state": {"text": "after"},
                "confidence": 0.5,
            }
        ],
        "selected_plan": {"plan_id": "PLAN-1", "candidate_action_ids": ["A-1"]},
        "executed_action": {"candidate_action_id": "A-1", "action": {"kind": "noop"}},
        "execution_result": {"ok": True},
        "observation_after": {"text": "after"},
        "belief_after": {"text": "after"},
        "outcome": {"success": True},
        "reward": 1.0,
        "cost": {
            "model_tokens": 10,
            "model_calls": 1,
            "tool_calls": 0,
            "latency_seconds": 0.1,
            "accelerator_seconds": 0,
        },
        "model_revision": "model@revision",
        "tool_revisions": [],
        "environment_revision": "env@revision",
    }


def test_template_protocol_is_schema_valid() -> None:
    protocol = load_yaml(ROOT / "experiments/EXP-0000-template/protocol.yaml")
    assert validate_experiment_protocol(protocol) == []


def test_evidence_and_outcome_cannot_be_conflated() -> None:
    protocol = load_yaml(ROOT / "experiments/EXP-0000-template/protocol.yaml")
    protocol["outcome_status"] = "supported"
    errors = validate_experiment_protocol(protocol)
    assert any("pending" in error for error in errors)


def test_artifact_verified_hash_is_required() -> None:
    schema = ROOT / "schemas/artifact.schema.json"
    artifact = {
        "schema_version": "0.1.0",
        "artifact_id": "ART-0001",
        "experiment_id": None,
        "producer": {"kind": "manual", "id": "test"},
        "kind": "report",
        "format": "json",
        "size_bytes": 0,
        "sha256": None,
        "version": None,
        "revision": None,
        "commit": None,
        "license": None,
        "provenance": "test fixture",
        "storage_uri": "s3://bucket/key",
        "public_access": False,
        "sensitivity": "internal",
        "retention": "ephemeral",
        "created_by_commit": None,
        "created_at": "2026-07-15T12:00:00Z",
        "verification_status": "content-hash-verified",
    }
    assert any("sha256" in error for error in validate_instance(artifact, schema))


def test_transition_cross_references_are_enforced() -> None:
    transition = _valid_transition()
    assert validate_transition_record(transition) == []
    invalid = deepcopy(transition)
    invalid["predicted_futures"][0]["candidate_action_id"] = "A-unknown"
    assert any("unknown candidate" in error for error in validate_transition_record(invalid))


def test_episode_steps_must_be_contiguous_and_unique() -> None:
    transition = _valid_transition()
    skipped = deepcopy(transition)
    skipped["transition_id"] = "TRN-episode-1-step-2"
    skipped["step_index"] = 2
    assert any("non-contiguous" in error for error in validate_episode_order([transition, skipped]))


def test_schema_documents_load_as_objects() -> None:
    for name in ("experiment", "artifact", "transition", "manifest", "compute"):
        assert "$id" in load_json(ROOT / f"schemas/{name}.schema.json")


def test_manifest_records_reject_unknown_fields() -> None:
    manifest = deepcopy(load_yaml(ROOT / "manifests/sources.yaml"))
    manifest["entries"][0]["untyped_claim"] = "must fail"
    errors = validate_instance(manifest, ROOT / "schemas/manifest.schema.json")
    assert any("untyped_claim" in error for error in errors)


def test_compute_entries_require_the_typed_contract() -> None:
    ledger = deepcopy(load_yaml(ROOT / "manifests/compute.yaml"))
    ledger["entries"].append({"id": "CMP-0001"})
    errors = validate_instance(ledger, ROOT / "schemas/compute.schema.json")
    assert any("experiment_id" in error for error in errors)


def test_confirmed_is_an_explicit_evidence_status() -> None:
    protocol = load_yaml(ROOT / "experiments/EXP-0000-template/protocol.yaml")
    protocol["lifecycle_status"] = "completed"
    protocol["evidence_status"] = "confirmed"
    protocol["outcome_status"] = "supported"
    assert validate_experiment_protocol(protocol) == []


def test_project_state_supports_an_authorized_precompute_phase(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    plan = docs / "exec-plans/active/PHASE_0_5.md"
    plan.parent.mkdir(parents=True)
    plan.write_text("# Phase 0.5 — Reading\n\nStatus: **in-progress**\n", encoding="utf-8")
    (docs / "PROJECT_STATE.yaml").write_text(
        "\n".join(
            (
                'phase: "0.5"',
                "phase_name: reading-reconciliation",
                "phase_status: in-progress",
                "paid_compute_allowed: false",
                "prototype_execution_allowed: false",
                "benchmark_execution_allowed: false",
                "training_allowed: false",
                "cloud_mutation_allowed: false",
                "authoritative_plan: docs/exec-plans/active/PHASE_0_5.md",
            )
        ),
        encoding="utf-8",
    )
    assert validate_project_state(tmp_path) == []


def test_project_state_rejects_compute_authority_before_phase_one(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    plan = docs / "exec-plans/active/PHASE_0_5.md"
    plan.parent.mkdir(parents=True)
    plan.write_text("# Phase 0.5 — Reading\n\nStatus: **in-progress**\n", encoding="utf-8")
    (docs / "PROJECT_STATE.yaml").write_text(
        "\n".join(
            (
                'phase: "0.5"',
                "phase_name: reading-reconciliation",
                "phase_status: in-progress",
                "paid_compute_allowed: true",
                "prototype_execution_allowed: false",
                "benchmark_execution_allowed: false",
                "training_allowed: false",
                "cloud_mutation_allowed: false",
                "authoritative_plan: docs/exec-plans/active/PHASE_0_5.md",
            )
        ),
        encoding="utf-8",
    )
    errors = validate_project_state(tmp_path)
    assert any("paid_compute_allowed must be false" in error for error in errors)


@pytest.mark.parametrize("phase", ["NaN", "Infinity", "-Infinity"])
def test_project_state_rejects_nonfinite_phase(tmp_path: Path, phase: str) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "PROJECT_STATE.yaml").write_text(
        "\n".join(
            (
                f'phase: "{phase}"',
                "phase_name: reading-reconciliation",
                "phase_status: in-progress",
                "paid_compute_allowed: false",
                "prototype_execution_allowed: false",
                "benchmark_execution_allowed: false",
                "training_allowed: false",
                "cloud_mutation_allowed: false",
                "authoritative_plan: docs/PHASE.md",
            )
        ),
        encoding="utf-8",
    )
    errors = validate_project_state(tmp_path)
    assert any("phase must be a nonnegative decimal string" in error for error in errors)


def test_project_state_rejects_authoritative_plan_path_escape(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "PROJECT_STATE.yaml").write_text(
        "\n".join(
            (
                'phase: "0.5"',
                "phase_name: reading-reconciliation",
                "phase_status: in-progress",
                "paid_compute_allowed: false",
                "prototype_execution_allowed: false",
                "benchmark_execution_allowed: false",
                "training_allowed: false",
                "cloud_mutation_allowed: false",
                "authoritative_plan: ../outside.md",
            )
        ),
        encoding="utf-8",
    )
    errors = validate_project_state(tmp_path)
    assert any("authoritative_plan is invalid" in error for error in errors)


def test_repository_contract_passes() -> None:
    assert run_all() == []


def test_rendered_site_validator_detects_broken_links(tmp_path: Path) -> None:
    site = tmp_path / "_site"
    for relative in (
        "generated/status.html",
        "generated/experiments.html",
        "generated/decisions.html",
        "generated/falsification.html",
        "failures/index.html",
        "weekly/index.html",
    ):
        path = site / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("<html></html>", encoding="utf-8")
    (site / "index.html").write_text('<a href="missing.html">missing</a>', encoding="utf-8")
    assert any("broken rendered target" in error for error in validate_site_output(tmp_path))
