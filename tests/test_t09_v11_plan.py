from __future__ import annotations

import copy
import hashlib
import inspect
import json
import re
import subprocess
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

from giclab.harness import t09_pragmatic_provider as provider
from giclab.harness import t09_sira_pilot as pilot
from giclab.harness.t09_provider_contracts import (
    V10_PROVIDER_CONTRACT,
    V11_PROVIDER_CONTRACT,
)

ROOT = Path(__file__).resolve().parents[1]
EXP = ROOT / "experiments/EXP-0001-sira-simulative-vs-reactive"
PLAN_PATH = EXP / "run-plans/proposals/PLAN-EXP0001-PILOT-V11.yaml"
SCHEMA_PATH = ROOT / "schemas/t09-v11-plan.schema.json"
V9_DISPOSITION_PATH = EXP / "T09_AUTONOMOUS_RETRY2_V9_DISPOSITION.json"
V10_PLAN_PATH = EXP / "run-plans/proposals/PLAN-EXP0001-PILOT-V10.yaml"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha256_git_blob(relative: str, revision: str) -> str:
    raw = subprocess.run(
        ["git", "-C", str(ROOT), "show", f"{revision}:{relative}"],
        check=True,
        capture_output=True,
    ).stdout
    return hashlib.sha256(raw).hexdigest()


def load_plan() -> dict[str, object]:
    value = yaml.safe_load(PLAN_PATH.read_text())
    assert isinstance(value, dict)
    return value


def test_v11_plan_is_schema_valid_complete_and_unauthorized() -> None:
    plan = load_plan()
    schema = json.loads(SCHEMA_PATH.read_text())
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(plan)
    assert PLAN_PATH.stat().st_size == 14_754
    assert sha256_file(PLAN_PATH) == (
        "34a405d06521bd3fb55379721dff9c5795954fcb099d641587e2169b37575411"
    )

    assert plan["plan_id"] == "PLAN-EXP0001-PILOT-V11"
    assert plan["status"] == {
        "authorized": False,
        "execution_allowed": False,
        "cloud_mutation_allowed": False,
        "paid_compute_allowed": False,
        "live_qualification_performed": False,
        "pilot_executed": False,
        "future_execution_category": 3,
        "terminal_state": "implementation-complete-pr-review-and-merge-required",
        "authorization_rule": (
            "a fresh Category 3 Luna authorization must bind the exact reviewed "
            "merged commit and this plan SHA-256 before any provider or model request"
        ),
    }


def test_v11_plan_binds_exact_repaired_control_sources() -> None:
    bindings = load_plan()["implementation_bindings"]
    assert isinstance(bindings, dict)
    accounting = bindings["provider_accounting"]
    refinalization = bindings["offline_refinalization"]
    cleanup = bindings["early_cleanup"]
    publication = bindings["owned_container_publication"]
    execution = bindings["execution_plane"]
    assert isinstance(accounting, dict)
    assert isinstance(refinalization, dict)
    assert isinstance(cleanup, dict)
    assert isinstance(publication, dict)
    assert isinstance(execution, dict)

    bound_paths = {
        accounting["path"]: accounting["sha256"],
        accounting["regression_path"]: accounting["regression_sha256"],
        refinalization["finalizer_projection_path"]: refinalization["finalizer_projection_sha256"],
        refinalization["evaluator_driver_path"]: refinalization["evaluator_driver_sha256"],
        refinalization["selector_path"]: refinalization["selector_sha256"],
        refinalization["receipt_schema_path"]: refinalization["receipt_schema_sha256"],
        cleanup["implementation_path"]: cleanup["implementation_sha256"],
        cleanup["provider_integration_path"]: cleanup["provider_integration_sha256"],
        cleanup["schema_path"]: cleanup["schema_sha256"],
        publication["reader_path"]: publication["reader_sha256"],
        publication["regression_path"]: publication["regression_sha256"],
        execution["pilot_library_path"]: execution["pilot_library_sha256"],
        execution["campaign_lifecycle_path"]: execution["campaign_lifecycle_sha256"],
        execution["provider_path"]: execution["provider_sha256"],
        execution["provider_contracts_path"]: execution["provider_contracts_sha256"],
        execution["remote_runner_path"]: execution["remote_runner_sha256"],
        execution["command_generator_path"]: execution["command_generator_sha256"],
        execution["runtime_profile_path"]: execution["runtime_profile_sha256"],
        execution["execution_contract_path"]: execution["execution_contract_sha256"],
        execution["command_manifests_path"]: execution["command_manifests_sha256"],
        execution["runtime_identity_path"]: execution["runtime_identity_sha256"],
        execution["execution_schema_path"]: execution["execution_schema_sha256"],
    }
    reviewed_ancestor = str(bindings["reviewed_implementation_ancestor"])
    for relative, expected_sha256 in bound_paths.items():
        assert isinstance(relative, str)
        observed = (
            sha256_git_blob(relative, reviewed_ancestor)
            if relative.endswith(".py")
            else sha256_file(ROOT / relative)
        )
        assert observed == expected_sha256
    condition_plans = execution["condition_plans"]
    assert isinstance(condition_plans, list)
    for item in condition_plans:
        assert isinstance(item, dict)
        assert sha256_file(ROOT / item["path"]) == item["sha256"]

    assert accounting["reservation_projection"] == (
        "authoritative-owned-per-call-records-math-fsum-exact-empty"
    )
    assert accounting["repeated_subtractive_bookkeeping"] is False
    assert accounting["automatic_retries"] == 0
    assert refinalization["network_disabled"] is True
    assert refinalization["model_replay_count"] == 0
    assert refinalization["browser_replay_count"] == 0
    assert refinalization["raw_mutation"] is False
    assert cleanup["initialize_before_package_transition"] is True
    assert cleanup["cross_host_journal_mode"] == (
        "one-hash-chain-provider-prefix-remote-continuation"
    )
    assert cleanup["provider_closeout_remote_journal_argument"] == ("--remote-cleanup-journal")
    assert cleanup["provider_termination_requires_optional_state"] is False
    assert cleanup["public_alias_is_cleanup_authority"] is False
    assert cleanup["optional_pilot_state_required"] is False
    assert publication == {
        **publication,
        "safe_zero_length_state": "publication-pending",
        "descriptor_no_follow_required": True,
        "exact_daemon_published_id_required": True,
        "exact_id_cleanup_only": True,
        "name_based_cleanup_authority": False,
    }


