from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import os
import sys
import time
import zipfile
from datetime import UTC, datetime
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
        "$schema": "../../../schemas/t07-bounded-smoke-plan-v2.schema.json",
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
            "api_request_service_tier": "default",
            "pricing_class": "standard",
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
        "private_security_binding": bounded.private_security_binding_contract(),
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
        "implementation": {
            "reviewed_commit": bounded.REVIEWED_IMPLEMENTATION_COMMIT,
            "artifacts": _artifacts(),
        },
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
    assert validate_instance(plan, ROOT / "schemas/t07-bounded-smoke-plan-v2.schema.json") == []


def test_locked_scientific_files_remain_exact() -> None:
    for relative, digest in bounded.SCIENTIFIC_HASHES.items():
        assert bounded.sha256_file(ROOT / relative) == digest


def test_v1_plan_and_runs_are_preserved_burned_and_v2_is_fresh() -> None:
    v1_path = ROOT / "containers/sira-smoke/bounded/bounded-smoke-plan-v1.json"
    encoded = v1_path.read_bytes()
    assert len(encoded) == 55_789
    assert hashlib.sha256(encoded).hexdigest() == (
        "0128e632e0a3a01f7ee0b9014396fed5782c8afa98459fe9ad4db5cc7db3148f"
    )
    v1 = json.loads(encoded)
    assert v1["identity"]["host_run_id"] == "RUN-T07-BOUNDED-HOST-0001"
    assert bounded.HOST_RUN_ID == "RUN-T07-BOUNDED-HOST-0002"
    assert bounded.REACTIVE_RUN_ID == "RUN-T07-BOUNDED-SIRA-REACTIVE-0002"
    assert bounded.SIMULATIVE_RUN_ID == "RUN-T07-BOUNDED-SIRA-SIMULATIVE-0002"
    assert v1["limits"] == valid_plan()["limits"]
    assert v1["scientific_lock"] == valid_plan()["scientific_lock"]


def test_v2_private_binding_public_surface_is_minimal_and_command_is_hash_bound() -> None:
    public = bounded.private_security_binding_contract()
    assert set(public) == {
        "binding_alias",
        "binding_sha256",
        "schema_version",
        "ruleset_name_pattern_id",
        "baseline_alias",
        "baseline_semantic_sha256",
        "canonicalizer_version",
        "parser_version",
        "restoration_alias",
        "restoration_payload_sha256",
    }
    assert public["binding_alias"].startswith("t07-bounded-binding-")
    assert len(str(public["binding_sha256"])) == 64
    materialize = bounded.local_supervisor_argv_templates()["materialize"]
    assert "${PRIVATE_SECURITY_BINDING_PATH}" in materialize
    assert "${PRIVATE_SECURITY_BINDING_SEAL_SHA256}" in materialize
    assert str(public["binding_sha256"]) in materialize
    assert "private-parameters.json" not in "\n".join(materialize)


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


def test_plan_rejects_tampered_reviewed_implementation_commit() -> None:
    plan = valid_plan()
    implementation = plan["implementation"]
    assert isinstance(implementation, dict)
    implementation["reviewed_commit"] = "0" * 40
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
        assert argv[argv.index("--pid") + 1] == "private"
        assert "host" not in argv
        assert "docker.sock" not in joined
        assert "--cap-drop" in argv and "ALL" in argv
        assert "no-new-privileges=true" in argv
        assert "--read-only" in argv
        assert "--pids-limit" in argv
        assert "--memory" in argv
        assert "--restart" in argv and "no" in argv
        assert "--pull" in argv and "never" in argv
        assert (
            "/giclab/attempt:rw,noexec,nosuid,nodev,size=67108864,uid=1000,gid=1000,mode=0700"
        ) in argv
        assert "${HOST_ATTEMPT_ROOT}" not in "\n".join(argv)
        assert all("type=bind" not in item or item.endswith(",readonly") for item in argv)
    assert "none" in bounded.browser_preflight_create_argv()
    assert "${SIRA_SECRET_FILE}" not in bounded.browser_preflight_create_argv()
    assert "${SIRA_SECRET_FILE}" in "\n".join(bounded.model_preflight_create_argv())
    lifecycle = bounded.lifecycle_argv_templates()
    assert lifecycle["copy_out"] == [
        "/usr/bin/docker",
        "cp",
        "${CONTAINER_ID}:/giclab/attempt/.",
        "${HOST_ATTEMPT_ROOT}",
    ]


