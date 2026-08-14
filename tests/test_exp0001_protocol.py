from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from decimal import Decimal
from pathlib import Path
from shutil import copytree

import yaml

from giclab.registry import load_json, load_yaml
from giclab.validation import (
    ROOT,
    validate_exp0001_contract,
    validate_experiment_run_profiles,
    validate_instance,
    validate_run_profile_readiness,
)

EXP_ROOT = ROOT / "experiments/EXP-0001-sira-simulative-vs-reactive"
CONDITIONS = {"SIRA-SIMULATIVE", "SIRA-REACTIVE"}


def test_exp0001_is_registered_with_incomplete_calibration_and_no_scientific_result() -> None:
    registry = load_yaml(ROOT / "experiments/registry.yaml")
    assert registry["experiments"][0]["experiment_id"] == "EXP-0001"
    assert registry["experiments"][0]["protocol"].endswith("/protocol.yaml")
    assert len(registry["experiments"][0]["run_profiles"]) == 2
    terminal_control_path = EXP_ROOT / "T09_PRAGMATIC_RETRY4_TERMINAL_CONTROL.json"
    assert registry["experiments"][0]["current_execution_control"] == {
        "path": terminal_control_path.relative_to(ROOT).as_posix(),
        "sha256": hashlib.sha256(terminal_control_path.read_bytes()).hexdigest(),
    }
    protocol = load_yaml(EXP_ROOT / "protocol.yaml")
    assert protocol["lifecycle_status"] == "planned"
    assert protocol["evidence_status"] == "not-evaluated"
    assert protocol["outcome_status"] == "pending"
    assert protocol["execution"] == {
        "authorized": False,
        "authorization_reference": None,
    }
    results = load_json(EXP_ROOT / "results-summary.json")
    assert results["run_status"] == (
        "calibration-pilot-incomplete-one-historical-unpaired-measurement-"
        "retry4-one-invalid-unscored-attempt"
    )
    assert results["measurements"] == [
        {
            "measurement_id": "MEAS-EXP0001-T09-V4-TASK-A-REACTIVE-0001",
            "kind": "descriptive-calibration-attempt",
            "run_id": "RUN-T09-TASK-A-REACTIVE-0002",
            "task_id": "7dcbbbdc7f1120cd",
            "condition": "SIRA-REACTIVE",
            "task_completed": True,
            "answer_produced": True,
            "evaluator_valid": True,
            "task_score": 0.0,
            "model_calls": 52,
            "total_tokens": 121900,
            "browser_actions": 13,
            "openai_cost_usd": 0.3626425,
            "wall_seconds": 199.19638025899985,
            "paired_result_available": False,
            "interpretation": "descriptive-calibration-only",
        }
    ]
    assert results["artifacts"] == [
        "experiments/EXP-0001-sira-simulative-vs-reactive/T08_SMOKE_ADJUDICATION.json",
        "experiments/EXP-0001-sira-simulative-vs-reactive/T08_SMOKE_PAIR_DIFF.json",
        (
            "experiments/EXP-0001-sira-simulative-vs-reactive/"
            "T09_PRAGMATIC_PREFLIGHT_DISPOSITION.json"
        ),
        ("experiments/EXP-0001-sira-simulative-vs-reactive/T09_PRAGMATIC_RETRY2_SUPERSESSION.json"),
        ("experiments/EXP-0001-sira-simulative-vs-reactive/T09_PRAGMATIC_RETRY2_DISPOSITION.json"),
        (
            "experiments/EXP-0001-sira-simulative-vs-reactive/"
            "T09_PRAGMATIC_RETRY3_FINALIZER_REGRESSION.json"
        ),
        ("experiments/EXP-0001-sira-simulative-vs-reactive/T09_PRAGMATIC_RETRY3_DISPOSITION.json"),
        (
            "experiments/EXP-0001-sira-simulative-vs-reactive/"
            "T09_PRAGMATIC_RETRY3_TERMINAL_CONTROL.json"
        ),
        (
            "experiments/EXP-0001-sira-simulative-vs-reactive/"
            "T09_PRAGMATIC_RETRY4_FINALIZER_REGRESSION.json"
        ),
        ("experiments/EXP-0001-sira-simulative-vs-reactive/T09_PRAGMATIC_RETRY4_DISPOSITION.json"),
        (
            "experiments/EXP-0001-sira-simulative-vs-reactive/"
            "T09_PRAGMATIC_RETRY4_TERMINAL_CONTROL.json"
        ),
    ]
    assert results["infrastructure_terminal_state"] == "t09-pilot-blocked-material-risk"