def test_v11_execution_plane_is_typed_renderable_and_statically_unauthorized() -> None:
    bindings = load_plan()["implementation_bindings"]
    assert isinstance(bindings, dict)
    execution = bindings["execution_plane"]
    assert isinstance(execution, dict)
    execution_path = ROOT / str(execution["execution_contract_path"])
    execution_document = json.loads(execution_path.read_text())
    execution_schema = json.loads((ROOT / str(execution["execution_schema_path"])).read_text())
    Draft202012Validator(execution_schema).validate(execution_document)
    loaded = pilot.load_execution_contract(
        execution_path,
        expected_sha256=str(execution["execution_contract_sha256"]),
    )
    assert tuple(attempt.run_id for attempt in loaded.attempts) == (
        V11_PROVIDER_CONTRACT.attempt_order
    )
    assert V11_PROVIDER_CONTRACT.plan_id == "PLAN-EXP0001-PILOT-V11"
    assert V11_PROVIDER_CONTRACT.host_run_id == "RUN-T09-PILOT-HOST-AUTONOMOUS-0004"
    assert execution_document["authorized"] is False
    assert execution_document["authorization_reference"] is None
    assert execution_document["execution_eligibility"] == (
        "blocked-until-fresh-category-3-authorization"
    )
    lifecycle = execution_document["provider_lifecycle"]
    assert lifecycle["model_metadata_before_lambda_launch"] is True
    assert lifecycle["model_metadata_request_count"] == 1
    assert lifecycle["model_metadata_snapshot"] == "gpt-4o-2024-11-20"
    assert lifecycle["model_substitution_allowed"] is False
    assert lifecycle["immutable_model_unavailable_disposition"] == (
        "stop-before-lambda-launch-zero-lambda-cost"
    )

    # V11 is stopped operational evidence.  Its command manifest remains
    # byte-identified at the reviewed ancestor; the mutable generator is
    # exercised against the successor package in the V12 regressions.
    commands = json.loads((ROOT / str(execution["command_manifests_path"])).read_text())
    assert commands["plan_id"] == "PLAN-EXP0001-PILOT-V11"
    assert commands["reviewed_implementation_ancestor"] == (
        "e91eccc01fa8d479cdfff270a8032dfb6283f5b4"
    )
    assert all(pair["valid"] is True for pair in commands["pair_diffs"])