def test_secret_value_is_never_part_of_rendered_or_committed_commands() -> None:
    canary = "".join(("s", "k-", "public-dummy-canary-abcdefghijklmnopqrstuvwxyz"))
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
        validate_instance(manifest, ROOT / "schemas/t07-bounded-smoke-evidence-v2.schema.json")
        == []
    )
    (tmp_path / "secret.txt").write_text(
        "".join(("s", "k-", "public-dummy-canary-abcdefghijklmnopqrstuvwxyz")), encoding="utf-8"
    )
    with pytest.raises(bounded.BoundedSmokeContractError, match="credential-shaped"):
        bounded.build_evidence_manifest(tmp_path)
    (tmp_path / "secret.txt").unlink()
    secret_shaped_name = "".join(("API_", "KEY=PUBLICDUMMYVALUE.txt"))
    (tmp_path / secret_shaped_name).write_text("safe\n", encoding="utf-8")
    with pytest.raises(bounded.BoundedSmokeContractError, match="credential-shaped"):
        bounded.build_evidence_manifest(tmp_path)


def test_secret_lease_holds_identity_and_destroys_without_retaining_value(tmp_path: Path) -> None:
    bootstrap = _load_bootstrap()
    secret_root = tmp_path / "secret-root"
    secret_root.mkdir()
    credential_path = secret_root / "sira_api_key"
    canary = b"PUBLIC_DUMMY_SECRET_CANARY_0123456789"
    credential_path.write_bytes(canary + b"\n")
    credential_path.chmod(0o600)
    lease = bootstrap.acquire_secret_lease(
        credential_path, forbidden_roots=(tmp_path / "repository",)
    )
    try:
        assert lease.read_value() == canary
        receipt = tmp_path / "secret-cleanup.json"
        record = lease.destroy(receipt)
        assert not credential_path.exists()
        assert record["manual_fallback_deletion_required"] is False
        assert canary not in receipt.read_bytes()
    finally:
        lease.close()


def test_secret_lease_path_replacement_truncates_held_inode_and_requires_rotation(
    tmp_path: Path,
) -> None:
    bootstrap = _load_bootstrap()
    secret_root = tmp_path / "secret-root"
    secret_root.mkdir()
    credential_path = secret_root / "sira_api_key"
    credential_path.write_text("PUBLIC_DUMMY_OLD_SECRET\n", encoding="utf-8")
    credential_path.chmod(0o600)
    lease = bootstrap.acquire_secret_lease(
        credential_path, forbidden_roots=(tmp_path / "repository",)
    )
    held_copy = secret_root / "held-original"
    credential_path.rename(held_copy)
    credential_path.write_text("PUBLIC_DUMMY_REPLACEMENT\n", encoding="utf-8")
    credential_path.chmod(0o600)
    receipt = tmp_path / "secret-cleanup.json"
    try:
        with pytest.raises(bootstrap.BootstrapError, match="manual delete"):
            lease.destroy(receipt)
        assert os.fstat(lease.descriptor).st_size == 0
        assert credential_path.read_text(encoding="utf-8") == "PUBLIC_DUMMY_REPLACEMENT\n"
        record = json.loads(receipt.read_text(encoding="utf-8"))
        assert record["path_identity_replaced"] is True
        assert record["manual_fallback_deletion_required"] is True
        assert b"PUBLIC_DUMMY_OLD_SECRET" not in receipt.read_bytes()
    finally:
        lease.close()


