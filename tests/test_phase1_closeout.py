from __future__ import annotations

import hashlib
import re
import subprocess

from giclab.harness.policy import load_project_execution_state
from giclab.registry import load_json, load_yaml
from giclab.validation import ROOT, validate_instance

EXP_ROOT = ROOT / "experiments/EXP-0001-sira-simulative-vs-reactive"
TERMINAL_CONTROL_PATH = EXP_ROOT / "T09_PRAGMATIC_RETRY5_POSTRUN_TERMINAL_CONTROL.json"
RETRY3_TERMINAL_CONTROL_PATH = EXP_ROOT / "T09_PRAGMATIC_RETRY3_TERMINAL_CONTROL.json"
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
    assert state["current_execution_control"] == {
        "path": TERMINAL_CONTROL_PATH.relative_to(ROOT).as_posix(),
        "sha256": hashlib.sha256(TERMINAL_CONTROL_PATH.read_bytes()).hexdigest(),
    }
    assert state["planned_execution_substrate"] is None
    assert state["historical_execution_substrate"] == {
        "decision_state": "bounded-smoke-v3-ready-unauthorized",
        "provider": "lambda-on-demand-cloud",
        "architecture": "x86_64",
        "persistent_filesystem": False,
        "gate_l1_authorized": False,
        "gate_l1_evidence_state": "complete-externally-sealed",
        "gate_l2_authorized": False,
        "gate_l2_decision_state": "bounded-manual-console-plan-ready-unauthorized",
        "gate_l3_state": "folded-into-bounded-preflight-unauthorized",
        "gate_l4_authorized": False,
        "local_alternatives": "terminal-rejected",
        "decision_document": "docs/harness/T07_BOUNDED_SMOKE_GOVERNANCE.md",
        "security_decision_document": ("docs/harness/T07_BOUNDED_SMOKE_SECURITY_BINDING_REPAIR.md"),
    }
    execution_state = load_project_execution_state(ROOT)
    assert execution_state.planned_execution_substrate is None
    assert execution_state.terminal_execution_control is not None
    assert execution_state.terminal_execution_control.superseded_plan_ids == frozenset(
        {"PLAN-EXP0001-SMOKE", "PLAN-EXP0001-PILOT-V6", "PLAN-EXP0001-PILOT-V7"}
    )
    assert execution_state.terminal_execution_control.registered_successor is None
    checkpoint = state["t08_checkpoint"]
    assert checkpoint["terminal_state"] == ("smoke_evidence_validated_pilot_planning_eligible")
    assert checkpoint["pilot_execution_authorized"] is False
    assert checkpoint["scientific_interpretation_allowed"] is False
    t09_checkpoint = state["t09_pragmatic_pilot_checkpoint"]
    assert t09_checkpoint["terminal_state"] == "t09-pilot-blocked-material-risk"
    assert t09_checkpoint["plan_id"] == "PLAN-EXP0001-PILOT-V3"
    assert t09_checkpoint["current_execution_and_analysis_blockers"] == [
        "exact-frozen-T07-container-image-unavailable-as-loadable-artifact"
    ]
    assert t09_checkpoint["future_execution_requires_dynamic_preflight"] is True
    assert t09_checkpoint["pilot_execution_authorized"] is False
    assert t09_checkpoint["current_turn_execution_authorized"] is False
    assert t09_checkpoint["single_use_authority_exhausted"] is True
    assert t09_checkpoint["dynamic_preflight_passed"] is False
    assert t09_checkpoint["empirical_attempts_entered"] == 0
    assert t09_checkpoint["evaluator_attempts_entered"] == 0
    assert t09_checkpoint["model_calls"] == 0
    assert t09_checkpoint["total_tokens"] == 0
    assert t09_checkpoint["browser_actions"] == 0
    assert t09_checkpoint["openai_cost_usd"] == 0.0
    assert t09_checkpoint["lambda_cost_usd"] == 0.414064252316667
    assert t09_checkpoint["cleanup_verified"] is True
    assert t09_checkpoint["scientific_result_claimed"] is False
    retry2 = state["t09_pragmatic_retry2_checkpoint"]
    assert retry2["plan_id"] == "PLAN-EXP0001-PILOT-V4"
    assert retry2["terminal_state"] == "t09-pilot-blocked-material-risk"
    assert retry2["current_turn_execution_authorized"] is False
    assert retry2["repository_plan_authorized"] is False
    assert retry2["single_use_authority_exhausted"] is True
    assert retry2["replacement_image_qualified"] is True
    assert retry2["dynamic_preflight_passed"] is True
    assert retry2["empirical_attempts_entered"] == 1
    assert retry2["attempts_completed"] == 1
    assert retry2["condition_retries"] == 0
    assert retry2["task_model_calls"] == 52
    assert retry2["total_tokens"] == 121900
    assert retry2["browser_actions"] == 13
    assert retry2["task_a_reactive"]["score"] == 0.0
    assert retry2["task_a_simulative"] == "not-run"
    assert retry2["task_b_simulative"] == "not-run"
    assert retry2["task_b_reactive"] == "not-run"
    assert retry2["realized_pairs"] == 0
    assert retry2["prior_t09_cost_usd"] == 0.414064252316667
    assert retry2["openai_cost_usd"] == 0.3626425
    assert retry2["lambda_cost_usd"] == 1.754109703373909
    assert retry2["new_campaign_total_cost_usd"] == 2.116752203373909
    assert retry2["cumulative_t09_cost_usd"] == 2.5308164556905757
    assert retry2["cumulative_t09_cost_cap_usd"] == 46.0
    assert retry2["cleanup_verified"] is True
    assert retry2["provider_terminal_or_absent"] is True
    assert retry2["zero_t09_instances"] is True
    assert retry2["security_restored"] is True
    assert retry2["scientific_result_claimed"] is False
    assert retry2["experiment_outcome_assigned"] is False
    retry3 = state["t09_pragmatic_retry3_checkpoint"]
    assert retry3["plan_id"] == "PLAN-EXP0001-PILOT-V5"
    assert retry3["terminal_state"] == "t09-pilot-blocked-material-risk"
    assert retry3["current_turn_execution_authorized"] is False
    assert retry3["repository_plan_authorized"] is False
    assert retry3["single_use_authority_exhausted"] is True
    assert retry3["launch_slots_exhausted"] is True
    assert retry3["provider_launch_count"] == retry3["maximum_launch_count"] == 2
    assert retry3["replacement_image_archive_preserved"] is True
    assert retry3["replacement_image_qualified"] is False
    assert retry3["dynamic_preflight_passed"] is False
    assert retry3["frozen_run_manifest_written"] is False
    assert retry3["empirical_attempts_entered"] == 0
    assert retry3["attempts_completed"] == 0
    assert retry3["condition_retries"] == 0
    assert retry3["model_metadata_requests"] == 0
    assert retry3["task_model_calls"] == 0
    assert retry3["total_tokens"] == 0
    assert retry3["browser_actions"] == 0
    assert retry3["realized_pairs"] == 0
    assert retry3["openai_cost_usd"] == 0.0
    assert retry3["lambda_cost_usd"] == 1.5106036795496942
    assert retry3["cumulative_t09_cost_usd"] == 4.04142013524027
    assert retry3["cleanup_verified"] is True
    assert retry3["provider_terminal_or_absent"] is True
    assert retry3["zero_t09_instances"] is True
    assert retry3["security_restored"] is True
    assert retry3["scientific_result_claimed"] is False
    assert retry3["experiment_outcome_assigned"] is False
    retry4 = state["t09_pragmatic_retry4_checkpoint"]
    assert retry4["plan_id"] == "PLAN-EXP0001-PILOT-V6"
    assert retry4["terminal_state"] == "t09-pilot-blocked-material-risk"
    assert retry4["current_turn_execution_authorized"] is False
    assert retry4["repository_plan_authorized"] is False
    assert retry4["single_use_authority_exhausted"] is True
    assert retry4["launch_slots_exhausted"] is True
    assert retry4["provider_launch_count"] == retry4["maximum_launch_count"] == 2
    assert retry4["retained_image_archive_verified"] is True
    assert retry4["dynamic_preflight_passed"] is True
    assert retry4["frozen_run_manifest_written"] is True
    assert retry4["empirical_attempts_entered"] == 1
    assert retry4["raw_attempts_complete"] == 0
    assert retry4["attempts_completed"] == 0
    assert retry4["condition_retries"] == 0
    assert retry4["model_metadata_requests"] == 2
    assert retry4["task_model_calls"] == 20
    assert retry4["total_tokens"] == 38_779
    assert retry4["browser_actions"] == 5
    assert retry4["realized_pairs"] == 0
    assert retry4["openai_cost_usd"] == 0.11752750000000001
    assert retry4["lambda_cost_usd"] == 1.583502975910902
    assert retry4["cumulative_t09_cost_usd"] == 5.742450611151172
    assert retry4["cleanup_verified"] is True
    assert retry4["provider_terminal_or_absent"] is True
    assert retry4["zero_t09_instances"] is True
    assert retry4["security_restored"] is True
    assert retry4["evidence_archive_original_preserved_byte_exact"] is True
    assert retry4["evidence_archive_posttermination_overlay_id"] == (
        "ARCHIVE-EXP0001-PILOT-V6-0004-POSTRUN-OVERLAY-0001"
    )
    assert retry4["evidence_archive_frozen_runtime_reconstructable_with_overlay"] is True
    assert retry4["scientific_result_claimed"] is False
    assert retry4["experiment_outcome_assigned"] is False
    retry5 = state["t09_pragmatic_retry5_checkpoint"]
    assert retry5["plan_id"] == "PLAN-EXP0001-PILOT-V7"
    assert retry5["terminal_state"] == "t09-pilot-blocked-material-risk"
    assert retry5["failure_state"] == "preempirical-control-binding-failure"
    assert retry5["current_turn_execution_authorized"] is False
    assert retry5["repository_plan_authorized"] is False
    assert retry5["single_use_authority_exhausted"] is True
    assert retry5["launch_slots_exhausted"] is True
    assert retry5["provider_launch_count"] == retry5["maximum_launch_count"] == 2
    assert retry5["retained_image_archive_verified_on_slot2"] is True
    assert retry5["replacement_image_imported"] is False
    assert retry5["dynamic_preflight_passed"] is False
    assert retry5["frozen_run_manifest_written"] is False
    assert retry5["empirical_attempts_entered"] == 0
    assert retry5["attempts_completed"] == 0
    assert retry5["condition_retries"] == 0
    assert retry5["model_metadata_requests"] == 0
    assert retry5["task_model_calls"] == 0
    assert retry5["total_tokens"] == 0
    assert retry5["browser_actions"] == 0
    assert retry5["realized_pairs"] == 0
    assert retry5["openai_cost_usd"] == 0.0
    assert retry5["lambda_cost_usd"] == 1.0706881238281727
    assert retry5["cumulative_t09_cost_usd"] == 6.813138735028173
    assert retry5["provider_terminal_or_absent"] is True
    assert retry5["zero_t09_instances"] is True
    assert retry5["security_restored"] is True
    assert retry5["host_cleanup_completion_receipt_available"] is False
    assert retry5["scientific_result_claimed"] is False
    assert retry5["experiment_outcome_assigned"] is False
    assert {path.name for path in (ROOT / "docs/exec-plans/active").glob("*.md")} == {
        "PHASE_1_ARTIFACT_EXECUTION.md"
    }
    assert (ROOT / "docs/harness/T09_PRAGMATIC_RETRY2_EXECUTION_PLAN.md").is_file()
    assert "Status: **successful**" in PHASE_075_PLAN.read_text(encoding="utf-8")
    assert "Status: **in-progress**" in PHASE_1_PLAN.read_text(encoding="utf-8")