def test_exp0001_locks_exactly_the_two_source_conditions() -> None:
    protocol = load_yaml(EXP_ROOT / "protocol.yaml")
    assert protocol["systems"] == {
        "treatment": "SIRA-SIMULATIVE",
        "controls": ["SIRA-REACTIVE"],
    }
    config = load_yaml(EXP_ROOT / "config.yaml")
    assert {item["id"] for item in config["conditions"].values()} == CONDITIONS
    assert "experiment_assignment" in (EXP_ROOT / "README.md").read_text(encoding="utf-8")
    assert "not evidence that the model learned" in (EXP_ROOT / "README.md").read_text(
        encoding="utf-8"
    )


def test_scientific_protocol_locks_sampling_estimand_retry_and_release() -> None:
    protocol = load_yaml(EXP_ROOT / "protocol.yaml")
    config = load_yaml(EXP_ROOT / "config.yaml")
    assert protocol["sampling"] == {
        "dataset_ids": ["DATA-SIRA-FANOUTQA-DEV"],
        "sample_size": 2,
        "replications": 1,
        "seeds": [42],
    }
    assert "no aggregate effect estimate" in protocol["metrics"]["primary"]
    assert config["sampling"]["pilot"]["tasks"][0]["order"] == [
        "SIRA-REACTIVE",
        "SIRA-SIMULATIVE",
    ]
    assert config["sampling"]["pilot"]["tasks"][1]["order"] == [
        "SIRA-SIMULATIVE",
        "SIRA-REACTIVE",
    ]
    assert config["retry_and_exclusion"]["task_failure_is_exclusion"] is False
    assert not config["retry_and_exclusion"]["new_attempt_identity_for_infrastructure_retry"]
    assert config["raw_retention"]["hash_before_normalization"]
    assert config["raw_retention"]["public_release"].startswith("blocked-")
    assert protocol["validity"]["invalid_run_criteria"]
    assert protocol["validity"]["inconclusive_criteria"]
    assert all(
        "do not complete" not in item for item in protocol["hypothesis"]["falsification_criteria"]
    )


def test_smoke_and_pilot_profiles_and_condition_plans_validate() -> None:
    assert validate_experiment_run_profiles() == []
    smoke = load_yaml(EXP_ROOT / "run-plans/smoke.yaml")
    pilot = load_yaml(EXP_ROOT / "run-plans/pilot.yaml")
    assert smoke["sampling"]["pair_count"] == 1
    assert smoke["interpretation_allowed"] is False
    assert pilot["sampling"]["pair_count"] == 2
    assert "cannot estimate an effect" in pilot["sample_rationale"]
    assert smoke["execution"]["authorized"] is False
    assert pilot["execution"]["authorized"] is False
    assert smoke["readiness"]["execution_eligibility"] == "eligible-after-authorization"
    assert smoke["readiness"]["unresolved_execution_blockers"] == []
    assert smoke["readiness"]["pre_execution_requirements"]
    assert pilot["readiness"]["execution_eligibility"] == "eligible-after-authorization"
    assert pilot["readiness"]["unresolved_execution_blockers"] == []
    terminal = load_json(EXP_ROOT / "T09_PRAGMATIC_RETRY4_TERMINAL_CONTROL.json")
    assert terminal["execution_eligibility"] == "blocked-pending-prerequisites"
    assert terminal["authorized"] is terminal["replayable"] is False
    assert {item["plan_id"] for item in terminal["superseded_registered_profiles"]} == {
        smoke["plan_id"],
        pilot["plan_id"],
    }
    assert set(smoke["sampling"]["conditions"]) == CONDITIONS
    assert set(pilot["sampling"]["conditions"]) == CONDITIONS


