from __future__ import annotations

import ast
import hashlib
from copy import deepcopy
from decimal import Decimal
from pathlib import Path

import pytest

from giclab.harness import t08_sira_smoke as t08
from giclab.harness.plan import load_run_plan
from giclab.registry import load_json, load_yaml
from giclab.validation import ROOT, validate_instance

EXP_ROOT = ROOT / "experiments/EXP-0001-sira-simulative-vs-reactive"
ADJUDICATION_PATH = EXP_ROOT / "T08_SMOKE_ADJUDICATION.json"
PAIR_DIFF_PATH = EXP_ROOT / "T08_SMOKE_PAIR_DIFF.json"


def test_t08_disposition_and_pair_diff_are_schema_valid() -> None:
    adjudication = load_json(ADJUDICATION_PATH)
    pair_diff = load_json(PAIR_DIFF_PATH)
    assert (
        validate_instance(
            adjudication,
            ROOT / "schemas/t08-sira-smoke-adjudication.schema.json",
        )
        == []
    )
    assert (
        validate_instance(
            pair_diff,
            ROOT / "schemas/t08-sira-smoke-pair-diff.schema.json",
        )
        == []
    )
    assert adjudication["terminal_state"] == ("smoke_evidence_validated_pilot_planning_eligible")
    assert adjudication["scientific_interpretation_allowed"] is False
    assert adjudication["pilot"]["execution_authorized"] is False
    assert pair_diff["classification"] == ("matched_pair_valid_with_documented_evidence_gaps")
    assert pair_diff["valid"] is True


def test_t08_schema_rejects_terminal_science_and_pair_contradictions() -> None:
    adjudication = load_json(ADJUDICATION_PATH)
    schema = ROOT / "schemas/t08-sira-smoke-adjudication.schema.json"
    interpreting = deepcopy(adjudication)
    interpreting["scientific_interpretation_allowed"] = True
    assert validate_instance(interpreting, schema)
    unauthorized_terminal = deepcopy(adjudication)
    unauthorized_terminal["terminal_state"] = "not-a-t08-terminal-state"
    assert validate_instance(unauthorized_terminal, schema)
    ineligible = deepcopy(adjudication)
    ineligible["pilot"]["protocol_preparation_eligible"] = False
    assert validate_instance(ineligible, schema)

    pair = load_json(PAIR_DIFF_PATH)
    invalid = deepcopy(pair)
    invalid["classification"] = "matched_pair_invalid"
    assert validate_instance(
        invalid,
        ROOT / "schemas/t08-sira-smoke-pair-diff.schema.json",
    )


def test_every_requested_condition_field_has_explicit_provenance() -> None:
    adjudication = load_json(ADJUDICATION_PATH)
    expected_fields = {
        "exact_command",
        "resolved_configuration",
        "task_query",
        "condition_mode",
        "working_directory",
        "environment_identity",
        "python_runtime",
        "container_image",
        "model_revision_by_role",
        "service_tier",
        "maximum_browser_steps",
        "start_timestamp",
        "stop_timestamp",
        "terminal_status",
        "model_call_sequence",
        "provider_usage_records",
        "browser_actions",
        "output_locations",
        "session_json",
        "text_logs",
        "screenshots",
        "normalized_events",
        "regulation_decision_record",
        "cleanup_record",
    }
    for mode in ("reactive", "simulative"):
        condition = adjudication["conditions"][mode]
        assert set(condition["reconstruction"]) == expected_fields
        assert condition["artifact_execution"] == "passed"
        basis = condition["artifact_execution_basis"]
        assert set(basis) == {
            "runtime_initialized",
            "model_requests_issued",
            "browser_action_performed",
            "session_evidence_written",
            "normal_exit",
            "owned_state_cleanup",
        }
        assert basis["browser_action_performed"]["provenance"] == "inferred"
        assert all(item["value"] is True for item in basis.values())
        assert condition["task_completion"] == "not_observed"
        assert condition["session_is_complete"] is False
        for field in condition["reconstruction"].values():
            assert field["provenance"] in {
                "observed",
                "derived",
                "inferred",
                "unavailable",
            }
            if field["provenance"] == "unavailable":
                assert field["value"] is None
            else:
                assert field["evidence_refs"]
    assert (
        adjudication["conditions"]["simulative"]["reconstruction"]["model_call_sequence"][
            "provenance"
        ]
        == "inferred"
    )
    for mode in ("reactive", "simulative"):
        browser = adjudication["conditions"][mode]["reconstruction"]["browser_actions"]
        assert browser["provenance"] == "inferred"
        assert browser["value"]["recorded_request_count"] == 1
        assert browser["value"]["structured_execution_results"] is None
        event_types = {
            item["event_type"]
            for item in adjudication["conditions"][mode]["reconstruction"]["normalized_events"][
                "value"
            ]
        }
        assert "requested_action" in event_types
        assert "executed_action" not in event_types