def test_frozen_profiles_are_unauthorized_and_postrun_control_makes_them_nonreplayable() -> None:
    smoke = load_yaml(EXP_ROOT / "run-plans/smoke.yaml")
    pilot = load_yaml(EXP_ROOT / "run-plans/pilot.yaml")
    archived_v6 = load_yaml(EXP_ROOT / "run-plans/proposals/PLAN-EXP0001-PILOT-V6.yaml")
    terminal = load_json(TERMINAL_CONTROL_PATH)
    registry = load_yaml(ROOT / "experiments/registry.yaml")["experiments"][0]
    assert smoke["plan_id"] == "PLAN-EXP0001-SMOKE"
    assert smoke["execution"] == {
        "authorized": False,
        "authorization_reference": None,
    }
    assert smoke["readiness"]["execution_eligibility"] == "eligible-after-authorization"
    assert smoke["readiness"]["unresolved_execution_blockers"] == []
    assert smoke["readiness"]["pre_execution_requirements"]
    assert archived_v6["plan_id"] == "PLAN-EXP0001-PILOT-V6"
    assert pilot["plan_id"] == "PLAN-EXP0001-PILOT-V7"
    assert pilot["execution"]["authorized"] is False
    assert pilot["readiness"]["execution_eligibility"] == "eligible-after-authorization"
    assert pilot["readiness"]["unresolved_execution_blockers"] == []
    assert pilot["readiness"]["pre_execution_requirements"]
    assert terminal["execution_eligibility"] == "blocked-pending-prerequisites"
    assert terminal["authorized"] is terminal["replayable"] is False
    assert terminal["supersedes_registered_profile_readiness"] is True
    assert terminal["successor"]["plan_id"] is None
    assert terminal["successor"]["profile_path"] is None
    assert terminal["successor"]["profile_sha256"] is None
    assert {item["plan_id"] for item in terminal["superseded_registered_profiles"]} == {
        "PLAN-EXP0001-SMOKE",
        "PLAN-EXP0001-PILOT-V6",
        "PLAN-EXP0001-PILOT-V7",
    }
    assert all(
        item["current_interpretation"] == "historical-consumed-nonreplayable"
        for item in terminal["superseded_registered_profiles"]
    )
    assert registry["current_execution_control"] == {
        "path": TERMINAL_CONTROL_PATH.relative_to(ROOT).as_posix(),
        "sha256": hashlib.sha256(TERMINAL_CONTROL_PATH.read_bytes()).hexdigest(),
    }
    for relative in smoke["condition_plan_paths"] + pilot["condition_plan_paths"]:
        condition = load_yaml(ROOT / relative)
        assert condition["execution"]["authorization"] == {
            "authorized": False,
            "authorization_reference": None,
            "command_sha256": None,
        }
        parent = smoke if condition["profile"] == "smoke" else pilot
        assert condition["profile_plan_id"] == parent["plan_id"]


def test_historical_status_surfaces_preserve_without_reopening_bounded_v3() -> None:
    assert "Historical bounded plan: `PLAN-T07-BOUNDED-SIRA-SMOKE-V3`" in (
        PHASE_1_PLAN.read_text(encoding="utf-8")
    )
    readiness = (ROOT / "docs/readiness/PHASE_1_SMOKE_READINESS.md").read_text(encoding="utf-8")
    assert "Historical consumed bounded plan: `PLAN-T07-BOUNDED-SIRA-SMOKE-V3`." in (readiness)
    assert "Prospective bounded plan:" not in readiness
    assert "Exact next run plan" not in readiness
    assert "T07 has not run" not in readiness
    assert "V7 consumed" in readiness or "V7 closed" in readiness

    governance = (ROOT / "docs/harness/T07_BOUNDED_SMOKE_GOVERNANCE.md").read_text(encoding="utf-8")
    matches = re.findall(
        r"^Prospective bounded plan: `([^`]+)`\.$",
        governance,
        flags=re.MULTILINE,
    )
    assert matches == ["PLAN-T07-BOUNDED-SIRA-SMOKE-V3"]
    assert "bounded-smoke V1 is the reviewed prospective path" not in governance
    assert "bounded smoke V1 ready for separate authorization" not in governance
    assert "/home/ubuntu/t07-bounded-output-0001" not in governance

    for path in (
        ROOT / "docs/DECISIONS.md",
        ROOT / "notebook/generated/decisions.qmd",
    ):
        rows = [
            line
            for line in path.read_text(encoding="utf-8").splitlines()
            if "only prospective execution path" in line
            or "supersede D-032's prospective identity" in line
            or "supersede its obsolete second-file secret prerequisite" in line
        ]
        assert "D-033" in rows[-2] and "PLAN-T07-BOUNDED-SIRA-SMOKE-V2" in rows[-2]
        assert "D-034" in rows[-1] and "PLAN-T07-BOUNDED-SIRA-SMOKE-V3" in rows[-1]


