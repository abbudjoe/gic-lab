from __future__ import annotations

import hashlib

from giclab.harness.policy import load_project_execution_state
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
    assert state["planned_execution_substrate"] == {
        "decision_state": "lambda-host-selected-design-only",
        "provider": "lambda-on-demand-cloud",
        "architecture": "x86_64",
        "persistent_filesystem": False,
        "gate_l1_authorized": False,
        "gate_l1_evidence_state": "complete-externally-sealed",
        "gate_l2_authorized": False,
        "gate_l2_decision_state": "inventory-evidence-insufficient",
        "gate_l3_state": "requirements-only",
        "gate_l4_authorized": False,
        "local_alternatives": "terminal-rejected",
        "decision_document": "docs/harness/T07_GATE_L0_LAMBDA_HOST_DECISION.md",
        "security_decision_document": (
            "docs/harness/T07_GATE_L2_RESOURCE_AND_SECURITY_DECISION_PACKET.md"
        ),
    }
    execution_state = load_project_execution_state(ROOT)
    substrate = execution_state.planned_execution_substrate
    assert substrate is not None
    assert substrate.decision_state == "lambda-host-selected-design-only"
    assert substrate.provider == "lambda-on-demand-cloud"
    assert substrate.architecture == "x86_64"
    assert substrate.gate_l1_evidence_state == "complete-externally-sealed"
    assert substrate.gate_l2_decision_state == "inventory-evidence-insufficient"
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


def test_t07_l13_preserves_all_five_locked_scientific_file_hashes() -> None:
    locked = {
        EXP_ROOT / "protocol.yaml": (
            "5bdf3fdcf2c486883ad74044bd373c1804362c7d9ad8e990f5e10fa1c0f99b4c"
        ),
        EXP_ROOT / "config.yaml": (
            "f05767de862f3f519f429f5b73baa67043ed96209f3d47db9fd2d084847ec16d"
        ),
        EXP_ROOT / "run-plans/smoke.yaml": (
            "ab276b9e49256d49f143e252eddf6fe5c447d6f9c11300745b450fb7f1d0e425"
        ),
        EXP_ROOT / "run-plans/conditions/smoke-reactive.yaml": (
            "7ca19470e550e48978090c9b7014e047c56d80962e40275b846f589b08bfb018"
        ),
        EXP_ROOT / "run-plans/conditions/smoke-simulative.yaml": (
            "68f5f4a4a123620bab039ba7bc6844243cad229ed992df6562bf0d8562874436"
        ),
    }
    for path, expected in locked.items():
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected


def test_t07_l14_one_request_plan_is_fresh_unauthorized_and_unexecuted() -> None:
    relative = "containers/sira-smoke/lambda/gate-l1a-ssh-key-fingerprint-plan-v1.json"
    path = ROOT / relative
    encoded = path.read_bytes()
    assert len(encoded) == 12_448
    assert hashlib.sha256(encoded).hexdigest() == (
        "23b29823b8daf94cfb463b275149ed562656c735955a4f449b8703334de531bc"
    )
    plan = load_json(path)
    assert plan["plan_id"] == "PLAN-T07-GATE-L1A-LAMBDA-SSH-KEY-FINGERPRINT-V1"
    assert plan["run_identity"]["run_id"] == ("RUN-T07-L1A-LAMBDA-SSH-KEY-FINGERPRINT-0001")
    assert plan["authorization"] == {
        "authorized": False,
        "authorization_reference": ("AUTH-T07-GATE-L1A-LAMBDA-SSH-KEY-FINGERPRINT-V1-PENDING"),
    }
    assert plan["requests"] == [
        {
            "request_id": "ssh-key-fingerprints",
            "method": "GET",
            "scheme": "https",
            "host": "cloud.lambda.ai",
            "path": "/api/v1/ssh-keys",
            "query_key_names": [],
            "max_response_bytes": 131072,
            "response_schema_path": (
                "containers/sira-smoke/lambda/endpoint-schemas-l1a/ssh-keys.schema.json"
            ),
            "response_schema_sha256": (
                "3cceae5b7fdea392cd16197533c32fb9a240dcdd6bff734f25db31c0baae615c"
            ),
        }
    ]
    assert not (
        ROOT / "artifacts/t07/lambda/gate-l1a/RUN-T07-L1A-LAMBDA-SSH-KEY-FINGERPRINT-0001"
    ).exists()


def test_t07_l14_public_surfaces_keep_key_evidence_pending_and_l2_blocked() -> None:
    surfaces = [
        ROOT / "docs/harness/T07_GATE_L1_4_SSH_KEY_FINGERPRINT_DESIGN.md",
        ROOT / "docs/harness/T07_GATE_L1A_SSH_KEY_AUTHORIZATION_PACKET.md",
        ROOT / "docs/harness/T07_GATE_L2_RESOURCE_AND_SECURITY_DECISION_PACKET.md",
        ROOT / "docs/readiness/PHASE_1_SMOKE_READINESS.md",
        ROOT / "docs/exec-plans/active/PHASE_1_ARTIFACT_EXECUTION.md",
        ROOT / "notebook/weekly/2026-08-08-phase-1.qmd",
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in surfaces)
    for required in (
        "PLAN-T07-GATE-L1A-LAMBDA-SSH-KEY-FINGERPRINT-V1",
        "RUN-T07-L1A-LAMBDA-SSH-KEY-FINGERPRINT-0001",
        "unauthorized",
        "Gate L2",
    ):
        assert required in combined
    assert "no key is selected" in combined or "does not select one" in combined


def test_closeout_retains_zero_scientific_execution_and_only_bounded_infrastructure() -> None:
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
    run2_root = "artifacts/t07/lambda/gate-l1/RUN-T07-L1-LAMBDA-INVENTORY-0002"
    run3_root = "artifacts/t07/lambda/gate-l1/RUN-T07-L1-LAMBDA-INVENTORY-0003"
    alias_root = "artifacts/t07/lambda/gate-l1-3/RUN-T07-L1-LAMBDA-INVENTORY-0003"
    retained_hashes = {
        f"{run2_root}/request-ledger.jsonl": (
            "a1cb81ce286881c33d879ce73787e755eed8ecd1f64ca2b9eaca7d39824a2c94"
        ),
        f"{run3_root}/request-ledger.jsonl": (
            "1f94068bdb1d1d2af0075d50c1a0c06eb1c077d4128f90bdc16fd571fa6af707"
        ),
        f"{run3_root}/inventory-redacted.json": (
            "022835438165e7e6e70dc992d6904f4e8b9448dc933d1d4c3e39ebdcc8914933"
        ),
        f"{run3_root}/inventory-copy-record.json": (
            "65068ff4884880ac8e6568652c0aba089e39c8fea621c4544e4da46edd01a5a8"
        ),
        f"{alias_root}/image-id-alias-map.json": (
            "9f37b9412110cc7433d5339cf4d8b1eadc92743eaa32db6bf8e4c59024a79d5f"
        ),
        f"{alias_root}/IMAGE_ALIAS_MAP_SEAL.json": (
            "ed3fb1ef3323f2b37150204ef060250e4f9510bbeb976d18d2fd1b8d9894c0b5"
        ),
    }
    retained_files = {
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / "artifacts").rglob("*")
        if path.is_file()
    }
    assert retained_files == set(retained_hashes)
    for relative, expected in retained_hashes.items():
        assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == expected
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