def test_v11_scientific_hash_regression_is_unchanged() -> None:
    plan = load_plan()
    science = plan["scientific_contract"]
    assert isinstance(science, dict)
    assert science["experiment_id"] == "EXP-0001"
    assert science["sira_commit"] == "93fb8d72de71f9a4a13419670adeb34d93cf7acd"
    assert science["model_revision_for_every_role"] == "gpt-4o-2024-11-20"
    assert science["protocol_sha256"] == sha256_file(EXP / "protocol.yaml")
    assert science["config_sha256"] == sha256_file(EXP / "config.yaml")
    dataset = science["dataset"]
    evaluator = science["evaluator"]
    assert isinstance(dataset, dict)
    assert isinstance(evaluator, dict)
    assert dataset == {
        "name": "FanOutQA November 2023 development snapshot",
        "source_commit": "989f4c40d9deea1ecb0897d7a17a9c0fe20d5c33",
        "sira_blob": "76ad1feb689b754bfe4e5e24d3ea371b647efa67",
        "sha256": "359300b029c6891567816f351bf8786e9b018d7af8a1a44b7da9ba5ef4651288",
    }
    assert evaluator["commit"] == science["sira_commit"]
    assert evaluator["contract_sha256"] == sha256_file(
        EXP / "contracts/T09_PILOT_EVALUATOR_CONTRACT.json"
    )
    assert evaluator["primary_score"] == "acc_loose"
    assert evaluator["provider_request_required"] is False

    attempts = plan["attempts"]
    assert isinstance(attempts, list)
    projected = [
        {
            "task_id": attempt["task_id"],
            "task_sha256": attempt["task_sha256"],
            "reference_sha256": attempt["reference_sha256"],
            "record_sha256": attempt["record_sha256"],
            "condition": attempt["condition"],
            "order_index": attempt["order_index"],
            "dataset_start_index": attempt["dataset_start_index"],
            "dataset_end_index": attempt["dataset_end_index"],
        }
        for attempt in attempts
        if isinstance(attempt, dict)
    ]
    assert projected == [
        {
            "task_id": "7dcbbbdc7f1120cd",
            "task_sha256": "153a4f251fbeb29bee8e5ca4626e6db14426063728b0d5cfa7eed3a9a230992b",
            "reference_sha256": "fc40734fa183e839b56a7c89b16faa5900865cbee7a4210fcb251a99176f98de",
            "record_sha256": "cc5c3fdeea2c1f58b6160175bd3104dbea40c290ea8b390d29413e6410d97e15",
            "condition": "reactive",
            "order_index": 1,
            "dataset_start_index": 0,
            "dataset_end_index": 1,
        },
        {
            "task_id": "7dcbbbdc7f1120cd",
            "task_sha256": "153a4f251fbeb29bee8e5ca4626e6db14426063728b0d5cfa7eed3a9a230992b",
            "reference_sha256": "fc40734fa183e839b56a7c89b16faa5900865cbee7a4210fcb251a99176f98de",
            "record_sha256": "cc5c3fdeea2c1f58b6160175bd3104dbea40c290ea8b390d29413e6410d97e15",
            "condition": "simulative",
            "order_index": 2,
            "dataset_start_index": 0,
            "dataset_end_index": 1,
        },
        {
            "task_id": "2120afba8009bad3",
            "task_sha256": "9b2b443898959b28c7408ed1ff56ebd332c9e7f2142657c11c7d09aa507ba66e",
            "reference_sha256": "2ee9d892e24441d5f5bbf31b7616c1ade5977af26d22e4020f92a162fa23becb",
            "record_sha256": "5f5a8ad5353b839def2ffc968c36c4314bb830f11f10268f410faa37690bc129",
            "condition": "simulative",
            "order_index": 1,
            "dataset_start_index": 1,
            "dataset_end_index": 2,
        },
        {
            "task_id": "2120afba8009bad3",
            "task_sha256": "9b2b443898959b28c7408ed1ff56ebd332c9e7f2142657c11c7d09aa507ba66e",
            "reference_sha256": "2ee9d892e24441d5f5bbf31b7616c1ade5977af26d22e4020f92a162fa23becb",
            "record_sha256": "5f5a8ad5353b839def2ffc968c36c4314bb830f11f10268f410faa37690bc129",
            "condition": "reactive",
            "order_index": 2,
            "dataset_start_index": 1,
            "dataset_end_index": 2,
        },
    ]


def normalized_pair_command(attempt: dict[str, object]) -> list[str]:
    argv = list(attempt["upstream_argv"])
    mode_index = argv.index("--mode") + 1
    config_index = argv.index("--config_name") + 1
    argv[mode_index] = "<CONDITION>"
    argv[config_index] = "<TREATMENT-CONFIG>"
    return argv