def test_current_public_surfaces_define_no_replayable_v7_successor() -> None:
    surfaces = (
        ROOT / "docs/readiness/PHASE_1_SMOKE_READINESS.md",
        ROOT / "notebook/weekly/2026-08-08-phase-1.qmd",
    )
    for path in surfaces:
        text = path.read_text(encoding="utf-8")
        assert "Exact next run plan" not in text
        assert "only next eligible profile" not in text
        assert "T07 has not run" not in text
        assert "V7" in text
        assert "no successor" in text.lower()


def test_terminal_control_supersedes_frozen_profile_and_execution_contract_claims() -> None:
    terminal = load_json(TERMINAL_CONTROL_PATH)
    assert (
        validate_instance(terminal, ROOT / "schemas/terminal-execution-control.schema.json") == []
    )
    disposition_path = ROOT / terminal["terminal_record"]["path"]
    disposition = load_json(disposition_path)
    assert (
        hashlib.sha256(disposition_path.read_bytes()).hexdigest()
        == (terminal["terminal_record"]["sha256"])
    )
    assert terminal["terminal_state"] == disposition["terminal_state"]
    assert disposition["single_use_authority_exhausted"] is True
    assert disposition["launch_slots_exhausted"] is True
    assert disposition["empirical_entry"] is False
    assert terminal["empirical_entry"] is False

    for binding in terminal["superseded_registered_profiles"]:
        path = ROOT / binding["path"]
        profile = load_yaml(path)
        assert hashlib.sha256(path.read_bytes()).hexdigest() == binding["sha256"]
        assert profile["plan_id"] == binding["plan_id"]
        assert (
            profile["readiness"]["execution_eligibility"]
            == (binding["historical_execution_eligibility"])
        )
        assert profile["execution"]["authorized"] is False

    assert len(terminal["superseded_execution_contracts"]) == 2
    for binding in terminal["superseded_execution_contracts"]:
        contract_path = ROOT / binding["path"]
        contract = load_json(contract_path)
        assert hashlib.sha256(contract_path.read_bytes()).hexdigest() == binding["sha256"]
        assert contract["contract_id"] == binding["contract_id"]
        assert contract["terminal_state"] == binding["historical_terminal_state"]
        assert contract["execution_eligibility"] == (binding["historical_execution_eligibility"])
        assert contract["authorized"] is False
        assert contract["material_blockers"] == []

    retry3_terminal = load_json(RETRY3_TERMINAL_CONTROL_PATH)
    assert "empirical_entry" not in retry3_terminal
    assert (
        validate_instance(
            retry3_terminal,
            ROOT / "schemas/terminal-execution-control.schema.json",
        )
        == []
    )


def test_exp0001_readme_records_t07_materialization_and_current_pilot_boundary() -> None:
    readme = " ".join((EXP_ROOT / "README.md").read_text(encoding="utf-8").split())
    assert "T07 bound the immutable substitute `gpt-4o-2024-11-20`" in readme
    assert "Any pilot must preserve or explicitly revise that immutable binding" in readme
    assert "14,400-second provider campaign" in readme
    assert "900-second cleanup reserve" in readme
    assert "PLAN-EXP0001-PILOT-V3" in readme
    assert "T07 preflight must bind the exact snapshot before execution" not in readme
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
        "Historical bounded-smoke rollback and cleanup",
        "Current publication limits and next-control boundary",
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


def test_t07_l13_preserves_all_five_historical_scientific_file_hashes() -> None:
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
        relative = path.relative_to(ROOT).as_posix()
        encoded = subprocess.run(
            [
                "git",
                "show",
                f"5698f04dfd08bc85a66d2355b0a4bd7d3ce24a23:{relative}",
            ],
            cwd=ROOT,
            check=True,
            capture_output=True,
        ).stdout
        assert hashlib.sha256(encoded).hexdigest() == expected


def test_t07_l1a_plan_is_preserved_and_its_consumed_run_is_sealed() -> None:
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
    run_root = ROOT / "artifacts/t07/lambda/gate-l1a/RUN-T07-L1A-LAMBDA-SSH-KEY-FINGERPRINT-0001"
    assert run_root.is_dir()
    assert hashlib.sha256((run_root / "request-ledger.jsonl").read_bytes()).hexdigest() == (
        "41dd54aa76e8cad871f8d4064b44fb8b013a83dea96eb4494a9575df21e30e13"
    )
    assert hashlib.sha256((run_root / "match-report.json").read_bytes()).hexdigest() == (
        "28e66e39bb569327cc3d53abcc4efc07aad59e5aeb51ff0e0959f00c22c2e855"
    )


def test_t07_public_surfaces_preserve_l1a_and_keep_l2_unauthorized() -> None:
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
    assert "manual-console-launch-required" in combined
    assert "high-assurance-infrastructure-frozen" in combined
    assert "ready-for-manual-console-qualification-authorization" not in combined
    assert "Gate L2" in combined and "unauthorized" in combined
    assert "gate-l2-host-qualification-plan.json" not in combined


def test_t07_l21_terminal_state_has_no_executable_plan_or_authorization() -> None:
    forbidden_plans = (
        ROOT / "containers/sira-smoke/lambda/gate-l2-host-qualification-plan.json",
        ROOT / "containers/sira-smoke/lambda/gate-l2-host-qualification-plan-v2.json",
    )
    assert all(not path.exists() for path in forbidden_plans)

    packet = (
        ROOT / "docs/harness/T07_GATE_L2_HOST_QUALIFICATION_AUTHORIZATION_PACKET.md"
    ).read_text(encoding="utf-8")
    design = (ROOT / "docs/harness/T07_GATE_L2_1_LAUNCH_RECOVERY_DESIGN.md").read_text(
        encoding="utf-8"
    )
    for document in (packet, design):
        assert "manual-console-launch-required" in document
        assert "no executable plan" in document.casefold()
    assert "## ready-to-copy authorization block" not in packet.casefold()
    assert "i authorize t07 gate l2" not in packet.casefold()


