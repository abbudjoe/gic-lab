from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
import threading
from dataclasses import replace
from pathlib import Path
from types import ModuleType

import pytest
from harness_test_support import valid_plan_data

import giclab.harness.adapters.sira as sira_module
from giclab.harness.adapters.sira import (
    SiRAAdapter,
    SiRACommandConfig,
    SiRAMode,
    SiRAPairMismatch,
    SiRATask,
    assert_sira_gate_a_matched_pair,
    sira_config_sha256,
    sira_pair_report_document,
)
from giclab.harness.models import RunPlan, RunProfile, command_document
from giclab.harness.plan import run_plan_from_mapping
from giclab.harness.sira_gate_a import (
    SIRA_API_BASE_URL,
    SIRA_MODEL_REVISION,
    SIRA_SECRET_VARIABLE,
    CanonicalChild,
    GateAContractError,
    ImmutableModelRouting,
    ModelRole,
    ProviderBudgetBoundary,
    ProviderBudgetExceeded,
    ProviderRequest,
    ProviderResponseUsage,
    SiRAAttemptLayout,
    SiRAEnvironmentContract,
    SmokeAuthorizationMaterialization,
    aggregate_caps,
    condition_caps,
    prepare_smoke_preauthorization,
    validate_sira_secret_names,
)
from giclab.harness.sira_gate_a_runtime import (
    _install_locked_llm_factory,
    _write_usage_ledger,
)
from giclab.registry import load_yaml
from giclab.validation import ROOT


def _config(mode: SiRAMode) -> SiRACommandConfig:
    return SiRACommandConfig(
        profile=RunProfile.SMOKE,
        job_name=f"T07-SMOKE-{mode.value.upper()}",
        mode=mode,
        task=SiRATask.open_query("go to google flights"),
    )


def _plan(config: SiRACommandConfig) -> RunPlan:
    data = valid_plan_data(
        max_wall_seconds=120,
        max_cost_usd=2.0,
        max_model_tokens=200_000,
        max_tool_calls=1,
    )
    data["profile"] = "smoke"
    data["run_id"] = f"RUN-T07-SMOKE-{config.mode.value.upper()}"
    data["condition"] = config.mode.condition
    data["seed"] = 42
    data["sources"]["upstream_source_id"] = sira_module.SIRA_SOURCE_ID
    data["sources"]["upstream_commit"] = sira_module.SIRA_UPSTREAM_COMMIT
    data["sources"]["config_sha256"] = sira_config_sha256(config)
    data["sources"]["model_revision"] = SIRA_MODEL_REVISION
    return run_plan_from_mapping(data)


def _boundary(mode: str = "reactive") -> ProviderBudgetBoundary:
    return ProviderBudgetBoundary(
        routing=ImmutableModelRouting.locked(),
        aggregate_caps=aggregate_caps(),
        condition_caps=condition_caps(mode),
    )


def test_every_model_role_is_immutably_routed_without_fallback() -> None:
    routing = ImmutableModelRouting.locked()
    assert set(routing.routes) == set(ModelRole)
    assert set(routing.routes.values()) == {SIRA_MODEL_REVISION}
    assert routing.provider_fallback_enabled is False
    assert routing.api_base_url == SIRA_API_BASE_URL
    assert len(routing.sha256()) == 64


@pytest.mark.parametrize("bad_model", ["gpt-4o", "gpt-4o-latest", "o3"])
def test_model_alias_and_mixed_routing_are_rejected(bad_model: str) -> None:
    routes = dict(ImmutableModelRouting.locked().routes)
    routes[ModelRole.CRITIC] = bad_model
    with pytest.raises(GateAContractError, match="every SiRA model role"):
        ImmutableModelRouting(routes=routes)
    with pytest.raises(GateAContractError, match="provider fallback"):
        ImmutableModelRouting(
            routes=ImmutableModelRouting.locked().routes,
            provider_fallback_enabled=True,
        )


