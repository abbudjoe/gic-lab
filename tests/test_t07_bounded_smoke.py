from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from giclab.harness import t07_bounded_smoke as bounded
from giclab.validation import ROOT, validate_instance


def _artifacts() -> list[dict[str, object]]:
    records = []
    for relative in sorted(bounded.REQUIRED_IMPLEMENTATION_ARTIFACTS):
        path = ROOT / relative
        records.append(
            {
                "path": relative,
                "bytes": path.stat().st_size,
                "sha256": bounded.sha256_file(path),
            }
        )
    return records


def valid_plan() -> dict[str, object]:
    conditions = []
    for index, condition in enumerate(bounded.CONDITION_ORDER, start=1):
        create = bounded.container_create_argv(condition)
        inner = bounded.condition_inner_argv(condition)
        conditions.append(
            {
                "condition": condition,
                "run_id": bounded.RUN_IDS[condition],
                "attempt": 1,
                "order_index": index,
                "mode": bounded.MODE_VALUES[condition],
                "container_create_argv_template": list(create),
                "container_create_template_sha256": bounded.template_sha256(create),
                "inner_argv_template": list(inner),
                "inner_argv_template_sha256": bounded.template_sha256(inner),
                "model_call_attempts": bounded.MODEL_CALL_CAPS[condition],
                "model_tokens": 200_000,
                "api_cost_usd": 2.0,
                "wall_seconds": 120,
                "browser_actions": 1,
                "output_bytes": 104_857_600,
            }
        )
    browser = bounded.browser_preflight_create_argv()
    model = bounded.model_preflight_create_argv()
    return {
        "$schema": "../../../schemas/t07-bounded-smoke-plan.schema.json",
        "identity": {
            "schema_version": bounded.SCHEMA_VERSION,
            "plan_id": bounded.PLAN_ID,
            "host_run_id": bounded.HOST_RUN_ID,
            "authorization_reference": bounded.AUTHORIZATION_PLACEHOLDER,
            "state": bounded.TERMINAL_STATE,
            "authorized": False,
            "branch": bounded.BRANCH,
            "fork_commit": bounded.FORK_COMMIT,
            "parent_branch": bounded.PARENT_BRANCH,
            "frozen_tag": bounded.FROZEN_TAG,
        },
        "scientific_lock": {
            "experiment_id": bounded.EXPERIMENT_ID,
            "profile_plan_id": bounded.SCIENTIFIC_PROFILE_ID,
            "pair_id": bounded.PAIR_ID,
            "condition_order": list(bounded.CONDITION_ORDER),
            "task_kind": "open-ended-query",
            "task_query": "go to google flights",
            "model": bounded.MODEL,
            "model_roles": {role: bounded.MODEL for role in bounded.MODEL_ROLES},
            "reproduction_level": "directional-reproduction",
            "interpretation_allowed": False,
            "pilot_authorized": False,
            "training": False,
        },
        "source_and_runtime": {
            "upstream_commit": bounded.UPSTREAM_COMMIT,
            "upstream_tree": bounded.UPSTREAM_TREE,
            "uv_lock_sha256": bounded.UPSTREAM_LOCK_SHA256,
            "routing_patch_sha256": bounded.ROUTING_PATCH_SHA256,
            "runtime_adaptation_sha256": bounded.RUNTIME_ADAPTATION_SHA256,
            "routing_sha256": bounded.ROUTING_SHA256,
            "base_image": bounded.BASE_IMAGE_INDEX,
            "base_image_index_digest": bounded.BASE_IMAGE_INDEX_DIGEST,
            "base_image_amd64_manifest": bounded.BASE_IMAGE_AMD64_MANIFEST,
            "base_image_amd64_config": bounded.BASE_IMAGE_AMD64_CONFIG,
            "base_image_compressed_bytes": bounded.BASE_IMAGE_COMPRESSED_BYTES,
            "platform": "linux/amd64",
            "python": "3.10",
            "uv_version": bounded.UV_VERSION,
            "uv_wheel": bounded.UV_WHEEL,
            "uv_wheel_url": bounded.UV_WHEEL_URL,
            "uv_wheel_bytes": bounded.UV_WHEEL_BYTES,
            "uv_wheel_sha256": bounded.UV_WHEEL_SHA256,
            "dependency_command": [
                "uv",
                "sync",
                "--frozen",
                "--extra",
                "eval",
                "--python",
                "3.10",
            ],
            "playwright": bounded.PLAYWRIGHT_VERSION,
            "chromium_revision": bounded.CHROMIUM_REVISION,
            "chromium_version": bounded.CHROMIUM_VERSION,
            "browser_download_command": None,
        },
        "provider_and_pricing": {
            "provider": bounded.PROVIDER,
            "api_base_url": bounded.API_BASE_URL,
            "model": bounded.MODEL,
            "standard_input_usd_per_million": 2.5,
            "standard_cached_input_usd_per_million": 1.25,
            "standard_output_usd_per_million": 10.0,
            "cap_method": "all-model-tokens-priced-at-output-rate",
            "service_tier": "standard",
        },
        "public_metadata": [dict(item) for item in bounded.PUBLIC_METADATA],
        "limits": dict(bounded.LIMITS),
        "preflights": {
            "browser": {
                "run_id": bounded.BROWSER_PREFLIGHT_RUN_ID,
                "network": "none",
                "browser_actions": 1,
                "model_calls": 0,
                "container_create_argv_template": list(browser),
                "container_create_template_sha256": bounded.template_sha256(browser),
            },
            "model": {
                "run_id": bounded.MODEL_PREFLIGHT_RUN_ID,
                "method": "GET",
                "url": f"{bounded.API_BASE_URL}models/{bounded.MODEL}",
                "model_calls": 0,
                "metadata_gets": 1,
                "container_create_argv_template": list(model),
                "container_create_template_sha256": bounded.template_sha256(model),
            },
        },
        "container_lifecycle": bounded.lifecycle_argv_templates(),
        "bootstrap_argv_template": list(bounded.bootstrap_argv_template()),
        "provider_observer": bounded.provider_observer_contract(),
        "storage": bounded.storage_contract(),
        "conditions": conditions,
        "secrets": {
            "provider_observer_variable": "LAMBDA_API_KEY",
            "workload_variable": "SIRA_API_KEY",
            "workload_file": "/run/secrets/sira_api_key",
            "forbidden_fallback": "OPENAI_API_KEY",
            "value_in_argv": False,
            "value_in_environment_list": False,
            "value_in_image": False,
            "value_in_labels": False,
            "value_in_evidence": False,
        },
        "lambda": {
            "product": "Lambda On-Demand Cloud",
            "api_base_url": "https://cloud.lambda.ai",
            "instance_type": bounded.SELECTED_INSTANCE_TYPE,
            "region": bounded.SELECTED_REGION,
            "architecture": bounded.SELECTED_ARCHITECTURE,
            "image_alias": bounded.SELECTED_IMAGE_ALIAS,
            "image_family": bounded.SELECTED_IMAGE_FAMILY,
            "image_version": bounded.SELECTED_IMAGE_VERSION,
            "ssh_key_name": bounded.SELECTED_SSH_KEY_NAME,
            "ssh_use": False,
            "persistent_filesystems": 0,
            "observed_price_cents_per_hour": bounded.OBSERVED_PRICE_CENTS_PER_HOUR,
            "global_firewall_baseline_alias": bounded.FIREWALL_BASELINE_ALIAS,
            "global_firewall_semantic_sha256": bounded.FIREWALL_BASELINE_SHA256,
            "mutations_actor": "user",
            "observer_operations": "GET-only",
        },
        "hard_blockers": list(bounded.HARD_BLOCKERS),
        "post_launch_stop_conditions": list(bounded.POST_LAUNCH_STOP_CONDITIONS),
        "deferred_limitations": list(bounded.DEFERRED_LIMITATIONS),
        "steps": [
            {"ordinal": ordinal, "actor": actor, "action": action, "stop_on_failure": True}
            for ordinal, actor, action in bounded.STEP_CONTRACT
        ],
        "implementation": {"reviewed_commit": "0" * 40, "artifacts": _artifacts()},
        "execution_permissions_now": {
            "lambda_account_requests": 0,
            "openai_account_requests": 0,
            "cloud_mutations": 0,
            "paid_compute": False,
            "jupyter": False,
            "containers": False,
            "browser": False,
            "sira": False,
            "scientific_execution": False,
        },
    }