def test_closeout_retains_zero_scientific_interpretation_and_typed_compute() -> None:
    compute = load_yaml(ROOT / "manifests/compute.yaml")
    results = load_json(EXP_ROOT / "results-summary.json")
    entries = {entry["id"]: entry for entry in compute["entries"]}
    planned = entries["CMP-0001"]
    assert planned == {
        "id": "CMP-0001",
        "experiment_id": "EXP-0001",
        "provider": "Lambda On-Demand Cloud",
        "hardware": "gpu_1x_a10",
        "region": "us-east-1",
        "started_at": None,
        "ended_at": None,
        "wall_clock_hours": 0.0,
        "accelerator_hours": 0.0,
        "cost_usd": 0.0,
        "authorization_reference": "AUTH-T07-BOUNDED-SIRA-SMOKE-V3-PENDING",
        "status": "planned",
    }
    assert entries["CMP-0002"] == {
        "id": "CMP-0002",
        "experiment_id": "EXP-0001",
        "provider": "Lambda On-Demand Cloud",
        "hardware": "gpu_1x_a10",
        "region": "us-east-1",
        "started_at": "2026-08-12T20:01:27.897128Z",
        "ended_at": "2026-08-12T20:26:40.632226Z",
        "wall_clock_hours": 0.4202041938888889,
        "accelerator_hours": 0.4202041938888889,
        "cost_usd": 0.5420634101166667,
        "authorization_reference": "AUTH-T07-PRAGMATIC-RESET-2026-08-12",
        "status": "failed",
    }
    assert entries["CMP-0003"] == {
        "id": "CMP-0003",
        "experiment_id": "EXP-0001",
        "provider": "Lambda On-Demand Cloud",
        "hardware": "gpu_1x_a10",
        "region": "us-east-1",
        "started_at": "2026-08-12T21:26:13.097888Z",
        "ended_at": "2026-08-12T21:52:35.003136Z",
        "wall_clock_hours": 0.43941812444444445,
        "accelerator_hours": 0.43941812444444445,
        "cost_usd": 0.5668493805333333,
        "authorization_reference": "AUTH-T07-PRAGMATIC-RETRY2-2026-08-12",
        "status": "completed",
    }
    assert entries["CMP-0004"] == {
        "id": "CMP-0004",
        "experiment_id": "EXP-0001",
        "provider": "Lambda On-Demand Cloud",
        "hardware": "gpu_1x_a10",
        "region": "us-east-1",
        "started_at": "2026-08-13T18:56:24.700507Z",
        "ended_at": "2026-08-13T19:15:40.228653Z",
        "wall_clock_hours": 0.320980040555556,
        "accelerator_hours": 0.320980040555556,
        "cost_usd": 0.414064252316667,
        "authorization_reference": "AUTH-T09-PRAGMATIC-PILOT-2026-08-13",
        "status": "failed",
    }
    assert entries["CMP-0005"] == {
        "id": "CMP-0005",
        "experiment_id": "EXP-0001",
        "provider": "Lambda On-Demand Cloud",
        "hardware": "gpu_1x_a10",
        "region": "us-east-1",
        "started_at": "2026-08-13T21:40:04.862007Z",
        "ended_at": "2026-08-13T23:01:40.051877Z",
        "wall_clock_hours": 1.3597749638557435,
        "accelerator_hours": 1.3597749638557435,
        "cost_usd": 1.754109703373909,
        "authorization_reference": "AUTH-T09-PRAGMATIC-RETRY2-2026-08-13",
        "status": "failed",
    }
    assert entries["CMP-0006"] == {
        "id": "CMP-0006",
        "experiment_id": "EXP-0001",
        "provider": "Lambda On-Demand Cloud",
        "hardware": "gpu_1x_a10",
        "region": "us-east-1",
        "started_at": "2026-08-14T12:13:58.357649Z",
        "ended_at": "2026-08-14T13:18:41.588704Z",
        "wall_clock_hours": 1.0786752931276957,
        "accelerator_hours": 1.0786752931276957,
        "cost_usd": 1.3914911281347275,
        "authorization_reference": "AUTH-T09-PRAGMATIC-RETRY3-2026-08-13",
        "status": "failed",
    }
    assert entries["CMP-0007"] == {
        "id": "CMP-0007",
        "experiment_id": "EXP-0001",
        "provider": "Lambda On-Demand Cloud",
        "hardware": "gpu_1x_a10",
        "region": "us-east-1",
        "started_at": "2026-08-14T14:55:37.113076Z",
        "ended_at": "2026-08-14T15:01:09.520196Z",
        "wall_clock_hours": 0.0923353111743927,
        "accelerator_hours": 0.0923353111743927,
        "cost_usd": 0.11911255141496659,
        "authorization_reference": "AUTH-T09-PRAGMATIC-RETRY3-2026-08-13",
        "status": "failed",
    }
    assert entries["CMP-0008"] == {
        "id": "CMP-0008",
        "experiment_id": "EXP-0001",
        "provider": "Lambda On-Demand Cloud",
        "hardware": "gpu_1x_a10",
        "region": "us-east-1",
        "started_at": "2026-08-14T19:30:01.774393Z",
        "ended_at": "2026-08-14T19:53:07.480665Z",
        "wall_clock_hours": 0.3849184089236789,
        "accelerator_hours": 0.3849184089236789,
        "cost_usd": 0.49654474751154587,
        "authorization_reference": "AUTH-T09-PRAGMATIC-RETRY4-2026-08-14",
        "status": "failed",
    }
    assert entries["CMP-0009"] == {
        "id": "CMP-0009",
        "experiment_id": "EXP-0001",
        "provider": "Lambda On-Demand Cloud",
        "hardware": "gpu_1x_a10",
        "region": "us-east-1",
        "started_at": "2026-08-14T20:38:38.105897Z",
        "ended_at": "2026-08-14T21:29:11.477697Z",
        "wall_clock_hours": 0.8426032778289583,
        "accelerator_hours": 0.8426032778289583,
        "cost_usd": 1.0869582283993562,
        "authorization_reference": "AUTH-T09-PRAGMATIC-RETRY4-2026-08-14",
        "status": "failed",
    }
    assert entries["CMP-0010"] == {
        "id": "CMP-0010",
        "experiment_id": "EXP-0001",
        "provider": "Lambda On-Demand Cloud",
        "hardware": "gpu_1x_a10",
        "region": "us-east-1",
        "started_at": "2026-08-15T07:35:19.316674Z",
        "ended_at": "2026-08-15T07:59:10.953213Z",
        "wall_clock_hours": 0.3976768163839976,
        "accelerator_hours": 0.3976768163839976,
        "cost_usd": 0.513003093135357,
        "authorization_reference": "AUTH-T09-PRAGMATIC-RETRY5-2026-08-14",
        "status": "failed",
    }
    assert entries["CMP-0011"] == {
        "id": "CMP-0011",
        "experiment_id": "EXP-0001",
        "provider": "Lambda On-Demand Cloud",
        "hardware": "gpu_1x_a10",
        "region": "us-east-1",
        "started_at": "2026-08-15T08:31:08.877246Z",
        "ended_at": "2026-08-15T08:57:05.207564Z",
        "wall_clock_hours": 0.43231397728125254,
        "accelerator_hours": 0.43231397728125254,
        "cost_usd": 0.5576850306928157,
        "authorization_reference": "AUTH-T09-PRAGMATIC-RETRY5-2026-08-14",
        "status": "failed",
    }
    summary = compute["phase_zero_summary"]
    assert summary["period_end"] == "2026-08-08"
    assert summary["paid_compute_authorized"] is False
    assert summary["cloud_mutations"] == 0
    assert summary["accelerator_hours"] == 0
    assert summary["cost_usd"] == 0
    assert summary["prototype_runs"] == 0
    assert summary["benchmark_runs"] == 0
    assert summary["training_runs"] == 0
    assert results["run_status"] == (
        "calibration-pilot-incomplete-one-historical-unpaired-measurement-"
        "retry4-one-invalid-unscored-attempt-retry5-no-run"
    )
    assert len(results["measurements"]) == 1
    assert results["measurements"][0]["paired_result_available"] is False
    assert results["evidence_status"] == "not-evaluated"
    assert results["outcome_status"] == "pending"
    assert results["artifacts"]
    run2_root = "artifacts/t07/lambda/gate-l1/RUN-T07-L1-LAMBDA-INVENTORY-0002"
    run3_root = "artifacts/t07/lambda/gate-l1/RUN-T07-L1-LAMBDA-INVENTORY-0003"
    alias_root = "artifacts/t07/lambda/gate-l1-3/RUN-T07-L1-LAMBDA-INVENTORY-0003"
    l1a_root = "artifacts/t07/lambda/gate-l1a/RUN-T07-L1A-LAMBDA-SSH-KEY-FINGERPRINT-0001"
    l20_root = "artifacts/t07/lambda/gate-l2-0/RUN-T07-L2-LAMBDA-HOST-QUALIFICATION-0001"
    l20_v2_root = f"{l20_root}/parameters-v2"
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
        f"{l1a_root}/request-ledger.jsonl": (
            "41dd54aa76e8cad871f8d4064b44fb8b013a83dea96eb4494a9575df21e30e13"
        ),
        f"{l1a_root}/ssh-keys-response.json": (
            "152828cb49e0720babc9bf0072c87361a8b8b20033f51cf8342f60647dde01eb"
        ),
        f"{l1a_root}/private-evidence.json": (
            "835b5692d67fa1286a84f2b6fc0a41318693a7e28171852d01f0d6db0a7293bb"
        ),
        f"{l1a_root}/match-report.json": (
            "28e66e39bb569327cc3d53abcc4efc07aad59e5aeb51ff0e0959f00c22c2e855"
        ),
        f"{l1a_root}/PRIVATE_EVIDENCE_SEAL.json": (
            "fd6f771318c4fe4ed94d457c0e24596260d0eb6d9cd83e9e18ab8cef43982f90"
        ),
        f"{l1a_root}/archive-finalization.jsonl": (
            "d40af3aa2eefd991ff765a416b4b6dc2d044f438bf05379a1a16990486ddb391"
        ),
        f"{l20_root}/human-decision-private.json": (
            "0b109b0150eec8739e30e86e5f1318b60c818cc3974354c67dc35a4e2dffd4ea"
        ),
        f"{l20_root}/HUMAN_DECISION_SEAL.json": (
            "5a1b9dec78e5a699809a4626876646ad687dfe5183859bf771ba75941f1814fc"
        ),
        f"{l20_root}/private-parameters.json": (
            "633bc9606725eb25881284820a26e9798698e3540b26654920c3dc71e2bee89e"
        ),
        f"{l20_root}/PRIVATE_PARAMETERS_SEAL.json": (
            "0682a25cc2595ef7415734cd5e3353975fca1bd99e23204440e6a1c212d4e31d"
        ),
        f"{l20_root}/PRIVATE_BUNDLE_SEAL.json": (
            "b46b31aa6ee35138fb03fe535aff621161a18218e8540db9e1252d5e0ece7b90"
        ),
        f"{l20_root}/PRIVATE_ARCHIVE_COPY_RECORD.json": (
            "5c0e5bb631cb39f46f1744f75e74e7a549b25f63d669d3e3c9d2b7b23a59c49a"
        ),
        f"{l20_v2_root}/human-decision-private.json": (
            "0b109b0150eec8739e30e86e5f1318b60c818cc3974354c67dc35a4e2dffd4ea"
        ),
        f"{l20_v2_root}/HUMAN_DECISION_SEAL.json": (
            "5a1b9dec78e5a699809a4626876646ad687dfe5183859bf771ba75941f1814fc"
        ),
        f"{l20_v2_root}/private-parameters.json": (
            "89028846f059c305d10a741c14681c537556666ac04f290dff9be8985bfe913b"
        ),
        f"{l20_v2_root}/PRIVATE_PARAMETERS_SEAL.json": (
            "4a6c6c3cfbf3a142b645fa361018bf6f6e6a8da99ec5ce01160d789b61b28dea"
        ),
        f"{l20_v2_root}/PRIVATE_BUNDLE_SEAL.json": (
            "7382a8b4b4262060b2cc01f686d18444c56af918e8bb552e9bee6e470b45e555"
        ),
        f"{l20_v2_root}/PRIVATE_ARCHIVE_COPY_RECORD.json": (
            "20240e23b7ad291ad728191a4b3d6133e693515999cfaf72d9eaa30608ad91d5"
        ),
    }
    retained_files = {
        path.relative_to(ROOT).as_posix()
        for namespace in (run2_root, run3_root, alias_root, l1a_root, l20_root)
        for path in (ROOT / namespace).rglob("*")
        if path.is_file()
    }
    # Gate L2.3's ignored private materialization is validated through the dedicated
    # held-descriptor/seal tests; this historical inventory continues to pin every
    # earlier Lambda-inventory artifact without coupling this historical inventory to
    # later pragmatic-run or protected private namespaces. Those namespaces have their
    # own mode/no-follow/seal and evidence-manifest tests.
    assert retained_files == set(retained_hashes)
    for relative, expected in retained_hashes.items():
        assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == expected
    assert not (ROOT / "traces").exists()