def test_budget_boundary_rejects_worst_case_before_fake_provider_send() -> None:
    boundary = _boundary()
    called = False

    def fake(_: ProviderRequest) -> tuple[str, ProviderResponseUsage]:
        nonlocal called
        called = True
        return "never", ProviderResponseUsage(1, 0, 1)

    request = ProviderRequest(
        role=ModelRole.POLICY,
        model=SIRA_MODEL_REVISION,
        input_tokens=199_999,
        max_output_tokens=2,
    )
    with pytest.raises(ProviderBudgetExceeded, match="condition budget"):
        boundary.invoke(request, fake)
    assert called is False
    assert boundary.condition_usage.model_call_attempts == 0


def test_budget_boundary_reconciles_token_categories_and_cost() -> None:
    boundary = _boundary()
    request = ProviderRequest(
        role=ModelRole.ENCODER,
        model=SIRA_MODEL_REVISION,
        input_tokens=100,
        max_output_tokens=50,
    )
    result = boundary.invoke(
        request,
        lambda _: ("ok", ProviderResponseUsage(100, 40, 25)),
    )
    assert result == "ok"
    usage = boundary.condition_usage
    assert (usage.input_tokens, usage.cached_input_tokens, usage.output_tokens) == (100, 40, 25)
    assert usage.total_tokens == 125
    assert usage.model_call_attempts == 1
    expected = ((60 * 2.5) + (40 * 1.25) + (25 * 10.0)) / 1_000_000
    assert usage.cost_usd == pytest.approx(expected)


def test_usage_over_declared_request_maximum_is_reconciled_before_failure() -> None:
    boundary = _boundary()
    request = ProviderRequest(
        role=ModelRole.ENCODER,
        model=SIRA_MODEL_REVISION,
        input_tokens=10,
        max_output_tokens=10,
    )
    with pytest.raises(ProviderBudgetExceeded, match="after reconciliation"):
        boundary.invoke(
            request,
            lambda _: ("invalid", ProviderResponseUsage(11, 0, 1)),
        )
    assert boundary.condition_usage.input_tokens == 11
    assert boundary.condition_usage.output_tokens == 1
    assert boundary.condition_usage.model_call_attempts == 1


def test_provider_and_parser_retries_share_the_same_attempt_counter() -> None:
    boundary = _boundary()
    request = ProviderRequest(
        role=ModelRole.ACTOR,
        model=SIRA_MODEL_REVISION,
        input_tokens=10,
        max_output_tokens=10,
    )

    def failure(_: ProviderRequest) -> tuple[str, ProviderResponseUsage]:
        raise ConnectionError("synthetic failure")

    with pytest.raises(ConnectionError, match="synthetic"):
        boundary.invoke(request, failure)
    failed_usage = boundary.condition_usage
    assert failed_usage.input_tokens == 10
    assert failed_usage.output_tokens == 10
    assert boundary.unreconciled_provider_attempts == 1
    parser_retry = replace(request, retry_kind="parser")
    boundary.invoke(parser_retry, lambda _: ("ok", ProviderResponseUsage(10, 0, 1)))
    assert boundary.condition_usage.model_call_attempts == 2
    with pytest.raises(GateAContractError, match="implicit provider retries"):
        replace(request, implicit_transport_retries=1)


def test_worst_case_attempt_is_persisted_before_provider_send() -> None:
    states: list[tuple[int, int, int]] = []
    boundary = ProviderBudgetBoundary(
        routing=ImmutableModelRouting.locked(),
        aggregate_caps=aggregate_caps(),
        condition_caps=condition_caps("reactive"),
        persist=lambda usage, unreconciled: states.append(
            (usage.model_call_attempts, usage.output_tokens, unreconciled)
        ),
    )
    request = ProviderRequest(
        role=ModelRole.POLICY,
        model=SIRA_MODEL_REVISION,
        input_tokens=10,
        max_output_tokens=20,
    )

    def fail_after_persistence(_: ProviderRequest) -> tuple[str, ProviderResponseUsage]:
        assert states[-1] == (1, 20, 0)
        raise TimeoutError("synthetic in-flight termination")

    with pytest.raises(TimeoutError, match="in-flight"):
        boundary.invoke(request, fail_after_persistence)
    assert states[-1] == (1, 20, 1)