def test_pair_diff_recomputes_only_approved_differences() -> None:
    pair = load_json(PAIR_DIFF_PATH)
    assert pair["invalidating_differences"] == []
    assert {item["field"] for item in pair["equalities"]} == {
        "frozen_git_commit",
        "sira_commit",
        "task",
        "python_version",
        "dependencies",
        "container_image",
        "browser_runtime",
        "model_snapshot",
        "model_role_routing",
        "instrumentation_and_evidence_code",
        "cost_calculation",
        "environment",
        "tools",
        "maximum_browser_steps",
        "execution_host_class",
    }
    command = pair["command_diff"]
    assert command["command_length"] == 79
    assert [(item["index"], item["field"]) for item in command["differences"]] == [
        (5, "container_name"),
        (35, "attempt_root"),
        (41, "condition_label"),
        (56, "gate_mode"),
        (60, "job_name"),
        (64, "upstream_mode"),
    ]
    assert pair["configuration_diff"]["approved_difference_fields"] == [
        "condition",
        "docker_argv",
        "model_call_attempt_cap",
        "order",
    ]
    bases = {item["field"]: item["comparison_basis"] for item in pair["equalities"]}
    assert bases["frozen_git_commit"] == "shared-immutable-binding"
    assert bases["task"] == "condition-owned-records-and-shared-binding"
    assert bases["environment"] == "condition-owned-records"
    assert bases["cost_calculation"] == "shared-recomputation-method"


def test_t08_exact_decimal_accounting_reconciles() -> None:
    assert t08.recompute_cost(
        input_tokens=4626,
        cached_input_tokens=0,
        output_tokens=260,
    ) == Decimal("0.014165")
    assert t08.recompute_cost(
        input_tokens=5447,
        cached_input_tokens=0,
        output_tokens=1255,
    ) == Decimal("0.0261675")
    adjudication = load_json(ADJUDICATION_PATH)
    aggregate = adjudication["accounting_reconciliation"]["aggregate"]
    assert aggregate == {
        "browser_actions": 2,
        "cached_input_tokens": 0,
        "input_tokens": 10073,
        "model_calls": 9,
        "output_tokens": 1515,
        "recomputed_cost_usd": "0.0403325",
        "total_tokens": 11588,
        "unreconciled_provider_attempts": 0,
        "wall_seconds_display_3dp": "39.397",
        "wall_seconds_raw": "39.397491319999743",
    }
    assert adjudication["accounting_reconciliation"]["per_call_usage"] == {
        "evidence_refs": [],
        "note": "No raw per-call provider usage receipt was retained.",
        "provenance": "unavailable",
        "value": None,
    }