def test_t09_pragmatic_preflight_disposition_is_non_scientific_and_closed() -> None:
    disposition_path = EXP_ROOT / "T09_PRAGMATIC_PREFLIGHT_DISPOSITION.json"
    disposition = load_json(disposition_path)
    assert disposition["schema_version"] == "0.1.0"
    assert disposition["record_id"] == "T09-PRAGMATIC-PREFLIGHT-DISPOSITION-0001"
    assert disposition["plan_id"] == "PLAN-EXP0001-PILOT-V3"
    assert disposition["frozen_package_commit"] == ("9dc7363561ec96812072e2c7824141d75b028332")
    assert disposition["terminal_state"] == "t09-pilot-blocked-material-risk"
    assert disposition["lifecycle_state"] == ("preflight-failed-closed-before-empirical-entry")
    assert disposition["empirical_entry"] is False
    assert disposition["scientific_result_claimed"] is False
    assert disposition["dataset"] == {
        "revision": "76ad1feb689b754bfe4e5e24d3ea371b647efa67",
        "task_ids": ["7dcbbbdc7f1120cd", "2120afba8009bad3"],
    }
    attempts = disposition["attempts"]
    assert attempts["empirical_attempts_entered"] == []
    assert attempts["evaluator_attempts_entered"] == []
    assert attempts["condition_retries"] == 0
    assert attempts["first_pair_checkpoint"] == "not-reached"
    for key in (
        "task_a_reactive",
        "task_a_simulative",
        "task_b_simulative",
        "task_b_reactive",
    ):
        assert attempts[key] == "not-run"
    attempt_dispositions = attempts["attempt_dispositions"]
    assert [item["run_id"] for item in attempt_dispositions] == attempts["frozen_order"]
    assert [item["condition"] for item in attempt_dispositions] == [
        "reactive",
        "simulative",
        "simulative",
        "reactive",
    ]
    for item in attempt_dispositions:
        assert item["state"] == "not-run"
        assert item["empirical_entry"] is False
        assert item["task_completion"] is None
        assert item["evaluator_validity"] == "not-run"
        assert item["task_score"] is None
        assert item["model_calls"] == 0
        assert item["total_tokens"] == 0
        assert item["browser_actions"] == 0
        assert item["openai_cost_usd"] == 0.0
    assert disposition["evaluator"] == {
        "identity": "exact-pinned-SiRA-FanOutQA-evaluator",
        "sira_commit": "93fb8d72de71f9a4a13419670adeb34d93cf7acd",
        "offline_contract_validated": True,
        "live_evaluator_executed": False,
        "live_evaluator_validity": "not-applicable-not-run",
    }
    assert disposition["usage"] == {
        "model_calls": 0,
        "input_tokens": 0,
        "cached_input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "browser_actions": 0,
        "openai_cost_usd": 0.0,
    }
    preflight = disposition["preflight"]
    assert preflight["expected_container_image_digest"] == (
        "sha256:035edf61718e84a8156f4f0f7817b134b0ce31488d3f0b50bbfba2b4a30cc61c"
    )
    assert preflight["rebuilt_container_image_digest"] == (
        "sha256:07875dc67336b90021df5ab920860a56268bbc9f3aada70accec23848d9905cf"
    )
    assert preflight["exact_container_identity_match"] is False
    assert preflight["frozen_image_retained_or_registry_available"] is False
    assert preflight["model_metadata_request_performed"] is False
    assert preflight["task_browser_action_performed"] is False
    assert preflight["evaluator_loaded"] is False
    provider = disposition["provider"]
    assert provider["launch_count"] == provider["maximum_launch_count"] == 1
    assert provider["persistent_filesystems"] == 0
    assert provider["conservative_wall_seconds"] == 1155.528146
    assert provider["accelerator_hours"] == 0.320980040555556
    assert provider["estimated_cost_usd"] == 0.414064252316667
    assert provider["terminal_or_absent"] is True
    assert provider["zero_t09_instances"] is True
    assert provider["security_restored"] is True
    assert disposition["gpu_accounting"] == {
        "a10_host_allocated": True,
        "pilot_or_evaluator_process_used_gpu": False,
        "host_gpu_visibility": "visible",
        "host_gpu_name": "NVIDIA A10",
        "host_gpu_utilization_percent_at_cleanup": 0,
        "host_gpu_memory_used_mib_at_cleanup": 0,
        "pilot_container_cuda_visible_devices": "disabled-empty",
        "pilot_container_gpu_device_request": "none",
        "acceleration_claimed": False,
    }
    assert disposition["cleanup"] == {
        "owned_container_residue": [],
        "temporary_secret_removed": True,
        "global_secret_scan_passed": True,
        "structural_privacy_scan_passed": True,
        "provider_terminal_or_absent": True,
        "zero_t09_instances": True,
        "security_restored": True,
    }
    assert disposition["pair_matching"]["task_a_static_pair_diff_valid"] is True
    assert disposition["pair_matching"]["task_b_static_pair_diff_valid"] is True
    assert disposition["pair_matching"]["command_manifest_sha256"] == (
        "8e8d5827df4688a8748828145ea0990d8397c771ae3add43790bbd45f732984d"
    )
    assert disposition["pair_matching"]["realized_pair_result_available"] is False
    evidence = disposition["evidence"]
    assert evidence["stage_archive_bytes"] == 1_195_031
    assert evidence == {
        "archive_id": "ARCHIVE-EXP0001-PILOT-V3-0001",
        "retention": "private-access-controlled-external",
        "public_release": "blocked-pending-review",
        "stage_archive_bytes": 1_195_031,
        "stage_archive_sha256": (
            "941c61b58ac2fd8717c06ae2f8ef25616ed23c7e36ba64e88d9944924d084bc1"
        ),
        "final_archive_manifest_sha256": (
            "740aa70a7f6a7e659f776038ab35366a6d3448a656d2396a8eda0f3c887df5f2"
        ),
        "final_archive_identity_sha256": (
            "706c5b8e434e16986773f36ec4ba3a8df2a9568026a3744d4f999a79ce4aebf2"
        ),
        "provider_entry_receipt_sha256": (
            "a7a397e8a9f7079c1ae632db42d0264a3bf3a7954db6cc2cb8cc95c7dd93abea"
        ),
        "provider_entry_source_manifest_sha256": (
            "e44d1bf4fabbad359c6478fa8664fe8ca94fef40a653deff0d83ab4030923e0f"
        ),
        "provider_closeout_receipt_sha256": (
            "c41cd84b555f371f27661903f1373ce2645c011ba3a9e41af33e3a1c6f8db4ac"
        ),
        "provider_closeout_source_manifest_sha256": (
            "f2e5d5fc78422dbd7c43476bdc7eea590f5b70b284cd32f040a844b8ab102a90"
        ),
    }
    for key, value in evidence.items():
        if key.endswith("_sha256"):
            assert re.fullmatch(r"[0-9a-f]{64}", value)

    registry = load_yaml(ROOT / "experiments/registry.yaml")
    experiment = next(
        item for item in registry["experiments"] if item["experiment_id"] == "EXP-0001"
    )
    assert disposition_path.relative_to(ROOT).as_posix() in experiment["evidence_records"]


