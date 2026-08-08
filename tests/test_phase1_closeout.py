from __future__ import annotations

from giclab.registry import load_json, load_yaml
from giclab.validation import ROOT

EXP_ROOT = ROOT / "experiments/EXP-0001-sira-simulative-vs-reactive"
PHASE_075_PLAN = (
    ROOT / "docs/exec-plans/completed/PHASE_0_75_UPSTREAM_AUDIT_HARNESS_PROTOCOL_LOCK.md"
)
PHASE_1_PLAN = ROOT / "docs/exec-plans/active/PHASE_1_ARTIFACT_EXECUTION.md"


def test_phase_one_is_the_only_active_non_executable_control_plane() -> None:
    state = load_yaml(ROOT / "docs/PROJECT_STATE.yaml")
    assert state["phase"] == "1"
    assert state["phase_name"] == "artifact-execution"
    assert state["phase_status"] == "in-progress"
    assert state["authoritative_plan"] == ("docs/exec-plans/active/PHASE_1_ARTIFACT_EXECUTION.md")
    for field in (
        "paid_compute_allowed",
        "prototype_execution_allowed",
        "benchmark_execution_allowed",
        "training_allowed",
        "cloud_mutation_allowed",
    ):
        assert state[field] is False
    assert state["authorized_run_profile"] == {
        "plan_id": None,
        "profile_path": None,
        "profile_sha256": None,
        "condition_plan_sha256s": [],
    }
    assert [path.name for path in (ROOT / "docs/exec-plans/active").glob("*.md")] == [
        "PHASE_1_ARTIFACT_EXECUTION.md"
    ]
    assert "Status: **successful**" in PHASE_075_PLAN.read_text(encoding="utf-8")
    assert "Status: **in-progress**" in PHASE_1_PLAN.read_text(encoding="utf-8")


def test_only_the_smoke_profile_is_eligible_for_later_authorization() -> None:
    smoke = load_yaml(EXP_ROOT / "run-plans/smoke.yaml")
    pilot = load_yaml(EXP_ROOT / "run-plans/pilot.yaml")
    assert smoke["plan_id"] == "PLAN-EXP0001-SMOKE"
    assert smoke["execution"] == {
        "authorized": False,
        "authorization_reference": None,
    }
    assert smoke["readiness"]["execution_eligibility"] == "eligible-after-authorization"
    assert smoke["readiness"]["unresolved_execution_blockers"] == []
    assert smoke["readiness"]["pre_execution_requirements"]
    assert pilot["execution"]["authorized"] is False
    assert pilot["readiness"]["execution_eligibility"] == "blocked-pending-prerequisites"
    assert pilot["readiness"]["unresolved_execution_blockers"]
    for relative in smoke["condition_plan_paths"] + pilot["condition_plan_paths"]:
        condition = load_yaml(ROOT / relative)
        assert condition["execution"]["authorization"] == {
            "authorized": False,
            "authorization_reference": None,
            "command_sha256": None,
        }
        parent = smoke if condition["profile"] == "smoke" else pilot
        assert condition["profile_plan_id"] == parent["plan_id"]


def test_exp0001_readme_assigns_materialization_to_t07_not_completed_t06() -> None:
    readme = " ".join((EXP_ROOT / "README.md").read_text(encoding="utf-8").split())
    assert "T07 preflight must bind the exact snapshot before execution" in readme
    assert "T07 must then satisfy its deterministic pre-execution requirements" in readme
    assert "not unresolved integration blockers" in readme
    assert "later integration must bind" not in readme
    assert "T06 or a later approved integration" not in readme


def test_readiness_names_every_exact_decision_and_future_track_boundary() -> None:
    readiness = (ROOT / "docs/readiness/PHASE_1_SMOKE_READINESS.md").read_text(encoding="utf-8")
    for required in (
        "`PLAN-EXP0001-SMOKE`",
        "`api_provider`",
        "`model_revision`",
        "`maximum_api_cost_usd`",
        "`maximum_wall_time_seconds`",
        "`required_cleanup`",
        "USD 4.00",
        "regulation_decision",
        "source_kind: experiment_assignment",
        "Rollback and cleanup",
        "Unresolved nonblocking questions",
        "infrastructure evidence only",
    ):
        assert required in readiness
    assert "not authorization" in readiness


def test_exp0001_science_and_h2k_boundary_remain_orthogonal() -> None:
    protocol = load_yaml(EXP_ROOT / "protocol.yaml")
    config = load_yaml(EXP_ROOT / "config.yaml")
    appendix = load_yaml(EXP_ROOT / "EVIDENCE_RETENTION_APPENDIX.yaml")
    registry = load_yaml(ROOT / "experiments/registry.yaml")
    assert protocol["systems"] == {
        "treatment": "SIRA-SIMULATIVE",
        "controls": ["SIRA-REACTIVE"],
    }
    assert {condition["id"] for condition in config["conditions"].values()} == {
        "SIRA-SIMULATIVE",
        "SIRA-REACTIVE",
    }
    assert appendix["scientific_effect_on_exp0001"] == "none"
    assert appendix["future_consumer"] == "RQ-H2K"
    assert [entry["experiment_id"] for entry in registry["experiments"]] == ["EXP-0001"]
    phase_plan = PHASE_1_PLAN.read_text(encoding="utf-8")
    assert "Phase 2" in phase_plan and "Out of scope" in phase_plan
    assert "| T16 |" not in phase_plan


def test_closeout_retains_zero_execution_and_empty_evidence_state() -> None:
    compute = load_yaml(ROOT / "manifests/compute.yaml")
    results = load_json(EXP_ROOT / "results-summary.json")
    assert compute["entries"] == []
    summary = compute["phase_zero_summary"]
    assert summary["period_end"] == "2026-08-08"
    assert summary["paid_compute_authorized"] is False
    assert summary["cloud_mutations"] == 0
    assert summary["accelerator_hours"] == 0
    assert summary["cost_usd"] == 0
    assert summary["prototype_runs"] == 0
    assert summary["benchmark_runs"] == 0
    assert summary["training_runs"] == 0
    assert results["run_status"] == "not-run"
    assert results["measurements"] == []
    assert results["artifacts"] == []
    assert not (ROOT / "artifacts").exists()
    assert not (ROOT / "traces").exists()


def test_public_surfaces_report_the_current_phase_and_single_next_gate() -> None:
    readme = " ".join((ROOT / "README.md").read_text(encoding="utf-8").split())
    home = " ".join((ROOT / "notebook/index.qmd").read_text(encoding="utf-8").split())
    note = " ".join(
        (ROOT / "notebook/weekly/2026-08-08-phase-1.qmd").read_text(encoding="utf-8").split()
    )
    for page in (readme, home, note):
        assert "Phase 1" in page
        assert "PLAN-EXP0001-SMOKE" in page or "smoke profile" in page
        assert "not authorization" in page


def test_resource_and_research_pages_do_not_reopen_completed_phase_zero_work() -> None:
    resources = " ".join((ROOT / "notebook/resources.qmd").read_text(encoding="utf-8").split())
    questions = " ".join((ROOT / "docs/RESEARCH_QUESTIONS.md").read_text(encoding="utf-8").split())
    assert "datasets.yaml` — currently empty" not in resources
    assert "zero-use Phase 0 compute ledger" not in resources
    assert "audited dataset identities" in resources
    assert "Phase 0.5 should reconcile" not in questions
    assert "A later Phase 1 protocol must select" not in questions
    assert "PLAN-EXP0001-SMOKE" in questions