def test_concurrent_provider_requests_reserve_capacity_before_send() -> None:
    caps = replace(
        condition_caps("reactive"),
        max_input_tokens=10,
        max_output_tokens=10,
        max_total_tokens=10,
    )
    boundary = ProviderBudgetBoundary(
        routing=ImmutableModelRouting.locked(),
        aggregate_caps=replace(
            aggregate_caps(),
            max_input_tokens=10,
            max_output_tokens=10,
            max_total_tokens=10,
        ),
        condition_caps=caps,
    )
    entered = threading.Event()
    release = threading.Event()
    errors: list[BaseException] = []
    request = ProviderRequest(
        role=ModelRole.POLICY,
        model=SIRA_MODEL_REVISION,
        input_tokens=3,
        max_output_tokens=3,
    )

    def slow(_: ProviderRequest) -> tuple[str, ProviderResponseUsage]:
        entered.set()
        release.wait(timeout=2)
        return "ok", ProviderResponseUsage(3, 0, 1)

    def owner() -> None:
        try:
            boundary.invoke(request, slow)
        except BaseException as exc:  # retain thread failure for the owner test
            errors.append(exc)

    thread = threading.Thread(target=owner)
    thread.start()
    assert entered.wait(timeout=2)
    with pytest.raises(ProviderBudgetExceeded, match="budget exceeded"):
        boundary.invoke(
            replace(request, input_tokens=4, max_output_tokens=4),
            lambda _: ("never", ProviderResponseUsage(4, 0, 1)),
        )
    release.set()
    thread.join(timeout=2)
    assert not thread.is_alive()
    assert errors == []


def test_browser_action_and_output_byte_caps_are_hard() -> None:
    boundary = _boundary()
    boundary.record_browser_action()
    with pytest.raises(ProviderBudgetExceeded, match="browser_actions"):
        boundary.record_browser_action()
    boundary.record_output_bytes(condition_caps("reactive").max_output_bytes)
    with pytest.raises(ProviderBudgetExceeded, match="output_bytes"):
        boundary.record_output_bytes(1)


def test_attempt_root_is_fresh_owned_and_collision_safe(tmp_path: Path) -> None:
    root = (tmp_path / "RUN-T07" / "attempt-0001").resolve()
    layout = SiRAAttemptLayout.planned(root)
    layout.allocate()
    assert layout.root.is_dir()
    assert layout.session.is_dir()
    assert layout.source_logs.is_dir()
    with pytest.raises(FileExistsError):
        layout.allocate()
    with pytest.raises(GateAContractError, match="fresh"):
        SiRAAttemptLayout.planned(root)


def test_environment_contract_keeps_installs_outside_clean_source(tmp_path: Path) -> None:
    source = (tmp_path / "source").resolve()
    external = (tmp_path / "runtime/environment").resolve()
    cache = (tmp_path / "runtime/playwright").resolve()
    uv_cache = (tmp_path / "runtime/uv-cache").resolve()
    contract = SiRAEnvironmentContract(source, external, cache, uv_cache)
    assert contract.installation_environment_names() == (
        "PLAYWRIGHT_BROWSERS_PATH",
        "UV_CACHE_DIR",
        "UV_PROJECT_ENVIRONMENT",
    )
    assert "--frozen" in contract.dependency_install_argv(Path("/opt/uv"))
    assert contract.dependency_install_argv(Path("/opt/uv"))[3:5] == ("--extra", "eval")
    assert contract.browser_install_argv()[-2:] == ("install", "chromium")
    with pytest.raises(GateAContractError, match="outside the source"):
        SiRAEnvironmentContract(source, source / ".venv", cache, uv_cache)


def test_secret_contract_validates_names_only_and_rejects_fallback() -> None:
    validate_sira_secret_names(requested=(SIRA_SECRET_VARIABLE,))
    with pytest.raises(GateAContractError, match="exactly SIRA_API_KEY"):
        validate_sira_secret_names(requested=("OPENAI_API_KEY",))
    with pytest.raises(GateAContractError, match="fallback"):
        validate_sira_secret_names(requested=(SIRA_SECRET_VARIABLE,), inherited=("OPENAI_API_KEY",))


