"""Repository-owned runtime adaptation for the pinned SiRA smoke.

The adapter is executed by the already-installed, external SiRA environment.  It
does not modify the upstream checkout.  It replaces only the provider construction,
log destinations, and environment cleanup surfaces before calling the pinned runner.
"""

from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import os
import platform
import resource
import sys
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from types import ModuleType
from typing import Any

from giclab.harness import t09_sira_pilot as t09_pilot
from giclab.harness.safety import CredentialExposureError, ExactCredentialScrubber
from giclab.harness.sira_gate_a import (
    SIRA_API_BASE_URL,
    SIRA_MODEL_REVISION,
    SIRA_SECRET_VARIABLE,
    SIRA_SERVICE_TIER,
    GateAContractError,
    ImmutableModelRouting,
    ModelRole,
    ProviderBudgetBoundary,
    ProviderBudgetUsage,
    ProviderRequest,
    ProviderResponseUsage,
    aggregate_caps,
    condition_caps,
    file_sha256,
    validate_sira_secret_names,
)
from giclab.harness.t09_sira_pilot import (
    EventWriter,
    PilotExecutionContract,
    ResourceGuard,
    T09PilotError,
    load_aggregate_usage,
    load_execution_contract,
    mark_empirical_entry,
    pilot_state_time_origins,
    write_aggregate_usage,
)

SIRA_MAX_OUTPUT_TOKENS_PER_CHOICE = 4_096


def _attempt_root_matches_raw_binding(attempt_root: Path, raw_output_root: str) -> bool:
    """Match the runtime-owned raw root, not its parent logical attempt root."""

    expected_suffix = Path(raw_output_root).parts
    return (
        bool(expected_suffix)
        and len(attempt_root.parts) >= len(expected_suffix)
        and attempt_root.parts[-len(expected_suffix) :] == expected_suffix
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--gate-upstream-runner", type=Path, required=True)
    parser.add_argument("--gate-attempt-root", type=Path, required=True)
    parser.add_argument("--gate-mode", choices=("reactive", "simulative"), required=True)
    parser.add_argument("--gate-adaptation-sha256", required=True)
    parser.add_argument("--gate-pilot-contract", type=Path)
    parser.add_argument("--gate-pilot-contract-sha256")
    parser.add_argument("--gate-pilot-library-sha256")
    parser.add_argument("--gate-pilot-attempt-id")
    parser.add_argument("--gate-condition-plan", type=Path)
    parser.add_argument("--gate-aggregate-ledger", type=Path)
    parser.add_argument("--gate-pilot-state", type=Path)
    parser.add_argument("upstream_argv", nargs=argparse.REMAINDER)
    return parser


def _usage(response: Any) -> ProviderResponseUsage:
    service_tier = (
        response.get("service_tier")
        if isinstance(response, Mapping)
        else getattr(response, "service_tier", None)
    )
    if service_tier != SIRA_SERVICE_TIER:
        raise GateAContractError("provider response service_tier must be exactly default")
    raw = (
        response.get("usage") if isinstance(response, Mapping) else getattr(response, "usage", None)
    )
    if raw is None:
        raise GateAContractError("provider response omitted required usage accounting")

    def value(*names: str) -> int:
        for name in names:
            candidate = raw.get(name) if isinstance(raw, Mapping) else getattr(raw, name, None)
            if candidate is not None:
                if type(candidate) is not int or candidate < 0:
                    raise GateAContractError(f"provider usage {name} is invalid")
                return candidate
        raise GateAContractError(f"provider response omitted usage field {names[0]}")

    input_tokens = value("prompt_tokens", "input_tokens")
    output_tokens = value("completion_tokens", "output_tokens")
    details = (
        raw.get("prompt_tokens_details")
        if isinstance(raw, Mapping)
        else getattr(raw, "prompt_tokens_details", None)
    )
    cached_tokens = 0
    if details is not None:
        cached = (
            details.get("cached_tokens")
            if isinstance(details, Mapping)
            else getattr(details, "cached_tokens", 0)
        )
        if cached is not None:
            if type(cached) is not int or cached < 0:
                raise GateAContractError("provider cached-token usage is invalid")
            cached_tokens = cached
    return ProviderResponseUsage(
        input_tokens=input_tokens,
        cached_input_tokens=cached_tokens,
        output_tokens=output_tokens,
        service_tier=service_tier,
    )


_LEDGER_WRITE_LOCK = threading.Lock()


class _PilotLineage(threading.local):
    parent_event_id: str | None = None
    action_event_id: str | None = None


def _json_safe(value: object) -> object:
    """Convert post-action provider objects to retained JSON without value inference."""

    def fallback(item: object) -> object:
        scalar = getattr(item, "item", None)
        if callable(scalar):
            try:
                return scalar()
            except (TypeError, ValueError):
                pass
        return {"unavailable_type": type(item).__name__}

    return json.loads(json.dumps(value, default=fallback))


def _ledger_document(
    usage: ProviderBudgetUsage,
    unreconciled_provider_attempts: int,
) -> dict[str, object]:
    return {
        "schema_version": "0.1.0",
        "model_revision": SIRA_MODEL_REVISION,
        "request_service_tier": SIRA_SERVICE_TIER,
        "observed_response_service_tiers": (
            [SIRA_SERVICE_TIER] if usage.default_service_tier_responses > 0 else []
        ),
        "default_service_tier_response_count": usage.default_service_tier_responses,
        "cost_usd": usage.cost_usd,
        "input_tokens": usage.input_tokens,
        "cached_input_tokens": usage.cached_input_tokens,
        "output_tokens": usage.output_tokens,
        "total_tokens": usage.total_tokens,
        "model_call_attempts": usage.model_call_attempts,
        "unreconciled_provider_attempts": unreconciled_provider_attempts,
        "browser_actions": usage.browser_actions,
        "output_bytes": usage.output_bytes,
    }


def _write_ledger(path: Path, boundary: ProviderBudgetBoundary) -> None:
    _write_usage_ledger(
        path,
        boundary.condition_usage,
        boundary.unreconciled_provider_attempts,
    )


def _write_usage_ledger(
    path: Path,
    usage: ProviderBudgetUsage,
    unreconciled_provider_attempts: int,
) -> None:
    with _LEDGER_WRITE_LOCK:
        temporary = path.with_suffix(f".{threading.get_ident()}.tmp")
        with temporary.open("w", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    _ledger_document(usage, unreconciled_provider_attempts),
                    indent=2,
                    sort_keys=True,
                )
                + "\n"
            )
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)


