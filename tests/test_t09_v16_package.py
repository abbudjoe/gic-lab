from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import cast

import yaml
from jsonschema import Draft202012Validator

from giclab.harness.t09_provider_contracts import (
    V15_PROVIDER_CONTRACT,
    V16_PROVIDER_CONTRACT,
)
from giclab.harness.t09_sira_pilot import command_argv_sha256, load_execution_contract
from giclab.validation import validate_t09_v16_plan

ROOT = Path(__file__).resolve().parents[1]
EXP = ROOT / "experiments/EXP-0001-sira-simulative-vs-reactive"
PLAN = EXP / "run-plans/proposals/PLAN-EXP0001-PILOT-V16.yaml"
PROFILE = EXP / "run-plans/proposals/T09_PILOT_RUNTIME_PROFILE_V16.yaml"
EXECUTION = EXP / "contracts/proposals/T09_PILOT_EXECUTION_CONTRACT_V16.json"
COMMANDS = EXP / "contracts/proposals/T09_PILOT_COMMAND_MANIFESTS_V16.json"
DISPOSITION = EXP / "T09_V15_EMPIRICAL_PREFIX_STOPPED_DISPOSITION.json"
CORE_COMMIT = "a235d1e6d287b5ea9daf5ca3787f9bbca278f3aa"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_script(name: str, relative: str) -> ModuleType:
    specification = importlib.util.spec_from_file_location(name, ROOT / relative)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


FREEZE = _load_script(
    "giclab_test_t09_v16_freeze_commands",
    "containers/sira-smoke/pragmatic/t09_freeze_commands.py",
)


def test_v16_package_is_exact_unauthorized_and_valid() -> None:
    plan = yaml.safe_load(PLAN.read_text())
    schema = json.loads((ROOT / "schemas/t09-v16-plan.schema.json").read_text())
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(plan)
    assert validate_t09_v16_plan(ROOT) == []
    assert (PLAN.stat().st_size, _sha256(PLAN)) == (
        20_851,
        "5a71e77b1d6876be856012b3ca8ed1456cf31a9321aca9bfaca73b13c659a939",
    )
    assert (PROFILE.stat().st_size, _sha256(PROFILE)) == (
        15_897,
        "80962bb30ed6aa879e4c1e8c7d7e25a119375c28e0897cd02e3ff1c0aa15b41a",
    )
    assert (COMMANDS.stat().st_size, _sha256(COMMANDS)) == (
        23_521,
        "377e45728dc53221e42e7910d0f13f14ed219dd947371c48d9730f1f3140507b",
    )
    status = cast(dict[str, object], plan["status"])
    assert all(
        status[field] is False
        for field in (
            "authorized",
            "execution_allowed",
            "cloud_mutation_allowed",
            "paid_compute_allowed",
            "live_qualification_performed",
            "pilot_executed",
        )
    )
    assert plan["identities"]["empirical_run_roots_materialized"] is False
    assert not (ROOT / "artifacts/EXP-0001/pilot-v16").exists()


def test_v16_binds_base_core_history_and_exact_decimal_accounting() -> None:
    plan = yaml.safe_load(PLAN.read_text())
    bindings = plan["implementation_bindings"]
    assert bindings["required_base_commit"] == "be09fe18dd46d0e5fe1aa65cfac29190edfa8aac"
    assert bindings["required_base_tree"] == "ff6242c0e57f11e1b0ca158a5af3bb782865782b"
    assert bindings["required_base_parent_1"] == "bce89afa79a120f7f5acb22fb20512ec9581f7a5"
    assert bindings["required_base_parent_2"] == "c764c852597b7c7a8f67f91963cfb749386c6887"
    assert bindings["reviewed_implementation_ancestor"] == CORE_COMMIT
    stopped = bindings["v15_empirical_prefix_stopped_disposition"]
    assert stopped == {
        "path": str(DISPOSITION.relative_to(ROOT)),
        "size_bytes": 3301,
        "sha256": "7222144a6d46ecb3590163a0db48ddcb210a162472bdea6b87a14f10d8633d70",
    }
    budget = plan["budget_contract"]
    assert budget["prior_t09_conservative_upper_bound_usd_decimal"] == ("36.36170860803283125")
    assert budget["effective_maximum_new_total_cost_under_cumulative_cap_usd_decimal"] == (
        "53.63829139196716875"
    )
    assert budget["v15_new_total_usd_decimal"] == "1.50565323024988195"


def test_v16_identities_are_fresh_and_science_is_unchanged() -> None:
    plan = yaml.safe_load(PLAN.read_text())
    v15 = yaml.safe_load((EXP / "run-plans/proposals/PLAN-EXP0001-PILOT-V15.yaml").read_text())
    assert plan["scientific_contract"] == v15["scientific_contract"]
    execution = json.loads(EXECUTION.read_text())
    loaded = load_execution_contract(EXECUTION, expected_sha256=_sha256(EXECUTION))
    assert loaded.provider_contract_version == "V16"
    assert tuple(attempt.run_id for attempt in loaded.attempts) == (
        V16_PROVIDER_CONTRACT.attempt_order
    )
    assert set(V16_PROVIDER_CONTRACT.attempt_order).isdisjoint(V15_PROVIDER_CONTRACT.attempt_order)
    assert set(V16_PROVIDER_CONTRACT.evaluator_run_ids).isdisjoint(
        V15_PROVIDER_CONTRACT.evaluator_run_ids
    )
    assert execution["runtime"]["local_finalizer_qualification_selector"] == [
        "--provider-contract",
        "V16",
    ]


def test_v16_command_document_equals_two_fresh_renders_and_self_hashes() -> None:
    first = FREEZE.render(ROOT, provider_version="V16")
    second = FREEZE.render(ROOT, provider_version="V16")
    first_bytes = FREEZE.encode_command_manifest_document(first)
    assert first_bytes == FREEZE.encode_command_manifest_document(second)
    assert first_bytes == COMMANDS.read_bytes()
    assert first["reviewed_implementation_ancestor"] == CORE_COMMIT
    selector = {"argument": "--provider-contract", "value": "V16"}
    for manifest in first["manifests"]:
        assert manifest["argv_sha256"] == command_argv_sha256(manifest["argv"])
        assert manifest["equality_surface"]["provider_contract_selector"] == selector
    assert len(first["pair_diffs"]) == 2
    assert all(pair["valid"] is True for pair in first["pair_diffs"])
    assert all(pair["required_equality_surface_equal"] is True for pair in first["pair_diffs"])


def test_v15_empirical_prefix_is_historical_and_not_pairable() -> None:
    stopped = json.loads(DISPOSITION.read_text())
    assert stopped["attempt"]["scientific_identity_consumed"] is True
    assert stopped["attempt"]["provider_call_accounting"] == {
        "outstanding_reservations": 0,
        "sent_response_reconciled": 24,
        "unknown": 0,
        "unreconciled": 0,
    }
    assert stopped["scientific_disposition"] == {
        "comparison_permitted": False,
        "realized_pair": None,
        "result_assignment": "stopped-condition-not-a-scientific-result",
    }
    plan = yaml.safe_load(PLAN.read_text())
    evidence = plan["evidence_contract"]
    assert evidence["v15_empirical_prefix_artifacts_are_immutable_historical_evidence"] is True
    assert evidence["v15_conditions_eligible_for_v16_pairing"] is False