def test_run_profile_schema_prevents_smoke_interpretation_but_allows_later_approval() -> None:
    schema = ROOT / "schemas/run-profile.schema.json"
    smoke = load_yaml(EXP_ROOT / "run-plans/smoke.yaml")
    assert validate_instance(smoke, schema) == []
    interpreting = deepcopy(smoke)
    interpreting["interpretation_allowed"] = True
    assert validate_instance(interpreting, schema)
    authorized = deepcopy(smoke)
    authorized["execution"] = {
        "authorized": True,
        "authorization_reference": "AUTH-EXP0001-SMOKE",
    }
    assert validate_instance(authorized, schema) == []


def test_run_profile_schema_allows_known_revision_confirmatory_profiles() -> None:
    profile = deepcopy(load_yaml(EXP_ROOT / "run-plans/smoke.yaml"))
    profile["plan_id"] = "PLAN-SYNTHETIC-CONFIRMATORY"
    profile["profile"] = "confirmatory"
    profile["study_stage"] = "confirmatory"
    profile["interpretation_allowed"] = True
    profile["model"]["historical_revision_known"] = True
    profile["model"]["reproduction_level"] = "confirmatory-replication"
    profile["model"]["substitution"] = None
    profile["readiness"]["execution_eligibility"] = "eligible-after-authorization"
    profile["readiness"]["unresolved_execution_blockers"] = []
    assert validate_instance(profile, ROOT / "schemas/run-profile.schema.json") == []


def test_v01_profile_schema_remains_readable_while_current_readiness_policy_is_strict() -> None:
    schema = ROOT / "schemas/run-profile.schema.json"
    smoke = load_yaml(EXP_ROOT / "run-plans/smoke.yaml")
    blocked_eligible = deepcopy(smoke)
    blocked_eligible["readiness"]["unresolved_execution_blockers"] = [
        "A later integration decision is still unresolved."
    ]
    assert validate_instance(blocked_eligible, schema) == []
    assert validate_run_profile_readiness(blocked_eligible)

    pilot = load_yaml(EXP_ROOT / "run-plans/pilot.yaml")
    unblocked_but_ineligible = deepcopy(pilot)
    unblocked_but_ineligible["readiness"]["execution_eligibility"] = "blocked-pending-prerequisites"
    unblocked_but_ineligible["readiness"]["unresolved_execution_blockers"] = []
    assert validate_instance(unblocked_but_ineligible, schema) == []
    assert validate_run_profile_readiness(unblocked_but_ineligible)

    unauthorized_only = deepcopy(pilot)
    unauthorized_only["execution"] = {
        "authorized": True,
        "authorization_reference": "AUTH-EXP0001-PILOT",
    }
    assert validate_instance(unauthorized_only, schema) == []
    assert validate_run_profile_readiness(unauthorized_only) == []


def test_authorization_transition_is_schema_valid_but_does_not_execute() -> None:
    profile = deepcopy(load_yaml(EXP_ROOT / "run-plans/smoke.yaml"))
    profile["execution"] = {
        "authorized": True,
        "authorization_reference": "AUTH-EXP0001-SMOKE",
    }
    assert validate_instance(profile, ROOT / "schemas/run-profile.schema.json") == []
    for relative in profile["condition_plan_paths"]:
        condition = deepcopy(load_yaml(ROOT / relative))
        condition["execution"]["authorization"] = {
            "authorized": True,
            "authorization_reference": "AUTH-EXP0001-SMOKE",
            "command_sha256": "0" * 64,
        }
        assert validate_instance(condition, ROOT / "schemas/run-plan.schema.json") == []


def test_model_strategy_is_directional_reproduction_under_substitution() -> None:
    smoke = load_yaml(EXP_ROOT / "run-plans/smoke.yaml")
    model = smoke["model"]
    assert model["upstream_alias"] == "gpt-4o"
    assert model["proposed_immutable_revision"] == "gpt-4o-2024-11-20"
    assert model["historical_revision_known"] is False
    assert model["reproduction_level"] == "directional-reproduction"
    model_manifest = load_yaml(ROOT / "manifests/models.yaml")
    assert any(
        entry["id"] == model["manifest_id"]
        and entry["revision"] == model["proposed_immutable_revision"]
        for entry in model_manifest["entries"]
    )