def test_archive_and_filesystem_manifest_verifiers_detect_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = b"retained evidence\n"
    manifest = {
        "files": [
            {
                "bytes": len(payload),
                "path": "evidence/payload.txt",
                "sha256": t08.sha256_bytes(payload),
            }
        ],
        "total_bytes": len(payload),
    }
    encoded = t08.canonical_json(manifest)
    monkeypatch.setattr(t08, "REMOTE_MANIFEST_SHA256", t08.sha256_bytes(encoded))
    files = {
        "evidence-manifest.json": encoded,
        "evidence/payload.txt": payload,
    }
    assert t08.verify_archive_manifest(files) == {
        "file_count": 1,
        "total_bytes": len(payload),
        "mismatches": 0,
    }
    corrupted = dict(files)
    corrupted["evidence/payload.txt"] = b"drift"
    with pytest.raises(t08.T08EvidenceError, match="payload drifted"):
        t08.verify_archive_manifest(corrupted)

    evidence = tmp_path / "evidence"
    evidence.mkdir()
    (evidence / "payload.txt").write_bytes(payload)
    filesystem_manifest = {
        "file_count": 1,
        "total_bytes": len(payload),
        "files": manifest["files"],
    }
    assert (
        t08.verify_filesystem_manifest(
            tmp_path,
            filesystem_manifest,
            context="synthetic retained evidence",
        )["mismatches"]
        == 0
    )
    (evidence / "payload.txt").write_bytes(b"drift")
    with pytest.raises(t08.T08EvidenceError, match="payload drifted"):
        t08.verify_filesystem_manifest(
            tmp_path,
            filesystem_manifest,
            context="synthetic retained evidence",
        )


def test_pilot_profile_has_explicit_unauthorized_sample_and_budget_contract() -> None:
    pilot_path = EXP_ROOT / "run-plans/pilot.yaml"
    pilot = load_yaml(pilot_path)
    assert validate_instance(pilot, ROOT / "schemas/run-profile.schema.json") == []
    assert pilot["execution"] == {"authorized": False, "authorization_reference": None}
    assert pilot["sampling"]["pair_count"] == 2
    assert pilot["budget"] == {
        "pricing_record": ("experiments/EXP-0001-sira-simulative-vs-reactive/pricing.yaml"),
        "max_cost_usd": 40.0,
        "max_provider_compute_cost_usd": 5.16,
        "max_total_cost_usd": 45.16,
        "max_model_calls": 4620,
        "max_model_tokens": 4_000_000,
        "max_browser_actions": 120,
        "max_wall_seconds": 14_400,
        "max_accelerator_hours": 4.0,
        "prior_t09_cost_usd": 0.414064252316667,
        "cumulative_t09_cost_cap_usd": 46.0,
        "condition_limits": {
            "SIRA-REACTIVE": {
                "attempts": 2,
                "max_model_calls_per_attempt": 1155,
                "max_model_tokens_per_attempt": 1_000_000,
                "max_browser_actions_per_attempt": 30,
                "max_wall_seconds_per_attempt": 3600,
                "max_openai_cost_usd_per_attempt": 10.0,
                "max_accelerator_hours_per_attempt": 1.0,
            },
            "SIRA-SIMULATIVE": {
                "attempts": 2,
                "max_model_calls_per_attempt": 1155,
                "max_model_tokens_per_attempt": 1_000_000,
                "max_browser_actions_per_attempt": 30,
                "max_wall_seconds_per_attempt": 3600,
                "max_openai_cost_usd_per_attempt": 10.0,
                "max_accelerator_hours_per_attempt": 1.0,
            },
        },
    }
    profile_sha256 = hashlib.sha256(pilot_path.read_bytes()).hexdigest()
    for relative in pilot["condition_plan_paths"]:
        child = load_yaml(ROOT / relative)
        typed_child = load_run_plan(ROOT / relative, schema_root=ROOT)
        assert child["profile_sha256"] == profile_sha256
        assert child["execution"]["backend"] == "cloud"
        assert child["execution"]["authorization"]["authorized"] is False
        assert child["budget"]["max_gpu_hours"] == 1.0
        expected_model_calls = 1155
        assert child["budget"]["max_model_calls"] == expected_model_calls
        assert typed_child.budget.max_model_calls == expected_model_calls