def test_v11_pair_command_and_configuration_diff_is_exact() -> None:
    attempts = load_plan()["attempts"]
    assert isinstance(attempts, list)
    typed_attempts = [attempt for attempt in attempts if isinstance(attempt, dict)]
    assert len(typed_attempts) == 4
    for left, right in (
        (typed_attempts[0], typed_attempts[1]),
        (typed_attempts[2], typed_attempts[3]),
    ):
        assert left["task_id"] == right["task_id"]
        assert left["task_sha256"] == right["task_sha256"]
        assert left["reference_sha256"] == right["reference_sha256"]
        assert left["record_sha256"] == right["record_sha256"]
        assert left["dataset_start_index"] == right["dataset_start_index"]
        assert left["dataset_end_index"] == right["dataset_end_index"]
        assert {left["condition"], right["condition"]} == {"reactive", "simulative"}
        assert normalized_pair_command(left) == normalized_pair_command(right)
        assert left["upstream_argv"].count("--max_retry") == 1
        retry_index = left["upstream_argv"].index("--max_retry")
        assert left["upstream_argv"][retry_index + 1] == "0"


def test_v11_fresh_identities_checkpoint_and_no_run_root_consumption() -> None:
    plan = load_plan()
    identities = plan["identities"]
    runtime = plan["runtime_contract"]
    attempts = plan["attempts"]
    assert isinstance(identities, dict)
    assert isinstance(runtime, dict)
    assert isinstance(attempts, list)
    run_ids = [attempt["run_id"] for attempt in attempts if isinstance(attempt, dict)]
    assert run_ids == identities["attempt_order"]
    assert len(run_ids) == len(set(run_ids)) == 4
    assert all(str(run_id).endswith("AUTONOMOUS-0004") for run_id in run_ids)
    assert all("AUTONOMOUS-0002" not in str(run_id) for run_id in run_ids)
    assert all("AUTONOMOUS-0003" not in str(run_id) for run_id in run_ids)
    checkpoint = runtime["first_pair_checkpoint"]
    assert isinstance(checkpoint, dict)
    assert checkpoint["after_run_id"] == run_ids[1]
    assert checkpoint["required_before_task_b"] is True
    assert all(
        attempt["output_root"] == "not-materialized-until-category-3"
        for attempt in attempts
        if isinstance(attempt, dict)
    )
    artifact_root = ROOT / "artifacts"
    assert not any(
        "autonomous-0004" in str(path).lower() for path in artifact_root.rglob("*") if path.is_dir()
    )


def test_v11_source_identity_metadata_order_and_conservative_budget_are_exact() -> None:
    plan = load_plan()
    bindings = plan["implementation_bindings"]
    budget = plan["budget_contract"]
    preconditions = plan["category_3_preconditions"]
    assert isinstance(bindings, dict)
    assert isinstance(budget, dict)
    assert isinstance(preconditions, list)
    assert bindings["required_base_commit"] == "1c6b093699288f37aa23526fe1e1672e50280093"
    assert bindings["required_base_tree"] == "39501c69af3296ce271d38aa235c26d80175a4b1"
    assert bindings["required_base_parent_2"] == "a2b30012bdf09080da844451ad0d987dde5da646"
    assert bindings["reviewed_implementation_ancestor"] == (
        "e91eccc01fa8d479cdfff270a8032dfb6283f5b4"
    )
    assert budget["prior_t09_observed_lower_bound_usd"] == 15.3545995873264159
    assert budget["prior_t09_conservative_upper_bound_usd"] == 33.1487895873264159
    assert budget["maximum_new_total_cost_usd"] == 58.0
    assert budget["effective_maximum_new_total_cost_under_cumulative_cap_usd"] == (
        56.8512104126735841
    )
    assert (
        budget["prior_t09_conservative_upper_bound_usd"]
        + budget["effective_maximum_new_total_cost_under_cumulative_cap_usd"]
        <= budget["cumulative_t09_cost_cap_usd"]
    )
    assert any(
        "exactly one authenticated gpt-4o-2024-11-20 model-metadata GET" in item
        and "zero Lambda cost" in item
        for item in preconditions
    )


def test_v10_plan_remains_exact_immutable_historical_operational_evidence() -> None:
    assert V10_PLAN_PATH.stat().st_size == 13_426
    assert sha256_file(V10_PLAN_PATH) == (
        "17c6502c625e0a3fcabc99180b0a432a60b27557be6a88f3289e45720951b38b"
    )
    assert V10_PROVIDER_CONTRACT.plan_id == "PLAN-EXP0001-PILOT-V10"
    evidence = load_plan()["evidence_contract"]
    assert isinstance(evidence, dict)
    assert evidence["v10_stopped_category_3_artifacts_are_immutable_operational_evidence"] is True
    assert evidence["v10_conditions_eligible_for_v11_pairing"] is False