def test_price_caps_are_exact_conservative_arithmetic_and_unauthorized() -> None:
    pricing = load_yaml(EXP_ROOT / "pricing.yaml")
    assert validate_instance(pricing, ROOT / "schemas/pricing.schema.json") == []
    output_rate = Decimal(str(pricing["rates_per_million_tokens"]["output"]))
    for profile_name in ("smoke", "pilot"):
        profile = pricing["profiles"][profile_name]
        per_attempt = (
            Decimal(profile["max_model_tokens_per_attempt"]) / Decimal(1_000_000)
        ) * output_rate
        assert per_attempt == Decimal(str(profile["max_cost_usd_per_attempt"]))
        assert per_attempt * profile["condition_attempts"] == Decimal(
            str(profile["proposed_profile_cap_usd"])
        )
        run_profile = load_yaml(EXP_ROOT / f"run-plans/{profile_name}.yaml")
        assert Decimal(str(run_profile["budget"]["max_cost_usd"])) == Decimal(
            str(profile["proposed_profile_cap_usd"])
        )
        assert pricing["authorization"][profile_name] is False
    assert pricing["model_manifest_id"] == "MODEL-OPENAI-GPT4O-2024-11-20"
    assert validate_exp0001_contract() == []


def test_h2k_appendix_is_additive_source_grounded_and_non_scientific() -> None:
    appendix = load_yaml(EXP_ROOT / "EVIDENCE_RETENTION_APPENDIX.yaml")
    assert appendix["future_consumer"] == "RQ-H2K"
    assert appendix["scientific_effect_on_exp0001"] == "none"
    assert {item["field"] for item in appendix["capture"]} == {
        "source_kind",
        "selected_mode",
        "policy_id",
        "policy_revision",
        "available_modes",
        "raw_source_references",
        "override",
        "fallback",
        "confidence",
        "field_provenance",
        "trace_sufficiency",
    }
    capture = {item["field"]: item for item in appendix["capture"]}
    for field in ("override", "fallback", "confidence"):
        assert capture[field]["requirement"] == "capture-only-when-present"
    assert "no-exp0001-metric-estimand-or-outcome-classification-effect" in appendix["prohibitions"]
    assert "does not support" in appendix["trace_sufficiency_boundary"]


def test_public_protocol_page_states_incomplete_calibration_and_future_track_boundary() -> None:
    page = (ROOT / "notebook/experiments/exp-0001-protocol.qmd").read_text(encoding="utf-8")
    prose = " ".join(page.split())
    assert "One T07 one-step reactive/simulative artifact smoke occurred" in prose
    assert "task completion was not observed" in prose
    assert "one descriptive full-task calibration measurement" in prose
    assert "no realized pair, checkpoint, condition comparison, or EXP-0001 outcome" in prose
    assert "not evidence of a learned internal regulation mechanism" in prose
    assert "not an EXP-0001 hypothesis, metric, outcome" in prose


def _copy_exp0001_contract(tmp_path: Path) -> Path:
    copytree(ROOT / "schemas", tmp_path / "schemas")
    copytree(EXP_ROOT, tmp_path / EXP_ROOT.relative_to(ROOT))
    copytree(ROOT / "manifests", tmp_path / "manifests")
    registry = load_yaml(ROOT / "experiments/registry.yaml")
    registry_path = tmp_path / "experiments/registry.yaml"
    registry_path.write_text(yaml.safe_dump(registry, sort_keys=False), encoding="utf-8")
    return tmp_path / EXP_ROOT.relative_to(ROOT)


def _write_yaml(path: Path, value: dict[str, object]) -> None:
    path.write_text(yaml.safe_dump(value, sort_keys=False), encoding="utf-8")


def _rebind_condition_profile_hashes(exp_root: Path) -> None:
    for name in ("smoke", "pilot"):
        profile_path = exp_root / f"run-plans/{name}.yaml"
        digest = hashlib.sha256(profile_path.read_bytes()).hexdigest()
        profile = load_yaml(profile_path)
        for relative in profile["condition_plan_paths"]:
            condition_path = exp_root / "run-plans/conditions" / Path(relative).name
            condition = load_yaml(condition_path)
            condition["profile_sha256"] = digest
            _write_yaml(condition_path, condition)


