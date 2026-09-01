from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from giclab.control.anti_shadow_lint import (
    lint_effect_neutral_source,
    validate_anti_shadow_lint,
)
from giclab.control.live_conformance import run_live_effect_conformance
from giclab.registry import load_json

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def conformance() -> dict[str, object]:
    return run_live_effect_conformance(ROOT)


def test_live_shaped_package_effect_conformance_is_schema_valid(
    conformance: dict[str, object],
) -> None:
    Draft202012Validator(
        load_json(ROOT / "schemas/t09-live-effect-conformance-receipt.schema.json")
    ).validate(conformance)
    assert conformance["complete"] is True
    assert conformance["shared_source_byte_map_unchanged"] is True
    assert conformance["actual_v17_artifacts_present"] is False
    assert conformance["actual_v17_artifacts_created"] is False
    assert conformance["network_provider_cloud_browser_science_effects"] == 0
    assert conformance["live_authority_created"] is False
    assert conformance["scientific_interpretation_allowed"] is False


def test_live_shaped_package_uses_exact_shared_controller_and_assembly(
    conformance: dict[str, object],
) -> None:
    assert conformance["shared_controller_entry_point"] == (
        "giclab.control.category3.execute_category3_transaction"
    )
    assert conformance["production_assembly_entry_point"] == (
        "giclab.control.production.build_production_adapter_assembly"
    )
    package = conformance["temporary_package"]
    assert isinstance(package, dict)
    assert package["controller_terminal_state"] == "category3-live-complete-clean"
    assert package["zero_real_effects"] is True
    assert package["repository_state_grants_authority"] is False
    assert package["projected_real_cost_usd"] == "0.00"


def test_live_shaped_metadata_clock_and_multievent_sessions(
    conformance: dict[str, object],
) -> None:
    package = conformance["temporary_package"]
    assert isinstance(package, dict)
    metadata = package["metadata"]
    clock = package["clock"]
    traces = package["condition_traces"]
    assert isinstance(metadata, dict) and isinstance(clock, dict) and isinstance(traces, dict)
    assert metadata == {
        "noncanonical_runtime_credential_reached_channel": True,
        "request_count": 1,
        "zero_retry": True,
        "zero_redirect": True,
        "zero_pagination": True,
        "credential_material_retained": False,
    }
    assert clock["injected"] is True
    assert clock["domains_separate"] is True
    assert 0.25 in clock["sleep_calls"]
    reactive = [value for run_id, value in traces.items() if "REACTIVE" in run_id]
    simulative = [value for run_id, value in traces.items() if "SIMULATIVE" in run_id]
    assert len(reactive) == len(simulative) == 2
    assert all(item["model_call_count"] >= 3 for item in reactive)
    assert all(len(item["model_roles"]) >= 2 for item in reactive)
    assert all(item["model_call_count"] >= 5 for item in simulative)
    assert all(len(item["model_roles"]) >= 3 for item in simulative)
    assert all(item["browser_action_count"] >= 2 for item in traces.values())
    accounting = package["model_call_accounting"]
    browser = package["browser_accounting"]
    assert isinstance(accounting, dict) and isinstance(browser, dict)
    assert accounting["total_calls"] == 16
    assert accounting["stable_unique_call_ids"] is True
    assert accounting["terminal_states_complete"] is True
    assert accounting["zero_retries"] is True
    assert browser["total_actions"] == 8
    failures = package["typed_failure_accounting"]
    assert isinstance(failures, dict)
    assert failures["known-provider-exception"] == {
        "terminal_state": "sent_provider_error_reconciled",
        "unknown_outcomes": 0,
        "model_call_attempts": 1,
        "zero_retries": True,
    }
    for name in ("ambiguous-task-model-send", "response-accounting-incomplete"):
        assert failures[name] == {
            "terminal_state": "sent_outcome_unknown",
            "unknown_outcomes": 1,
            "model_call_attempts": 1,
            "zero_retries": True,
        }