def _load_bootstrap() -> ModuleType:
    path = ROOT / "containers/sira-smoke/bounded/bootstrap.py"
    spec = importlib.util.spec_from_file_location("test_t07_bounded_bootstrap", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_valid_plan_is_exact_and_schema_valid() -> None:
    plan = valid_plan()
    bounded.validate_plan(plan, repository_root=ROOT)
    assert validate_instance(plan, ROOT / "schemas/t07-bounded-smoke-plan.schema.json") == []


def test_locked_scientific_files_remain_exact() -> None:
    for relative, digest in bounded.SCIENTIFIC_HASHES.items():
        assert bounded.sha256_file(ROOT / relative) == digest


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("identity", "authorized"), True),
        (("scientific_lock", "model"), "gpt-4o"),
        (("scientific_lock", "interpretation_allowed"), True),
        (("limits", "automatic_retries"), 1),
        (("limits", "openai_api_cost_cents_aggregate"), 401),
        (("lambda", "persistent_filesystems"), 1),
    ],
)
def test_plan_rejects_authority_science_and_budget_drift(
    path: tuple[str, str], value: object
) -> None:
    plan = valid_plan()
    section = plan[path[0]]
    assert isinstance(section, dict)
    section[path[1]] = value
    with pytest.raises(bounded.BoundedSmokeContractError):
        bounded.validate_plan(plan)