def test_source_shaped_llm_factory_routes_every_completion_through_boundary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, object]] = []
    completion_kwargs: list[dict[str, object]] = []

    class FakeUpstreamLLM:
        def __init__(self, **kwargs: object) -> None:
            calls.append(kwargs)
            self.model_name = kwargs["model"]
            self.max_output_tokens = 16_384

        def get_token_count(self, messages: object) -> int:
            assert messages
            return 3

        def _completion(self, *args: object, **kwargs: object) -> dict[str, object]:
            del args
            completion_kwargs.append(kwargs)
            output_tokens = 5_000 if kwargs.get("n") == 20 else 2
            return {
                "usage": {
                    "prompt_tokens": 3,
                    "completion_tokens": output_tokens,
                    "prompt_tokens_details": {"cached_tokens": 1},
                }
            }

        def completion(self, *args: object, **kwargs: object) -> dict[str, object]:
            return self._completion(*args, **kwargs)

    llm_module = ModuleType("sira.web.utils.llm")
    llm_module.LLM = FakeUpstreamLLM  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "sira.web.utils.llm", llm_module)
    runner = ModuleType("source_shaped_runner")
    ledger = tmp_path / "provider-budget.json"
    boundary = ProviderBudgetBoundary(
        routing=ImmutableModelRouting.locked(),
        aggregate_caps=aggregate_caps(),
        condition_caps=condition_caps("reactive"),
        persist=lambda usage, unreconciled: _write_usage_ledger(ledger, usage, unreconciled),
    )
    _write_usage_ledger(ledger, boundary.condition_usage, 0)
    _install_locked_llm_factory(runner, boundary=boundary, ledger_path=ledger)

    role_llms = runner.make_llm(SIRA_MODEL_REVISION, "synthetic-not-a-secret")  # type: ignore[attr-defined]
    assert set(role_llms) == {role.value for role in ModelRole}
    for role in ModelRole:
        role_llms[role.value].completion(messages=[{"role": "user", "content": role.value}])
    role_llms[ModelRole.POLICY.value].completion(
        messages=[{"role": "user", "content": "multi-sample"}], n=20
    )
    assert len(calls) == len(ModelRole)
    assert all(call["model"] == SIRA_MODEL_REVISION for call in calls)
    assert all(call["base_url"] == SIRA_API_BASE_URL for call in calls)
    assert all(call["custom_llm_provider"] == "openai" for call in calls)
    assert all(call["num_retries"] == 0 for call in calls)
    assert completion_kwargs[-1]["max_completion_tokens"] == 4_096
    assert boundary.condition_usage.model_call_attempts == len(ModelRole) + 1
    assert boundary.condition_usage.output_tokens == 5_000 + (2 * len(ModelRole))
    assert ledger.is_file()

    errors: list[BaseException] = []

    def concurrent_completion() -> None:
        try:
            role_llms[ModelRole.CRITIC.value].completion(
                messages=[{"role": "user", "content": "concurrent"}]
            )
        except BaseException as exc:
            errors.append(exc)

    threads = [threading.Thread(target=concurrent_completion) for _ in range(5)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=2)
    assert errors == []
    assert load_yaml(ledger)["model_call_attempts"] == len(ModelRole) + 6
    with pytest.raises(GateAContractError, match="unapproved model alias"):
        runner.make_llm("gpt-4o", "synthetic-not-a-secret")  # type: ignore[attr-defined]


def test_authorization_rejects_unsealed_or_wrong_profile_children() -> None:
    digest = "a" * 64
    children = (
        CanonicalChild("SIRA-REACTIVE", "reactive.yaml", "b" * 64, "c" * 64),
        CanonicalChild("SIRA-SIMULATIVE", "simulative.yaml", "d" * 64, "e" * 64),
    )
    materialization = SmokeAuthorizationMaterialization(
        profile_plan_id="PLAN-EXP0001-SMOKE",
        profile_path="smoke.yaml",
        profile_sha256=digest,
        giclab_commit="f" * 40,
        upstream_commit=sira_module.SIRA_UPSTREAM_COMMIT,
        protocol_sha256=digest,
        config_sha256=digest,
        environment_sha256=digest,
        routing_sha256=digest,
        children=children,
    )
    materialization.assert_child_allowed("SIRA-REACTIVE", "b" * 64, "c" * 64, attempt=1)
    with pytest.raises(GateAContractError, match="outside the sealed"):
        materialization.assert_child_allowed("SIRA-REACTIVE", "b" * 64, "0" * 64, attempt=1)
    with pytest.raises(GateAContractError, match="outside the sealed"):
        materialization.assert_child_allowed("SIRA-REACTIVE", "b" * 64, "c" * 64, attempt=2)
    with pytest.raises(GateAContractError, match="only PLAN-EXP0001-SMOKE"):
        replace(materialization, profile_plan_id="PLAN-EXP0001-PILOT")
    with pytest.raises(GateAContractError, match="cannot materialize live"):
        replace(materialization, execution_authorized=True)