def test_t08_public_outputs_are_path_and_secret_value_safe() -> None:
    paths = [
        ADJUDICATION_PATH,
        PAIR_DIFF_PATH,
        ROOT / "docs/harness/T08_SIRA_SMOKE_EVIDENCE_ADJUDICATION.md",
        ROOT / "docs/harness/T08_SIRA_SMOKE_EVIDENCE_LEDGER.md",
        ROOT / "docs/harness/T08_SIRA_SMOKE_PAIR_DIFF.md",
        ROOT / "docs/harness/T08_SIRA_PILOT_READINESS.md",
        ROOT / "docs/harness/T09_SIRA_EXPLORATORY_PILOT_PLAN.md",
        ROOT / "docs/harness/T09_SIRA_PILOT_PREAUTHORIZATION_PACKET.md",
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in paths)
    assert "/Users/" not in combined
    assert "/Volumes/" not in combined
    assert '"jupyter_token":' not in combined
    assert '"jupyter_url":' not in combined
    assert "token=" not in combined
    adjudication = load_json(ADJUDICATION_PATH)
    retained = adjudication["cleanup"]["ephemeral_provider_access_material"]
    assert retained["affected_artifact_count"] == 37
    assert retained["secret_values_emitted"] is False
    assert retained["sensitive_key_names"] == ["jupyter_token", "jupyter_url"]


def test_t08_adjudicator_has_no_live_execution_import_surface() -> None:
    source_path = ROOT / "src/giclab/harness/t08_sira_smoke.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    imported_roots = {
        alias.name.split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        (node.module or "").split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    assert imported_roots.isdisjoint(
        {"boto3", "httpx", "openai", "requests", "socket", "subprocess", "urllib"}
    )
    assert not hasattr(t08, "run_sira")


def test_t08_keeps_exp0001_scientifically_pending_and_every_permission_false() -> None:
    results = load_json(EXP_ROOT / "results-summary.json")
    assert results["lifecycle_status"] == "planned"
    assert results["evidence_status"] == "not-evaluated"
    assert results["outcome_status"] == "pending"
    assert len(results["measurements"]) == 1
    assert results["measurements"][0]["kind"] == "descriptive-calibration-attempt"
    assert results["measurements"][0]["paired_result_available"] is False
    assert results["measurements"][0]["interpretation"] == "descriptive-calibration-only"
    state = load_yaml(ROOT / "docs/PROJECT_STATE.yaml")
    for field in (
        "paid_compute_allowed",
        "prototype_execution_allowed",
        "benchmark_execution_allowed",
        "training_allowed",
        "cloud_mutation_allowed",
    ):
        assert state[field] is False
    assert state["t08_checkpoint"]["pilot_execution_authorized"] is False
    assert state["t08_checkpoint"]["scientific_interpretation_allowed"] is False


def test_t08_assembly_and_phase_plan_are_closed_without_pilot_authority() -> None:
    ledger = (ROOT / "docs/harness/T08_SIRA_SMOKE_EVIDENCE_LEDGER.md").read_text(encoding="utf-8")
    plan = (ROOT / "docs/exec-plans/active/PHASE_1_ARTIFACT_EXECUTION.md").read_text(
        encoding="utf-8"
    )
    assert "Assembly status: **complete**" in ledger
    assert "Terminal state: **`smoke_evidence_validated_pilot_planning_eligible`**" in ledger
    assert "| T08-DOD-11 " in ledger and "| met |" in ledger
    assert "| T08-DOD-12 " in ledger and "met; clean commit is the handoff artifact" in ledger
    assert "| P1-DOD-03 " in plan and "report, review, and gate. | met |" in plan
    assert "pilot execution remains unauthorized" in plan
