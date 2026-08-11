"""Offline control plane for the manually supervised T07 bounded smoke.

This module is intentionally transport- and runtime-inert.  It validates the future
manual plan, materializes exact argument arrays, enforces observed budget/evidence
records, and adjudicates redacted provider/container cleanup observations.  It has no
method that can call Lambda or OpenAI, mutate a cloud resource, or launch Docker.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import stat
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import ROUND_CEILING, Decimal
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import Final

SCHEMA_VERSION: Final = "0.1.0"
BRANCH: Final = "phase-1/sira-smoke-bounded"
FORK_COMMIT: Final = "397a391b736528dd1049023d629100193e823c49"
PARENT_BRANCH: Final = "phase-1/sira-smoke-lambda"
FROZEN_TAG: Final = "t07-high-assurance-infrastructure-v1"

PLAN_ID: Final = "PLAN-T07-BOUNDED-SIRA-SMOKE-V1"
HOST_RUN_ID: Final = "RUN-T07-BOUNDED-HOST-0001"
REACTIVE_RUN_ID: Final = "RUN-T07-BOUNDED-SIRA-REACTIVE-0001"
SIMULATIVE_RUN_ID: Final = "RUN-T07-BOUNDED-SIRA-SIMULATIVE-0001"
BROWSER_PREFLIGHT_RUN_ID: Final = "RUN-T07-BOUNDED-BROWSER-PREFLIGHT-0001"
MODEL_PREFLIGHT_RUN_ID: Final = "RUN-T07-BOUNDED-MODEL-PREFLIGHT-0001"
AUTHORIZATION_PLACEHOLDER: Final = "AUTH-T07-BOUNDED-SIRA-SMOKE-V1-PENDING"
TERMINAL_STATE: Final = "ready-for-bounded-smoke-authorization"

EXPERIMENT_ID: Final = "EXP-0001"
SCIENTIFIC_PROFILE_ID: Final = "PLAN-EXP0001-SMOKE"
PAIR_ID: Final = "PAIR-EXP0001-SMOKE-0000"
MODEL: Final = "gpt-4o-2024-11-20"
PROVIDER: Final = "OpenAI"
API_BASE_URL: Final = "https://api.openai.com/v1/"
UPSTREAM_COMMIT: Final = "93fb8d72de71f9a4a13419670adeb34d93cf7acd"
UPSTREAM_TREE: Final = "6a6d9068b94d7632d3533a3d6f013d4de6ff76e8"
UPSTREAM_LOCK_SHA256: Final = "138585129c7f369887591d30d9727f8dd466639fa78fb00adc5a04f1e9b2d76e"
ROUTING_PATCH_SHA256: Final = "4d7e2a25f4313fc754db0fa17aeda51cc5cd75a5653adaf13b01ce87a71cb8ed"
RUNTIME_ADAPTATION_SHA256: Final = (
    "894783a47c19efc5e141a90a4dd63920b9440e1ef231aad5b2738b1f524bbbcd"
)
ROUTING_SHA256: Final = "8a0e6e2934c98ba3faefab51c6408da2476df428bd43688e41d8aea8280c9619"

BASE_IMAGE_INDEX: Final = (
    "mcr.microsoft.com/playwright/python:v1.39.0-jammy@"
    "sha256:96955ff5cc37e13f5f1b21f5171afb9fed7e028025aa9d81c690501cd7fa0c6c"
)
BASE_IMAGE_INDEX_DIGEST: Final = (
    "sha256:96955ff5cc37e13f5f1b21f5171afb9fed7e028025aa9d81c690501cd7fa0c6c"
)
BASE_IMAGE_AMD64_MANIFEST: Final = (
    "sha256:8f7d4d5ef52dbe4af81db537258ae6d15c71b86c6984dd6030dac8f34c86ebcd"
)
BASE_IMAGE_AMD64_CONFIG: Final = (
    "sha256:801969079a1e0ae8c657adc45f7acac5abcc7fab846e60cd42c883ee78dded51"
)
BASE_IMAGE_COMPRESSED_BYTES: Final = 742_924_281
UV_VERSION: Final = "0.11.7"
UV_WHEEL: Final = "uv-0.11.7-py3-none-manylinux_2_17_x86_64.manylinux2014_x86_64.whl"
UV_WHEEL_BYTES: Final = 24_933_975
UV_WHEEL_SHA256: Final = "4e4d5e31bea86e1b6e0f5a0f95e14e80018e6f6c0129256d2915a4b3d793644d"
UV_WHEEL_URL: Final = (
    "https://files.pythonhosted.org/packages/83/eb/"
    "4e1557daf6693cb446ed28185664ad6682fd98c6dbac9e433cbc35df450a/" + UV_WHEEL
)

PLAYWRIGHT_VERSION: Final = "1.39.0"
CHROMIUM_REVISION: Final = "1084"
CHROMIUM_VERSION: Final = "119.0.6045.9"
SELECTED_INSTANCE_TYPE: Final = "gpu_1x_a10"
SELECTED_REGION: Final = "us-east-1"
SELECTED_ARCHITECTURE: Final = "x86_64"
SELECTED_IMAGE_ALIAS: Final = "img-0032"
SELECTED_IMAGE_FAMILY: Final = "lambda-stack-22-04"
SELECTED_IMAGE_VERSION: Final = "22.4.5-2141"
SELECTED_SSH_KEY_NAME: Final = "fractal-lambda-codex"
OBSERVED_PRICE_CENTS_PER_HOUR: Final = 129
FIREWALL_BASELINE_ALIAS: Final = "l2m-firewall-baseline-b0ef71115811"
FIREWALL_BASELINE_SHA256: Final = "b0ef711158113cdbdbb1707cb43f21a635271bb2e93bfc0e898ce7118589f764"
EXTERNAL_ARCHIVE_MOUNT: Final = "/Volumes/Macintosh HD - Data"
EXTERNAL_ARCHIVE_UUID: Final = "8478609D-FA37-4ED5-875D-47AE912B9151"
EXTERNAL_PHYSICAL_STORE_UUID: Final = "7904A6F1-F483-4ED7-9E34-BFECAB31C63E"

SCIENTIFIC_HASHES: Final[Mapping[str, str]] = MappingProxyType(
    {
        "experiments/EXP-0001-sira-simulative-vs-reactive/protocol.yaml": (
            "5bdf3fdcf2c486883ad74044bd373c1804362c7d9ad8e990f5e10fa1c0f99b4c"
        ),
        "experiments/EXP-0001-sira-simulative-vs-reactive/config.yaml": (
            "f05767de862f3f519f429f5b73baa67043ed96209f3d47db9fd2d084847ec16d"
        ),
        "experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/smoke.yaml": (
            "ab276b9e49256d49f143e252eddf6fe5c447d6f9c11300745b450fb7f1d0e425"
        ),
        (
            "experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/"
            "conditions/smoke-reactive.yaml"
        ): "7ca19470e550e48978090c9b7014e047c56d80962e40275b846f589b08bfb018",
        (
            "experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/"
            "conditions/smoke-simulative.yaml"
        ): "68f5f4a4a123620bab039ba7bc6844243cad229ed992df6562bf0d8562874436",
    }
)

HARD_BLOCKERS: Final = (
    "repository_identity_drift",
    "sira_source_identity_drift",
    "immutable_model_unavailable",
    "model_routing_mixed_or_floating",
    "secret_channel_failure",
    "projected_openai_api_cost_above_usd_4",
    "lambda_price_or_projected_normal_cost_above_usd_2",
    "evidence_root_not_fresh",
    "selected_lambda_resource_unavailable",
    "user_presence_unavailable",
    "provider_termination_path_unavailable",
    "prior_attempt_running_instance_unresolved",
)
DEFERRED_LIMITATIONS: Final = (
    "manual_console_launch_is_not_exactly_once_api_proven",
    "browser_descendant_containment_is_practical_not_formally_exhaustive",
    "provider_or_control_plane_outage_can_extend_billing",
    "runtime_supply_chain_pinning_is_practical_not_exhaustive_attestation",
    "setup_is_manually_supervised_and_not_production_automation",
    "setup_network_wire_bytes_are_admission_and_disk_accounted_not_exactly_metered",
    "one_pair_smoke_has_no_scientific_power",
)
POST_LAUNCH_STOP_CONDITIONS: Final = (
    "cloud_ide_unavailable",
    "bootstrap_failure",
    "model_or_api_failure",
    "browser_or_container_failure",
    "budget_or_wall_limit_reached",
    "evidence_download_failure",
    "pair_contract_drift",
)
STEP_CONTRACT: Final = (
    (1, "local-verifier", "materialize_fresh_external_authorization_and_private_binding"),
    (2, "observer", "read_only_provider_preflight"),
    (3, "user", "apply_temporary_private_32_global_firewall_if_needed"),
    (4, "user", "create_one_unique_owned_regional_ruleset_if_needed"),
    (5, "observer", "verify_exact_security_controls_before_launch"),
    (6, "user", "launch_exactly_one_selected_instance_with_one_click"),
    (7, "observer", "bind_exactly_one_owned_instance"),
    (8, "user", "open_cloud_ide_jupyter"),
    (9, "user", "upload_exact_bounded_bundle_secret_file_and_authorization"),
    (10, "bootstrap", "run_hash_first_bootstrap_once"),
    (11, "bootstrap", "run_no_network_browser_lifecycle_preflight"),
    (12, "bootstrap", "verify_exact_model_snapshot_once"),
    (13, "bootstrap", "run_reactive_once_then_simulative_once"),
    (14, "bootstrap", "capture_remove_verify_and_package_success_or_failure_evidence"),
    (15, "user", "download_success_or_failure_evidence_and_identity_records"),
    (16, "local-verifier", "verify_inbound_manifest_hashes_and_retain_source"),
    (17, "user", "terminate_exact_bound_instance"),
    (18, "observer", "verify_exact_instance_terminal_or_absent_and_billing_stopped"),
    (19, "user", "delete_owned_regional_ruleset_and_restore_global_firewall_if_changed"),
    (20, "observer", "verify_ruleset_absence_and_exact_firewall_restoration"),
    (21, "local-verifier", "seal_and_copy_complete_or_failed_evidence_to_external_archive"),
)
PUBLIC_METADATA: Final = (
    {
        "subject": "OpenAI GPT-4o dated snapshot documentation",
        "url": "https://developers.openai.com/api/docs/models/gpt-4o",
        "retrieved_at_utc": "2026-08-11T20:46:49Z",
        "bytes": 388_761,
        "sha256": "f1139b9abc5a3e767e38401bcd4f7a290a34c9fafbbc256185fa75645b776d6c",
    },
    {
        "subject": "OpenAI API pricing documentation",
        "url": "https://openai.com/api/pricing/",
        "retrieved_at_utc": "2026-08-11T20:46:49Z",
        "bytes": 542_673,
        "sha256": "46fd914a3927db808d6d8c0d89933300a12e586927cbc80171097a41715c5104",
    },
    {
        "subject": "SiRA immutable Git commit metadata",
        "url": ("https://api.github.com/repos/sailing-lab/sira/git/commits/" + UPSTREAM_COMMIT),
        "retrieved_at_utc": "2026-08-11T21:08:52Z",
        "bytes": 2_368,
        "sha256": "9e3ab7c973d6b448606fb2f1646e1ef4de6bd293ee60df28eedca78ab0a6451a",
    },
    {
        "subject": "PyPI uv 0.11.7 release metadata",
        "url": "https://pypi.org/pypi/uv/0.11.7/json",
        "retrieved_at_utc": "2026-08-11T21:08:52Z",
        "bytes": 30_118,
        "sha256": "05baa3ae199e6f62e0485e26f5db829e35f70f09272edcfbb1b9454ed5ac0b3b",
    },
    {
        "subject": "MCR Playwright 1.39.0 OCI index",
        "url": (
            "https://mcr.microsoft.com/v2/playwright/python/manifests/" + BASE_IMAGE_INDEX_DIGEST
        ),
        "retrieved_at_utc": "2026-08-11T21:08:52Z",
        "bytes": 743,
        "sha256": "96955ff5cc37e13f5f1b21f5171afb9fed7e028025aa9d81c690501cd7fa0c6c",
    },
)
REQUIRED_IMPLEMENTATION_ARTIFACTS: Final = frozenset(
    {
        "containers/sira-smoke/bounded/.dockerignore",
        "containers/sira-smoke/bounded/Containerfile.amd64",
        "containers/sira-smoke/bounded/bootstrap.py",
        "containers/sira-smoke/bounded/local_supervisor_bootstrap.py",
        "containers/sira-smoke/bounded/browser_preflight.py",
        "containers/sira-smoke/bounded/harness_init.py",
        "containers/sira-smoke/bounded/model_preflight.py",
        "containers/sira-smoke/container_entrypoint.py",
        "containers/sira-smoke/fixtures/static.html",
        "containers/sira-smoke/sira-immutable-model-routing.patch",
        "schemas/t07-bounded-smoke-evidence.schema.json",
        "schemas/t07-bounded-smoke-authorization.schema.json",
        "schemas/t07-bounded-smoke-observer-ledger.schema.json",
        "schemas/t07-bounded-smoke-plan.schema.json",
        "schemas/t07-bounded-smoke-private-binding.schema.json",
        "containers/sira-smoke/lambda/endpoint-schemas-v3/firewall-rulesets.schema.json",
        "containers/sira-smoke/lambda/endpoint-schemas-v3/global-firewall-ruleset.schema.json",
        "containers/sira-smoke/lambda/endpoint-schemas-v3/images.schema.json",
        "containers/sira-smoke/lambda/endpoint-schemas-v3/instance-types.schema.json",
        "containers/sira-smoke/lambda/endpoint-schemas-v3/instances.schema.json",
        "containers/sira-smoke/lambda/endpoint-schemas-v3/regions.schema.json",
        "containers/sira-smoke/lambda/endpoint-schemas-v3/ssh-keys.schema.json",
        "docs/COMPUTE_POLICY.md",
        "docs/PROJECT_STATE.yaml",
        "docs/STORAGE_POLICY.md",
        "manifests/compute.yaml",
        "src/giclab/__init__.py",
        "src/giclab/harness/lambda_archive.py",
        "src/giclab/harness/sira_gate_a.py",
        "src/giclab/harness/sira_gate_a_runtime.py",
        "src/giclab/harness/sira_storage.py",
        "src/giclab/harness/t07_bounded_smoke.py",
        "src/giclab/harness/t07_bounded_supervisor.py",
        "src/giclab/registry.py",
    }
)

MODEL_ROLES: Final = (
    "default",
    "encoder",
    "memory",
    "policy",
    "world_model",
    "critic",
    "actor",
    "fallback",
)
CONDITION_ORDER: Final = ("SIRA-REACTIVE", "SIRA-SIMULATIVE")
RUN_IDS: Final = {
    "SIRA-REACTIVE": REACTIVE_RUN_ID,
    "SIRA-SIMULATIVE": SIMULATIVE_RUN_ID,
}
MODE_VALUES: Final = {"SIRA-REACTIVE": "reactive", "SIRA-SIMULATIVE": "simulative"}
JOB_NAMES: Final = {
    "SIRA-REACTIVE": "EXP-0001-SMOKE-REACTIVE",
    "SIRA-SIMULATIVE": "EXP-0001-SMOKE-SIMULATIVE",
}
MODEL_CALL_CAPS: Final = {"SIRA-REACTIVE": 16, "SIRA-SIMULATIVE": 61}

LIMITS: Final[Mapping[str, int | str]] = MappingProxyType(
    {
        "openai_api_cost_cents_aggregate": 400,
        "openai_api_cost_cents_per_condition": 200,
        "model_tokens_aggregate": 400_000,
        "model_tokens_per_condition": 200_000,
        "model_call_attempts_aggregate": 77,
        "model_call_attempts_reactive": 16,
        "model_call_attempts_simulative": 61,
        "model_metadata_gets": 1,
        "condition_wall_seconds_each": 120,
        "condition_wall_seconds_aggregate": 240,
        "browser_actions_each": 1,
        "browser_actions_aggregate": 2,
        "browser_preflight_actions": 1,
        "condition_attempts_each": 1,
        "condition_attempts_aggregate": 2,
        "automatic_retries": 0,
        "implicit_provider_retries": 0,
        "persistent_filesystems": 0,
        "instances": 1,
        "manual_launch_clicks": 1,
        "provider_hard_wall_seconds": 3_600,
        "normal_termination_click_deadline_seconds": 3_300,
        "provider_cost_cap_cents": 200,
        "projected_provider_cost_cents": 129,
        "condition_output_bytes_each": 104_857_600,
        "condition_output_bytes_aggregate": 209_715_200,
        "condition_payload_tmpfs_bytes_each": 67_108_864,
        "condition_control_evidence_reserve_bytes_each": 37_748_736,
        "sealed_bundle_bytes": 301_989_888,
        "remote_evidence_bytes": 268_435_456,
        "local_evidence_bytes": 301_989_888,
        "bootstrap_process_output_bytes": 33_554_432,
        "docker_control_output_bytes": 33_554_432,
        "docker_lifecycle_calls": 128,
        "docker_lifecycle_call_scope": "aggregate-work-and-cleanup",
        "owned_containers": 4,
        "lambda_read_only_gets": 13,
        "lambda_response_bytes_per_get": 1_048_576,
        "lambda_response_bytes_aggregate": 13_631_488,
        "lambda_observer_ledger_bytes": 262_144,
        "lambda_observer_ledger_events": 96,
        "lambda_observer_event_bytes": 4_096,
        "lambda_observer_wall_seconds": 3_600,
        "local_authorization_bytes": 65_536,
        "local_private_binding_bytes": 1_048_576,
        "archive_files": 128,
        "archive_wall_seconds": 600,
        "network_download_admission_bytes": 2_147_483_648,
        "network_download_metering": "exact-for-uv-only-setup-disk-delta-enforced",
        "runtime_disk_increment_bytes": 17_179_869_184,
        "remote_preflight_free_bytes": 34_359_738_368,
        "mac_prewrite_floor_bytes": 8_891_924_480,
        "mac_retained_floor_bytes": 8_589_934_592,
        "external_prewrite_floor_bytes": 200_350_182_605,
        "external_retained_floor_bytes": 200_048_192_717,
        "container_cpu_millis": 2_000,
        "container_memory_bytes": 4_294_967_296,
        "container_memory_swap_bytes": 4_294_967_296,
        "container_pids": 512,
        "container_shm_bytes": 1_073_741_824,
        "container_tmpfs_bytes": 134_217_728,
        "container_term_seconds": 5,
        "container_log_max_bytes": 8_388_608,
        "container_log_max_files": 1,
        "container_restart_policy": "no",
        "container_cleanup_reserve_seconds": 120,
    }
)

_HEX40 = re.compile(r"^[a-f0-9]{40}$")
_HEX64 = re.compile(r"^[a-f0-9]{64}$")
_SAFE_ID = re.compile(r"^[A-Z0-9][A-Z0-9._-]{2,127}$")
_IMAGE_ID = re.compile(r"^sha256:[a-f0-9]{64}$")
_PLACEHOLDER = re.compile(r"^\$\{[A-Z][A-Z0-9_]*\}$")
_SECRET_SHAPES = (
    re.compile(rb"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(rb"(?im)^[ \t]*[A-Z0-9_]*(?:API_KEY|TOKEN|SECRET)[ \t]*=[^\r\n]+$"),
)


class BoundedSmokeContractError(ValueError):
    """The bounded-smoke plan or evidence violates its fixed contract."""


def canonical_json_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        + b"\n"
    )


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    if path.is_symlink() or not path.is_file():
        raise BoundedSmokeContractError(f"bound path is not a regular file: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1_048_576):
            digest.update(chunk)
    return digest.hexdigest()


def _strict_json(encoded: bytes, *, context: str) -> dict[str, object]:
    def pairs(items: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in items:
            if key in result:
                raise BoundedSmokeContractError(f"{context} contains a duplicate key")
            result[key] = value
        return result

    try:
        value = json.loads(
            encoded,
            object_pairs_hook=pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(
                BoundedSmokeContractError(f"{context} contains a non-finite number")
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise BoundedSmokeContractError(f"{context} is not strict JSON") from None
    if not isinstance(value, dict):
        raise BoundedSmokeContractError(f"{context} must be an object")
    return value


def read_json_file(path: Path, *, max_bytes: int = 1_048_576) -> dict[str, object]:
    try:
        before = path.lstat()
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except OSError:
        raise BoundedSmokeContractError("required JSON input is unavailable") from None
    try:
        opened = os.fstat(descriptor)
        if (
            not stat.S_ISREG(before.st_mode)
            or stat.S_ISLNK(before.st_mode)
            or before.st_nlink != 1
            or (before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino)
            or opened.st_size > max_bytes
        ):
            raise BoundedSmokeContractError("required JSON input identity is unsafe")
        encoded = bytearray()
        while True:
            chunk = os.read(descriptor, min(65_536, max_bytes + 1 - len(encoded)))
            if not chunk:
                break
            encoded.extend(chunk)
            if len(encoded) > max_bytes:
                raise BoundedSmokeContractError("required JSON input exceeds its cap")
        if len(encoded) != opened.st_size:
            raise BoundedSmokeContractError("required JSON input changed while held")
        return _strict_json(bytes(encoded), context=path.name)
    finally:
        os.close(descriptor)


def _mapping(value: object, *, context: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or any(not isinstance(key, str) for key in value):
        raise BoundedSmokeContractError(f"{context} must be an object")
    return value


def _sequence(value: object, *, context: str) -> Sequence[object]:
    if not isinstance(value, list):
        raise BoundedSmokeContractError(f"{context} must be an array")
    return value


def _text(value: object, *, context: str) -> str:
    if not isinstance(value, str) or not value:
        raise BoundedSmokeContractError(f"{context} must be a nonempty string")
    return value


def _integer(value: object, *, context: str) -> int:
    if type(value) is not int or value < 0:
        raise BoundedSmokeContractError(f"{context} must be a nonnegative integer")
    return value


def _money_cents_ceiling(value: object, *, context: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise BoundedSmokeContractError(f"{context} must be numeric")
    amount = Decimal(str(value)) * 100
    if not amount.is_finite() or amount < 0:
        raise BoundedSmokeContractError(f"{context} must be finite and nonnegative")
    return int(amount.to_integral_value(rounding=ROUND_CEILING))


def _numeric_limit(name: str) -> int:
    value = LIMITS[name]
    if type(value) is not int:
        raise BoundedSmokeContractError(f"numeric limit {name} is malformed")
    return value


def condition_inner_argv(condition: str) -> tuple[str, ...]:
    if condition not in CONDITION_ORDER:
        raise BoundedSmokeContractError("condition is outside the locked pair")
    mode = MODE_VALUES[condition]
    evidence = "/giclab/attempt"
    return (
        "/opt/sira/.venv/bin/python",
        "/opt/giclab-src/giclab/harness/sira_gate_a_runtime.py",
        "--gate-upstream-runner",
        "/opt/sira/scripts/run_web_agent.py",
        "--gate-attempt-root",
        evidence,
        "--gate-mode",
        mode,
        "--gate-adaptation-sha256",
        RUNTIME_ADAPTATION_SHA256,
        "--",
        JOB_NAMES[condition],
        "--query",
        "go to google flights",
        "--mode",
        mode,
        "--agent",
        "sira",
        "--model",
        MODEL,
        "--max_steps",
        "1",
        "--timeout",
        "30",
        "--max_retry",
        "0",
        "--output_dir",
        evidence + "/sira-output",
        "--seed",
        "42",
    )


def _container_create_prefix(
    *,
    name: str,
    network: str,
    cpu: str,
    memory_bytes: int,
    pids: int,
    shm_bytes: int,
    run_id: str,
    condition: str,
) -> list[str]:
    labels = (
        ("experiment", EXPERIMENT_ID),
        ("profile", PLAN_ID),
        ("condition", condition),
        ("run-id", run_id),
        ("attempt", "1"),
        ("repository-commit", "${EXECUTION_COMMIT}"),
        ("source-commit", UPSTREAM_COMMIT),
        ("authorization", "${AUTHORIZATION_REFERENCE}"),
    )
    argv = [
        "/usr/bin/docker",
        "create",
        "--name",
        name,
        "--pull",
        "never",
        "--platform",
        "linux/amd64",
        "--network",
        network,
        "--ipc",
        "private",
        "--cgroupns",
        "private",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges=true",
        "--read-only",
        "--init",
        "--restart",
        "no",
        "--cpus",
        cpu,
        "--memory",
        str(memory_bytes),
        "--memory-swap",
        str(memory_bytes),
        "--pids-limit",
        str(pids),
        "--shm-size",
        str(shm_bytes),
        "--tmpfs",
        "/tmp:rw,noexec,nosuid,nodev,size=134217728,uid=1000,gid=1000,mode=0700",
        "--log-driver",
        "local",
        "--log-opt",
        "max-size=8388608",
        "--log-opt",
        "max-file=1",
        "--user",
        "1000:1000",
    ]
    for key, value in labels:
        argv.extend(("--label", f"org.giclab.t07.{key}={value}"))
    return argv


def browser_preflight_create_argv() -> tuple[str, ...]:
    argv = _container_create_prefix(
        name="t07-bounded-browser-preflight-0001",
        network="none",
        cpu="1.000",
        memory_bytes=1_073_741_824,
        pids=128,
        shm_bytes=536_870_912,
        run_id=BROWSER_PREFLIGHT_RUN_ID,
        condition="BROWSER-PREFLIGHT",
    )
    argv.extend(
        (
            "--tmpfs",
            "/giclab/attempt:rw,noexec,nosuid,nodev,size=67108864,uid=1000,gid=1000,mode=0700",
            "--entrypoint",
            "/usr/bin/python3",
            "${IMAGE_ID}",
            "/opt/giclab/browser_preflight.py",
        )
    )
    return tuple(argv)


def model_preflight_create_argv() -> tuple[str, ...]:
    argv = _container_create_prefix(
        name="t07-bounded-model-preflight-0001",
        network="bridge",
        cpu="1.000",
        memory_bytes=536_870_912,
        pids=64,
        shm_bytes=67_108_864,
        run_id=MODEL_PREFLIGHT_RUN_ID,
        condition="MODEL-PREFLIGHT",
    )
    argv.extend(
        (
            "--tmpfs",
            "/giclab/attempt:rw,noexec,nosuid,nodev,size=67108864,uid=1000,gid=1000,mode=0700",
            "--mount",
            "type=bind,src=${SIRA_SECRET_FILE},dst=/run/secrets/sira_api_key,readonly",
            "--entrypoint",
            "/usr/bin/python3",
            "${IMAGE_ID}",
            "/opt/giclab/container_entrypoint.py",
            "--",
            "/usr/bin/python3",
            "/opt/giclab/model_preflight.py",
        )
    )
    return tuple(argv)


def container_create_argv(condition: str) -> tuple[str, ...]:
    if condition not in CONDITION_ORDER:
        raise BoundedSmokeContractError("condition is outside the locked pair")
    mode = MODE_VALUES[condition]
    argv = _container_create_prefix(
        name=f"t07-bounded-{mode}-0001",
        network="bridge",
        cpu="2.000",
        memory_bytes=4_294_967_296,
        pids=512,
        shm_bytes=1_073_741_824,
        run_id=RUN_IDS[condition],
        condition=condition,
    )
    argv.extend(
        (
            "--tmpfs",
            "/giclab/attempt:rw,noexec,nosuid,nodev,size=67108864,uid=1000,gid=1000,mode=0700",
            "--mount",
            "type=bind,src=${SIRA_SECRET_FILE},dst=/run/secrets/sira_api_key,readonly",
            "--entrypoint",
            "/usr/bin/python3",
            "${IMAGE_ID}",
            "/opt/giclab/container_entrypoint.py",
            "--",
            *condition_inner_argv(condition),
        )
    )
    return tuple(argv)


def lifecycle_argv_templates() -> dict[str, list[str]]:
    """Return the only Docker lifecycle arrays allowed for owned containers."""

    return {
        "start_attached": ["/usr/bin/docker", "start", "--attach", "${CONTAINER_ID}"],
        "start_detached": ["/usr/bin/docker", "start", "${CONTAINER_ID}"],
        "inspect": ["/usr/bin/docker", "inspect", "${CONTAINER_ID}"],
        "top": [
            "/usr/bin/docker",
            "top",
            "${CONTAINER_ID}",
            "-eo",
            "pid,ppid,pgid,sid,stat,comm,args",
        ],
        "readiness": [
            "/usr/bin/docker",
            "exec",
            "${CONTAINER_ID}",
            "/usr/bin/test",
            "-f",
            "${READINESS_PATH}",
        ],
        "copy_out": [
            "/usr/bin/docker",
            "cp",
            "${CONTAINER_ID}:/giclab/attempt/.",
            "${HOST_ATTEMPT_ROOT}",
        ],
        "stop": ["/usr/bin/docker", "stop", "--time", "5", "${CONTAINER_ID}"],
        "kill": ["/usr/bin/docker", "kill", "${CONTAINER_ID}"],
        "remove": ["/usr/bin/docker", "rm", "--force", "${CONTAINER_ID}"],
        "container_residue": [
            "/usr/bin/docker",
            "ps",
            "--all",
            "--filter",
            "label=org.giclab.t07.run-id=${RUN_ID}",
            "--format",
            "{{.ID}}",
        ],
        "network_residue": [
            "/usr/bin/docker",
            "network",
            "ls",
            "--filter",
            "label=org.giclab.t07.run-id=${RUN_ID}",
            "--format",
            "{{.ID}}",
        ],
        "volume_residue": [
            "/usr/bin/docker",
            "volume",
            "ls",
            "--filter",
            "label=org.giclab.t07.run-id=${RUN_ID}",
            "--format",
            "{{.Name}}",
        ],
    }


def bootstrap_argv_template() -> tuple[str, ...]:
    return (
        "/usr/bin/python3",
        "-I",
        "/home/ubuntu/t07-bounded-bundle/containers/sira-smoke/bounded/bootstrap.py",
        "--plan",
        (
            "/home/ubuntu/t07-bounded-bundle/containers/sira-smoke/bounded/"
            "bounded-smoke-plan-v1.json"
        ),
        "--plan-sha256",
        "${PLAN_SHA256}",
        "--contract-file",
        "/home/ubuntu/t07-bounded-bundle/src/giclab/harness/t07_bounded_smoke.py",
        "--contract-sha256",
        "${CONTRACT_SHA256}",
        "--authorization",
        "/home/ubuntu/t07-bounded-authorization.json",
        "--authorization-sha256",
        "${AUTHORIZATION_SHA256}",
        "--bundle-root",
        "/home/ubuntu/t07-bounded-bundle",
        "--secret-file",
        "/home/ubuntu/.config/giclab/sira_api_key",
        "--output-root",
        "/home/ubuntu/t07-bounded-output-0001",
    )


def local_supervisor_argv_templates() -> dict[str, list[str]]:
    repository = "${REPOSITORY_ROOT}"
    base = [
        "/usr/bin/python3",
        "-I",
        repository + "/containers/sira-smoke/bounded/local_supervisor_bootstrap.py",
        "--repository-root",
        repository,
        "--supervisor-file",
        repository + "/src/giclab/harness/t07_bounded_supervisor.py",
        "--supervisor-sha256",
        "${SUPERVISOR_SHA256}",
        "--plan",
        repository + "/containers/sira-smoke/bounded/bounded-smoke-plan-v1.json",
        "--plan-sha256",
        "${PLAN_SHA256}",
        "--contract-file",
        repository + "/src/giclab/harness/t07_bounded_smoke.py",
        "--contract-sha256",
        "${CONTRACT_SHA256}",
        "--expected-commit",
        "${EXECUTION_COMMIT}",
    ]
    authority = [
        "--authorization",
        repository + "/artifacts/t07/bounded/RUN-T07-BOUNDED-HOST-0001/authorization.json",
        "--authorization-sha256",
        "${AUTHORIZATION_SHA256}",
        "--private-binding",
        repository + "/artifacts/t07/bounded/RUN-T07-BOUNDED-HOST-0001/private-binding.json",
        "--private-binding-sha256",
        "${PRIVATE_BINDING_SHA256}",
    ]
    output: dict[str, list[str]] = {
        "materialize": [
            *base,
            "materialize",
            "--authorization-reference",
            "${AUTHORIZATION_REFERENCE}",
            "--source-parameters",
            repository + "/artifacts/t07/lambda/gate-l2m/"
            "RUN-T07-L2M-MANUAL-CONSOLE-HOST-QUALIFICATION-0003/"
            "materialization-v1/private-parameters.json",
            "--source-parameters-sha256",
            "a9b210594ed3b4c962f414b8a2d9509d14a2d7deb097050e92321e6da4d5d096",
            "--restoration-payload",
            repository + "/artifacts/t07/lambda/gate-l2m/"
            "T07-HIGH-ASSURANCE-FIREWALL-CLOSEOUT-0001/restoration-payload.json",
            "--restoration-payload-sha256",
            "50ca7febe9f160ada862371376485ea2ece11b373d25179ccd578d9c7acd42b8",
        ],
    }
    for phase in ("prelaunch", "security", "post_launch", "termination", "terminal"):
        output[f"observe_{phase}"] = [*base, "observe", *authority, "--phase", phase]
    for disposition in ("complete", "failed"):
        output[f"archive_{disposition}"] = [
            *base,
            "archive",
            *authority,
            "--disposition",
            disposition,
        ]
    return output


def provider_observer_contract() -> dict[str, object]:
    return {
        "transport": "in-process-https-no-shell",
        "method": "GET",
        "redirect_follows": 0,
        "pagination_requests": 0,
        "automatic_retries": 0,
        "phases": [
            {
                "phase": "prelaunch",
                "paths": [
                    "/api/v1/instance-types",
                    "/api/v1/images",
                    "/api/v1/regions",
                    "/api/v1/ssh-keys",
                    "/api/v1/firewall-rulesets",
                    "/api/v1/firewall-rulesets/global",
                    "/api/v1/instances",
                ],
            },
            {
                "phase": "security",
                "paths": [
                    "/api/v1/firewall-rulesets",
                    "/api/v1/firewall-rulesets/global",
                ],
            },
            {
                "phase": "post_launch",
                "paths": [
                    "/api/v1/instances",
                ],
            },
            {
                "phase": "termination",
                "paths": [
                    "/api/v1/instances",
                ],
            },
            {
                "phase": "terminal",
                "paths": [
                    "/api/v1/firewall-rulesets",
                    "/api/v1/firewall-rulesets/global",
                ],
            },
        ],
        "request_ledger": {
            "path": ("artifacts/t07/bounded/RUN-T07-BOUNDED-HOST-0001/request-ledger.jsonl"),
            "fsync_each_event": True,
            "max_bytes": 262_144,
            "max_events": 96,
            "max_event_bytes": 4_096,
        },
        "argv_templates": local_supervisor_argv_templates(),
    }


def storage_contract() -> dict[str, object]:
    return {
        "remote_active_root": "/home/ubuntu/t07-bounded-output-0001",
        "persistent_filesystem_count": 0,
        "local_inbound_root": "artifacts/t07/bounded/RUN-T07-BOUNDED-HOST-0001/inbound",
        "external_mount": EXTERNAL_ARCHIVE_MOUNT,
        "external_volume_uuid": EXTERNAL_ARCHIVE_UUID,
        "external_physical_store_uuid": EXTERNAL_PHYSICAL_STORE_UUID,
        "external_archive_root": (
            EXTERNAL_ARCHIVE_MOUNT + "/GIC-Lab/t07/sealed-artifacts/RUN-T07-BOUNDED-HOST-0001"
        ),
        "archive_cap_bytes": 301_989_888,
        "external_retained_floor_bytes": 200_048_192_717,
        "external_prewrite_floor_bytes": 200_350_182_605,
        "mac_prewrite_floor_bytes": 8_891_924_480,
        "mac_retained_floor_bytes": 8_589_934_592,
        "one_way_copy": True,
        "source_retained_until_destination_hash_verified": True,
        "held_no_follow_descriptors": True,
        "internal_fallback": False,
        "live_bidirectional_sync": False,
    }


def template_sha256(argv: Sequence[str]) -> str:
    if not argv or any(not isinstance(item, str) or not item for item in argv):
        raise BoundedSmokeContractError("argument template must contain nonempty strings")
    return sha256_bytes(canonical_json_bytes(list(argv)))


def materialize_argv(
    template: Sequence[str],
    substitutions: Mapping[str, str],
) -> tuple[str, ...]:
    required = {item for item in template if _PLACEHOLDER.fullmatch(item) is not None}
    embedded = {
        match.group(0) for item in template for match in re.finditer(r"\$\{[A-Z][A-Z0-9_]*\}", item)
    }
    required.update(embedded)
    if required != set(substitutions):
        raise BoundedSmokeContractError("command substitutions do not exactly match placeholders")
    result: list[str] = []
    for item in template:
        rendered = item
        for placeholder, value in substitutions.items():
            if not value or "\x00" in value or "\n" in value or "\r" in value:
                raise BoundedSmokeContractError("command substitution is unsafe")
            rendered = rendered.replace(placeholder, value)
        if "${" in rendered:
            raise BoundedSmokeContractError("command retains an unresolved placeholder")
        result.append(rendered)
    return tuple(result)


def assert_pair_command_contract(
    reactive: Sequence[str],
    simulative: Sequence[str],
) -> None:
    expected_reactive = container_create_argv("SIRA-REACTIVE")
    expected_simulative = container_create_argv("SIRA-SIMULATIVE")
    if tuple(reactive) != expected_reactive or tuple(simulative) != expected_simulative:
        raise BoundedSmokeContractError("condition command differs from its canonical rendering")
    if len(reactive) != len(simulative):
        raise BoundedSmokeContractError("condition command lengths differ")
    allowed_pairs = {
        ("t07-bounded-reactive-0001", "t07-bounded-simulative-0001"),
        ("reactive", "simulative"),
        ("EXP-0001-SMOKE-REACTIVE", "EXP-0001-SMOKE-SIMULATIVE"),
        (
            "org.giclab.t07.condition=SIRA-REACTIVE",
            "org.giclab.t07.condition=SIRA-SIMULATIVE",
        ),
        (
            f"org.giclab.t07.run-id={REACTIVE_RUN_ID}",
            f"org.giclab.t07.run-id={SIMULATIVE_RUN_ID}",
        ),
    }
    differences = {
        (left, right) for left, right in zip(reactive, simulative, strict=True) if left != right
    }
    if differences != allowed_pairs:
        raise BoundedSmokeContractError("condition command drift exceeds declared differences")


@dataclass(frozen=True, slots=True)
class BudgetUsage:
    condition: str
    cost_usd: float
    input_tokens: int
    cached_input_tokens: int
    output_tokens: int
    model_call_attempts: int
    browser_actions: int
    wall_seconds: float
    output_bytes: int
    attempt: int = 1

    def __post_init__(self) -> None:
        if self.condition not in CONDITION_ORDER or self.attempt != 1:
            raise BoundedSmokeContractError("budget usage is outside the one-attempt pair")
        if not math.isfinite(self.cost_usd) or self.cost_usd < 0:
            raise BoundedSmokeContractError("observed API cost is invalid")
        if not math.isfinite(self.wall_seconds) or self.wall_seconds < 0:
            raise BoundedSmokeContractError("observed wall time is invalid")
        for field in (
            "input_tokens",
            "cached_input_tokens",
            "output_tokens",
            "model_call_attempts",
            "browser_actions",
            "output_bytes",
        ):
            value = getattr(self, field)
            if type(value) is not int or value < 0:
                raise BoundedSmokeContractError(f"observed {field} is invalid")
        if self.cached_input_tokens > self.input_tokens:
            raise BoundedSmokeContractError("cached input exceeds total input")

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


def validate_pair_budget(usages: Sequence[BudgetUsage]) -> None:
    if tuple(item.condition for item in usages) != CONDITION_ORDER:
        raise BoundedSmokeContractError("budget evidence is not the ordered locked pair")
    for usage in usages:
        if (
            _money_cents_ceiling(usage.cost_usd, context="observed API cost")
            > _numeric_limit("openai_api_cost_cents_per_condition")
            or usage.total_tokens > _numeric_limit("model_tokens_per_condition")
            or usage.model_call_attempts > MODEL_CALL_CAPS[usage.condition]
            or usage.browser_actions > _numeric_limit("browser_actions_each")
            or usage.wall_seconds > _numeric_limit("condition_wall_seconds_each")
            or usage.output_bytes > _numeric_limit("condition_output_bytes_each")
        ):
            raise BoundedSmokeContractError("condition usage exceeds its bound")
    if (
        sum(_money_cents_ceiling(item.cost_usd, context="observed API cost") for item in usages)
        > _numeric_limit("openai_api_cost_cents_aggregate")
        or sum(item.total_tokens for item in usages) > _numeric_limit("model_tokens_aggregate")
        or sum(item.model_call_attempts for item in usages)
        > _numeric_limit("model_call_attempts_aggregate")
        or sum(item.browser_actions for item in usages)
        > _numeric_limit("browser_actions_aggregate")
        or sum(item.wall_seconds for item in usages)
        > _numeric_limit("condition_wall_seconds_aggregate")
        or sum(item.output_bytes for item in usages)
        > _numeric_limit("condition_output_bytes_aggregate")
    ):
        raise BoundedSmokeContractError("pair usage exceeds its aggregate bound")


def validate_provider_preflight(observation: Mapping[str, object]) -> None:
    expected = {
        "schema_version": SCHEMA_VERSION,
        "instance_type": SELECTED_INSTANCE_TYPE,
        "region": SELECTED_REGION,
        "architecture": SELECTED_ARCHITECTURE,
        "image_alias": SELECTED_IMAGE_ALIAS,
        "image_family": SELECTED_IMAGE_FAMILY,
        "image_version": SELECTED_IMAGE_VERSION,
        "ssh_key_name": SELECTED_SSH_KEY_NAME,
        "firewall_baseline_alias": FIREWALL_BASELINE_ALIAS,
        "firewall_semantic_sha256": FIREWALL_BASELINE_SHA256,
        "running_instance_count": 0,
        "price_cents_per_hour": OBSERVED_PRICE_CENTS_PER_HOUR,
        "capacity_available": True,
        "image_offered": True,
        "ssh_key_present": True,
        "manual_termination_path_available": True,
        "user_present_for_billable_operation": True,
        "pagination_present": False,
        "retry_count": 0,
    }
    if set(observation) != set(expected) or any(
        observation.get(key) != value for key, value in expected.items()
    ):
        raise BoundedSmokeContractError("provider preflight is incomplete or drifted")
    projected = math.ceil(_numeric_limit("provider_hard_wall_seconds") / 60) * (
        OBSERVED_PRICE_CENTS_PER_HOUR / 60
    )
    if projected > _numeric_limit("provider_cost_cap_cents"):
        raise BoundedSmokeContractError("projected provider cost exceeds its cap")


def validate_terminal_provider_observation(observation: Mapping[str, object]) -> None:
    expected = {
        "schema_version": SCHEMA_VERSION,
        "owned_instance_match_count": 0,
        "running_owned_instance_count": 0,
        "owned_regional_ruleset_match_count": 0,
        "global_firewall_baseline_alias": FIREWALL_BASELINE_ALIAS,
        "global_firewall_semantic_sha256": FIREWALL_BASELINE_SHA256,
        "provider_terminal_or_absent": True,
        "billing_stopped": True,
        "pagination_present": False,
    }
    if set(observation) != set(expected) or any(
        observation.get(key) != value for key, value in expected.items()
    ):
        raise BoundedSmokeContractError("provider cleanup is not terminal and exact")


def validate_container_cleanup(observation: Mapping[str, object]) -> None:
    required = {
        "schema_version",
        "condition",
        "container_id_sha256",
        "terminal_state_observed",
        "removed",
        "owned_container_residue_count",
        "owned_network_residue_count",
        "owned_volume_residue_count",
        "browser_process_residue_count",
        "evidence_captured_before_removal",
    }
    if set(observation) != required:
        raise BoundedSmokeContractError("container cleanup record has an invalid field set")
    if (
        observation.get("schema_version") != SCHEMA_VERSION
        or observation.get("condition")
        not in (*CONDITION_ORDER, "BROWSER-PREFLIGHT", "MODEL-PREFLIGHT")
        or not isinstance(observation.get("container_id_sha256"), str)
        or _HEX64.fullmatch(str(observation["container_id_sha256"])) is None
        or observation.get("terminal_state_observed") is not True
        or observation.get("removed") is not True
        or observation.get("evidence_captured_before_removal") is not True
        or any(
            observation.get(field) != 0
            for field in (
                "owned_container_residue_count",
                "owned_network_residue_count",
                "owned_volume_residue_count",
                "browser_process_residue_count",
            )
        )
    ):
        raise BoundedSmokeContractError("container cleanup is incomplete")


def _validate_relative_path(value: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if path.is_absolute() or not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        raise BoundedSmokeContractError("artifact path is unsafe")
    return path


def build_evidence_manifest(
    evidence_root: Path,
    *,
    max_total_bytes: int = 268_435_456,
    max_files: int = 4_096,
) -> dict[str, object]:
    root = evidence_root.resolve(strict=True)
    if root.is_symlink() or not root.is_dir():
        raise BoundedSmokeContractError("evidence root is unsafe")
    entries: list[dict[str, object]] = []
    total = 0
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        _validate_relative_path(relative)
        metadata = path.lstat()
        if stat.S_ISDIR(metadata.st_mode):
            continue
        if not stat.S_ISREG(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode):
            raise BoundedSmokeContractError("evidence contains a non-regular entry")
        if path.name == "EVIDENCE_MANIFEST.json":
            continue
        total += metadata.st_size
        if total > max_total_bytes or len(entries) + 1 > max_files:
            raise BoundedSmokeContractError("evidence exceeds its file or byte cap")
        encoded = path.read_bytes()
        if any(pattern.search(encoded) for pattern in _SECRET_SHAPES):
            raise BoundedSmokeContractError("evidence contains a credential-shaped value")
        entries.append(
            {
                "path": relative,
                "bytes": len(encoded),
                "sha256": sha256_bytes(encoded),
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "plan_id": PLAN_ID,
        "host_run_id": HOST_RUN_ID,
        "files": entries,
        "file_count": len(entries),
        "total_bytes": total,
    }


def validate_evidence_manifest(document: Mapping[str, object]) -> None:
    if (
        set(document)
        != {"schema_version", "plan_id", "host_run_id", "files", "file_count", "total_bytes"}
        or document.get("schema_version") != SCHEMA_VERSION
        or document.get("plan_id") != PLAN_ID
        or document.get("host_run_id") != HOST_RUN_ID
    ):
        raise BoundedSmokeContractError("evidence manifest identity drifted")
    files = _sequence(document.get("files"), context="evidence manifest files")
    if document.get("file_count") != len(files) or len(files) > 4_096:
        raise BoundedSmokeContractError("evidence manifest file count drifted")
    paths: set[str] = set()
    total = 0
    for raw in files:
        item = _mapping(raw, context="evidence manifest entry")
        if set(item) != {"path", "bytes", "sha256"}:
            raise BoundedSmokeContractError("evidence manifest entry drifted")
        path = _text(item.get("path"), context="evidence path")
        _validate_relative_path(path)
        if path in paths:
            raise BoundedSmokeContractError("evidence manifest repeats a path")
        paths.add(path)
        size = _integer(item.get("bytes"), context="evidence bytes")
        digest = _text(item.get("sha256"), context="evidence sha256")
        if _HEX64.fullmatch(digest) is None:
            raise BoundedSmokeContractError("evidence hash is invalid")
        total += size
    if total != document.get("total_bytes") or total > _numeric_limit("remote_evidence_bytes"):
        raise BoundedSmokeContractError("evidence manifest total drifted")


def _validate_artifact_bindings(plan: Mapping[str, object], repository_root: Path) -> None:
    implementation = _mapping(plan.get("implementation"), context="implementation")
    artifacts = _sequence(implementation.get("artifacts"), context="implementation artifacts")
    seen: set[str] = set()
    for raw in artifacts:
        item = _mapping(raw, context="implementation artifact")
        if set(item) != {"path", "bytes", "sha256"}:
            raise BoundedSmokeContractError("implementation artifact field set drifted")
        relative = _text(item.get("path"), context="implementation artifact path")
        _validate_relative_path(relative)
        if relative in seen:
            raise BoundedSmokeContractError("implementation artifact is duplicated")
        seen.add(relative)
        path = repository_root / relative
        if path.is_symlink() or not path.is_file():
            raise BoundedSmokeContractError("implementation artifact is unavailable")
        encoded = path.read_bytes()
        if item.get("bytes") != len(encoded) or item.get("sha256") != sha256_bytes(encoded):
            raise BoundedSmokeContractError("implementation artifact identity drifted")


def validate_plan(plan: Mapping[str, object], *, repository_root: Path | None = None) -> None:
    expected_top_level = {
        "$schema",
        "identity",
        "scientific_lock",
        "source_and_runtime",
        "provider_and_pricing",
        "public_metadata",
        "limits",
        "preflights",
        "container_lifecycle",
        "bootstrap_argv_template",
        "provider_observer",
        "storage",
        "conditions",
        "secrets",
        "lambda",
        "hard_blockers",
        "post_launch_stop_conditions",
        "deferred_limitations",
        "steps",
        "implementation",
        "execution_permissions_now",
    }
    if (
        set(plan) != expected_top_level
        or plan.get("$schema") != "../../../schemas/t07-bounded-smoke-plan.schema.json"
    ):
        raise BoundedSmokeContractError("plan top-level contract drifted")
    identity = _mapping(plan.get("identity"), context="plan identity")
    expected_identity = {
        "schema_version": SCHEMA_VERSION,
        "plan_id": PLAN_ID,
        "host_run_id": HOST_RUN_ID,
        "authorization_reference": AUTHORIZATION_PLACEHOLDER,
        "state": TERMINAL_STATE,
        "authorized": False,
        "branch": BRANCH,
        "fork_commit": FORK_COMMIT,
        "parent_branch": PARENT_BRANCH,
        "frozen_tag": FROZEN_TAG,
    }
    if set(identity) != set(expected_identity) or any(
        identity.get(key) != value for key, value in expected_identity.items()
    ):
        raise BoundedSmokeContractError("plan identity or authorization state drifted")

    science = _mapping(plan.get("scientific_lock"), context="scientific lock")
    expected_science = {
        "experiment_id": EXPERIMENT_ID,
        "profile_plan_id": SCIENTIFIC_PROFILE_ID,
        "pair_id": PAIR_ID,
        "condition_order": list(CONDITION_ORDER),
        "task_kind": "open-ended-query",
        "task_query": "go to google flights",
        "model": MODEL,
        "model_roles": {role: MODEL for role in MODEL_ROLES},
        "reproduction_level": "directional-reproduction",
        "interpretation_allowed": False,
        "pilot_authorized": False,
        "training": False,
    }
    if science != expected_science:
        raise BoundedSmokeContractError("scientific lock drifted")

    source = _mapping(plan.get("source_and_runtime"), context="source and runtime")
    expected_source = {
        "upstream_commit": UPSTREAM_COMMIT,
        "upstream_tree": UPSTREAM_TREE,
        "uv_lock_sha256": UPSTREAM_LOCK_SHA256,
        "routing_patch_sha256": ROUTING_PATCH_SHA256,
        "runtime_adaptation_sha256": RUNTIME_ADAPTATION_SHA256,
        "routing_sha256": ROUTING_SHA256,
        "base_image": BASE_IMAGE_INDEX,
        "base_image_index_digest": BASE_IMAGE_INDEX_DIGEST,
        "base_image_amd64_manifest": BASE_IMAGE_AMD64_MANIFEST,
        "base_image_amd64_config": BASE_IMAGE_AMD64_CONFIG,
        "base_image_compressed_bytes": BASE_IMAGE_COMPRESSED_BYTES,
        "platform": "linux/amd64",
        "python": "3.10",
        "uv_version": UV_VERSION,
        "uv_wheel": UV_WHEEL,
        "uv_wheel_url": UV_WHEEL_URL,
        "uv_wheel_bytes": UV_WHEEL_BYTES,
        "uv_wheel_sha256": UV_WHEEL_SHA256,
        "dependency_command": ["uv", "sync", "--frozen", "--extra", "eval", "--python", "3.10"],
        "playwright": PLAYWRIGHT_VERSION,
        "chromium_revision": CHROMIUM_REVISION,
        "chromium_version": CHROMIUM_VERSION,
        "browser_download_command": None,
    }
    if source != expected_source:
        raise BoundedSmokeContractError("source or runtime identity drifted")

    metadata = _sequence(plan.get("public_metadata"), context="public metadata")
    if metadata != list(PUBLIC_METADATA):
        raise BoundedSmokeContractError("public metadata identity drifted")

    preflights = _mapping(plan.get("preflights"), context="preflights")
    expected_preflights = {
        "browser": {
            "run_id": BROWSER_PREFLIGHT_RUN_ID,
            "network": "none",
            "browser_actions": 1,
            "model_calls": 0,
            "container_create_argv_template": list(browser_preflight_create_argv()),
            "container_create_template_sha256": template_sha256(browser_preflight_create_argv()),
        },
        "model": {
            "run_id": MODEL_PREFLIGHT_RUN_ID,
            "method": "GET",
            "url": f"{API_BASE_URL}models/{MODEL}",
            "model_calls": 0,
            "metadata_gets": 1,
            "container_create_argv_template": list(model_preflight_create_argv()),
            "container_create_template_sha256": template_sha256(model_preflight_create_argv()),
        },
    }
    if preflights != expected_preflights:
        raise BoundedSmokeContractError("preflight command contract drifted")

    lifecycle = _mapping(plan.get("container_lifecycle"), context="container lifecycle")
    if lifecycle != lifecycle_argv_templates():
        raise BoundedSmokeContractError("container lifecycle command contract drifted")
    bootstrap = _sequence(plan.get("bootstrap_argv_template"), context="bootstrap argv")
    if tuple(bootstrap) != bootstrap_argv_template():
        raise BoundedSmokeContractError("bootstrap command contract drifted")
    if _mapping(plan.get("provider_observer"), context="provider observer") != (
        provider_observer_contract()
    ):
        raise BoundedSmokeContractError("provider observer contract drifted")
    if _mapping(plan.get("storage"), context="storage") != storage_contract():
        raise BoundedSmokeContractError("storage contract drifted")

    routing = _mapping(plan.get("provider_and_pricing"), context="provider and pricing")
    if (
        routing.get("provider") != PROVIDER
        or routing.get("api_base_url") != API_BASE_URL
        or routing.get("model") != MODEL
        or routing.get("standard_input_usd_per_million") != 2.5
        or routing.get("standard_cached_input_usd_per_million") != 1.25
        or routing.get("standard_output_usd_per_million") != 10.0
        or routing.get("cap_method") != "all-model-tokens-priced-at-output-rate"
        or routing.get("service_tier") != "standard"
    ):
        raise BoundedSmokeContractError("provider or pricing contract drifted")

    caps = _mapping(plan.get("limits"), context="limits")
    if caps != LIMITS:
        raise BoundedSmokeContractError("numeric limits drifted")

    conditions = _sequence(plan.get("conditions"), context="conditions")
    if len(conditions) != 2:
        raise BoundedSmokeContractError("plan must contain exactly two conditions")
    commands: dict[str, Sequence[str]] = {}
    for index, raw in enumerate(conditions):
        item = _mapping(raw, context="condition")
        condition = CONDITION_ORDER[index]
        argv = _sequence(item.get("container_create_argv_template"), context="container argv")
        inner = _sequence(item.get("inner_argv_template"), context="inner argv")
        expected = {
            "condition": condition,
            "run_id": RUN_IDS[condition],
            "attempt": 1,
            "order_index": index + 1,
            "mode": MODE_VALUES[condition],
            "container_create_argv_template": list(container_create_argv(condition)),
            "container_create_template_sha256": template_sha256(container_create_argv(condition)),
            "inner_argv_template": list(condition_inner_argv(condition)),
            "inner_argv_template_sha256": template_sha256(condition_inner_argv(condition)),
            "model_call_attempts": MODEL_CALL_CAPS[condition],
            "model_tokens": 200_000,
            "api_cost_usd": 2.0,
            "wall_seconds": 120,
            "browser_actions": 1,
            "output_bytes": 104_857_600,
        }
        if item != expected:
            raise BoundedSmokeContractError("condition plan drifted")
        commands[condition] = tuple(_text(value, context="container argv item") for value in argv)
        if tuple(inner) != condition_inner_argv(condition):
            raise BoundedSmokeContractError("inner command drifted")
    assert_pair_command_contract(commands["SIRA-REACTIVE"], commands["SIRA-SIMULATIVE"])

    secrets = _mapping(plan.get("secrets"), context="secret contract")
    if secrets != {
        "provider_observer_variable": "LAMBDA_API_KEY",
        "workload_variable": "SIRA_API_KEY",
        "workload_file": "/run/secrets/sira_api_key",
        "forbidden_fallback": "OPENAI_API_KEY",
        "value_in_argv": False,
        "value_in_environment_list": False,
        "value_in_image": False,
        "value_in_labels": False,
        "value_in_evidence": False,
    }:
        raise BoundedSmokeContractError("secret contract drifted")

    provider = _mapping(plan.get("lambda"), context="Lambda contract")
    if (
        provider.get("product") != "Lambda On-Demand Cloud"
        or provider.get("api_base_url") != "https://cloud.lambda.ai"
        or provider.get("instance_type") != SELECTED_INSTANCE_TYPE
        or provider.get("region") != SELECTED_REGION
        or provider.get("architecture") != SELECTED_ARCHITECTURE
        or provider.get("image_alias") != SELECTED_IMAGE_ALIAS
        or provider.get("image_family") != SELECTED_IMAGE_FAMILY
        or provider.get("image_version") != SELECTED_IMAGE_VERSION
        or provider.get("ssh_key_name") != SELECTED_SSH_KEY_NAME
        or provider.get("ssh_use") is not False
        or provider.get("persistent_filesystems") != 0
        or provider.get("observed_price_cents_per_hour") != OBSERVED_PRICE_CENTS_PER_HOUR
        or provider.get("global_firewall_baseline_alias") != FIREWALL_BASELINE_ALIAS
        or provider.get("global_firewall_semantic_sha256") != FIREWALL_BASELINE_SHA256
        or provider.get("mutations_actor") != "user"
        or provider.get("observer_operations") != "GET-only"
    ):
        raise BoundedSmokeContractError("Lambda resource contract drifted")

    blockers = _sequence(plan.get("hard_blockers"), context="hard blockers")
    post_launch = _sequence(
        plan.get("post_launch_stop_conditions"), context="post-launch stop conditions"
    )
    limitations = _sequence(plan.get("deferred_limitations"), context="deferred limitations")
    if (
        blockers != list(HARD_BLOCKERS)
        or post_launch != list(POST_LAUNCH_STOP_CONDITIONS)
        or limitations != list(DEFERRED_LIMITATIONS)
    ):
        raise BoundedSmokeContractError("blocker or limitation register drifted")

    steps = _sequence(plan.get("steps"), context="steps")
    expected_steps = [
        {"ordinal": ordinal, "actor": actor, "action": action, "stop_on_failure": True}
        for ordinal, actor, action in STEP_CONTRACT
    ]
    if (
        not steps
        or steps != expected_steps
        or [item.get("ordinal") for item in map(lambda x: _mapping(x, context="step"), steps)]
        != list(range(1, len(steps) + 1))
    ):
        raise BoundedSmokeContractError("manual step order drifted")
    if any(
        _mapping(raw, context="step").get("actor")
        not in {"observer", "user", "bootstrap", "local-verifier"}
        for raw in steps
    ):
        raise BoundedSmokeContractError("manual step actor drifted")

    implementation = _mapping(plan.get("implementation"), context="implementation")
    reviewed_commit = implementation.get("reviewed_commit")
    artifacts = _sequence(implementation.get("artifacts"), context="implementation artifacts")
    artifact_paths = {
        _text(_mapping(item, context="implementation artifact").get("path"), context="path")
        for item in artifacts
    }
    if (
        set(implementation) != {"reviewed_commit", "artifacts"}
        or not isinstance(reviewed_commit, str)
        or _HEX40.fullmatch(reviewed_commit) is None
        or artifact_paths != REQUIRED_IMPLEMENTATION_ARTIFACTS
    ):
        raise BoundedSmokeContractError("implementation binding is incomplete or drifted")

    if plan.get("execution_permissions_now") != {
        "lambda_account_requests": 0,
        "openai_account_requests": 0,
        "cloud_mutations": 0,
        "paid_compute": False,
        "jupyter": False,
        "containers": False,
        "browser": False,
        "sira": False,
        "scientific_execution": False,
    }:
        raise BoundedSmokeContractError("current execution permissions are not all closed")

    if repository_root is not None:
        for relative, digest in SCIENTIFIC_HASHES.items():
            if sha256_file(repository_root / relative) != digest:
                raise BoundedSmokeContractError("locked scientific file drifted")
        _validate_artifact_bindings(plan, repository_root)


__all__ = [
    "AUTHORIZATION_PLACEHOLDER",
    "BRANCH",
    "BROWSER_PREFLIGHT_RUN_ID",
    "CONDITION_ORDER",
    "FORK_COMMIT",
    "HOST_RUN_ID",
    "LIMITS",
    "MODEL",
    "MODEL_PREFLIGHT_RUN_ID",
    "PLAN_ID",
    "REACTIVE_RUN_ID",
    "SIMULATIVE_RUN_ID",
    "TERMINAL_STATE",
    "BoundedSmokeContractError",
    "BudgetUsage",
    "assert_pair_command_contract",
    "bootstrap_argv_template",
    "browser_preflight_create_argv",
    "build_evidence_manifest",
    "canonical_json_bytes",
    "condition_inner_argv",
    "container_create_argv",
    "lifecycle_argv_templates",
    "local_supervisor_argv_templates",
    "materialize_argv",
    "model_preflight_create_argv",
    "provider_observer_contract",
    "read_json_file",
    "sha256_bytes",
    "sha256_file",
    "storage_contract",
    "template_sha256",
    "validate_container_cleanup",
    "validate_evidence_manifest",
    "validate_pair_budget",
    "validate_plan",
    "validate_provider_preflight",
    "validate_terminal_provider_observation",
]