def _clean_contract_repository(tmp_path: Path) -> Path:
    repository = tmp_path / "repository"
    relative_paths = (
        "docs/PROJECT_STATE.yaml",
        "experiments/EXP-0001-sira-simulative-vs-reactive/protocol.yaml",
        "experiments/EXP-0001-sira-simulative-vs-reactive/config.yaml",
        "experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/smoke.yaml",
        "experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/conditions/smoke-reactive.yaml",
        "experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/conditions/smoke-simulative.yaml",
    )
    for relative in relative_paths:
        target = repository / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)
    subprocess.run(("git", "init", "-q", str(repository)), check=True)
    subprocess.run(("git", "-C", str(repository), "add", "."), check=True)
    subprocess.run(
        (
            "git",
            "-C",
            str(repository),
            "-c",
            "user.name=Gate A Test",
            "-c",
            "user.email=gate-a@example.invalid",
            "commit",
            "-qm",
            "fixture",
        ),
        check=True,
    )
    return repository.resolve()


def test_preauthorization_hashes_clean_commit_and_seals_canonical_children(
    tmp_path: Path,
) -> None:
    repository = _clean_contract_repository(tmp_path)
    materialization = prepare_smoke_preauthorization(
        repository,
        environment_sha256="a" * 64,
        routing=ImmutableModelRouting.locked(),
        command_sha256s={
            "SIRA-REACTIVE": "b" * 64,
            "SIRA-SIMULATIVE": "c" * 64,
        },
    )
    assert materialization.profile_plan_id == "PLAN-EXP0001-SMOKE"
    assert (
        materialization.giclab_commit
        == subprocess.run(
            ("git", "-C", str(repository), "rev-parse", "HEAD"),
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    )
    assert materialization.profile_sha256 == (
        "ab276b9e49256d49f143e252eddf6fe5c447d6f9c11300745b450fb7f1d0e425"
    )
    assert {child.condition for child in materialization.children} == {
        "SIRA-REACTIVE",
        "SIRA-SIMULATIVE",
    }
    with pytest.raises(GateAContractError, match="exactly the sealed smoke pair"):
        prepare_smoke_preauthorization(
            repository,
            environment_sha256="a" * 64,
            routing=ImmutableModelRouting.locked(),
            command_sha256s={"SIRA-REACTIVE": "b" * 64},
        )
    (repository / "dirty.txt").write_text("dirty\n", encoding="utf-8")
    with pytest.raises(GateAContractError, match="must be clean"):
        prepare_smoke_preauthorization(
            repository,
            environment_sha256="a" * 64,
            routing=ImmutableModelRouting.locked(),
            command_sha256s={
                "SIRA-REACTIVE": "b" * 64,
                "SIRA-SIMULATIVE": "c" * 64,
            },
        )


def test_gate_a_commands_are_finite_owned_and_machine_diffed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sira_module, "_verify_pinned_git_checkout", lambda *_: None)
    uv = shutil.which("uv")
    if uv is None:
        raise AssertionError("uv is required for command rendering")
    source = (tmp_path / "source").resolve()
    (source / "scripts").mkdir(parents=True)
    (source / "scripts/run_web_agent.py").write_text("# pinned fixture\n", encoding="utf-8")
    environment_root = (tmp_path / "external/environment").resolve()
    cache = (tmp_path / "external/playwright").resolve()
    environment_root.mkdir(parents=True)
    cache.mkdir(parents=True)
    (environment_root / "identity").write_text("locked\n", encoding="utf-8")
    (cache / "identity").write_text("locked\n", encoding="utf-8")
    uv_cache = (tmp_path / "external/uv-cache").resolve()
    uv_cache.mkdir(parents=True)
    (uv_cache / "identity").write_text("locked\n", encoding="utf-8")
    environment = SiRAEnvironmentContract(source, environment_root, cache, uv_cache)
    reactive = SiRAAdapter(_config(SiRAMode.REACTIVE), Path(uv))
    simulative = SiRAAdapter(_config(SiRAMode.SIMULATIVE), Path(uv))
    reactive_plan = _plan(reactive.config)
    simulative_plan = _plan(simulative.config)
    reactive_root = (tmp_path / "artifacts/reactive/attempt-0001").resolve()
    simulative_root = (tmp_path / "artifacts/simulative/attempt-0001").resolve()
    reactive_command = reactive.build_gate_a_command(
        reactive_plan,
        source,
        reactive_root,
        environment=environment,
        giclab_source_root=ROOT / "src",
    )
    simulative_command = simulative.build_gate_a_command(
        simulative_plan,
        source,
        simulative_root,
        environment=environment,
        giclab_source_root=ROOT / "src",
    )
    rendered = command_document(reactive_command)
    assert "--no-sync" in rendered["argv"]
    assert SIRA_MODEL_REVISION in rendered["argv"]
    assert rendered["environment"]["GICLAB_REQUIRE_DESCENDANT_CONTAINMENT"] == "1"
    assert rendered["environment"]["UV_CACHE_DIR"] == str(uv_cache)
    assert rendered["unowned_output_patterns"] == []
    assert rendered["resource_projection"]["unbounded_applicable"] == []
    assert rendered["resource_projection"]["cost_usd"] == 2.0
    assert rendered["resource_projection"]["model_tokens"] == 200_000
    assert rendered["secret_environment"] == [SIRA_SECRET_VARIABLE]
    assert "OPENAI_API_KEY" not in str(rendered)
    adaptation_index = rendered["argv"].index("--gate-adaptation-sha256") + 1
    adaptation = ROOT / "src/giclab/harness/sira_gate_a_runtime.py"
    assert rendered["argv"][adaptation_index] == hashlib.sha256(adaptation.read_bytes()).hexdigest()

    report = assert_sira_gate_a_matched_pair(
        reactive,
        reactive_plan,
        reactive_command,
        simulative,
        simulative_plan,
        simulative_command,
        upstream_root=source,
        reactive_attempt_root=reactive_root,
        simulative_attempt_root=simulative_root,
        environment=environment,
        giclab_source_root=ROOT / "src",
    )
    document = sira_pair_report_document(report)
    assert document["all_other_fields_equal"] is True
    assert {item["field"] for item in document["config_differences"]} == {
        "job_name",
        "mode",
    }
    drifted = replace(
        simulative_command,
        environment={**simulative_command.environment, "UNDECLARED": "drift"},
    )
    with pytest.raises(SiRAPairMismatch, match="canonical rendering"):
        assert_sira_gate_a_matched_pair(
            reactive,
            reactive_plan,
            reactive_command,
            simulative,
            simulative_plan,
            drifted,
            upstream_root=source,
            reactive_attempt_root=reactive_root,
            simulative_attempt_root=simulative_root,
            environment=environment,
            giclab_source_root=ROOT / "src",
        )


def test_committed_gate_a_condition_diff_has_only_declared_argv_changes() -> None:
    document = load_yaml(ROOT / "docs/harness/sira/T07_GATE_A_CONDITION_DIFF.yaml")
    runtime = ROOT / "src/giclab/harness/sira_gate_a_runtime.py"
    assert (
        document["common"]["runtime_adaptation_sha256"]
        == hashlib.sha256(runtime.read_bytes()).hexdigest()
    )
    assert document["common"]["routing_sha256"] == ImmutableModelRouting.locked().sha256()
    reactive = document["resolved_argv"]["reactive"]
    simulative = document["resolved_argv"]["simulative"]
    assert len(reactive) == len(simulative)
    actual = {
        index
        for index, values in enumerate(zip(reactive, simulative, strict=True))
        if values[0] != values[1]
    }
    assert actual == {11, 13, 17, 21, 33}
    assert document["all_other_fields_equal"] is True
    assert document["execution_authorized"] is False