def test_t09_retry2_disposition_reconciles_one_attempt_without_a_pair_or_outcome() -> None:
    disposition_path = EXP_ROOT / "T09_PRAGMATIC_RETRY2_DISPOSITION.json"
    disposition = load_json(disposition_path)
    state = load_yaml(ROOT / "docs/PROJECT_STATE.yaml")["t09_pragmatic_retry2_checkpoint"]
    results = load_json(EXP_ROOT / "results-summary.json")
    compute = {
        entry["id"]: entry for entry in load_yaml(ROOT / "manifests/compute.yaml")["entries"]
    }

    assert disposition["record_id"] == "T09-PRAGMATIC-RETRY2-DISPOSITION-0001"
    assert disposition["plan_id"] == "PLAN-EXP0001-PILOT-V4"
    assert (
        disposition["terminal_state"]
        == state["terminal_state"]
        == ("t09-pilot-blocked-material-risk")
    )
    assert disposition["lifecycle_state"] == (
        "stopped-after-one-valid-scored-attempt-before-pair-completion"
    )
    assert disposition["scientific_result_claimed"] is False
    assert disposition["experiment_outcome_assigned"] is False
    assert disposition["experiment_evidence_status"] == "not-evaluated"

    runtime = disposition["replacement_runtime"]
    assert runtime["replacement_image_id"] == state["replacement_image_id"]
    assert runtime["functional_equivalence_passed"] is True
    assert runtime["build_count"] == runtime["qualification_count"] == 1
    assert runtime["model_metadata_requests"] == 1
    assert runtime["preflight_task_model_requests"] == 0
    assert runtime["preflight_task_browser_actions"] == 0
    assert runtime["loadable_image_archive_preserved"] is False

    attempts = disposition["attempts"]
    assert attempts["empirical_attempts_entered"] == ["RUN-T09-TASK-A-REACTIVE-0002"]
    assert attempts["attempts_completed"] == ["RUN-T09-TASK-A-REACTIVE-0002"]
    assert attempts["condition_retries"] == 0
    reactive = attempts["task_a_reactive"]
    assert reactive["task_completion"] == "completed"
    assert reactive["evaluator_validity"] is True
    assert reactive["task_score"] == 0.0
    assert reactive["invalid_infrastructure_attempt"] is False
    assert reactive["condition_failure"] is False
    for key in ("task_a_simulative", "task_b_simulative", "task_b_reactive"):
        assert attempts[key]["state"] == "not-run"
        assert attempts[key]["empirical_entry"] is False
    assert attempts["first_pair_checkpoint"] == ("not-reached-stopped-before-task-a-simulative")
    assert attempts["realized_task_a_pair"] is False
    assert attempts["realized_task_b_pair"] is False

    usage = disposition["usage"]
    assert usage == {
        "model_metadata_requests": 1,
        "task_model_calls": 52,
        "input_tokens": 114181,
        "cached_input_tokens": 0,
        "output_tokens": 7719,
        "total_tokens": 121900,
        "browser_actions": 13,
        "condition_attempts": 1,
        "condition_retries": 0,
        "openai_cost_usd": 0.3626425,
    }
    provider = disposition["provider"]
    assert provider["launch_count"] == provider["maximum_launch_count"] == 1
    assert provider["persistent_filesystems"] == 0
    assert provider["terminal_or_absent"] is True
    assert provider["zero_t09_instances"] is True
    assert provider["security_restored"] is True
    assert provider["termination_request_count"] == 1
    assert compute["CMP-0005"]["accelerator_hours"] == provider["accelerator_hours"]
    assert compute["CMP-0005"]["cost_usd"] == provider["list_cost_usd"]

    cost = disposition["cost_reconciliation"]
    assert cost["new_campaign_total_cost_usd"] == state["new_campaign_total_cost_usd"]
    assert cost["cumulative_t09_cost_usd"] == state["cumulative_t09_cost_usd"]
    assert cost["all_cost_caps_respected"] is True
    assert disposition["pair_matching"]["task_a_realized_pair_available"] is False
    assert disposition["pair_matching"]["task_b_realized_pair_available"] is False
    assert disposition["pair_matching"]["paired_or_comparative_interpretation_permitted"] is False
    assert results["measurements"][0]["run_id"] == reactive["run_id"]
    assert results["measurements"][0]["task_score"] == reactive["task_score"]
    assert results["measurements"][0]["paired_result_available"] is False

    evidence = disposition["evidence"]
    assert evidence["archive_id"] == state["evidence_archive_id"]
    for key, value in evidence.items():
        if key.endswith("_sha256"):
            assert re.fullmatch(r"[0-9a-f]{64}", value)
    public_text = disposition_path.read_text(encoding="utf-8")
    assert not re.search(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", public_text)
    assert "JUPYTER_TOKEN" not in public_text
    assert "OPENAI_API_KEY" not in public_text
    assert "LAMBDA_API_KEY" not in public_text
    assert 'provider_account_identifier"' not in public_text

    registry = load_yaml(ROOT / "experiments/registry.yaml")
    experiment = next(
        item for item in registry["experiments"] if item["experiment_id"] == "EXP-0001"
    )
    assert disposition_path.relative_to(ROOT).as_posix() in experiment["evidence_records"]


def test_t09_retry3_disposition_reconciles_two_launches_and_zero_attempts() -> None:
    disposition_path = EXP_ROOT / "T09_PRAGMATIC_RETRY3_DISPOSITION.json"
    disposition = load_json(disposition_path)
    state = load_yaml(ROOT / "docs/PROJECT_STATE.yaml")["t09_pragmatic_retry3_checkpoint"]
    results = load_json(EXP_ROOT / "results-summary.json")
    compute = {
        entry["id"]: entry for entry in load_yaml(ROOT / "manifests/compute.yaml")["entries"]
    }

    assert disposition["record_id"] == "T09-PRAGMATIC-RETRY3-DISPOSITION-0001"
    assert disposition["plan_id"] == state["plan_id"] == "PLAN-EXP0001-PILOT-V5"
    assert (
        disposition["terminal_state"]
        == state["terminal_state"]
        == ("t09-pilot-blocked-material-risk")
    )
    assert disposition["empirical_entry"] is False
    assert disposition["scientific_result_claimed"] is False
    assert disposition["experiment_outcome_assigned"] is False
    assert disposition["experiment_evidence_status"] == "not-evaluated"
    assert disposition["single_use_authority_exhausted"] is True
    assert disposition["launch_slots_exhausted"] is True

    regression = disposition["real_evidence_regression"]
    assert regression["receipt_sha256"] == (
        "e19c7ccfb0ec9244e97a2601910b312282de8daed2b3c9d30edc807173f029d6"
    )
    assert regression["two_run_semantic_projection_equal"] is True
    assert regression["additional_model_requests"] == 0
    assert regression["additional_browser_actions"] == 0
    assert regression["included_in_v5_paired_results"] is False

    runtime = disposition["replacement_runtime"]
    assert runtime["candidate_build_attempt_count"] == 1
    assert runtime["additional_build_count_on_slot2"] == 0
    assert runtime["loadable_image_archive_preserved"] is True
    assert runtime["slot2_image_import_started"] is False
    assert runtime["slot2_functional_qualification_started"] is False
    assert runtime["replacement_image_qualified_for_v5"] is False
    assert runtime["frozen_run_manifest_written"] is False
    assert runtime["frozen_run_manifest_sha256"] is None

    attempts = disposition["attempts"]
    assert attempts["empirical_attempts_entered"] == []
    assert attempts["raw_attempts_complete"] == []
    assert attempts["attempts_completed"] == []
    assert attempts["condition_retries"] == 0
    for key in ("task_a_reactive", "task_a_simulative", "task_b_simulative", "task_b_reactive"):
        assert attempts[key]["state"] == "not-run"
        assert attempts[key]["empirical_entry"] is False
    assert attempts["first_pair_checkpoint"] == "not-reached-no-empirical-attempt-started"
    assert attempts["realized_task_a_pair"] is False
    assert attempts["realized_task_b_pair"] is False

    assert disposition["usage"] == {
        "model_metadata_requests": 0,
        "task_model_calls": 0,
        "input_tokens": 0,
        "cached_input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "browser_actions": 0,
        "condition_attempts": 0,
        "condition_retries": 0,
        "openai_cost_usd": 0.0,
    }

    provider = disposition["provider"]
    assert provider["launch_count"] == provider["maximum_launch_count"] == 2
    assert provider["persistent_filesystems"] == 0
    assert provider["termination_request_count"] == 2
    assert provider["terminal_or_absent"] is True
    assert provider["zero_t09_instances"] is True
    assert provider["security_restored"] is True
    assert provider["campaign_wall_exception"] == "none"
    assert provider["active_lambda_duration_seconds"] == (
        provider["slot1"]["owned_lambda_duration_seconds"]
        + provider["slot2"]["owned_lambda_duration_seconds"]
    )
    assert provider["list_cost_usd"] == (
        provider["slot1"]["list_cost_usd"] + provider["slot2"]["list_cost_usd"]
    )
    for slot, compute_id in (("slot1", "CMP-0006"), ("slot2", "CMP-0007")):
        assert provider[slot]["termination_request_count"] == 1
        assert provider[slot]["terminal_or_absent"] is True
        assert provider[slot]["zero_t09_instances"] is True
        assert provider[slot]["security_restored"] is True
        assert compute[compute_id]["accelerator_hours"] == provider[slot]["accelerator_hours"]
        assert compute[compute_id]["cost_usd"] == provider[slot]["list_cost_usd"]

    costs = disposition["cost_reconciliation"]
    assert costs["new_openai_cost_usd"] == state["openai_cost_usd"] == 0.0
    assert costs["new_lambda_cost_usd"] == state["lambda_cost_usd"]
    assert costs["new_campaign_total_cost_usd"] == state["new_campaign_total_cost_usd"]
    assert costs["cumulative_t09_cost_usd"] == state["cumulative_t09_cost_usd"]
    assert costs["all_cost_caps_respected"] is True
    assert disposition["cleanup"]["provider_terminal_or_absent"] is True
    assert disposition["cleanup"]["zero_t09_instances"] is True
    assert disposition["cleanup"]["security_restored"] is True
    assert disposition["pair_matching"]["task_a_realized_pair_available"] is False
    assert disposition["pair_matching"]["task_b_realized_pair_available"] is False
    assert disposition["pair_matching"]["paired_or_comparative_interpretation_permitted"] is False

    assert len(results["measurements"]) == 1
    assert results["measurements"][0]["run_id"] == "RUN-T09-TASK-A-REACTIVE-0002"
    assert disposition_path.relative_to(ROOT).as_posix() in results["artifacts"]
    evidence = disposition["evidence"]
    assert evidence["archive_id"] == state["evidence_archive_id"]
    assert evidence["archive_file_count"] == 224
    assert evidence["archive_payload_bytes"] == 2792322
    for key, value in evidence.items():
        if key.endswith("_sha256"):
            assert re.fullmatch(r"[0-9a-f]{64}", value)

    public_text = disposition_path.read_text(encoding="utf-8")
    assert not re.search(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", public_text)
    assert "/Volumes/" not in public_text
    assert "/Users/" not in public_text
    assert "JUPYTER_TOKEN" not in public_text
    assert "OPENAI_API_KEY" not in public_text
    assert "LAMBDA_API_KEY" not in public_text
    assert 'provider_account_identifier"' not in public_text

    registry = load_yaml(ROOT / "experiments/registry.yaml")
    experiment = next(
        item for item in registry["experiments"] if item["experiment_id"] == "EXP-0001"
    )
    assert disposition_path.relative_to(ROOT).as_posix() in experiment["evidence_records"]


def test_t09_retry4_disposition_reconciles_one_invalid_unscored_attempt() -> None:
    disposition_path = EXP_ROOT / "T09_PRAGMATIC_RETRY4_DISPOSITION.json"
    disposition = load_json(disposition_path)
    state = load_yaml(ROOT / "docs/PROJECT_STATE.yaml")["t09_pragmatic_retry4_checkpoint"]
    results = load_json(EXP_ROOT / "results-summary.json")
    compute = {
        entry["id"]: entry for entry in load_yaml(ROOT / "manifests/compute.yaml")["entries"]
    }

    assert disposition["record_id"] == "T09-PRAGMATIC-RETRY4-DISPOSITION-0001"
    assert disposition["plan_id"] == state["plan_id"] == "PLAN-EXP0001-PILOT-V6"
    assert (
        disposition["terminal_state"]
        == state["terminal_state"]
        == ("t09-pilot-blocked-material-risk")
    )
    assert disposition["empirical_entry"] is True
    assert disposition["scientific_result_claimed"] is False
    assert disposition["experiment_outcome_assigned"] is False
    assert disposition["experiment_evidence_status"] == "not-evaluated"
    assert disposition["single_use_authority_exhausted"] is True
    assert disposition["launch_slots_exhausted"] is True

    attempts = disposition["attempts"]
    assert attempts["empirical_attempts_entered"] == ["RUN-T09-TASK-A-REACTIVE-0004"]
    assert attempts["raw_attempts_complete"] == []
    assert attempts["attempts_completed"] == []
    assert attempts["condition_retries"] == 0
    reactive = attempts["task_a_reactive"]
    assert reactive["state"] == "consumed-infrastructure-invalid-unscored"
    assert reactive["process_exit_code"] == 143
    assert reactive["stop_reason"] == "attempt_output_bytes"
    assert reactive["task_score"] is None
    assert reactive["raw_attempt_complete"] is False
    for key in ("task_a_simulative", "task_b_simulative", "task_b_reactive"):
        assert attempts[key]["state"] == "not-run"
        assert attempts[key]["empirical_entry"] is False
    assert attempts["realized_task_a_pair"] is False
    assert attempts["realized_task_b_pair"] is False

    usage = disposition["usage"]
    assert usage["task_model_calls"] == 20
    assert usage["total_tokens"] == 38_779
    assert usage["browser_actions_requested"] == 5
    assert usage["post_action_results"] == 4
    assert usage["condition_attempts"] == 1
    assert usage["condition_retries"] == 0
    assert usage["openai_cost_usd"] == 0.11752750000000001

    provider = disposition["provider"]
    assert provider["launch_count"] == provider["maximum_launch_count"] == 2
    assert provider["active_lambda_duration_seconds"] == (
        provider["slot1"]["owned_lambda_duration_seconds"]
        + provider["slot2"]["owned_lambda_duration_seconds"]
    )
    assert provider["list_cost_usd"] == (
        provider["slot1"]["list_cost_usd"] + provider["slot2"]["list_cost_usd"]
    )
    for slot, compute_id in (("slot1", "CMP-0008"), ("slot2", "CMP-0009")):
        assert provider[slot]["termination_request_count"] == 1
        assert provider[slot]["terminal_or_absent"] is True
        assert provider[slot]["zero_t09_instances"] is True
        assert provider[slot]["security_restored"] is True
        assert compute[compute_id]["accelerator_hours"] == provider[slot]["accelerator_hours"]
        assert compute[compute_id]["cost_usd"] == provider[slot]["list_cost_usd"]
    assert provider["slot2"]["provider_preflight_seconds"] == 2353.116389989853
    assert provider["slot2"]["empirical_to_terminal_and_zero_seconds"] == (680.255410194397)
    assert provider["slot2"]["clock_reconciliation_after_termination"] is True

    costs = disposition["cost_reconciliation"]
    assert costs["new_openai_cost_usd"] == state["openai_cost_usd"]
    assert costs["new_lambda_cost_usd"] == state["lambda_cost_usd"]
    assert costs["new_campaign_total_cost_usd"] == state["new_campaign_total_cost_usd"]
    assert costs["cumulative_t09_cost_usd"] == state["cumulative_t09_cost_usd"]
    assert costs["all_cost_caps_respected"] is True
    assert disposition["cleanup"]["provider_terminal_or_absent"] is True
    assert disposition["cleanup"]["zero_t09_instances"] is True
    assert disposition["cleanup"]["security_restored"] is True
    assert disposition["pair_matching"]["task_a_realized_pair_available"] is False
    assert disposition["pair_matching"]["task_b_realized_pair_available"] is False
    assert disposition["pair_matching"]["paired_or_comparative_interpretation_permitted"] is False
    evidence = disposition["evidence"]
    assert evidence["original_archive_preserved_byte_exact"] is True
    assert evidence["slot2_stage_completeness"] == ("reconstructable-with-posttermination-overlay")
    assert evidence["posttermination_overlay_manifest_sha256"] == (
        "1eedf1d9423f720ec15a74045799228127c59b341c097c4d160c93aa9e508ed2"
    )
    assert evidence["posttermination_overlay_identity_sha256"] == (
        "a07cee4c06733098fb1400df3e27af04dff59dac8aba333f6ff050c8777233c9"
    )
    assert evidence["posttermination_clock_reconciliation_sha256"] == (
        "989d5625c719d3b081cba9f1b254ee81c1e4f56aa6f6bf44bdb7ed5c8dd7884f"
    )
    assert evidence["posttermination_overlay_member_bytes"] == 597_140
    assert evidence["frozen_runtime_reconstructable_with_overlay"] is True
    assert len(results["measurements"]) == 1
    assert results["measurements"][0]["run_id"] == "RUN-T09-TASK-A-REACTIVE-0002"
    assert disposition_path.relative_to(ROOT).as_posix() in results["artifacts"]
    assert (
        disposition_path.relative_to(ROOT).as_posix()
        in (load_yaml(ROOT / "experiments/registry.yaml")["experiments"][0]["evidence_records"])
    )

    public_text = disposition_path.read_text(encoding="utf-8")
    assert not re.search(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", public_text)
    assert "/Volumes/" not in public_text
    assert "/Users/" not in public_text
    assert "JUPYTER_TOKEN" not in public_text
    assert "OPENAI_API_KEY" not in public_text
    assert "LAMBDA_API_KEY" not in public_text
    assert 'provider_account_identifier"' not in public_text


def test_public_surfaces_report_the_current_phase_and_unauthorized_next_gate() -> None:
    readme = " ".join((ROOT / "README.md").read_text(encoding="utf-8").split())
    home = " ".join((ROOT / "notebook/index.qmd").read_text(encoding="utf-8").split())
    note = " ".join(
        (ROOT / "notebook/weekly/2026-08-08-phase-1.qmd").read_text(encoding="utf-8").split()
    )
    for page in (readme, home, note):
        assert "Phase 1" in page
        assert (
            "PLAN-EXP0001-SMOKE" in page or "PLAN-EXP0001-PILOT" in page or "artifact smoke" in page
        )
        assert any(
            boundary in page.lower()
            for boundary in ("not authorization", "does not authorize", "unauthorized")
        )
        assert "score" in page and "0.0" in page
        assert "no pair" in page.lower()


def test_resource_and_research_pages_do_not_reopen_completed_phase_zero_work() -> None:
    resources = " ".join((ROOT / "notebook/resources.qmd").read_text(encoding="utf-8").split())
    questions = " ".join((ROOT / "docs/RESEARCH_QUESTIONS.md").read_text(encoding="utf-8").split())
    assert "datasets.yaml` — currently empty" not in resources
    assert "zero-use Phase 0 compute ledger" not in resources
    assert "audited dataset identities" in resources
    assert "Phase 0.5 should reconcile" not in questions
    assert "A later Phase 1 protocol must select" not in questions
    assert "PLAN-EXP0001-SMOKE" in questions
