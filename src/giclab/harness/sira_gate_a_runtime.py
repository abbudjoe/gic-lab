"""Repository-owned runtime adaptation for the pinned SiRA smoke.

The adapter is executed by the already-installed, external SiRA environment.  It
does not modify the upstream checkout.  It replaces only the provider construction,
log destinations, and environment cleanup surfaces before calling the pinned runner.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import platform
import sys
import threading
from collections.abc import Mapping, Sequence
from pathlib import Path
from types import ModuleType
from typing import Any

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

SIRA_MAX_OUTPUT_TOKENS_PER_CHOICE = 4_096


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--gate-upstream-runner", type=Path, required=True)
    parser.add_argument("--gate-attempt-root", type=Path, required=True)
    parser.add_argument("--gate-mode", choices=("reactive", "simulative"), required=True)
    parser.add_argument("--gate-adaptation-sha256", required=True)
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


def _reconcile_browser_actions(
    upstream_argv: Sequence[str],
    boundary: ProviderBudgetBoundary,
) -> None:
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
    session = json.loads(sessions[0].read_text(encoding="utf-8"))
    history = session.get("history") if isinstance(session, Mapping) else None
    if not isinstance(history, list):
        raise GateAContractError("session history is unavailable for browser-action accounting")
    for _ in history:
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
                    response = unbudgeted_completion(*args, **kwargs)
                    return response, _usage(response)

                return boundary.invoke(request, send)

            self._completion = completion_once

    def make_llm(model: str, credential: str) -> dict[str, Any]:
        if model != SIRA_MODEL_REVISION:
            raise GateAContractError("upstream command requested an unapproved model alias")
        return {role.value: BudgetedLLM(role=role, credential=credential) for role in ModelRole}

    runner_any: Any = runner
    runner_any.make_llm = make_llm


def run(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if not args.upstream_argv or args.upstream_argv[0] != "--":
        raise GateAContractError("upstream argv must follow a -- boundary")
    runner_path = args.gate_upstream_runner.resolve(strict=True)
    attempt_root = args.gate_attempt_root.resolve(strict=True)
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
    boundary = ProviderBudgetBoundary(
        routing=routing,
        aggregate_caps=aggregate_caps(),
        condition_caps=condition_caps(args.gate_mode),
        persist=lambda usage, unreconciled: _write_usage_ledger(ledger_path, usage, unreconciled),
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
    _install_locked_llm_factory(runner, boundary=boundary, ledger_path=ledger_path)
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
        return created

    runner.gym.make = tracked_gym_make
    sys.argv = [str(runner_path), *args.upstream_argv[1:]]
    cleanup_path = attempt_root / "runtime-cleanup.json"
    close_errors: list[str] = []
    try:
        runner.main()
    finally:
        for environment in opened_environments:
            try:
                environment.close()
            except Exception as exc:  # cleanup evidence must survive a source close failure
                close_errors.append(type(exc).__name__)
        cleanup_path.write_text(
            json.dumps(
                {
                    "schema_version": "0.1.0",
                    "tracked_browser_environments": len(opened_environments),
                    "close_error_types": close_errors,
                    "all_environment_closes_succeeded": not close_errors,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        try:
            if sys.exc_info()[0] is None:
                _reconcile_browser_actions(args.upstream_argv[1:], boundary)
        finally:
            _write_ledger(ledger_path, boundary)
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