def test_profile_validation_rejects_swapped_order_and_model_drift(tmp_path: Path) -> None:
    exp_root = _copy_exp0001_contract(tmp_path)
    condition_path = exp_root / "run-plans/conditions/pilot-v6-task-0000-reactive.yaml"
    condition = load_yaml(condition_path)
    condition["pairing"]["order_index"] = 2
    condition["sources"]["model_revision"] = "wrong-revision"
    _write_yaml(condition_path, condition)
    errors = validate_experiment_run_profiles(tmp_path)
    assert any("pair identity/order mismatch" in error for error in errors)
    assert any("model revision/profile mismatch" in error for error in errors)


def test_exp0001_validation_rejects_duplicate_task_and_wrong_slice(tmp_path: Path) -> None:
    exp_root = _copy_exp0001_contract(tmp_path)
    profile_path = exp_root / "run-plans/pilot.yaml"
    profile = load_yaml(profile_path)
    profile["sampling"]["counterbalancing"][1]["task_id"] = "7dcbbbdc7f1120cd"
    _write_yaml(profile_path, profile)
    for name in ("pilot-v6-task-0000-reactive.yaml", "pilot-v6-task-0000-simulative.yaml"):
        condition_path = exp_root / "run-plans/conditions" / name
        condition = load_yaml(condition_path)
        condition["task"]["start_idx"] = 9
        condition["task"]["end_idx"] = 10
        _write_yaml(condition_path, condition)
    generic_errors = validate_experiment_run_profiles(tmp_path)
    specific_errors = validate_exp0001_contract(tmp_path)
    assert any("task IDs must be unique" in error for error in generic_errors)
    assert any("locked task or slice drift" in error for error in specific_errors)


def test_exp0001_validation_rejects_retry2_pair_overclaim(tmp_path: Path) -> None:
    exp_root = _copy_exp0001_contract(tmp_path)
    disposition_path = exp_root / "T09_PRAGMATIC_RETRY2_DISPOSITION.json"
    disposition = load_json(disposition_path)
    disposition["attempts"]["realized_task_a_pair"] = True
    disposition_path.write_text(
        json.dumps(disposition, indent=2) + "\n",
        encoding="utf-8",
    )
    errors = validate_exp0001_contract(tmp_path)
    assert any("one-attempt/no-pair disposition drifted" in error for error in errors)


def test_exp0001_validation_rejects_retry3_empirical_overclaim(tmp_path: Path) -> None:
    exp_root = _copy_exp0001_contract(tmp_path)
    disposition_path = exp_root / "T09_PRAGMATIC_RETRY3_DISPOSITION.json"
    disposition = load_json(disposition_path)
    disposition["attempts"]["empirical_attempts_entered"] = ["RUN-T09-TASK-A-REACTIVE-0003"]
    disposition_path.write_text(
        json.dumps(disposition, indent=2) + "\n",
        encoding="utf-8",
    )
    errors = validate_exp0001_contract(tmp_path)
    assert any("zero-attempt disposition drifted" in error for error in errors)


def test_profile_validation_rejects_task_source_and_dataset_revision_drift(
    tmp_path: Path,
) -> None:
    exp_root = _copy_exp0001_contract(tmp_path)
    profile_path = exp_root / "run-plans/pilot.yaml"
    profile = load_yaml(profile_path)
    profile["sampling"]["counterbalancing"][0]["task_source"] = "DATA-SIRA-FANOUTQA-DEV[8:9]"
    _write_yaml(profile_path, profile)
    condition_path = exp_root / "run-plans/conditions/pilot-v6-task-0000-reactive.yaml"
    condition = load_yaml(condition_path)
    condition["task"]["dataset_revision"] = "wrong-dataset-revision"
    _write_yaml(condition_path, condition)
    errors = validate_experiment_run_profiles(tmp_path)
    assert any("pair task source/slice mismatch" in error for error in errors)
    assert any("task/source dataset revision mismatch" in error for error in errors)


def test_profile_validation_rejects_open_query_prefix_drift(tmp_path: Path) -> None:
    exp_root = _copy_exp0001_contract(tmp_path)
    for name in ("smoke-reactive.yaml", "smoke-simulative.yaml"):
        condition_path = exp_root / "run-plans/conditions" / name
        condition = load_yaml(condition_path)
        condition["task"]["query"] = "go"
        _write_yaml(condition_path, condition)
    errors = validate_experiment_run_profiles(tmp_path)
    assert any("pair task source/query mismatch" in error for error in errors)


