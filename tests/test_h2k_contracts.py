from __future__ import annotations

from giclab.registry import load_yaml
from giclab.validation import ROOT


def test_h2k_track_is_planned_deferred_and_has_no_active_experiment() -> None:
    track = (ROOT / "docs/H2K_OPTION_PRESERVATION.md").read_text(encoding="utf-8")
    research = (ROOT / "docs/RESEARCH_QUESTIONS.md").read_text(encoding="utf-8")
    decisions = (ROOT / "docs/DECISIONS.md").read_text(encoding="utf-8")
    risks = (ROOT / "docs/RISK_REGISTER.md").read_text(encoding="utf-8")
    notebook = (ROOT / "notebook/research/index.qmd").read_text(encoding="utf-8")
    registry = load_yaml(ROOT / "experiments/registry.yaml")

    assert "Status: **planned/deferred**" in track
    assert "Active experiment: **none**" in track
    assert "Planning regulation is the first candidate mechanism" in track
    assert "EXP-0001 remains" in track and "not an internalization experiment" in track
    assert "adds no Phase 2" in track
    assert "RQ-H2K — Progressive Harness-to-Kernel" in research
    assert "D-014" in decisions
    assert "Fixed external assignment is labeled learned regulation" in risks
    assert "There is no active RQ-H2K experiment" in notebook
    assert [entry["experiment_id"] for entry in registry["experiments"]] == ["EXP-0001"]
    assert all("h2k" not in entry["protocol"].lower() for entry in registry["experiments"])


def test_active_plan_records_successful_t04_5_and_t05() -> None:
    plan = (
        ROOT / "docs/exec-plans/active/PHASE_0_75_UPSTREAM_AUDIT_HARNESS_PROTOCOL_LOCK.md"
    ).read_text(encoding="utf-8")
    assert "T04.5 and T05 are complete; T06 is the next permitted assembly item" in " ".join(
        plan.split()
    )
    assert "| T04.5 | Preserve the planned/deferred" in plan
    assert "P075-DOD-09 |" in plan and "| met |" in plan
    assert "| T05 | Register and lock draft `EXP-0001`" in plan
    assert any(
        line.startswith("| T05 |") and line.endswith("| successful |") for line in plan.splitlines()
    )
    assert "Assembly status: **successful**" in plan
    assert "P075-DOD-09" in plan


def test_sr2am_h2k_addendum_is_source_grounded_and_preserves_unknowns() -> None:
    addendum = load_yaml(ROOT / "docs/audits/sr2am/H2K_TRACE_REQUIREMENTS_ADDENDUM.yaml")
    assert addendum["status"] == "planned-later-phase-capture"
    assert addendum["execution_authorized"] is False
    assert addendum["source"]["commit"] == ("6f4ac7824ffc7d12453ffaa53d25e5f34bf3aeb0")
    required = {
        "explicit_configurator_or_regulation_output",
        "plan_no_plan_choice",
        "plan_horizon_or_depth",
        "structured_predicted_futures",
        "reactive_reasoning_output",
        "action_output",
        "model_identity",
        "prompt_and_template_identity",
        "generation_identity",
        "serving_identity",
        "tool_identity",
        "raw_source_paths",
        "parser_provenance",
    }
    requirements = {item["field"]: item for item in addendum["capture_requirements"]}
    assert set(requirements) == required
    for item in requirements.values():
        assert isinstance(item["source_paths"], list)
        assert item["t02_status"]
        assert item["normalization"]
    assert requirements["plan_no_plan_choice"]["t02_status"] == "unavailable"
    assert requirements["structured_predicted_futures"]["source_paths"] == []
    assert "typed_configurator_decision" in addendum["explicit_unknowns_from_t02"]
    parser_fields = set(addendum["parser_provenance_contract"]["required_fields"])
    assert {
        "parser_id",
        "parser_version",
        "input_artifact_sha256",
        "source_paths_consumed",
        "unavailable_fields",
        "parse_status",
    } <= parser_fields
    assert "latent_internalization_inference" in addendum["analysis_boundary"]["prohibited"]


def test_t04_5_preserves_zero_execution_control_plane() -> None:
    state = load_yaml(ROOT / "docs/PROJECT_STATE.yaml")
    compute = load_yaml(ROOT / "manifests/compute.yaml")
    for key in (
        "paid_compute_allowed",
        "prototype_execution_allowed",
        "benchmark_execution_allowed",
        "training_allowed",
        "cloud_mutation_allowed",
    ):
        assert state[key] is False
    summary = compute["phase_zero_summary"]
    assert summary["cloud_mutations"] == 0
    assert summary["accelerator_hours"] == 0
    assert summary["cost_usd"] == 0
    assert summary["prototype_runs"] == 0
    assert summary["benchmark_runs"] == 0
    assert summary["training_runs"] == 0
    assert compute["entries"] == []