def test_live_shaped_package_loads_exact_plan_owned_budgets(
    conformance: dict[str, object],
) -> None:
    package = conformance["temporary_package"]
    assert isinstance(package, dict)
    budget = package["package_budget"]
    assert isinstance(budget, dict)
    aggregate = budget["aggregate_caps"]
    conditions = budget["condition_caps"]
    assert isinstance(aggregate, dict) and isinstance(conditions, dict)
    assert aggregate == {
        "max_cost_usd": 40.0,
        "max_input_tokens": 4_000_000,
        "max_cached_input_tokens": 4_000_000,
        "max_output_tokens": 4_000_000,
        "max_total_tokens": 4_000_000,
        "max_model_call_attempts": 4_620,
        "max_wall_seconds": 14_400,
        "max_browser_actions": 120,
        "max_output_bytes": 2_147_483_648,
    }
    assert set(conditions) == set(budget["attempt_order"])
    assert all(
        condition
        == {
            "max_cost_usd": 10.0,
            "max_input_tokens": 1_000_000,
            "max_cached_input_tokens": 1_000_000,
            "max_output_tokens": 1_000_000,
            "max_total_tokens": 1_000_000,
            "max_model_call_attempts": 1_155,
            "max_wall_seconds": 3_600,
            "max_browser_actions": 30,
            "max_output_bytes": 536_870_912,
        }
        for condition in conditions.values()
    )
    assert budget["zero_retry"] is True
    assert budget["model_revision"] == "gpt-4o-2024-11-20"
    assert budget["service_tier"] == "default"


def test_live_shaped_host_raw_finalizer_evaluator_and_cleanup_chain(
    conformance: dict[str, object],
) -> None:
    package = conformance["temporary_package"]
    assert isinstance(package, dict)
    host = package["host_transaction"]
    chain = package["raw_finalizer_evaluator_chain"]
    cleanup = package["cleanup"]
    assert isinstance(host, dict) and isinstance(chain, dict) and isinstance(cleanup, dict)
    assert all(host.values())
    assert chain == {
        "attempt_count": 4,
        "raw_files_hash_validated": True,
        "finalizer_consumed_raw_manifests": True,
        "effect_answer_reached_finalized_session": True,
        "evaluator_consumed_finalized_sessions": True,
    }
    assert cleanup == {
        "state": "complete",
        "resumed": False,
        "provider_resources_zero": True,
        "security_restored": True,
        "privacy_clean": True,
    }


def test_anti_shadow_lint_inventory_and_mutations() -> None:
    receipt = validate_anti_shadow_lint(ROOT)
    Draft202012Validator(
        load_json(ROOT / "schemas/t09-anti-shadow-lint-receipt.schema.json")
    ).validate(receipt)
    assert receipt["complete"] is True
    assert receipt["findings"] == []
    base_inventory = receipt["base_assumption_inventory"]
    assert isinstance(base_inventory, list)
    assert [item["assumption_id"] for item in base_inventory] == [
        f"SA-{index:02d}" for index in range(1, 13)
    ]
    assert all(
        item["classification"] == "shared production-wrapper defect" for item in base_inventory
    )
    counts = receipt["classification_counts"]
    assert isinstance(counts, dict)
    assert counts["shared production-wrapper defect"] == 0

    source = """
credential = _FAKE_OPENAI_VALUE
call_id = 'CALL-SHADOW-1'
answer = _TASK_A_ANSWER
caps = ProviderBudgetCaps(max_model_call_attempts=1)
"""
    findings = lint_effect_neutral_source(source, relative_path="src/giclab/control/effects.py")
    assert {item.code for item in findings} == {"T09S001", "T09S003", "T09S006", "T09S011"}


def test_conformance_semantic_hash_is_exact(conformance: dict[str, object]) -> None:
    document = dict(conformance)
    observed = document.pop("semantic_sha256")
    encoded = json.dumps(
        document,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    assert observed == hashlib.sha256(encoded).hexdigest()