def test_profile_validation_rejects_parent_identity_and_hash_drift(tmp_path: Path) -> None:
    exp_root = _copy_exp0001_contract(tmp_path)
    condition_path = exp_root / "run-plans/conditions/smoke-reactive.yaml"
    condition = load_yaml(condition_path)
    condition["profile_plan_id"] = "PLAN-EXP0001-PILOT"
    condition["profile_sha256"] = "0" * 64
    _write_yaml(condition_path, condition)
    errors = validate_experiment_run_profiles(tmp_path)
    assert any("parent profile plan ID mismatch" in error for error in errors)
    assert any("parent profile hash mismatch" in error for error in errors)


def test_t05_control_plane_records_exact_base_and_no_stale_not_started_claim() -> None:
    ledger = (ROOT / "docs/harness/T05_ASSEMBLY_LEDGER.md").read_text(encoding="utf-8")
    plan = (
        ROOT / "docs/exec-plans/completed/PHASE_0_75_UPSTREAM_AUDIT_HARNESS_PROTOCOL_LOCK.md"
    ).read_text(encoding="utf-8")
    plan_prose = " ".join(plan.split())
    assert "471d6950087a1a10983aaa97bde8b2becf3b6aca" in ledger
    assert "T04.5 and T05 are complete" in plan_prose
    assert "T05 remains not-started" not in plan


def test_generic_profile_validator_does_not_impose_sira_conditions(tmp_path: Path) -> None:
    copytree(ROOT / "schemas", tmp_path / "schemas")
    generic_root = tmp_path / "experiments/EXP-0002-generic-pair"
    copytree(EXP_ROOT, generic_root)
    for path in generic_root.rglob("*.yaml"):
        text = path.read_text(encoding="utf-8")
        text = text.replace("EXP-0001-sira-simulative-vs-reactive", "EXP-0002-generic-pair")
        text = text.replace("EXP-0001", "EXP-0002")
        text = text.replace("SIRA-SIMULATIVE", "GENERIC-TREATMENT")
        text = text.replace("SIRA-REACTIVE", "GENERIC-CONTROL")
        path.write_text(text, encoding="utf-8")
    _rebind_condition_profile_hashes(generic_root)
    registry_path = tmp_path / "experiments/registry.yaml"
    registry_path.write_text(
        yaml.safe_dump(
            {
                "experiments": [
                    {
                        "experiment_id": "EXP-0002",
                        "protocol": "experiments/EXP-0002-generic-pair/protocol.yaml",
                        "run_profiles": [
                            "experiments/EXP-0002-generic-pair/run-plans/smoke.yaml",
                            "experiments/EXP-0002-generic-pair/run-plans/pilot.yaml",
                        ],
                    }
                ]
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    assert validate_experiment_run_profiles(tmp_path) == []


def test_materialized_pair_rejects_condition_owned_config_drift_but_not_command_hashes(
    tmp_path: Path,
) -> None:
    exp_root = _copy_exp0001_contract(tmp_path)
    profile_path = exp_root / "run-plans/smoke.yaml"
    profile = load_yaml(profile_path)
    profile["execution"] = {
        "authorized": True,
        "authorization_reference": "AUTH-EXP0001-SMOKE",
    }
    _write_yaml(profile_path, profile)
    _rebind_condition_profile_hashes(exp_root)
    for index, relative in enumerate(profile["condition_plan_paths"], start=1):
        condition_path = tmp_path / relative
        condition = load_yaml(condition_path)
        condition["sources"]["config_sha256"] = str(index) * 64
        condition["execution"]["authorization"] = {
            "authorized": True,
            "authorization_reference": "AUTH-EXP0001-SMOKE",
            "command_sha256": str(index + 2) * 64,
        }
        _write_yaml(condition_path, condition)
    errors = validate_experiment_run_profiles(tmp_path)
    assert errors
    assert any("matched pair source drift on config_sha256" in error for error in errors)
    assert not any("command_sha256" in error for error in errors)