def test_exact_model_is_bound_to_every_role_and_command() -> None:
    plan = valid_plan()
    science = plan["scientific_lock"]
    assert isinstance(science, dict)
    model_roles = science["model_roles"]
    assert isinstance(model_roles, dict)
    assert set(model_roles.values()) == {bounded.MODEL}
    for condition in bounded.CONDITION_ORDER:
        argv = bounded.container_create_argv(condition)
        assert bounded.MODEL in argv
        assert "gpt-4o" not in argv
    bounded.assert_pair_command_contract(
        bounded.container_create_argv("SIRA-REACTIVE"),
        bounded.container_create_argv("SIRA-SIMULATIVE"),
    )


def test_container_templates_enforce_bounded_security_policy() -> None:
    for argv in (
        bounded.browser_preflight_create_argv(),
        bounded.model_preflight_create_argv(),
        *(bounded.container_create_argv(item) for item in bounded.CONDITION_ORDER),
    ):
        joined = "\n".join(argv)
        assert "--privileged" not in argv
        assert "--pid" not in argv
        assert "host" not in argv
        assert "docker.sock" not in joined
        assert "--cap-drop" in argv and "ALL" in argv
        assert "no-new-privileges=true" in argv
        assert "--read-only" in argv
        assert "--pids-limit" in argv
        assert "--memory" in argv
        assert "--restart" in argv and "no" in argv
        assert "--pull" in argv and "never" in argv
    assert "none" in bounded.browser_preflight_create_argv()
    assert "${SIRA_SECRET_FILE}" not in bounded.browser_preflight_create_argv()
    assert "${SIRA_SECRET_FILE}" in "\n".join(bounded.model_preflight_create_argv())


def test_secret_value_is_never_part_of_rendered_or_committed_commands() -> None:
    canary = "sk-public-dummy-canary-abcdefghijklmnopqrstuvwxyz"
    plan_text = json.dumps(valid_plan())
    assert canary not in plan_text
    assert "OPENAI_API_KEY" in plan_text
    assert "/run/secrets/sira_api_key" in plan_text
    assert "Authorization: Bearer" not in plan_text


def test_pair_budget_accepts_boundary_and_rejects_each_overrun() -> None:
    reactive = bounded.BudgetUsage(
        "SIRA-REACTIVE", 2.0, 100_000, 0, 100_000, 16, 1, 120, 104_857_600
    )
    simulative = bounded.BudgetUsage(
        "SIRA-SIMULATIVE", 2.0, 100_000, 0, 100_000, 61, 1, 120, 104_857_600
    )
    bounded.validate_pair_budget((reactive, simulative))
    with pytest.raises(bounded.BoundedSmokeContractError):
        bounded.validate_pair_budget(
            (
                bounded.BudgetUsage("SIRA-REACTIVE", 2.01, 100_000, 0, 100_000, 16, 1, 120, 1),
                simulative,
            )
        )


def _provider_preflight() -> dict[str, object]:
    return {
        "schema_version": bounded.SCHEMA_VERSION,
        "instance_type": bounded.SELECTED_INSTANCE_TYPE,
        "region": bounded.SELECTED_REGION,
        "architecture": bounded.SELECTED_ARCHITECTURE,
        "image_alias": bounded.SELECTED_IMAGE_ALIAS,
        "image_family": bounded.SELECTED_IMAGE_FAMILY,
        "image_version": bounded.SELECTED_IMAGE_VERSION,
        "ssh_key_name": bounded.SELECTED_SSH_KEY_NAME,
        "firewall_baseline_alias": bounded.FIREWALL_BASELINE_ALIAS,
        "firewall_semantic_sha256": bounded.FIREWALL_BASELINE_SHA256,
        "running_instance_count": 0,
        "price_cents_per_hour": 129,
        "capacity_available": True,
        "image_offered": True,
        "ssh_key_present": True,
        "manual_termination_path_available": True,
        "user_present_for_billable_operation": True,
        "pagination_present": False,
        "retry_count": 0,
    }