def test_v11_cleanup_authority_precedes_post_identity_package_transition() -> None:
    source = inspect.getsource(provider._launch_campaign_impl)
    exact_id = source.index("instance_id = instance_ids[0]")
    cleanup_initialize = source.index("_initial_preflight_cleanup_state(", exact_id)
    package_transition = source.index("CleanupLifecycleStage.PACKAGE_TRANSITION", exact_id)
    provisional_source = source.index("_provisional_owner_binding(", exact_id)
    source_staging = source.index("CleanupLifecycleStage.SOURCE_STAGING", exact_id)
    assert exact_id < cleanup_initialize < package_transition < provisional_source < source_staging

    provider_source = (ROOT / "src/giclab/harness/t09_pragmatic_provider.py").read_text()
    remote_source = (ROOT / "containers/sira-smoke/pragmatic/t09_remote_runner.py").read_text()
    assert 'closeout.add_argument("--remote-cleanup-journal", type=Path)' in provider_source
    assert "ACTIVE_PROVIDER_CONTRACT" not in remote_source
    assert "contract.container_prefix" in remote_source
    assert V11_PROVIDER_CONTRACT.container_prefix == "giclab-t09-pilot-v11-autonomous-"
    assert "import_continuation(remote)" in provider_source


def contains_secret_or_private_ip(value: object) -> bool:
    encoded = json.dumps(value, sort_keys=True)
    secret_patterns = (
        r"sk-[A-Za-z0-9_-]{16,}",
        r"(?i)(?:api[_-]?key|password|token)\s*[=:]\s*[^,}\s]+",
        r"\b(?:10\.|192\.168\.|172\.(?:1[6-9]|2[0-9]|3[01])\.)\d{1,3}\.\d{1,3}",
    )
    return any(re.search(pattern, encoded) is not None for pattern in secret_patterns)


def test_v11_plan_privacy_and_secret_canary_regression() -> None:
    plan = load_plan()
    assert not contains_secret_or_private_ip(plan)
    canary = copy.deepcopy(plan)
    assert isinstance(canary["status"], dict)
    canary["status"]["authorization_rule"] = (
        "OPENAI_" + "API_KEY" + "=" + "s" + "k-" + "public-fixture-canary-value"
    )
    assert contains_secret_or_private_ip(canary)


def test_v9_disposition_remains_immutable_historical_nonpair_evidence() -> None:
    disposition = json.loads(V9_DISPOSITION_PATH.read_text())
    assert disposition["plan_id"] == "PLAN-EXP0001-PILOT-V9"
    assert disposition["qualification_and_freeze"] == {
        **disposition["qualification_and_freeze"],
        "frozen_package_commit": "630e6f9fcd22f6998d14e4fa48aee2224f6b2808",
        "replacement_image_id": (
            "sha256:abe8ed38f5c5b5a0a63fa726a74034dc5c192a12c0fccfe1319f97c27ceaf0a3"
        ),
        "frozen_run_manifest_sha256": (
            "9f75c6d1fc22cbb0df713df8a40671165bffe0232b2254d7ad416d01a73c1378"
        ),
    }
    task_a_reactive = disposition["attempts"]["task_a_reactive"]
    task_a_simulative = disposition["attempts"]["task_a_simulative"]
    assert task_a_reactive["state"] == "valid-scored-condition-failure"
    assert task_a_reactive["score"] == 0.0
    assert task_a_reactive["model_call_attempts"] == 20
    assert task_a_reactive["total_tokens"] == 40152
    assert task_a_reactive["browser_actions"] == 5
    assert task_a_reactive["openai_cost_usd"] == 0.1232325
    assert task_a_simulative["state"] == "consumed-infrastructure-invalid-unscored"
    assert task_a_simulative["model_call_attempts"] == 12
    assert task_a_simulative["terminal_reconciled_responses"] == 11
    assert (
        task_a_simulative["terminal_reconciled_responses"]
        + task_a_simulative["unreconciled_provider_attempts"]
        == 12
    )
    assert task_a_simulative["unreconciled_provider_attempts"] == 1
    assert task_a_simulative["unknown_outcomes"] == 0
    assert disposition["pair_matching"]["paired_or_comparative_interpretation_permitted"] is False