def _session_path(upstream_argv: Sequence[str]) -> Path:
    indexes = [index for index, value in enumerate(upstream_argv) if value == "--output_dir"]
    if len(indexes) != 1 or indexes[0] + 1 >= len(upstream_argv):
        raise GateAContractError("upstream output directory is unavailable for reconciliation")
    output_directory = Path(upstream_argv[indexes[0] + 1]).resolve(strict=True)
    sessions = sorted(
        path
        for path in output_directory.glob("*.json")
        if path.name != "output.jsonl" and path.is_file() and not path.is_symlink()
    )
    if len(sessions) != 1:
        raise GateAContractError("browser-action reconciliation requires one session JSON")
    return sessions[0]


def _session_history(upstream_argv: Sequence[str]) -> list[object]:
    session = json.loads(_session_path(upstream_argv).read_text(encoding="utf-8"))
    history = session.get("history") if isinstance(session, Mapping) else None
    if not isinstance(history, list):
        raise GateAContractError("session history is unavailable for browser-action accounting")
    return history


def _write_json_evidence(path: Path, value: object) -> None:
    """Atomically fsync one value-only evidence record."""

    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_suffix(f".{os.getpid()}.tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        handle.write(json.dumps(value, indent=2, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)
    directory = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def _remove_secret_bearing_artifacts(
    root: Path,
    scrubber: ExactCredentialScrubber,
) -> list[str]:
    """Remove any retained file containing the exact injected credential."""

    removed: list[str] = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink() or not path.is_file():
            continue
        try:
            scrubber.assert_file(path, label="retained pilot artifact")
        except CredentialExposureError:
            removed.append(path.relative_to(root).as_posix())
            path.unlink()
    return removed


def _reconcile_browser_actions(
    upstream_argv: Sequence[str],
    boundary: ProviderBudgetBoundary,
) -> None:
    for _ in _session_history(upstream_argv):
        boundary.record_browser_action()


def _load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise GateAContractError(f"cannot load pinned runtime module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _install_locked_llm_factory(
    runner: ModuleType,
    *,
    boundary: ProviderBudgetBoundary,
    ledger_path: Path,
    pilot_events: EventWriter | None = None,
    pilot_lineage: _PilotLineage | None = None,
    before_empirical_operation: Callable[[], None] | None = None,
    resource_guard: ResourceGuard | None = None,
    observe_credential: Callable[[str], None] | None = None,
) -> None:
    upstream_llm_module = importlib.import_module("sira.web.utils.llm")
    upstream_llm = upstream_llm_module.LLM

    class BudgetedLLM(upstream_llm):  # type: ignore[misc, valid-type]
        def __init__(self, *, role: ModelRole, credential: str) -> None:
            self._gate_role = role
            credential_option = {"api_key": credential}
            super().__init__(
                model=SIRA_MODEL_REVISION,
                base_url=SIRA_API_BASE_URL,
                custom_llm_provider="openai",
                num_retries=0,
                llm_timeout=boundary.condition_caps.max_wall_seconds,
                **credential_option,
            )
            self_any: Any = self
            unbudgeted_completion: Any = self_any._completion

            def completion_once(*args: Any, **kwargs: Any) -> Any:
                if resource_guard is not None:
                    resource_guard.check()
                messages = kwargs.get("messages")
                if messages is None and len(args) > 1:
                    messages = args[1]
                if messages is None:
                    raise GateAContractError("provider request omitted messages")
                input_tokens = self.get_token_count(messages)
                declared_per_choice = kwargs.get("max_completion_tokens", self.max_output_tokens)
                if type(declared_per_choice) is not int or declared_per_choice < 0:
                    raise GateAContractError("provider output maximum is unavailable")
                per_choice = min(declared_per_choice, SIRA_MAX_OUTPUT_TOKENS_PER_CHOICE)
                sample_count = kwargs.get("n", 1)
                if type(sample_count) is not int or sample_count < 1:
                    raise GateAContractError("provider sample count must be a positive integer")
                kwargs["max_completion_tokens"] = per_choice
                requested_tier = kwargs.get("service_tier", SIRA_SERVICE_TIER)
                if requested_tier != SIRA_SERVICE_TIER:
                    raise GateAContractError(
                        "provider request service_tier must be exactly default"
                    )
                kwargs["service_tier"] = SIRA_SERVICE_TIER
                request = ProviderRequest(
                    role=self._gate_role,
                    model=self.model_name,
                    input_tokens=input_tokens,
                    max_output_tokens=per_choice * sample_count,
                    service_tier=SIRA_SERVICE_TIER,
                    implicit_transport_retries=0,
                )

                def send(_: ProviderRequest) -> tuple[Any, ProviderResponseUsage]:
                    parent = pilot_lineage.parent_event_id if pilot_lineage is not None else None
                    try:
                        response = unbudgeted_completion(*args, **kwargs)
                        observed_usage = _usage(response)
                    except Exception as exc:
                        if pilot_events is not None:
                            pilot_events.append(
                                "provider-call-failed",
                                {
                                    "role": self._gate_role.value,
                                    "model": self.model_name,
                                    "requested_service_tier": SIRA_SERVICE_TIER,
                                    "exception_type": type(exc).__name__,
                                    "retry": "forbidden",
                                },
                                parent_event_id=parent,
                            )
                        raise
                    if pilot_events is not None:
                        response_id = (
                            response.get("id")
                            if isinstance(response, Mapping)
                            else getattr(response, "id", None)
                        )
                        system_fingerprint = (
                            response.get("system_fingerprint")
                            if isinstance(response, Mapping)
                            else getattr(response, "system_fingerprint", None)
                        )
                        pilot_events.append(
                            "provider-call-receipt",
                            {
                                "role": self._gate_role.value,
                                "model": self.model_name,
                                "requested_service_tier": SIRA_SERVICE_TIER,
                                "returned_service_tier": observed_usage.service_tier,
                                "provider_response_id": response_id,
                                "system_fingerprint": system_fingerprint,
                                "usage": {
                                    "input_tokens": observed_usage.input_tokens,
                                    "cached_input_tokens": observed_usage.cached_input_tokens,
                                    "output_tokens": observed_usage.output_tokens,
                                    "total_tokens": (
                                        observed_usage.input_tokens + observed_usage.output_tokens
                                    ),
                                },
                                "retry": "none",
                            },
                            parent_event_id=parent,
                        )
                    return response, observed_usage

                result = boundary.invoke(
                    request,
                    send,
                    before_send=before_empirical_operation,
                )
                if resource_guard is not None:
                    resource_guard.check()
                return result

            self._completion = completion_once

    def make_llm(model: str, credential: str) -> dict[str, Any]:
        if model != SIRA_MODEL_REVISION:
            raise GateAContractError("upstream command requested an unapproved model alias")
        if observe_credential is not None:
            observe_credential(credential)
        return {role.value: BudgetedLLM(role=role, credential=credential) for role in ModelRole}

    runner_any: Any = runner
    runner_any.make_llm = make_llm


def run(argv: Sequence[str] | None = None) -> int:
    core_limits = resource.getrlimit(resource.RLIMIT_CORE)
    if core_limits != (0, 0):
        raise GateAContractError("condition process-tree core limit is not exactly zero")
    args = _parser().parse_args(argv)
    if not args.upstream_argv or args.upstream_argv[0] != "--":
        raise GateAContractError("upstream argv must follow a -- boundary")
    pilot_values = (
        args.gate_pilot_contract,
        args.gate_pilot_contract_sha256,
        args.gate_pilot_library_sha256,
        args.gate_pilot_attempt_id,
        args.gate_condition_plan,
        args.gate_aggregate_ledger,
        args.gate_pilot_state,
    )
    if any(value is not None for value in pilot_values) and not all(
        value is not None for value in pilot_values
    ):
        raise GateAContractError("T09 pilot runtime arguments must be supplied together")
    pilot_enabled = all(value is not None for value in pilot_values)
    runner_path = args.gate_upstream_runner.resolve(strict=True)
    attempt_root = args.gate_attempt_root.resolve(strict=True)
    pilot_contract: PilotExecutionContract | None = None
    condition_plan_path: Path | None = None
    pilot_state_path: Path | None = None
    aggregate_ledger_path: Path | None = None
    resource_guard: ResourceGuard | None = None
    pilot_events: EventWriter | None = None
    pilot_lineage: _PilotLineage | None = None
    empirical_entered = False
    if pilot_enabled:
        assert isinstance(args.gate_pilot_contract, Path)
        assert isinstance(args.gate_pilot_contract_sha256, str)
        assert isinstance(args.gate_pilot_library_sha256, str)
        assert isinstance(args.gate_pilot_attempt_id, str)
        assert isinstance(args.gate_condition_plan, Path)
        assert isinstance(args.gate_aggregate_ledger, Path)
        assert isinstance(args.gate_pilot_state, Path)
        pilot_contract = load_execution_contract(
            args.gate_pilot_contract.resolve(strict=True),
            expected_sha256=args.gate_pilot_contract_sha256,
        )
        pilot_library_path = Path(t09_pilot.__file__).resolve(strict=True)
        if file_sha256(pilot_library_path) != args.gate_pilot_library_sha256:
            raise GateAContractError("repository-owned T09 pilot library hash changed")
        attempt = pilot_contract.attempt(args.gate_pilot_attempt_id)
        condition_plan_path = args.gate_condition_plan.resolve(strict=True)
        if (
            condition_plan_path.name != Path(attempt.condition_plan_path).name
            or file_sha256(condition_plan_path) != attempt.condition_plan_sha256
        ):
            raise GateAContractError("pilot condition plan changed from its frozen binding")
        if attempt.condition != args.gate_mode:
            raise GateAContractError("pilot attempt mode does not match its frozen condition")
        if attempt.upstream_argv != tuple(args.upstream_argv[1:]):
            raise GateAContractError("pilot upstream argv drifted from the execution contract")
        if not _attempt_root_matches_raw_binding(attempt_root, attempt.raw_output_root):
            raise GateAContractError("pilot attempt root drifted from the execution contract")
        pilot_state_path = args.gate_pilot_state.resolve(strict=True)
        aggregate_ledger_path = args.gate_aggregate_ledger.resolve(strict=False)
    if attempt_root in runner_path.parents:
        raise GateAContractError("upstream runner must remain outside the attempt root")
    if file_sha256(Path(__file__).resolve(strict=True)) != args.gate_adaptation_sha256:
        raise GateAContractError("repository-owned runtime adaptation hash changed")
    validate_sira_secret_names(
        requested=(SIRA_SECRET_VARIABLE,),
        inherited=tuple(name for name in os.environ if name == "OPENAI_API_KEY"),
    )
    os.environ.pop("OPENAI_API_KEY", None)
    os.environ["DEBUG_LOG_FOLDER"] = str(attempt_root / "source-logs" / "debug")
    runtime_cwd = attempt_root / "source-runtime"
    runtime_cwd.mkdir(mode=0o700, exist_ok=False)
    (attempt_root / "source-logs" / "debug").mkdir(parents=True, mode=0o700)
    (attempt_root / "source-logs" / "agent").mkdir(mode=0o700)
    os.chdir(runtime_cwd)

    routing = ImmutableModelRouting.locked()
    ledger_path = attempt_root / "provider-budget.json"
    initial_aggregate_usage = ProviderBudgetUsage()
    aggregate_persist: Callable[[ProviderBudgetUsage, int], None] | None = None
    condition_budget_caps = condition_caps(args.gate_mode)
    aggregate_budget_caps = aggregate_caps()
    if pilot_contract is not None:
        assert aggregate_ledger_path is not None
        assert pilot_state_path is not None
        initial_aggregate_usage = load_aggregate_usage(
            aggregate_ledger_path,
            contract_sha256=pilot_contract.sha256,
        )
        condition_budget_caps = pilot_contract.limits.condition_provider_caps()
        aggregate_budget_caps = pilot_contract.limits.aggregate_provider_caps()

        def persist_pilot_aggregate(
            usage: ProviderBudgetUsage,
            unreconciled: int,
        ) -> None:
            write_aggregate_usage(
                aggregate_ledger_path,
                contract_sha256=pilot_contract.sha256,
                usage=usage,
                unreconciled_provider_attempts=unreconciled,
            )

        aggregate_persist = persist_pilot_aggregate
        condition_started = time.monotonic()
        time_origins = pilot_state_time_origins(
            pilot_state_path,
            execution_contract_sha256=pilot_contract.sha256,
            run_id=args.gate_pilot_attempt_id,
        )
        pilot_control_root = pilot_state_path.parent
        pilot_root = pilot_control_root.parent
        if (
            pilot_control_root.name != "pilot-v7"
            or aggregate_ledger_path.parent != pilot_control_root
            or pilot_root not in attempt_root.parents
        ):
            raise GateAContractError("pilot state, aggregate ledger, and attempt roots disagree")
        resource_guard = ResourceGuard(
            pilot_contract.limits,
            attempt_root=attempt_root,
            pilot_root=pilot_root,
            condition_started=condition_started,
            pair_started=time_origins.pair_started,
            campaign_started=time_origins.campaign_started,
            owned_lambda_started=time_origins.owned_lambda_started,
            prior_lambda_duration_seconds=time_origins.prior_lambda_duration_seconds,
            prior_lambda_cost_usd=time_origins.prior_lambda_cost_usd,
        )
        resource_guard.check()
        pilot_events = EventWriter(attempt_root / "normalized-events.jsonl")
        pilot_lineage = _PilotLineage()
        pilot_events.append(
            "regulation-decision-assignment",
            {
                "source_kind": "experiment_assignment",
                "condition": attempt.condition,
                "scientific_effect_on_h2k": "none",
            },
        )

    def before_empirical_operation() -> None:
        nonlocal empirical_entered
        if pilot_contract is None:
            return
        assert pilot_state_path is not None
        assert resource_guard is not None
        resource_guard.check()
        if not empirical_entered:
            mark_empirical_entry(
                pilot_state_path,
                execution_contract_sha256=pilot_contract.sha256,
                run_id=args.gate_pilot_attempt_id,
            )
            empirical_entered = True

    boundary = ProviderBudgetBoundary(
        routing=routing,
        aggregate_caps=aggregate_budget_caps,
        condition_caps=condition_budget_caps,
        persist=lambda usage, unreconciled: _write_usage_ledger(ledger_path, usage, unreconciled),
        initial_aggregate_usage=initial_aggregate_usage,
        persist_aggregate=aggregate_persist,
    )
    _write_ledger(ledger_path, boundary)
    (attempt_root / "runtime-environment.json").write_text(
        json.dumps(
            {
                "schema_version": "0.1.0",
                "python_executable": sys.executable,
                "python_version": platform.python_version(),
                "os": platform.system(),
                "architecture": platform.machine(),
                "upstream_runner": str(runner_path),
                "runtime_adaptation_sha256": args.gate_adaptation_sha256,
                "routing_sha256": routing.sha256(),
                "pilot_execution_contract_sha256": (
                    pilot_contract.sha256 if pilot_contract is not None else None
                ),
                "pilot_attempt_id": args.gate_pilot_attempt_id,
                "core_soft_limit": core_limits[0],
                "core_hard_limit": core_limits[1],
                "gpu_accounting": {
                    "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES"),
                    "gpu_use_claimed": False,
                    "visibility_interpretation": "visible-or-disabled-but-unused",
                    "scientific_variable": False,
                },
                "environment_variable_names": sorted(
                    {
                        "DEBUG_LOG_FOLDER",
                        "PLAYWRIGHT_BROWSERS_PATH",
                        "PYTHONDONTWRITEBYTECODE",
                        "PYTHONPATH",
                        SIRA_SECRET_VARIABLE,
                        "UV_CACHE_DIR",
                        "UV_PROJECT_ENVIRONMENT",
                    }
                ),
                "secret_variable_names": [SIRA_SECRET_VARIABLE],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    runner = _load_module(runner_path, "giclab_t07_pinned_sira_runner")
    observed_credentials: list[str] = []

    def observe_credential(value: str) -> None:
        if observed_credentials and observed_credentials[0] != value:
            raise GateAContractError("more than one provider credential reached the runtime")
        if not observed_credentials:
            observed_credentials.append(value)

    _install_locked_llm_factory(
        runner,
        boundary=boundary,
        ledger_path=ledger_path,
        pilot_events=pilot_events,
        pilot_lineage=pilot_lineage,
        before_empirical_operation=before_empirical_operation if pilot_contract else None,
        resource_guard=resource_guard,
        observe_credential=observe_credential if pilot_contract else None,
    )
    if pilot_events is not None and pilot_lineage is not None:
        original_make_agent = runner.make_agent

        def instrumented_make_agent(*agent_args: Any, **agent_kwargs: Any) -> Any:
            agent = original_make_agent(*agent_args, **agent_kwargs)
            original_step = agent.step

            def instrumented_agent_step(raw_observation: Any) -> Any:
                step_event_id = pilot_events.append(
                    "agent-step-started",
                    {"observation_available": raw_observation is not None},
                )
                pilot_lineage.parent_event_id = step_event_id
                try:
                    action, thoughts = original_step(raw_observation)
                finally:
                    pilot_lineage.parent_event_id = None
                action_event_id = pilot_events.append(
                    "requested-browser-action",
                    {"requested_action": action, "agent_step_info": _json_safe(thoughts)},
                    parent_event_id=step_event_id,
                )
                pilot_lineage.action_event_id = action_event_id
                return action, thoughts

            agent.step = instrumented_agent_step
            return agent

        runner_any_for_agent: Any = runner
        runner_any_for_agent.make_agent = instrumented_make_agent
    logger_module = importlib.import_module("sira.web.utils.logger")
    original_agent_logger = logger_module.get_agent_logger

    def owned_agent_logger(log_file: str = "default_log.log", log_dir: str | None = None) -> Any:
        del log_dir
        return original_agent_logger(
            log_file=log_file,
            log_dir=str(attempt_root / "source-logs" / "agent"),
        )

    runner_any: Any = runner
    logger_any: Any = logger_module
    runner_any.get_agent_logger = owned_agent_logger
    logger_any.get_agent_logger = owned_agent_logger

    opened_environments: list[Any] = []
    original_gym_make = runner.gym.make

    def tracked_gym_make(*make_args: Any, **make_kwargs: Any) -> Any:
        created = original_gym_make(*make_args, **make_kwargs)
        current = created
        seen: set[int] = set()
        while hasattr(current, "env") and id(current) not in seen:
            seen.add(id(current))
            current = current.env
        opened_environments.append(current)
        if pilot_events is not None and pilot_lineage is not None:
            original_environment_step = current.step

            def instrumented_environment_step(action: str) -> Any:
                if resource_guard is not None:
                    resource_guard.check()
                boundary.record_browser_action(before_action=before_empirical_operation)
                action_event_id = pilot_lineage.action_event_id
                if action_event_id is None:
                    action_event_id = pilot_events.append(
                        "requested-browser-action",
                        {"requested_action": action, "agent_step_info": None},
                    )
                try:
                    result = original_environment_step(action)
                except Exception as exc:
                    pilot_events.append(
                        "post-action-result",
                        {
                            "requested_action": action,
                            "result_available": False,
                            "exception_type": type(exc).__name__,
                        },
                        parent_event_id=action_event_id,
                    )
                    pilot_lineage.action_event_id = None
                    raise
                if not isinstance(result, tuple) or len(result) != 5:
                    raise GateAContractError("browser step returned an unexpected result shape")
                observation, reward, terminated, truncated, info = result
                serializable_observation = runner.get_serializable_obs(
                    current,
                    copy.deepcopy(observation),
                )
                pilot_events.append(
                    "post-action-result",
                    {
                        "requested_action": action,
                        "result_available": True,
                        "observation": _json_safe(serializable_observation),
                        "reward": _json_safe(reward),
                        "terminated": _json_safe(terminated),
                        "truncated": _json_safe(truncated),
                        "info": _json_safe(info),
                    },
                    parent_event_id=action_event_id,
                )
                pilot_lineage.action_event_id = None
                if resource_guard is not None:
                    resource_guard.check()
                return result

            current.step = instrumented_environment_step
        return created

    runner.gym.make = tracked_gym_make
    sys.argv = [str(runner_path), *args.upstream_argv[1:]]
    cleanup_path = attempt_root / "runtime-cleanup.json"
    close_errors: list[str] = []
    secret_cleanup = {
        "credential_observed": False,
        "credential_removed_from_environment": False,
        "secret_bearing_artifacts_removed": [],
        "remaining_exact_credential_matches": None,
    }
    runner_succeeded = False
    try:
        runner.main()
        runner_succeeded = True
    finally:
        for environment in opened_environments:
            try:
                environment.close()
            except Exception as exc:  # cleanup evidence must survive a source close failure
                close_errors.append(type(exc).__name__)
        if pilot_contract is not None:
            if len(observed_credentials) != 1:
                close_errors.append("CredentialObservationIncomplete")
            else:
                secret_cleanup["credential_observed"] = True
                scrubber = ExactCredentialScrubber(observed_credentials)
                os.environ.pop(SIRA_SECRET_VARIABLE, None)
                secret_cleanup["credential_removed_from_environment"] = True
                removed = _remove_secret_bearing_artifacts(attempt_root, scrubber)
                secret_cleanup["secret_bearing_artifacts_removed"] = removed
                remaining_matches = 0
                for retained_path in sorted(attempt_root.rglob("*")):
                    if retained_path.is_symlink() or not retained_path.is_file():
                        continue
                    try:
                        scrubber.assert_file(retained_path, label="retained pilot artifact")
                    except CredentialExposureError:
                        remaining_matches += 1
                secret_cleanup["remaining_exact_credential_matches"] = remaining_matches
                if remaining_matches:
                    close_errors.append("CredentialExposureError")
        _write_json_evidence(
            cleanup_path,
            {
                "schema_version": "0.1.0",
                "tracked_browser_environments": len(opened_environments),
                "close_error_types": close_errors,
                "all_environment_closes_succeeded": not close_errors,
                "pilot_attempt_id": args.gate_pilot_attempt_id,
                "empirical_entry_crossed": empirical_entered,
                "secret_cleanup": secret_cleanup,
            },
        )
        try:
            if runner_succeeded:
                if pilot_contract is None:
                    _reconcile_browser_actions(args.upstream_argv[1:], boundary)
                else:
                    if not empirical_entered:
                        raise T09PilotError(
                            "a successful pilot condition had no empirical operation"
                        )
                    if close_errors:
                        raise T09PilotError("pilot browser cleanup did not complete")
                    history = _session_history(args.upstream_argv[1:])
                    if len(history) != boundary.condition_usage.browser_actions:
                        raise T09PilotError(
                            "pre-action browser counter and retained session history disagree"
                        )
                    assert resource_guard is not None
                    snapshot = resource_guard.check()
                    boundary.record_output_bytes(snapshot.attempt_output_bytes)
                    if pilot_events is not None:
                        pilot_events.append(
                            "cleanup-receipt",
                            {
                                "tracked_browser_environments": len(opened_environments),
                                "all_environment_closes_succeeded": not close_errors,
                                "attempt_output_bytes": snapshot.attempt_output_bytes,
                                "pilot_disk_bytes": snapshot.pilot_disk_bytes,
                                "gpu_use_claimed": False,
                            },
                        )
        finally:
            _write_ledger(ledger_path, boundary)
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