def test_provider_preflight_and_terminal_checks_fail_closed() -> None:
    bounded.validate_provider_preflight(_provider_preflight())
    drift = _provider_preflight()
    drift["running_instance_count"] = 1
    with pytest.raises(bounded.BoundedSmokeContractError):
        bounded.validate_provider_preflight(drift)
    terminal = {
        "schema_version": bounded.SCHEMA_VERSION,
        "owned_instance_match_count": 0,
        "running_owned_instance_count": 0,
        "owned_regional_ruleset_match_count": 0,
        "global_firewall_baseline_alias": bounded.FIREWALL_BASELINE_ALIAS,
        "global_firewall_semantic_sha256": bounded.FIREWALL_BASELINE_SHA256,
        "provider_terminal_or_absent": True,
        "billing_stopped": True,
        "pagination_present": False,
    }
    bounded.validate_terminal_provider_observation(terminal)
    terminal["billing_stopped"] = False
    with pytest.raises(bounded.BoundedSmokeContractError):
        bounded.validate_terminal_provider_observation(terminal)


def test_evidence_manifest_is_schema_valid_bounded_and_secret_safe(tmp_path: Path) -> None:
    (tmp_path / "record.json").write_text('{"ok":true}\n', encoding="utf-8")
    manifest = bounded.build_evidence_manifest(tmp_path)
    bounded.validate_evidence_manifest(manifest)
    assert (
        validate_instance(manifest, ROOT / "schemas/t07-bounded-smoke-evidence.schema.json") == []
    )
    (tmp_path / "secret.txt").write_text(
        "sk-public-dummy-canary-abcdefghijklmnopqrstuvwxyz", encoding="utf-8"
    )
    with pytest.raises(bounded.BoundedSmokeContractError, match="credential-shaped"):
        bounded.build_evidence_manifest(tmp_path)


class _FakeRunner:
    def __init__(self) -> None:
        self.deadline = 10**12
        self.argv: list[tuple[str, ...]] = []
        self.removed = False

    def remaining(self) -> float:
        return 300.0

    def run(
        self,
        argv: Any,
        *,
        cwd: Path,
        timeout: float | None = None,
        check: bool = True,
    ) -> Any:
        del cwd, timeout, check
        command = tuple(argv)
        self.argv.append(command)
        bootstrap = _load_bootstrap()
        stdout = b""
        returncode = 0
        if command[1] == "create":
            stdout = b"a" * 64 + b"\n"
        elif command[1:3] == ("start", "--attach"):
            stdout = b"completed\n"
        elif command[1] == "inspect":
            if self.removed:
                returncode = 1
            else:
                stdout = b'[{"State":{"Running":false,"Status":"exited"}}]\n'
        elif command[1] == "top":
            stdout = b"PID PPID PGID SID STAT COMMAND ARGS\n"
        elif command[1] == "stop":
            returncode = 1
        elif command[1] == "rm":
            self.removed = True
        return bootstrap.CommandResult(command, returncode, stdout, b"", 0.01)


def test_lifecycle_failed_stop_still_kills_removes_and_seals_cleanup(tmp_path: Path) -> None:
    bootstrap = _load_bootstrap()
    work = _FakeRunner()
    cleanup = _FakeRunner()
    template = bounded.container_create_argv("SIRA-REACTIVE")
    result = bootstrap.run_owned_container(
        condition="SIRA-REACTIVE",
        run_id=bounded.REACTIVE_RUN_ID,
        create_template=template,
        substitutions={
            "${HOST_ATTEMPT_ROOT}": str(tmp_path),
            "${SIRA_SECRET_FILE}": "/private/dummy-secret-file",
            "${EXECUTION_COMMIT}": "1" * 40,
            "${AUTHORIZATION_REFERENCE}": "AUTH-T07-BOUNDED-SIRA-SMOKE-V1-TEST",
            "${IMAGE_ID}": "sha256:" + "2" * 64,
        },
        plan=valid_plan(),
        contract=bounded,
        work_runner=work,
        cleanup_runner=cleanup,
        evidence_root=tmp_path,
        attached=True,
        wall_seconds=120,
    )
    assert result.returncode == 0
    operations = [item[1] for item in cleanup.argv]
    assert operations[:3] == ["stop", "kill", "inspect"]
    assert "rm" in operations
    cleanup_record = json.loads((tmp_path / "container-cleanup.json").read_text())
    bounded.validate_container_cleanup(cleanup_record)


def test_committed_plan_matches_runtime_contract_when_present() -> None:
    path = ROOT / "containers/sira-smoke/bounded/bounded-smoke-plan-v1.json"
    if not path.exists():
        pytest.skip("plan is generated only after the reviewed implementation commit exists")
    document = json.loads(path.read_text(encoding="utf-8"))
    bounded.validate_plan(document, repository_root=ROOT)
    assert validate_instance(document, ROOT / "schemas/t07-bounded-smoke-plan.schema.json") == []