def test_early_failure_bundle_is_bounded_secret_safe_and_complete(tmp_path: Path) -> None:
    bootstrap = _load_bootstrap()
    output_root = tmp_path / "t07-bounded-output-0002"
    cleanup = tmp_path / "cleanup.json"
    cleanup.write_text(
        json.dumps(
            {
                "schema_version": "0.1.0",
                "secret_variable_name": "SIRA_API_KEY",
                "secret_file_basename": "sira_api_key",
                "held_identity_established_before_preflight": True,
                "truncated_before_unlink": True,
                "unlinked": True,
                "absence_verified": True,
                "path_identity_replaced": False,
                "value_or_hash_retained": False,
                "manual_fallback_deletion_required": False,
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    archive = bootstrap.package_early_failure_evidence(
        output_root,
        failure_stage="invocation_validation",
        secret_target_identity_established=True,
        secret_cleanup_verified=True,
        secret_value_read=False,
        secret_cleanup_source=cleanup,
    )
    early_root = tmp_path / "t07-bounded-output-0002-early-failure"
    assert archive.parent == early_root
    assert archive.stat().st_size <= bootstrap.MAX_EARLY_FAILURE_EVIDENCE_BYTES
    assert {
        "t07-bounded-early-failure-evidence.zip",
        "EARLY_FAILURE_ARCHIVE_IDENTITY.json",
        "TERMINATE_REQUIRED.json",
        "evidence",
    } == {path.name for path in early_root.iterdir()}
    with zipfile.ZipFile(archive) as opened:
        assert "FAILURE_EVIDENCE_MANIFEST.json" in opened.namelist()
        assert "evidence/early-failure-disposition.json" in opened.namelist()
        assert "evidence/secret-cleanup.json" in opened.namelist()


class _FakeRunner:
    def __init__(self, *, unsafe_privileged: bool = False) -> None:
        self.deadline = 10**12
        self.argv: list[tuple[str, ...]] = []
        self.removed = False
        self.stopped = False
        self.create_argv: tuple[str, ...] | None = None
        self.unsafe_privileged = unsafe_privileged

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
            self.create_argv = command
            stdout = b"a" * 64 + b"\n"
        elif command[1] == "wait":
            stdout = b"0\n"
            self.stopped = True
        elif command[1] == "logs":
            stdout = b"completed\n"
        elif command[1] == "inspect":
            if self.removed:
                returncode = 1
            else:
                running = not self.stopped
                status = "running" if running else "exited"
                if running and self.create_argv is not None:
                    argv = self.create_argv

                    def option(name: str) -> str:
                        return argv[argv.index(name) + 1]

                    def options(name: str) -> list[str]:
                        return [
                            argv[index + 1] for index, value in enumerate(argv) if value == name
                        ]

                    image = next(value for value in argv if value.startswith("sha256:"))
                    image_index = argv.index(image)
                    labels = dict(value.split("=", 1) for value in options("--label"))
                    tmpfs = {
                        value.split(":", 1)[0]: value.split(":", 1)[1]
                        for value in options("--tmpfs")
                    }
                    host_mounts: list[dict[str, object]] = []
                    realized_mounts: list[dict[str, object]] = []
                    for value in options("--mount"):
                        fields = dict(
                            part.split("=", 1) for part in value.split(",") if "=" in part
                        )
                        host_mounts.append(
                            {
                                "Type": "bind",
                                "Source": fields["src"],
                                "Target": fields["dst"],
                                "ReadOnly": True,
                            }
                        )
                        realized_mounts.append(
                            {
                                "Type": "bind",
                                "Source": fields["src"],
                                "Destination": fields["dst"],
                                "RW": False,
                            }
                        )
                    inspected = {
                        "Id": "a" * 64,
                        "Name": "/" + option("--name"),
                        "Image": image,
                        "State": {"Running": True, "Status": "running"},
                        "Config": {
                            "Image": image,
                            "User": option("--user"),
                            "Entrypoint": [option("--entrypoint")],
                            "Cmd": list(argv[image_index + 1 :]),
                            "Labels": labels,
                            "Env": ["PATH=/usr/bin"],
                        },
                        "HostConfig": {
                            "Privileged": self.unsafe_privileged,
                            "PidMode": "private",
                            "NetworkMode": option("--network"),
                            "IpcMode": option("--ipc"),
                            "CgroupnsMode": option("--cgroupns"),
                            "UTSMode": "",
                            "CapAdd": None,
                            "CapDrop": ["ALL"],
                            "SecurityOpt": ["no-new-privileges=true"],
                            "ReadonlyRootfs": True,
                            "Init": True,
                            "AutoRemove": False,
                            "RestartPolicy": {"Name": "no", "MaximumRetryCount": 0},
                            "NanoCpus": int(float(option("--cpus")) * 1_000_000_000),
                            "Memory": int(option("--memory")),
                            "MemorySwap": int(option("--memory-swap")),
                            "PidsLimit": int(option("--pids-limit")),
                            "ShmSize": int(option("--shm-size")),
                            "Tmpfs": tmpfs,
                            "Binds": None,
                            "VolumesFrom": None,
                            "Mounts": host_mounts,
                            "LogConfig": {
                                "Type": option("--log-driver"),
                                "Config": dict(
                                    value.split("=", 1) for value in options("--log-opt")
                                ),
                            },
                        },
                        "Mounts": realized_mounts,
                    }
                else:
                    inspected = {"Id": "a" * 64, "State": {"Running": running, "Status": status}}
                stdout = json.dumps([inspected]).encode() + b"\n"
        elif command[1] == "top":
            stdout = b"PID PPID PGID SID STAT COMMAND ARGS\n1 0 1 1 Ss python entrypoint\n"
        elif command[1] == "stop":
            self.stopped = True
            returncode = 1
        elif command[1] == "kill":
            self.stopped = True
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
            "${AUTHORIZATION_REFERENCE}": "AUTH-T07-BOUNDED-SIRA-SMOKE-V2-TEST",
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
    assert operations[:4] == ["cp", "stop", "kill", "inspect"]
    assert "rm" in operations
    cleanup_record = json.loads((tmp_path / "container-cleanup.json").read_text())
    bounded.validate_container_cleanup(cleanup_record)


def test_unsafe_realized_container_policy_blocks_release_and_still_cleans_up(
    tmp_path: Path,
) -> None:
    bootstrap = _load_bootstrap()
    work = _FakeRunner(unsafe_privileged=True)
    cleanup = _FakeRunner()
    with pytest.raises(bootstrap.BootstrapError, match="inspect policy"):
        bootstrap.run_owned_container(
            condition="SIRA-REACTIVE",
            run_id=bounded.REACTIVE_RUN_ID,
            create_template=bounded.container_create_argv("SIRA-REACTIVE"),
            substitutions={
                "${SIRA_SECRET_FILE}": "/private/dummy-secret-file",
                "${EXECUTION_COMMIT}": "1" * 40,
                "${AUTHORIZATION_REFERENCE}": "AUTH-T07-BOUNDED-SIRA-SMOKE-V2-TEST",
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
    assert not any("/usr/bin/touch" in command for command in work.argv)
    assert any(command[1] == "rm" for command in cleanup.argv)


def test_work_and_cleanup_runners_share_one_command_budget(tmp_path: Path) -> None:
    bootstrap = _load_bootstrap()
    meter = bootstrap.CommandMeter(
        max_calls=2,
        output_cap=1_024,
        cleanup_reserved_calls=1,
        cleanup_reserved_output_bytes=512,
    )
    work = bootstrap.CommandRunner(deadline=time.monotonic() + 10, meter=meter, scope="work")
    cleanup = bootstrap.CommandRunner(deadline=time.monotonic() + 10, meter=meter, scope="cleanup")
    work.run(("/usr/bin/true",), cwd=tmp_path)
    with pytest.raises(bootstrap.BootstrapError, match="preserves cleanup reserve"):
        work.run(("/usr/bin/true",), cwd=tmp_path)
    cleanup.run(("/usr/bin/true",), cwd=tmp_path)
    assert work.call_count == cleanup.call_count == 2


def test_bounded_tree_enumerator_counts_directories_and_stops_at_cap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bootstrap = _load_bootstrap()
    monkeypatch.setattr(bootstrap, "MAX_EVIDENCE_FILES", 3)
    for index in range(4):
        (tmp_path / f"empty-{index}").mkdir()
    with pytest.raises(bootstrap.BootstrapError, match="filesystem-entry cap"):
        bootstrap._bounded_regular_files(tmp_path, context="synthetic evidence")


def test_write_all_recovers_from_injected_short_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bootstrap = _load_bootstrap()
    output = tmp_path / "short-write.bin"
    original_write = bootstrap.os.write

    def short_write(descriptor: int, encoded: bytes | memoryview) -> int:
        return original_write(descriptor, bytes(encoded[: max(1, len(encoded) // 3)]))

    monkeypatch.setattr(bootstrap.os, "write", short_write)
    expected = b"bounded-durable-write" * 64
    bootstrap._write_bytes(output, expected, cap=len(expected))
    assert output.read_bytes() == expected


def test_failed_command_writes_durable_secret_safe_receipt(tmp_path: Path) -> None:
    bootstrap = _load_bootstrap()
    ledger = tmp_path / "command-meter.jsonl"
    meter = bootstrap.CommandMeter(
        max_calls=4,
        output_cap=1_024,
        cleanup_reserved_calls=1,
        cleanup_reserved_output_bytes=256,
        ledger_path=ledger,
    )
    runner = bootstrap.CommandRunner(
        deadline=time.monotonic() + 10,
        meter=meter,
        scope="work",
    )
    stdout_canary = "PUBLIC_DUMMY_STDOUT_PRIVATE"
    stderr_canary = "PUBLIC_DUMMY_STDERR_PRIVATE"
    with pytest.raises(bootstrap.BootstrapError) as caught:
        runner.run(
            (
                sys.executable,
                "-c",
                (
                    "import sys;"
                    f"sys.stdout.write({stdout_canary!r});"
                    f"sys.stderr.write({stderr_canary!r});"
                    "raise SystemExit(7)"
                ),
            ),
            cwd=tmp_path,
        )
    assert caught.value.failure_code == "command_nonzero_exit"
    events = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
    failure = events[-1]
    assert failure["event_type"] == "command_failed"
    assert failure["returncode"] == 7
    assert failure["failure_code"] == "command_nonzero_exit"
    assert failure["stdout_bytes"] == len(stdout_canary)
    assert failure["stderr_bytes"] == len(stderr_canary)
    assert isinstance(failure["elapsed_ms"], int) and failure["elapsed_ms"] >= 0
    retained = ledger.read_bytes()
    assert stdout_canary.encode() not in retained
    assert stderr_canary.encode() not in retained


def test_failure_archive_is_bounded_and_excludes_secret_canary(tmp_path: Path) -> None:
    bootstrap = _load_bootstrap()
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    (evidence / "safe.json").write_text('{"status":"failed"}\n', encoding="utf-8")
    canary = "PUBLIC_DUMMY_OPAQUE_CANARY_0123456789"
    (evidence / "unsafe.log").write_text(canary, encoding="utf-8")
    (tmp_path / "TERMINATE_REQUIRED.json").write_text("{}\n", encoding="utf-8")
    archive = bootstrap.package_failure_evidence(
        tmp_path,
        evidence,
        bounded,
        secret_value=canary.encode(),
    )
    assert archive.stat().st_size <= bootstrap.MAX_FAILURE_EVIDENCE_BYTES
    with zipfile.ZipFile(archive) as opened:
        names = set(opened.namelist())
        assert "evidence/safe.json" in names
        assert "evidence/unsafe.log" not in names
        assert canary.encode() not in b"".join(opened.read(name) for name in names)
    incident = json.loads((tmp_path / "TERMINATE_REQUIRED.json").read_text(encoding="utf-8"))
    assert incident["failure_class"] == "credential_material_detected"
    assert incident["manual_credential_rotation_required"] is True


@pytest.mark.parametrize(
    "transform",
    (
        lambda value: value,
        lambda value: value.hex().encode("ascii"),
        lambda value: value.hex().upper().encode("ascii"),
        base64.b64encode,
        lambda value: base64.b64encode(value).rstrip(b"="),
        base64.urlsafe_b64encode,
        lambda value: base64.urlsafe_b64encode(value).rstrip(b"="),
        lambda value: hashlib.sha256(value).digest(),
        lambda value: hashlib.sha256(value).hexdigest().encode("ascii"),
        lambda value: hashlib.sha256(value).hexdigest().upper().encode("ascii"),
    ),
)
def test_success_and_failure_archives_reject_secret_derivatives(
    tmp_path: Path, transform: Any
) -> None:
    bootstrap = _load_bootstrap()
    canary_bytes = b"PUBLIC_DUMMY_OPAQUE_CANARY_0123456789"
    transformed = transform(canary_bytes)

    success = tmp_path / "success"
    success.mkdir()
    (success / "output.bin").write_bytes(b"prefix:" + transformed + b":suffix")
    with pytest.raises(bootstrap.BootstrapError, match="supplied secret"):
        bootstrap._assert_secret_absent(success, canary_bytes)

    failure = tmp_path / "failure"
    evidence = failure / "evidence"
    evidence.mkdir(parents=True)
    (evidence / "safe.json").write_text('{"status":"failed"}\n', encoding="utf-8")
    (evidence / "unsafe.bin").write_bytes(b"prefix:" + transformed + b":suffix")
    (failure / "TERMINATE_REQUIRED.json").write_text("{}\n", encoding="utf-8")
    archive = bootstrap.package_failure_evidence(
        failure,
        evidence,
        bounded,
        secret_value=canary_bytes,
    )
    with zipfile.ZipFile(archive) as opened:
        assert "evidence/unsafe.bin" not in opened.namelist()
        retained = b"".join(opened.read(name) for name in opened.namelist())
    assert transformed not in retained


def test_known_authorization_reference_is_not_a_secret_derivative_false_positive(
    tmp_path: Path,
) -> None:
    bootstrap = _load_bootstrap()
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    authorization = b"AUTH-T07-BOUNDED-SIRA-SMOKE-V2-TEST"
    (evidence / "authority.json").write_bytes(
        b'{"authorization_reference":"' + authorization + b'"}\n'
    )
    bootstrap._assert_secret_absent(
        evidence,
        b"PUBLIC_DUMMY_OPAQUE_CANARY_0123456789",
    )


def test_failure_archive_reserves_mandatory_incident_and_cleanup_at_file_cap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bootstrap = _load_bootstrap()
    monkeypatch.setattr(bootstrap, "MAX_EVIDENCE_FILES", 4)
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    cleanup = evidence / "secret-cleanup.json"
    cleanup.write_text('{"absence_verified":true}\n', encoding="utf-8")
    for ordinal in range(3):
        (evidence / f"optional-{ordinal:02d}.json").write_text("{}\n", encoding="utf-8")
    (tmp_path / "TERMINATE_REQUIRED.json").write_text(
        '{"provider_termination_required":true}\n', encoding="utf-8"
    )

    archive = bootstrap.package_failure_evidence(tmp_path, evidence, bounded)

    with zipfile.ZipFile(archive) as opened:
        names = set(opened.namelist())
        manifest = json.loads(opened.read("FAILURE_EVIDENCE_MANIFEST.json"))
    assert "TERMINATE_REQUIRED.json" in names
    assert "evidence/secret-cleanup.json" in names
    assert manifest["file_count"] == 4
    assert manifest["skipped_cap_or_unsafe_file_count"] == 1


def test_reconstruction_and_compute_closeout_records_are_source_grounded(
    tmp_path: Path,
) -> None:
    bootstrap = _load_bootstrap()
    (tmp_path / "normalized-events.jsonl").write_bytes(b"{}\n" * 4)
    bootstrap.write_reconstruction_records(tmp_path, contract=bounded)
    compute = bootstrap.write_bootstrap_execution(
        tmp_path,
        contract=bounded,
        status="completed",
        started_at=datetime(2026, 8, 11, 20, 0, tzinfo=UTC),
        ended_at=datetime(2026, 8, 11, 20, 10, tzinfo=UTC),
    )
    assert compute["provider_allocation_accounting"] is False
    assert compute["wall_clock_seconds"] == 600
    assert (tmp_path / "normalized-events.jsonl").read_text().count("\n") == 4
    equivalence = json.loads((tmp_path / "pair-equivalence.json").read_text())
    assert equivalence["canonical_condition_diff_only"] is True


def test_committed_plan_matches_runtime_contract_when_present() -> None:
    path = ROOT / "containers/sira-smoke/bounded/bounded-smoke-plan-v2.json"
    if not path.exists():
        pytest.skip("plan is generated only after the reviewed implementation commit exists")
    document = json.loads(path.read_text(encoding="utf-8"))
    bounded.validate_plan(document, repository_root=ROOT)
    assert validate_instance(document, ROOT / "schemas/t07-bounded-smoke-plan-v2.schema.json") == []
