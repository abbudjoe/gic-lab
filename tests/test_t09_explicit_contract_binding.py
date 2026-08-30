from __future__ import annotations

import importlib.util
import inspect
import json
from dataclasses import replace
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

from giclab.harness.t09_provider_contracts import (
    V11_PROVIDER_CONTRACT,
    V12_PROVIDER_CONTRACT,
    V13_PROVIDER_CONTRACT,
    T09ProviderContractError,
    provider_contract,
    provider_contract_for_plan_id,
)
from giclab.harness.t09_sira_pilot import (
    load_aggregate_observed_usage,
    load_aggregate_usage,
    write_aggregate_usage,
)

ROOT = Path(__file__).resolve().parents[1]
QUALIFIER_PATH = ROOT / "containers/sira-smoke/pragmatic/t09_local_finalizer_qualification.py"
V11_EXECUTION = ROOT / str(V11_PROVIDER_CONTRACT.execution_contract_path)
V12_EXECUTION = ROOT / str(V12_PROVIDER_CONTRACT.execution_contract_path)
V13_EXECUTION = ROOT / str(V13_PROVIDER_CONTRACT.execution_contract_path)


def _load_qualifier() -> ModuleType:
    specification = importlib.util.spec_from_file_location(
        "giclab_t09_explicit_local_qualification_test",
        QUALIFIER_PATH,
    )
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def _legacy_v11_global_check(execution_path: Path, qualifier: ModuleType) -> None:
    execution = json.loads(execution_path.read_text(encoding="utf-8"))
    if execution["plan_id"] != V11_PROVIDER_CONTRACT.plan_id:
        raise qualifier.LocalQualificationError("local finalizer execution contract drifted")


def test_historical_v12_defect_fixture_reproduces_old_v11_global_failure() -> None:
    qualifier = _load_qualifier()
    with pytest.raises(
        qualifier.LocalQualificationError,
        match="local finalizer execution contract drifted",
    ):
        _legacy_v11_global_check(V12_EXECUTION, qualifier)


@pytest.mark.parametrize(
    ("contract", "execution_path"),
    (
        (V11_PROVIDER_CONTRACT, V11_EXECUTION),
        (V12_PROVIDER_CONTRACT, V12_EXECUTION),
        (V13_PROVIDER_CONTRACT, V13_EXECUTION),
    ),
)
def test_historical_package_validation_uses_the_explicit_exact_contract(
    contract: object,
    execution_path: Path,
) -> None:
    qualifier = _load_qualifier()
    execution, command_path, profile = qualifier._validate_selected_package(
        ROOT,
        contract,
        execution_path,
    )
    assert execution["plan_id"] == contract.plan_id
    projection = qualifier._selected_identity_projection(
        contract,
        command_path=command_path,
        provider_profile=profile,
    )
    assert projection["plan_id"] == contract.plan_id
    assert projection["qualification_id"] == contract.local_finalizer_qualification_id
    assert projection["attempt_order"] == list(contract.attempt_order)
    assert projection["evaluator_run_ids"] == list(contract.evaluator_run_ids)


@pytest.mark.parametrize(
    ("contract", "execution_path"),
    (
        (V11_PROVIDER_CONTRACT, V12_EXECUTION),
        (V12_PROVIDER_CONTRACT, V11_EXECUTION),
        (V13_PROVIDER_CONTRACT, V12_EXECUTION),
        (V12_PROVIDER_CONTRACT, V13_EXECUTION),
    ),
)
def test_cross_version_execution_contract_mixtures_fail_closed(
    contract: object,
    execution_path: Path,
) -> None:
    qualifier = _load_qualifier()
    with pytest.raises(
        qualifier.LocalQualificationError,
        match="execution contract path crosses provider versions",
    ):
        qualifier._validate_selected_package(ROOT, contract, execution_path)


def test_local_qualifier_requires_exactly_one_selector() -> None:
    qualifier = _load_qualifier()
    with pytest.raises(
        qualifier.LocalQualificationError,
        match="exactly one provider-contract version or plan identity is required",
    ):
        qualifier._selected_contract(SimpleNamespace(provider_contract=None, plan_id=None))
    with pytest.raises(
        qualifier.LocalQualificationError,
        match="exactly one provider-contract version or plan identity is required",
    ):
        qualifier._selected_contract(
            SimpleNamespace(
                provider_contract="V11",
                plan_id=V11_PROVIDER_CONTRACT.plan_id,
            )
        )
    assert (
        qualifier._selected_contract(SimpleNamespace(provider_contract="V11", plan_id=None))
        is V11_PROVIDER_CONTRACT
    )
    assert (
        qualifier._selected_contract(
            SimpleNamespace(
                provider_contract=None,
                plan_id=V12_PROVIDER_CONTRACT.plan_id,
            )
        )
        is V12_PROVIDER_CONTRACT
    )
    assert (
        qualifier._selected_contract(SimpleNamespace(provider_contract="V13", plan_id=None))
        is V13_PROVIDER_CONTRACT
    )


def test_unsupported_contract_selectors_fail_closed() -> None:
    qualifier = _load_qualifier()
    with pytest.raises(qualifier.LocalQualificationError, match="selector is unsupported"):
        qualifier._selected_contract(SimpleNamespace(provider_contract="latest", plan_id=None))
    with pytest.raises(T09ProviderContractError, match="unsupported"):
        provider_contract("current")
    with pytest.raises(T09ProviderContractError, match="unsupported"):
        provider_contract_for_plan_id("PLAN-EXP0001-PILOT-LATEST")


def test_active_surfaces_have_no_implicit_pilot_contract_globals_or_defaults() -> None:
    forbidden = (
        "ACTIVE_PROVIDER_CONTRACT",
        "PLAN_ID",
        "ATTEMPT_ORDER",
        "RUNTIME_QUALIFICATION_ID",
        "LOCAL_FINALIZER_QUALIFICATION_ID",
        "FROZEN_RUN_MANIFEST_ID",
    )
    for relative in (
        "src/giclab/harness/t09_sira_pilot.py",
        "containers/sira-smoke/pragmatic/t09_local_finalizer_qualification.py",
        "containers/sira-smoke/pragmatic/t09_freeze_commands.py",
        "containers/sira-smoke/pragmatic/t09_remote_runner.py",
    ):
        source = (ROOT / relative).read_text(encoding="utf-8")
        assert all(value not in source for value in forbidden)
    for function in (
        load_aggregate_usage,
        load_aggregate_observed_usage,
        write_aggregate_usage,
    ):
        assert inspect.signature(function).parameters["plan_id"].default is inspect.Parameter.empty


def test_versioned_contract_values_are_immutable_and_isolated() -> None:
    changed_v11 = replace(V11_PROVIDER_CONTRACT, host_run_id="RUN-T09-PILOT-HOST-FIXTURE")
    assert changed_v11.host_run_id != V11_PROVIDER_CONTRACT.host_run_id
    assert provider_contract("V11") is V11_PROVIDER_CONTRACT
    assert provider_contract("V12") is V12_PROVIDER_CONTRACT
    assert provider_contract("V13") is V13_PROVIDER_CONTRACT
    assert V12_PROVIDER_CONTRACT.host_run_id == "RUN-T09-PILOT-HOST-AUTONOMOUS-0005"
    assert V13_PROVIDER_CONTRACT.host_run_id == "RUN-T09-PILOT-HOST-AUTONOMOUS-0006"
