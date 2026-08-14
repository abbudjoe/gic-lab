"""Offline contracts and runtime guards for the T09 SiRA calibration pilot.

This module has no cloud, browser, or model-provider client.  Its command and
budget helpers are inert until a separately authorized supervisor passes the
frozen contract to the T07 pragmatic runtime adaptation.
"""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import math
import os
import re
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from types import ModuleType
from typing import Any, Final, Literal, cast

from giclab.harness.sira_gate_a import (
    ProviderBudgetCaps,
    ProviderBudgetUsage,
)

PLAN_ID: Final = "PLAN-EXP0001-PILOT-V5"
EXPERIMENT_ID: Final = "EXP-0001"
SIRA_COMMIT: Final = "93fb8d72de71f9a4a13419670adeb34d93cf7acd"
MODEL_REVISION: Final = "gpt-4o-2024-11-20"
SERVICE_TIER: Final = "default"
DATASET_REVISION: Final = "76ad1feb689b754bfe4e5e24d3ea371b647efa67"
DATASET_SHA256: Final = "359300b029c6891567816f351bf8786e9b018d7af8a1a44b7da9ba5ef4651288"
EVALUATOR_SHA256: Final = "2f99ec6ca40a5d5b49beea61c71d55a85652697b07f92a1c2aaefe85e727ab79"
TASK_IDS: Final = ("7dcbbbdc7f1120cd", "2120afba8009bad3")
TASK_ROW_SHA256S: Final = (
    "cc5c3fdeea2c1f58b6160175bd3104dbea40c290ea8b390d29413e6410d97e15",
    "5f5a8ad5353b839def2ffc968c36c4314bb830f11f10268f410faa37690bc129",
)
TASK_TEXT_SHA256S: Final = (
    "153a4f251fbeb29bee8e5ca4626e6db14426063728b0d5cfa7eed3a9a230992b",
    "9b2b443898959b28c7408ed1ff56ebd332c9e7f2142657c11c7d09aa507ba66e",
)
TASK_REFERENCE_SHA256S: Final = (
    "fc40734fa183e839b56a7c89b16faa5900865cbee7a4210fcb251a99176f98de",
    "2ee9d892e24441d5f5bbf31b7616c1ade5977af26d22e4020f92a162fa23becb",
)
ATTEMPT_ORDER: Final = (
    "RUN-T09-TASK-A-REACTIVE-0003",
    "RUN-T09-TASK-A-SIMULATIVE-0003",
    "RUN-T09-TASK-B-SIMULATIVE-0003",
    "RUN-T09-TASK-B-REACTIVE-0003",
)
EVALUATOR_RUN_IDS: Final = (
    "RUN-T09-EVAL-TASK-A-REACTIVE-0003",
    "RUN-T09-EVAL-TASK-A-SIMULATIVE-0003",
    "RUN-T09-EVAL-TASK-B-SIMULATIVE-0003",
    "RUN-T09-EVAL-TASK-B-REACTIVE-0003",
)
RUNTIME_QUALIFICATION_ID: Final = "QUAL-T09-PILOT-V5-IMAGE-0001"
FROZEN_RUN_MANIFEST_ID: Final = "RUN-MANIFEST-EXP0001-PILOT-V5-0003"
HISTORICAL_IMAGE_ID: Final = (
    "sha256:035edf61718e84a8156f4f0f7817b134b0ce31488d3f0b50bbfba2b4a30cc61c"
)

_HEX64 = re.compile(r"^[a-f0-9]{64}$")
_SAFE_EVENT_ID = re.compile(r"^[A-Z0-9][A-Z0-9._-]{2,127}$")


class T09PilotError(ValueError):
    """Raised when frozen T09 pilot material violates its machine contract."""


class T09BudgetExceeded(RuntimeError):
    """Raised before the next empirical operation would exceed a hard cap."""


@dataclass(frozen=True, slots=True)
class CampaignLifecycleLimits:
    """One finite, actual-time provider campaign shared by every pilot phase."""

    campaign_provider_wall_seconds: int
    normal_cleanup_reserve_seconds: int
    provider_termination_cutoff_seconds: int
    post_condition_evaluator_evidence_seconds: int
    termination_dispatch_margin_seconds: int
    max_lambda_instances: int
    max_launch_count: int
    persistent_filesystems: int

    def __post_init__(self) -> None:
        values = (
            self.campaign_provider_wall_seconds,
            self.normal_cleanup_reserve_seconds,
            self.provider_termination_cutoff_seconds,
            self.post_condition_evaluator_evidence_seconds,
            self.termination_dispatch_margin_seconds,
            self.max_lambda_instances,
            self.max_launch_count,
            self.persistent_filesystems,
        )
        if any(type(value) is not int or value < 0 for value in values):
            raise T09PilotError("campaign lifecycle limits must be non-negative integers")
        if self.campaign_provider_wall_seconds != 14_400:
            raise T09PilotError("campaign provider wall must remain 14,400 seconds")
        if self.normal_cleanup_reserve_seconds != 900:
            raise T09PilotError("normal cleanup reserve must remain 900 seconds")
        if self.post_condition_evaluator_evidence_seconds != 600:
            raise T09PilotError("post-condition evaluator/evidence handoff must remain 600 seconds")
        if self.termination_dispatch_margin_seconds != 60:
            raise T09PilotError("provider termination dispatch margin must remain 60 seconds")
        if (
            self.provider_termination_cutoff_seconds
            != self.campaign_provider_wall_seconds - self.normal_cleanup_reserve_seconds
        ):
            raise T09PilotError("provider termination cutoff must preserve the cleanup reserve")
        if (
            self.max_lambda_instances != 1
            or self.max_launch_count != 2
            or self.persistent_filesystems != 0
        ):
            raise T09PilotError(
                "campaign requires one simultaneous instance, at most two pre-empirical "
                "launches, and no filesystem"
            )

    def elapsed_seconds(self, *, billable_started_at: float, now: float) -> float:
        elapsed = now - billable_started_at
        if not math.isfinite(elapsed) or elapsed < 0:
            raise T09PilotError("campaign clock is unavailable or in the future")
        return elapsed

    def remaining_seconds(self, *, billable_started_at: float, now: float) -> float:
        return max(
            0.0,
            self.campaign_provider_wall_seconds
            - self.elapsed_seconds(billable_started_at=billable_started_at, now=now),
        )

    def required_attempt_seconds(self, *, attempt_hard_wall_seconds: int) -> int:
        """Return the one source-of-truth admission envelope for an attempt."""

        if type(attempt_hard_wall_seconds) is not int or attempt_hard_wall_seconds <= 0:
            raise T09PilotError("attempt hard wall must be a positive integer")
        return (
            attempt_hard_wall_seconds
            + self.post_condition_evaluator_evidence_seconds
            + self.termination_dispatch_margin_seconds
            + self.normal_cleanup_reserve_seconds
        )

    def admit_remaining(
        self,
        *,
        remaining_campaign_seconds: float,
        attempt_hard_wall_seconds: int,
    ) -> bool:
        """Apply the typed admission rule to an already-derived remaining wall."""

        if not math.isfinite(remaining_campaign_seconds) or remaining_campaign_seconds < 0:
            return False
        return remaining_campaign_seconds >= self.required_attempt_seconds(
            attempt_hard_wall_seconds=attempt_hard_wall_seconds
        )

    def admit_attempt(
        self,
        *,
        billable_started_at: float,
        now: float,
        attempt_hard_wall_seconds: int,
    ) -> bool:
        return self.admit_remaining(
            remaining_campaign_seconds=self.remaining_seconds(
                billable_started_at=billable_started_at,
                now=now,
            ),
            attempt_hard_wall_seconds=attempt_hard_wall_seconds,
        )

    def termination_due(self, *, billable_started_at: float, now: float) -> bool:
        return (
            self.elapsed_seconds(billable_started_at=billable_started_at, now=now)
            >= self.provider_termination_cutoff_seconds
        )


def file_sha256(path: Path) -> str:
    """Hash an exact retained file without following a non-file surface."""

    resolved = path.resolve(strict=True)
    if not resolved.is_file():
        raise T09PilotError(f"expected a regular file: {path}")
    digest = hashlib.sha256()
    with resolved.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_sha256(value: object) -> str:
    """Hash JSON-compatible data using the pilot canonicalization rule."""

    encoded = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _strict_object(value: object, *, context: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise T09PilotError(f"{context} must be a string-keyed object")
    return cast(dict[str, object], value)


def load_json_object(path: Path, *, context: str) -> dict[str, object]:
    try:
        value: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise T09PilotError(f"{context} is not readable canonical JSON") from exc
    return _strict_object(value, context=context)


@dataclass(frozen=True, slots=True)
class RuntimeQualification:
    """The source-derived pre-entry binding for the one accepted V5 image."""

    manifest_id: str
    qualification_id: str
    clean_package_commit: str
    replacement_image_id: str
    historical_image_id: str
    build_context_manifest_sha256: str
    package_manifest_sha256: str
    chromium_executable_sha256: str
    patched_upstream_runner_sha256: str
    python_interpreter_path: str
    python_interpreter_sha256: str
    evaluator_overlay_manifest_sha256: str
    evaluator_overlay_entries_sha256: str
    evaluator_overlay_packages_sha256: str
    model_metadata_request_count: int
    model_task_request_count: int
    task_browser_action_count: int
    build_count: int
    qualification_count: int
    empirical_entry_crossed: bool

    @classmethod
    def from_document(cls, value: object) -> RuntimeQualification:
        document = _strict_object(value, context="frozen runtime qualification")
        result = cls(
            manifest_id=_required_string(document.get("manifest_id"), context="frozen manifest ID"),
            qualification_id=_required_string(
                document.get("qualification_id"), context="qualification ID"
            ),
            clean_package_commit=_required_string(
                document.get("clean_package_commit"), context="clean package commit"
            ),
            replacement_image_id=_required_string(
                document.get("replacement_image_id"), context="replacement image ID"
            ),
            historical_image_id=_required_string(
                document.get("historical_image_id"), context="historical image ID"
            ),
            build_context_manifest_sha256=_required_string(
                document.get("build_context_manifest_sha256"),
                context="build-context manifest hash",
            ),
            package_manifest_sha256=_required_string(
                document.get("package_manifest_sha256"), context="package manifest hash"
            ),
            chromium_executable_sha256=_required_string(
                document.get("chromium_executable_sha256"), context="Chromium hash"
            ),
            patched_upstream_runner_sha256=_required_string(
                document.get("patched_upstream_runner_sha256"),
                context="patched upstream runner hash",
            ),
            python_interpreter_path=_required_string(
                document.get("python_interpreter_path"),
                context="Python interpreter path",
            ),
            python_interpreter_sha256=_required_string(
                document.get("python_interpreter_sha256"),
                context="Python interpreter hash",
            ),
            evaluator_overlay_manifest_sha256=_required_string(
                document.get("evaluator_overlay_manifest_sha256"),
                context="evaluator overlay manifest hash",
            ),
            evaluator_overlay_entries_sha256=_required_string(
                document.get("evaluator_overlay_entries_sha256"),
                context="evaluator overlay entries hash",
            ),
            evaluator_overlay_packages_sha256=_required_string(
                document.get("evaluator_overlay_packages_sha256"),
                context="evaluator overlay packages hash",
            ),
            model_metadata_request_count=_required_int(
                document.get("model_metadata_request_count"),
                context="model metadata request count",
            ),
            model_task_request_count=_required_int(
                document.get("model_task_request_count"), context="model task request count"
            ),
            task_browser_action_count=_required_int(
                document.get("task_browser_action_count"),
                context="task browser action count",
            ),
            build_count=_required_int(document.get("build_count"), context="build count"),
            qualification_count=_required_int(
                document.get("qualification_count"), context="qualification count"
            ),
            empirical_entry_crossed=document.get("empirical_entry_crossed") is True,
        )
        hashes = (
            result.build_context_manifest_sha256,
            result.package_manifest_sha256,
            result.chromium_executable_sha256,
            result.patched_upstream_runner_sha256,
            result.python_interpreter_sha256,
            result.evaluator_overlay_manifest_sha256,
            result.evaluator_overlay_entries_sha256,
            result.evaluator_overlay_packages_sha256,
        )
        if (
            document.get("schema_version") != "0.1.0"
            or document.get("plan_id") != PLAN_ID
            or result.manifest_id != FROZEN_RUN_MANIFEST_ID
            or result.qualification_id != RUNTIME_QUALIFICATION_ID
            or re.fullmatch(r"[a-f0-9]{40}", result.clean_package_commit) is None
            or re.fullmatch(r"sha256:[a-f0-9]{64}", result.replacement_image_id) is None
            or result.historical_image_id != HISTORICAL_IMAGE_ID
            or result.python_interpreter_path != "/opt/sira/.venv/bin/python"
            or any(_HEX64.fullmatch(item) is None for item in hashes)
            or result.model_metadata_request_count != 1
            or result.model_task_request_count != 0
            or result.task_browser_action_count != 0
            or result.build_count != 1
            or result.qualification_count != 1
            or document.get("empirical_entry_crossed") is not False
            or document.get("post_entry_code_science_image_freeze") is not True
        ):
            raise T09PilotError("frozen runtime qualification contract drifted")
        return result


@dataclass(frozen=True, slots=True)
class AttemptBinding:
    """One immutable condition attempt from the T09 execution contract."""

    run_id: str
    pair_id: str
    task_id: str
    task_index: int
    condition: Literal["reactive", "simulative"]
    order_index: int
    output_root: str
    raw_output_root: str
    finalized_output_root: str
    condition_plan_path: str
    condition_plan_sha256: str
    protocol_sha256: str
    config_sha256: str
    environment_sha256: str
    giclab_commit: str
    upstream_argv: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.run_id not in ATTEMPT_ORDER:
            raise T09PilotError("attempt run ID is not in the frozen order")
        if self.task_id not in TASK_IDS or self.task_index not in (0, 1):
            raise T09PilotError("attempt task binding is not frozen")
        if self.condition not in ("reactive", "simulative"):
            raise T09PilotError("attempt condition is invalid")
        if self.order_index not in (1, 2):
            raise T09PilotError("attempt order index must be one or two")
        if (
            not self.output_root
            or Path(self.output_root).is_absolute()
            or ".." in Path(self.output_root).parts
        ):
            raise T09PilotError("attempt output root must be repository relative")
        if (
            self.raw_output_root != f"{self.output_root}/raw"
            or self.finalized_output_root != f"{self.output_root}/finalized"
        ):
            raise T09PilotError("attempt raw/finalized roots drifted from its owned root")
        if (
            not self.condition_plan_path
            or Path(self.condition_plan_path).is_absolute()
            or ".." in Path(self.condition_plan_path).parts
            or _HEX64.fullmatch(self.condition_plan_sha256) is None
        ):
            raise T09PilotError("attempt condition-plan binding is invalid")
        if any(
            _HEX64.fullmatch(value) is None
            for value in (self.protocol_sha256, self.config_sha256, self.environment_sha256)
        ):
            raise T09PilotError("attempt common scientific/runtime binding is invalid")
        if (
            self.giclab_commit != "unknown"
            and re.fullmatch(r"[a-f0-9]{40}", self.giclab_commit) is None
        ):
            raise T09PilotError("attempt GIC Lab commit binding is invalid")
        if not self.upstream_argv:
            raise T09PilotError("attempt upstream argv cannot be empty")


@dataclass(frozen=True, slots=True)
class RuntimeLimits:
    """Hard and expected resource limits locked before empirical entry."""

    expected_browser_actions_per_attempt: int
    max_browser_actions_per_attempt: int
    max_model_calls_per_attempt: int
    max_model_tokens_per_attempt: int
    max_openai_cost_usd_per_attempt: float
    max_condition_wall_seconds: int
    max_pair_wall_seconds: int
    max_total_wall_seconds: int
    max_output_bytes_per_attempt: int
    max_disk_bytes: int
    max_lambda_duration_seconds: int
    max_lambda_cost_usd: float
    max_attempts: int
    max_retries_after_empirical_entry: int

    def __post_init__(self) -> None:
        integers = (
            self.expected_browser_actions_per_attempt,
            self.max_browser_actions_per_attempt,
            self.max_model_calls_per_attempt,
            self.max_model_tokens_per_attempt,
            self.max_condition_wall_seconds,
            self.max_pair_wall_seconds,
            self.max_total_wall_seconds,
            self.max_output_bytes_per_attempt,
            self.max_disk_bytes,
            self.max_lambda_duration_seconds,
            self.max_attempts,
            self.max_retries_after_empirical_entry,
        )
        if any(type(value) is not int or value < 0 for value in integers):
            raise T09PilotError("runtime integer limits must be non-negative integers")
        if self.expected_browser_actions_per_attempt > self.max_browser_actions_per_attempt:
            raise T09PilotError("expected browser actions exceed the hard maximum")
        if self.max_pair_wall_seconds != 2 * self.max_condition_wall_seconds:
            raise T09PilotError("pair wall cap must equal two condition caps")
        if self.max_total_wall_seconds != 2 * self.max_pair_wall_seconds:
            raise T09PilotError("total wall cap must equal two pair caps")
        if self.max_lambda_duration_seconds != self.max_total_wall_seconds:
            raise T09PilotError("Lambda and total wall caps must be identical")
        if self.max_attempts != 4 or self.max_retries_after_empirical_entry != 0:
            raise T09PilotError("the calibration pilot requires four attempts and zero retry")
        for value in (self.max_openai_cost_usd_per_attempt, self.max_lambda_cost_usd):
            if not math.isfinite(value) or value < 0:
                raise T09PilotError("runtime monetary limits must be finite and non-negative")

    def condition_provider_caps(self) -> ProviderBudgetCaps:
        return ProviderBudgetCaps(
            max_cost_usd=self.max_openai_cost_usd_per_attempt,
            max_input_tokens=self.max_model_tokens_per_attempt,
            max_cached_input_tokens=self.max_model_tokens_per_attempt,
            max_output_tokens=self.max_model_tokens_per_attempt,
            max_total_tokens=self.max_model_tokens_per_attempt,
            max_model_call_attempts=self.max_model_calls_per_attempt,
            max_wall_seconds=self.max_condition_wall_seconds,
            max_browser_actions=self.max_browser_actions_per_attempt,
            max_output_bytes=self.max_output_bytes_per_attempt,
        )

    def aggregate_provider_caps(self) -> ProviderBudgetCaps:
        multiplier = self.max_attempts
        condition = self.condition_provider_caps()
        return replace(
            condition,
            max_cost_usd=condition.max_cost_usd * multiplier,
            max_input_tokens=condition.max_input_tokens * multiplier,
            max_cached_input_tokens=condition.max_cached_input_tokens * multiplier,
            max_output_tokens=condition.max_output_tokens * multiplier,
            max_total_tokens=condition.max_total_tokens * multiplier,
            max_model_call_attempts=condition.max_model_call_attempts * multiplier,
            max_wall_seconds=self.max_total_wall_seconds,
            max_browser_actions=condition.max_browser_actions * multiplier,
            max_output_bytes=condition.max_output_bytes * multiplier,
        )


@dataclass(frozen=True, slots=True)
class PilotExecutionContract:
    """Validated subset of the immutable machine execution contract."""

    path: Path
    sha256: str
    limits: RuntimeLimits
    attempts: tuple[AttemptBinding, ...]
    dataset_contract_path: str
    dataset_contract_sha256: str
    evaluator_contract_path: str
    evaluator_contract_sha256: str
    action_timeout_seconds: int
    first_pair_checkpoint_required: bool
    campaign: CampaignLifecycleLimits

    def attempt(self, run_id: str) -> AttemptBinding:
        matches = [item for item in self.attempts if item.run_id == run_id]
        if len(matches) != 1:
            raise T09PilotError("attempt ID is absent or duplicated in the contract")
        return matches[0]


def _required_int(value: object, *, context: str) -> int:
    if type(value) is not int:
        raise T09PilotError(f"{context} must be an integer")
    return value


def _required_number(value: object, *, context: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise T09PilotError(f"{context} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise T09PilotError(f"{context} must be finite")
    return result


def _required_string(value: object, *, context: str) -> str:
    if not isinstance(value, str) or not value:
        raise T09PilotError(f"{context} must be a nonempty string")
    return value


def load_execution_contract(path: Path, *, expected_sha256: str) -> PilotExecutionContract:
    """Load and semantically validate the exact T09 execution contract."""

    if _HEX64.fullmatch(expected_sha256) is None or file_sha256(path) != expected_sha256:
        raise T09PilotError("execution contract hash does not match")
    document = load_json_object(path, context="T09 execution contract")
    expected_identity = {
        "schema_version": "0.3.0",
        "plan_id": PLAN_ID,
        "experiment_id": EXPERIMENT_ID,
        "sira_commit": SIRA_COMMIT,
        "model_revision": MODEL_REVISION,
        "service_tier": SERVICE_TIER,
        "authorized": False,
    }
    for field, expected in expected_identity.items():
        if document.get(field) != expected:
            raise T09PilotError(f"execution contract {field} drifted")

    raw_limits = _strict_object(document.get("runtime_limits"), context="runtime limits")
    limits = RuntimeLimits(
        expected_browser_actions_per_attempt=_required_int(
            raw_limits.get("expected_browser_actions_per_attempt"),
            context="expected browser actions",
        ),
        max_browser_actions_per_attempt=_required_int(
            raw_limits.get("max_browser_actions_per_attempt"),
            context="browser-action cap",
        ),
        max_model_calls_per_attempt=_required_int(
            raw_limits.get("max_model_calls_per_attempt"), context="model-call cap"
        ),
        max_model_tokens_per_attempt=_required_int(
            raw_limits.get("max_model_tokens_per_attempt"), context="token cap"
        ),
        max_openai_cost_usd_per_attempt=_required_number(
            raw_limits.get("max_openai_cost_usd_per_attempt"), context="OpenAI cost cap"
        ),
        max_condition_wall_seconds=_required_int(
            raw_limits.get("max_condition_wall_seconds"), context="condition wall cap"
        ),
        max_pair_wall_seconds=_required_int(
            raw_limits.get("max_pair_wall_seconds"), context="pair wall cap"
        ),
        max_total_wall_seconds=_required_int(
            raw_limits.get("max_total_wall_seconds"), context="total wall cap"
        ),
        max_output_bytes_per_attempt=_required_int(
            raw_limits.get("max_output_bytes_per_attempt"), context="output-byte cap"
        ),
        max_disk_bytes=_required_int(raw_limits.get("max_disk_bytes"), context="disk cap"),
        max_lambda_duration_seconds=_required_int(
            raw_limits.get("max_lambda_duration_seconds"), context="Lambda-duration cap"
        ),
        max_lambda_cost_usd=_required_number(
            raw_limits.get("max_lambda_cost_usd"), context="Lambda-cost cap"
        ),
        max_attempts=_required_int(raw_limits.get("max_attempts"), context="attempt cap"),
        max_retries_after_empirical_entry=_required_int(
            raw_limits.get("max_retries_after_empirical_entry"), context="retry cap"
        ),
    )
    raw_attempts = document.get("attempts")
    if not isinstance(raw_attempts, list):
        raise T09PilotError("execution attempts must be a list")
    attempts: list[AttemptBinding] = []
    for raw in raw_attempts:
        item = _strict_object(raw, context="attempt")
        argv = item.get("upstream_argv")
        if not isinstance(argv, list) or not all(isinstance(arg, str) for arg in argv):
            raise T09PilotError("attempt upstream argv must be a string list")
        condition = _required_string(item.get("condition"), context="attempt condition")
        if condition not in {"reactive", "simulative"}:
            raise T09PilotError("attempt condition is not reactive or simulative")
        attempts.append(
            AttemptBinding(
                run_id=_required_string(item.get("run_id"), context="attempt run ID"),
                pair_id=_required_string(item.get("pair_id"), context="attempt pair ID"),
                task_id=_required_string(item.get("task_id"), context="attempt task ID"),
                task_index=_required_int(item.get("task_index"), context="attempt task index"),
                condition=cast(Literal["reactive", "simulative"], condition),
                order_index=_required_int(item.get("order_index"), context="attempt order"),
                output_root=_required_string(item.get("output_root"), context="output root"),
                raw_output_root=_required_string(
                    item.get("raw_output_root"), context="raw output root"
                ),
                finalized_output_root=_required_string(
                    item.get("finalized_output_root"), context="finalized output root"
                ),
                condition_plan_path=_required_string(
                    item.get("condition_plan_path"), context="condition plan path"
                ),
                condition_plan_sha256=_required_string(
                    item.get("condition_plan_sha256"), context="condition plan hash"
                ),
                protocol_sha256=_required_string(
                    item.get("protocol_sha256"), context="protocol hash"
                ),
                config_sha256=_required_string(item.get("config_sha256"), context="config hash"),
                environment_sha256=_required_string(
                    item.get("environment_sha256"), context="environment hash"
                ),
                giclab_commit=_required_string(item.get("giclab_commit"), context="GIC Lab commit"),
                upstream_argv=tuple(cast(list[str], argv)),
            )
        )
    if tuple(item.run_id for item in attempts) != ATTEMPT_ORDER:
        raise T09PilotError("attempt order drifted")
    if len({(item.task_id, item.condition) for item in attempts}) != 4:
        raise T09PilotError("attempt task-condition bindings are not bijective")

    bindings = _strict_object(document.get("contract_bindings"), context="contract bindings")
    dataset = _strict_object(bindings.get("dataset"), context="dataset binding")
    evaluator = _strict_object(bindings.get("evaluator"), context="evaluator binding")
    action_timeout = _required_int(
        raw_limits.get("action_timeout_seconds"), context="action timeout"
    )
    if action_timeout != 30:
        raise T09PilotError("action timeout must remain 30 seconds")
    checkpoint = _strict_object(document.get("first_pair_checkpoint"), context="checkpoint")
    if checkpoint.get("required") is not True:
        raise T09PilotError("first-pair checkpoint must be required")
    raw_campaign = _strict_object(document.get("provider_lifecycle"), context="provider lifecycle")
    campaign = CampaignLifecycleLimits(
        campaign_provider_wall_seconds=_required_int(
            raw_campaign.get("campaign_provider_wall_seconds"),
            context="campaign provider wall",
        ),
        normal_cleanup_reserve_seconds=_required_int(
            raw_campaign.get("normal_cleanup_reserve_seconds"),
            context="normal cleanup reserve",
        ),
        provider_termination_cutoff_seconds=_required_int(
            raw_campaign.get("provider_termination_cutoff_seconds"),
            context="provider termination cutoff",
        ),
        post_condition_evaluator_evidence_seconds=_required_int(
            raw_campaign.get("post_condition_evaluator_evidence_seconds"),
            context="post-condition evaluator/evidence handoff",
        ),
        termination_dispatch_margin_seconds=_required_int(
            raw_campaign.get("termination_dispatch_margin_seconds"),
            context="provider termination dispatch margin",
        ),
        max_lambda_instances=_required_int(
            raw_campaign.get("max_lambda_instances"), context="Lambda instance cap"
        ),
        max_launch_count=_required_int(
            raw_campaign.get("max_launch_count"), context="Lambda launch cap"
        ),
        persistent_filesystems=_required_int(
            raw_campaign.get("persistent_filesystems"), context="persistent filesystem cap"
        ),
    )
    if (
        limits.max_total_wall_seconds != campaign.campaign_provider_wall_seconds
        or limits.max_lambda_duration_seconds != campaign.campaign_provider_wall_seconds
    ):
        raise T09PilotError("runtime and provider campaign walls must be identical")
    return PilotExecutionContract(
        path=path.resolve(strict=True),
        sha256=expected_sha256,
        limits=limits,
        attempts=tuple(attempts),
        dataset_contract_path=_required_string(dataset.get("path"), context="dataset path"),
        dataset_contract_sha256=_required_string(dataset.get("sha256"), context="dataset hash"),
        evaluator_contract_path=_required_string(evaluator.get("path"), context="evaluator path"),
        evaluator_contract_sha256=_required_string(
            evaluator.get("sha256"), context="evaluator hash"
        ),
        action_timeout_seconds=action_timeout,
        first_pair_checkpoint_required=True,
        campaign=campaign,
    )


def usage_to_document(usage: ProviderBudgetUsage) -> dict[str, int | float]:
    return {
        "cost_usd": usage.cost_usd,
        "input_tokens": usage.input_tokens,
        "cached_input_tokens": usage.cached_input_tokens,
        "output_tokens": usage.output_tokens,
        "total_tokens": usage.total_tokens,
        "model_call_attempts": usage.model_call_attempts,
        "default_service_tier_responses": usage.default_service_tier_responses,
        "browser_actions": usage.browser_actions,
        "output_bytes": usage.output_bytes,
    }


def usage_from_document(value: object) -> ProviderBudgetUsage:
    raw = _strict_object(value, context="provider usage")
    integers: dict[str, int] = {}
    for field in (
        "input_tokens",
        "cached_input_tokens",
        "output_tokens",
        "total_tokens",
        "model_call_attempts",
        "default_service_tier_responses",
        "browser_actions",
        "output_bytes",
    ):
        integers[field] = _required_int(raw.get(field), context=f"usage {field}")
    return ProviderBudgetUsage(
        cost_usd=_required_number(raw.get("cost_usd"), context="usage cost"),
        **integers,
    )


def load_aggregate_usage(path: Path, *, contract_sha256: str) -> ProviderBudgetUsage:
    """Load the prior sequential-attempt aggregate or return a typed zero state."""

    if not path.exists():
        return ProviderBudgetUsage()
    document = load_json_object(path, context="aggregate budget ledger")
    if document.get("schema_version") != "0.1.0" or document.get("plan_id") != PLAN_ID:
        raise T09PilotError("aggregate budget ledger identity drifted")
    if document.get("execution_contract_sha256") != contract_sha256:
        raise T09PilotError("aggregate budget ledger contract binding drifted")
    if document.get("unreconciled_provider_attempts") != 0:
        raise T09PilotError("an unreconciled provider attempt forbids another condition")
    return usage_from_document(document.get("usage"))


def write_aggregate_usage(
    path: Path,
    *,
    contract_sha256: str,
    usage: ProviderBudgetUsage,
    unreconciled_provider_attempts: int,
) -> None:
    """Durably persist aggregate usage after every provider/action transition."""

    if unreconciled_provider_attempts < 0:
        raise T09PilotError("unreconciled attempt count cannot be negative")
    document = {
        "schema_version": "0.1.0",
        "plan_id": PLAN_ID,
        "execution_contract_sha256": contract_sha256,
        "unreconciled_provider_attempts": unreconciled_provider_attempts,
        "usage": usage_to_document(usage),
    }
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_suffix(f".{os.getpid()}.tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        handle.write(json.dumps(document, indent=2, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def initialize_pilot_state(
    path: Path,
    *,
    execution_contract_sha256: str,
    pilot_started_at_epoch: float,
    lambda_started_at_epoch: float,
) -> None:
    """Create the one sequential attempt ledger during an authorized preflight."""

    if path.exists():
        raise T09PilotError("pilot state already exists; it cannot be reset for a retry")
    for value in (pilot_started_at_epoch, lambda_started_at_epoch):
        if not math.isfinite(value) or value <= 0:
            raise T09PilotError("pilot and Lambda start epochs must be positive and finite")
    document = {
        "schema_version": "0.2.0",
        "plan_id": PLAN_ID,
        "execution_contract_sha256": execution_contract_sha256,
        "pilot_started_at_epoch": pilot_started_at_epoch,
        "lambda_started_at_epoch": lambda_started_at_epoch,
        "first_pair_started_at_epoch": pilot_started_at_epoch,
        "second_pair_started_at_epoch": None,
        "empirical_attempts_entered": [],
        "raw_attempts_complete": [],
        "raw_attempt_bindings": {},
        "attempts_completed": [],
        "attempt_finalizations": {},
        "attempt_finalization_history": {},
        "first_pair_decision": None,
    }
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    _write_json_atomic(path, document)


def _write_json_atomic(path: Path, document: Mapping[str, object]) -> None:
    temporary = path.with_suffix(f".{os.getpid()}.tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        handle.write(json.dumps(document, indent=2, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _load_pilot_state(path: Path, *, contract_sha256: str) -> dict[str, object]:
    state = load_json_object(path, context="pilot attempt state")
    if (
        state.get("schema_version") != "0.2.0"
        or state.get("plan_id") != PLAN_ID
        or state.get("execution_contract_sha256") != contract_sha256
    ):
        raise T09PilotError("pilot attempt-state identity drifted")
    for field in ("empirical_attempts_entered", "raw_attempts_complete", "attempts_completed"):
        value = state.get(field)
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise T09PilotError(f"pilot state {field} is malformed")
        if len(value) != len(set(value)) or any(item not in ATTEMPT_ORDER for item in value):
            raise T09PilotError(f"pilot state {field} is not a unique frozen-order subset")
        if value != [item for item in ATTEMPT_ORDER if item in value]:
            raise T09PilotError(f"pilot state {field} is not in frozen order")
    raw_bindings = state.get("raw_attempt_bindings")
    if not isinstance(raw_bindings, dict) or not all(
        isinstance(key, str) and isinstance(value, dict) for key, value in raw_bindings.items()
    ):
        raise T09PilotError("pilot state raw attempt bindings are malformed")
    raw_complete = cast(list[str], state["raw_attempts_complete"])
    if set(raw_bindings) != set(raw_complete):
        raise T09PilotError("pilot state raw attempt bindings do not match sealed attempts")
    for binding in raw_bindings.values():
        if set(binding) != {"manifest_sha256", "receipt_sha256"} or any(
            not isinstance(value, str) or _HEX64.fullmatch(value) is None
            for value in binding.values()
        ):
            raise T09PilotError("pilot state raw attempt binding is malformed")
    finalizations = state.get("attempt_finalizations")
    if not isinstance(finalizations, dict) or not all(
        isinstance(key, str) and isinstance(value, dict) for key, value in finalizations.items()
    ):
        raise T09PilotError("pilot state attempt finalizations are malformed")
    completed = cast(list[str], state["attempts_completed"])
    if set(finalizations) != set(completed):
        raise T09PilotError("pilot selected finalizations do not match completed attempts")
    history = state.get("attempt_finalization_history")
    if not isinstance(history, dict) or not all(
        isinstance(key, str)
        and isinstance(value, list)
        and all(isinstance(item, dict) for item in value)
        for key, value in history.items()
    ):
        raise T09PilotError("pilot state finalization history is malformed")
    return state


def mark_empirical_entry(
    path: Path,
    *,
    execution_contract_sha256: str,
    run_id: str,
) -> None:
    """Consume one immutable attempt identity before its first call or action."""

    state = _load_pilot_state(path, contract_sha256=execution_contract_sha256)
    entered = cast(list[str], state["empirical_attempts_entered"])
    raw_complete = cast(list[str], state["raw_attempts_complete"])
    if run_id in entered:
        raise T09BudgetExceeded("zero-retry rule forbids re-entering an empirical attempt")
    if (
        entered != list(ATTEMPT_ORDER[: len(entered)])
        or raw_complete != entered[: len(raw_complete)]
        or len(raw_complete) != len(entered)
    ):
        raise T09PilotError("pilot attempt history is not a valid prefix of the frozen order")
    if len(entered) >= len(ATTEMPT_ORDER) or run_id != ATTEMPT_ORDER[len(entered)]:
        raise T09BudgetExceeded("attempt count or frozen attempt order would be violated")
    if len(entered) == 2 and state.get("first_pair_decision") != "continue-to-task-b":
        raise T09BudgetExceeded("Task B is blocked until the first-pair checkpoint passes")
    entered.append(run_id)
    state["empirical_attempts_entered"] = entered
    _write_json_atomic(path, state)


def mark_raw_attempt_complete(
    path: Path,
    *,
    execution_contract_sha256: str,
    run_id: str,
    raw_manifest_sha256: str,
    raw_receipt_sha256: str,
) -> None:
    """Seal the consumed condition as reconstructable before downstream processing."""

    if (
        _HEX64.fullmatch(raw_manifest_sha256) is None
        or _HEX64.fullmatch(raw_receipt_sha256) is None
    ):
        raise T09PilotError("raw attempt hashes must be SHA-256")
    state = _load_pilot_state(path, contract_sha256=execution_contract_sha256)
    entered = cast(list[str], state["empirical_attempts_entered"])
    raw_complete = cast(list[str], state["raw_attempts_complete"])
    raw_bindings = state.setdefault("raw_attempt_bindings", {})
    if not isinstance(raw_bindings, dict):
        raise T09PilotError("raw attempt binding state is malformed")
    if run_id in raw_complete:
        if raw_bindings.get(run_id) != {
            "manifest_sha256": raw_manifest_sha256,
            "receipt_sha256": raw_receipt_sha256,
        }:
            raise T09PilotError("existing raw attempt binding disagrees with retained bytes")
        return
    if (
        run_id not in entered
        or run_id != ATTEMPT_ORDER[len(raw_complete)]
        or entered[: len(raw_complete) + 1] != list(ATTEMPT_ORDER[: len(raw_complete) + 1])
    ):
        raise T09PilotError("raw attempt completion is missing, duplicated, or out of order")
    raw_complete.append(run_id)
    state["raw_attempts_complete"] = raw_complete
    if run_id in raw_bindings:
        raise T09PilotError("raw attempt binding is malformed or duplicated")
    raw_bindings[run_id] = {
        "manifest_sha256": raw_manifest_sha256,
        "receipt_sha256": raw_receipt_sha256,
    }
    _write_json_atomic(path, state)


def mark_attempt_completed(
    path: Path,
    *,
    execution_contract_sha256: str,
    run_id: str,
    finalizer_source_sha256: str,
    finalizer_commit: str,
    finalizer_dependency_manifest_sha256: str,
    evaluator_contract_sha256: str,
    interpreter: str,
    interpreter_sha256: str,
    finalized_output_root: str,
    finalization_complete_sha256: str,
) -> None:
    """Select one downstream finalization without reopening the condition attempt."""

    if (
        _HEX64.fullmatch(finalizer_source_sha256) is None
        or _HEX64.fullmatch(finalizer_dependency_manifest_sha256) is None
        or _HEX64.fullmatch(evaluator_contract_sha256) is None
        or _HEX64.fullmatch(interpreter_sha256) is None
        or _HEX64.fullmatch(finalization_complete_sha256) is None
        or re.fullmatch(r"[a-f0-9]{40}", finalizer_commit) is None
        or interpreter != "/opt/sira/.venv/bin/python"
    ):
        raise T09PilotError("finalizer code identity is malformed")

    state = _load_pilot_state(path, contract_sha256=execution_contract_sha256)
    entered = cast(list[str], state["empirical_attempts_entered"])
    raw_complete = cast(list[str], state["raw_attempts_complete"])
    finalizations = cast(dict[str, dict[str, object]], state["attempt_finalizations"])
    history = cast(dict[str, list[dict[str, object]]], state["attempt_finalization_history"])
    if run_id not in entered or run_id not in raw_complete:
        raise T09PilotError("attempt completion is missing, duplicated, or out of order")
    selection: dict[str, object] = {
        "finalizer_source_sha256": finalizer_source_sha256,
        "finalizer_commit": finalizer_commit,
        "finalizer_dependency_manifest_sha256": finalizer_dependency_manifest_sha256,
        "evaluator_contract_sha256": evaluator_contract_sha256,
        "interpreter": interpreter,
        "interpreter_sha256": interpreter_sha256,
        "finalized_output_root": finalized_output_root,
        "finalization_complete_sha256": finalization_complete_sha256,
    }
    retained_history = history.setdefault(run_id, [])
    if selection not in retained_history:
        retained_history.append(selection)
    finalizations[run_id] = selection
    state["attempts_completed"] = [
        attempt_run_id for attempt_run_id in ATTEMPT_ORDER if attempt_run_id in finalizations
    ]
    state["attempt_finalizations"] = finalizations
    state["attempt_finalization_history"] = history
    _write_json_atomic(path, state)


def record_first_pair_checkpoint(
    path: Path,
    *,
    execution_contract_sha256: str,
    decision: Mapping[str, object],
    decided_at_epoch: float,
) -> None:
    """Seal the one automatic checkpoint; only a passing decision opens Task B."""

    state = _load_pilot_state(path, contract_sha256=execution_contract_sha256)
    if state.get("first_pair_decision") is not None:
        raise T09PilotError("the first-pair checkpoint cannot be repeated")
    if state["attempts_completed"] != list(ATTEMPT_ORDER[:2]):
        raise T09PilotError("checkpoint requires both Task A attempts to be complete")
    finalizations = cast(dict[str, dict[str, object]], state["attempt_finalizations"])
    finalizer_closures = {
        canonical_sha256(
            {
                key: item[key]
                for key in (
                    "finalizer_source_sha256",
                    "finalizer_commit",
                    "finalizer_dependency_manifest_sha256",
                    "evaluator_contract_sha256",
                    "interpreter",
                    "interpreter_sha256",
                )
            }
        )
        for run_id in ATTEMPT_ORDER[:2]
        if (item := finalizations.get(run_id)) is not None
    }
    if len(finalizer_closures) != 1:
        raise T09PilotError("checkpoint requires one uniform Task A finalizer closure")
    result = decision.get("decision")
    if result not in {"continue-to-task-b", "stop-before-task-b"}:
        raise T09PilotError("checkpoint decision is invalid")
    state["first_pair_decision"] = result
    state["first_pair_decision_sha256"] = canonical_sha256(decision)
    if result == "continue-to-task-b":
        if not math.isfinite(decided_at_epoch) or decided_at_epoch <= 0:
            raise T09PilotError("second-pair epoch is invalid")
        state["second_pair_started_at_epoch"] = decided_at_epoch
    _write_json_atomic(path, state)


def pilot_state_time_origins(
    path: Path,
    *,
    execution_contract_sha256: str,
    run_id: str,
    wall_time: Callable[[], float] = time.time,
    monotonic: Callable[[], float] = time.monotonic,
) -> tuple[float, float, float]:
    """Convert retained wall epochs to monotonic pair/pilot/Lambda origins."""

    state = _load_pilot_state(path, contract_sha256=execution_contract_sha256)
    attempt_index = ATTEMPT_ORDER.index(run_id)
    pair_field = (
        "first_pair_started_at_epoch" if attempt_index < 2 else "second_pair_started_at_epoch"
    )
    epoch_values = (
        state.get(pair_field),
        state.get("pilot_started_at_epoch"),
        state.get("lambda_started_at_epoch"),
    )
    valid_epoch_types = all(
        isinstance(value, (int, float)) and not isinstance(value, bool) for value in epoch_values
    )
    if not valid_epoch_types:
        raise T09PilotError("pilot state timing origins are incomplete")
    now_wall = wall_time()
    now_monotonic = monotonic()
    result: list[float] = []
    for raw in epoch_values:
        assert isinstance(raw, (int, float))
        elapsed = now_wall - float(raw)
        if not math.isfinite(elapsed) or elapsed < 0:
            raise T09PilotError("pilot state timing origin is in the future")
        result.append(now_monotonic - elapsed)
    return result[0], result[1], result[2]


@dataclass(frozen=True, slots=True)
class ResourceSnapshot:
    """Locally measurable wall, output, disk, and Lambda accounting state."""

    condition_elapsed_seconds: float
    pair_elapsed_seconds: float
    total_elapsed_seconds: float
    attempt_output_bytes: int
    pilot_disk_bytes: int
    lambda_elapsed_seconds: float
    lambda_cost_usd: float


class ResourceGuard:
    """Fail-closed counter checked before each model call and browser action."""

    def __init__(
        self,
        limits: RuntimeLimits,
        *,
        attempt_root: Path,
        pilot_root: Path,
        condition_started: float,
        pair_started: float,
        pilot_started: float,
        lambda_started: float,
        lambda_hourly_price_usd: float = 1.29,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self.limits = limits
        self.attempt_root = attempt_root
        self.pilot_root = pilot_root
        self.condition_started = condition_started
        self.pair_started = pair_started
        self.pilot_started = pilot_started
        self.lambda_started = lambda_started
        self.lambda_hourly_price_usd = lambda_hourly_price_usd
        self.monotonic = monotonic

    @staticmethod
    def _tree_bytes(root: Path) -> int:
        total = 0
        if not root.exists():
            return 0
        for directory, _, files in os.walk(root):
            for name in files:
                path = Path(directory) / name
                try:
                    if not path.is_symlink():
                        total += path.stat().st_size
                except FileNotFoundError:
                    continue
        return total

    def snapshot(self) -> ResourceSnapshot:
        now = self.monotonic()
        lambda_elapsed = max(0.0, now - self.lambda_started)
        return ResourceSnapshot(
            condition_elapsed_seconds=max(0.0, now - self.condition_started),
            pair_elapsed_seconds=max(0.0, now - self.pair_started),
            total_elapsed_seconds=max(0.0, now - self.pilot_started),
            attempt_output_bytes=self._tree_bytes(self.attempt_root),
            pilot_disk_bytes=self._tree_bytes(self.pilot_root),
            lambda_elapsed_seconds=lambda_elapsed,
            lambda_cost_usd=lambda_elapsed * self.lambda_hourly_price_usd / 3600.0,
        )

    def check(self) -> ResourceSnapshot:
        snapshot = self.snapshot()
        violations: list[str] = []
        comparisons = (
            (
                "condition_wall_seconds",
                snapshot.condition_elapsed_seconds,
                self.limits.max_condition_wall_seconds,
            ),
            ("pair_wall_seconds", snapshot.pair_elapsed_seconds, self.limits.max_pair_wall_seconds),
            (
                "total_wall_seconds",
                snapshot.total_elapsed_seconds,
                self.limits.max_total_wall_seconds,
            ),
            (
                "attempt_output_bytes",
                snapshot.attempt_output_bytes,
                self.limits.max_output_bytes_per_attempt,
            ),
            ("pilot_disk_bytes", snapshot.pilot_disk_bytes, self.limits.max_disk_bytes),
            (
                "lambda_duration_seconds",
                snapshot.lambda_elapsed_seconds,
                self.limits.max_lambda_duration_seconds,
            ),
            ("lambda_cost_usd", snapshot.lambda_cost_usd, self.limits.max_lambda_cost_usd),
        )
        for name, observed, maximum in comparisons:
            if observed > maximum:
                violations.append(name)
        if violations:
            raise T09BudgetExceeded("hard resource cap exceeded: " + ", ".join(violations))
        return snapshot


@dataclass(frozen=True, slots=True)
class PairCheckpointInput:
    """Evidence required for the automatic post-Task-A calibration decision."""

    attempt_run_ids: tuple[str, str]
    valid_evidence: tuple[bool, bool]
    evaluator_succeeded: tuple[bool, bool]
    pair_match_valid: bool
    credential_issue: bool
    cleanup_issue: bool
    severe_floor_or_ceiling_failure: bool
    actual_usage: ProviderBudgetUsage
    actual_pair_wall_seconds: float
    projected_aggregate_cost_usd: float
    actual_lambda_cost_usd: float
    remaining_campaign_seconds: float
    next_attempt_hard_wall_seconds: int = 3_600
    prior_t09_cost_usd: float = 2.5308164556905757
    cumulative_t09_cost_cap_usd: float = 48.0


def first_pair_decision(value: PairCheckpointInput) -> dict[str, object]:
    """Apply the predeclared pass/stop checkpoint without scientific inference."""

    reasons: list[str] = []
    if value.attempt_run_ids != ATTEMPT_ORDER[:2]:
        reasons.append("task_a_attempt_identity_or_order_invalid")
    if not all(value.valid_evidence):
        reasons.append("task_a_valid_evidence_missing")
    if not all(value.evaluator_succeeded):
        reasons.append("task_a_evaluator_failed")
    if not value.pair_match_valid:
        reasons.append("task_a_pair_match_invalid")
    if value.credential_issue:
        reasons.append("credential_issue")
    if value.cleanup_issue:
        reasons.append("cleanup_issue")
    if value.severe_floor_or_ceiling_failure:
        reasons.append("task_b_cannot_add_calibration_value")
    usage = value.actual_usage
    strict_half_caps = {
        "model_calls": 2_310,
        "tokens": 2_000_000,
        "browser_actions": 60,
        "wall_seconds": 7_200,
        "openai_cost_usd": 20.0,
        "lambda_cost_usd": 2.58,
        "total_cost_usd": 22.58,
    }
    actual_total_cost = usage.cost_usd + value.actual_lambda_cost_usd
    if usage.model_call_attempts >= strict_half_caps["model_calls"]:
        reasons.append("first_pair_model_call_threshold_reached")
    if usage.total_tokens >= strict_half_caps["tokens"]:
        reasons.append("first_pair_token_threshold_reached")
    if usage.browser_actions >= strict_half_caps["browser_actions"]:
        reasons.append("first_pair_browser_action_threshold_reached")
    if (
        not math.isfinite(value.actual_pair_wall_seconds)
        or value.actual_pair_wall_seconds >= strict_half_caps["wall_seconds"]
    ):
        reasons.append("first_pair_wall_threshold_reached")
    if usage.cost_usd >= strict_half_caps["openai_cost_usd"]:
        reasons.append("first_pair_openai_cost_threshold_reached")
    if value.actual_lambda_cost_usd >= strict_half_caps["lambda_cost_usd"]:
        reasons.append("first_pair_lambda_cost_threshold_reached")
    if actual_total_cost >= strict_half_caps["total_cost_usd"]:
        reasons.append("first_pair_total_cost_threshold_reached")
    if not math.isfinite(value.projected_aggregate_cost_usd) or (
        value.projected_aggregate_cost_usd > 45.16
    ):
        reasons.append("projected_aggregate_cost_exceeds_hard_cap")
    projected_cumulative = value.prior_t09_cost_usd + value.projected_aggregate_cost_usd
    if not math.isfinite(projected_cumulative) or (
        projected_cumulative > value.cumulative_t09_cost_cap_usd
    ):
        reasons.append("projected_cumulative_t09_cost_exceeds_hard_cap")
    lifecycle = CampaignLifecycleLimits(
        campaign_provider_wall_seconds=14_400,
        normal_cleanup_reserve_seconds=900,
        provider_termination_cutoff_seconds=13_500,
        post_condition_evaluator_evidence_seconds=600,
        termination_dispatch_margin_seconds=60,
        max_lambda_instances=1,
        max_launch_count=2,
        persistent_filesystems=0,
    )
    required_campaign_seconds = lifecycle.required_attempt_seconds(
        attempt_hard_wall_seconds=value.next_attempt_hard_wall_seconds
    )
    if not lifecycle.admit_remaining(
        remaining_campaign_seconds=value.remaining_campaign_seconds,
        attempt_hard_wall_seconds=value.next_attempt_hard_wall_seconds,
    ):
        reasons.append("insufficient_campaign_time_for_next_attempt_and_cleanup")
    return {
        "schema_version": "0.1.0",
        "plan_id": PLAN_ID,
        "decision": "continue-to-task-b" if not reasons else "stop-before-task-b",
        "scientific_sampling_claim": "none-calibration-checkpoint-only",
        "reasons": reasons,
        "actual_first_pair_total_cost_usd": actual_total_cost,
        "projected_aggregate_cost_usd": value.projected_aggregate_cost_usd,
        "prior_t09_cost_usd": value.prior_t09_cost_usd,
        "projected_cumulative_t09_cost_usd": projected_cumulative,
        "cumulative_t09_cost_cap_usd": value.cumulative_t09_cost_cap_usd,
        "remaining_campaign_seconds": value.remaining_campaign_seconds,
        "required_campaign_seconds_for_next_attempt": required_campaign_seconds,
        "thresholds": strict_half_caps,
    }


_SENSITIVE_KEY_FRAGMENTS: Final = (
    "api_key",
    "authorization",
    "cloud_credential",
    "jupyter_token",
    "jupyter_url",
    "private_cidr",
    "private_ip",
    "provider_account",
    "secret",
)


def structurally_redact(value: object) -> object:
    """Remove secret/private fields by key rather than value heuristics."""

    if isinstance(value, Mapping):
        redacted: dict[str, object] = {}
        for raw_key, child in value.items():
            key = str(raw_key)
            lowered = key.lower()
            if any(fragment in lowered for fragment in _SENSITIVE_KEY_FRAGMENTS):
                redacted[key] = {"redacted": True, "reason": "structural-sensitive-field"}
            else:
                redacted[key] = structurally_redact(child)
        return redacted
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [structurally_redact(item) for item in value]
    return value


class EventWriter:
    """Append immutable causal events with bounded, structurally redacted payloads."""

    def __init__(self, path: Path, *, max_event_bytes: int = 16 * 1024 * 1024) -> None:
        self.path = path
        self.max_event_bytes = max_event_bytes
        self.sequence = 0
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)

    def append(
        self,
        kind: str,
        payload: Mapping[str, object],
        *,
        parent_event_id: str | None = None,
    ) -> str:
        invalid_parent = (
            parent_event_id is not None and _SAFE_EVENT_ID.fullmatch(parent_event_id) is None
        )
        if not kind or invalid_parent:
            raise T09PilotError("event kind or causal parent is invalid")
        self.sequence += 1
        event_id = f"EVT-T09-{self.sequence:08d}"
        document = {
            "schema_version": "0.1.0",
            "event_id": event_id,
            "parent_event_id": parent_event_id,
            "sequence": self.sequence,
            "kind": kind,
            "payload": structurally_redact(dict(payload)),
        }
        encoded = (json.dumps(document, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
        if len(encoded) > self.max_event_bytes:
            raise T09BudgetExceeded("one evidence event exceeds its byte cap")
        with self.path.open("ab") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        return event_id


@dataclass(frozen=True, slots=True)
class EvaluatorIdentity:
    root: Path
    dataset_path: Path
    task_index: int
    fixture_subset: bool = False

    def verify(self) -> None:
        expected_files = {
            "evaluator.py": EVALUATOR_SHA256,
            "run.py": "e6741326a4b0d3a1fe542748d03c86f1e15f87c3de25b4937e17b3e2472afd17",
            "utils/helpers.py": "e816bb09d232d820edfc090ff7b2f8f5a4674f27e30b87a9a8d876ffd82c681e",
            "utils/models.py": "9638bc652ced674d3c6ff4b63148a913070cee01f350ca773dcbfa2ed1b01cd3",
            "utils/norm.py": "c0a5da77ab7014bbb86e8310310b538881f01129d594afc537dd17d565b40eff",
        }
        for relative, expected in expected_files.items():
            if file_sha256(self.root / relative) != expected:
                raise T09PilotError(f"pinned evaluator file drifted: {relative}")
        if self.fixture_subset:
            try:
                rows: object = json.loads(self.dataset_path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                raise T09PilotError("FanOutQA fixture subset is unreadable") from exc
            if not isinstance(rows, list) or len(rows) != 2:
                raise T09PilotError("FanOutQA fixture subset must contain the two frozen rows")
            observed = tuple(canonical_sha256(row) for row in rows)
            if observed != TASK_ROW_SHA256S:
                raise T09PilotError("FanOutQA fixture rows drifted from the frozen records")
        elif file_sha256(self.dataset_path) != DATASET_SHA256:
            raise T09PilotError("pinned FanOutQA dataset bytes drifted")
        if self.task_index not in (0, 1):
            raise T09PilotError("evaluator task index must be one of the two frozen rows")


def _load_pinned_evaluator(identity: EvaluatorIdentity) -> ModuleType:
    identity.verify()
    evaluator_path = identity.root / "evaluator.py"
    spec = importlib.util.spec_from_file_location(
        "giclab_t09_pinned_fanout_evaluator", evaluator_path
    )
    if spec is None or spec.loader is None:
        raise T09PilotError("cannot load the pinned FanOutQA evaluator")
    module = importlib.util.module_from_spec(spec)
    root = str(identity.root)
    shadowed_utils = {
        name: loaded
        for name, loaded in sys.modules.items()
        if name == "utils" or name.startswith("utils.")
    }
    for name in shadowed_utils:
        sys.modules.pop(name, None)
    previous_bytecode_setting = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    sys.path.insert(0, root)
    try:
        spec.loader.exec_module(module)
        loaded_utils = {
            name: loaded
            for name, loaded in sys.modules.items()
            if name == "utils" or name.startswith("utils.")
        }
        for name, loaded in loaded_utils.items():
            source = getattr(loaded, "__file__", None)
            resolved_source = Path(source).resolve(strict=True) if source is not None else None
            if resolved_source is not None and identity.root not in resolved_source.parents:
                raise T09PilotError(f"pinned evaluator imported an external module: {name}")
    finally:
        if sys.path[0] == root:
            sys.path.pop(0)
        for name in tuple(sys.modules):
            if name == "utils" or name.startswith("utils."):
                sys.modules.pop(name, None)
        sys.modules.update(shadowed_utils)
        sys.dont_write_bytecode = previous_bytecode_setting
    return module


def evaluate_retained_session(
    identity: EvaluatorIdentity,
    session_paths: Sequence[Path],
) -> dict[str, object]:
    """Run the exact upstream scorer once, with fail-closed evidence cardinality."""

    if len(session_paths) != 1:
        code = "duplicate_evidence" if len(session_paths) > 1 else "missing_evidence"
        return {
            "schema_version": "0.1.0",
            "evaluator_valid": False,
            "failure_code": code,
            "score": None,
            "upstream_output": None,
        }
    session_path = session_paths[0]
    try:
        session = load_json_object(session_path, context="retained SiRA session")
        history = session.get("history")
        if not isinstance(history, list):
            raise T09PilotError("session history is missing")
        evaluator_module = _load_pinned_evaluator(identity)
        evaluator_class: Any = evaluator_module.FanOutQAEvaluator
        evaluator = evaluator_class(
            str(identity.dataset_path),
            start_idx=identity.task_index,
            end_idx=identity.task_index + 1,
        )
        upstream_row, records = evaluator.evaluate_batch([str(session_path)])
        if not isinstance(upstream_row, dict) or not isinstance(records, list) or len(records) != 1:
            raise T09PilotError("upstream evaluator returned an unexpected output shape")
        record = records[0]
        if not isinstance(record, dict) or record.get("id") != TASK_IDS[identity.task_index]:
            raise T09PilotError("upstream evaluator task identity drifted")
        score = _required_number(upstream_row.get("acc_loose"), context="loose accuracy")
        if not 0.0 <= score <= 1.0:
            raise T09PilotError("normalized task score is outside [0, 1]")
        final_action: object = history[-1][1] if history and isinstance(history[-1], list) else None
        answer_produced = isinstance(final_action, str) and bool(
            re.fullmatch(r"send_msg_to_user\((['\"])(.*)\1\)", final_action, flags=re.DOTALL)
        )
        outcome = record.get("outcome")
        task_completed = (
            session.get("is_complete") is True
            and answer_produced
            and outcome == "Response Returned"
        )
        return {
            "schema_version": "0.1.0",
            "evaluator_valid": True,
            "failure_code": None,
            "answer_produced": answer_produced,
            "task_completed": task_completed,
            "score": score,
            "score_provenance": {
                "kind": "exact-pinned-upstream-fanoutqa-evaluator",
                "evaluator_sha256": EVALUATOR_SHA256,
                "deterministic_fields": [
                    "acc_loose",
                    "acc_strict",
                    "rouge1",
                    "rouge2",
                    "rougeL",
                ],
                "judge_model": None,
            },
            "upstream_output": {
                "scores": copy.deepcopy(upstream_row),
                "record": copy.deepcopy(record),
            },
        }
    except Exception as exc:
        return {
            "schema_version": "0.1.0",
            "evaluator_valid": False,
            "failure_code": "evaluator_exception",
            "exception_type": type(exc).__name__,
            "score": None,
            "upstream_output": None,
        }


def outcome_contract(
    *,
    process_exit_code: int | None,
    artifact_executed: bool,
    task_completed: bool,
    answer_produced: bool,
    evaluator_valid: bool,
    score: float | None,
    infrastructure_failure: bool,
    missing_required_evidence: bool,
    infrastructure_failure_reasons: Sequence[str] = (),
) -> dict[str, object]:
    """Classify orthogonal attempt states without equating exit zero with success."""

    if evaluator_valid != (score is not None):
        raise T09PilotError("valid evaluator state and score presence must agree")
    if score is not None and (not math.isfinite(score) or not 0.0 <= score <= 1.0):
        raise T09PilotError("task score must be finite and bounded")
    if infrastructure_failure != bool(infrastructure_failure_reasons):
        raise T09PilotError("infrastructure failure state and explicit failure reasons must agree")
    valid_scored_attempt = (
        artifact_executed
        and evaluator_valid
        and not infrastructure_failure
        and not missing_required_evidence
    )
    return {
        "schema_version": "0.3.0",
        "process_exit": {
            "observed": process_exit_code is not None,
            "code": process_exit_code,
            "zero": process_exit_code == 0 if process_exit_code is not None else None,
        },
        "artifact_execution": artifact_executed,
        "task_completion": "completed" if task_completed else "incomplete",
        "answer_production": answer_produced,
        "evaluator_validity": evaluator_valid,
        "task_score": score,
        "valid_scored_attempt": valid_scored_attempt,
        "invalid_infrastructure_attempt": infrastructure_failure,
        "infrastructure_failure_reasons": sorted(set(infrastructure_failure_reasons)),
        "condition_failure": (
            artifact_executed
            and evaluator_valid
            and not task_completed
            and not infrastructure_failure
            and not missing_required_evidence
        ),
        "missing_evidence": missing_required_evidence,
        "evaluator_failure": not evaluator_valid,
    }


_UPSTREAM_FLAG_ORDER: Final = (
    "--dataset",
    "--mode",
    "--agent",
    "--config_name",
    "--model",
    "--max_steps",
    "--timeout",
    "--max_retry",
    "--data_root",
    "--output_dir",
    "--start_idx",
    "--end_idx",
    "--seed",
)


def _validated_upstream_argv(
    contract: PilotExecutionContract,
    attempt: AttemptBinding,
) -> dict[str, str]:
    argv = attempt.upstream_argv
    if len(argv) != 1 + 2 * len(_UPSTREAM_FLAG_ORDER):
        raise T09PilotError("upstream argv has an unexpected cardinality")
    flags = tuple(argv[index] for index in range(1, len(argv), 2))
    if flags != _UPSTREAM_FLAG_ORDER:
        raise T09PilotError("upstream argv flag order or cardinality drifted")
    values = {argv[index]: argv[index + 1] for index in range(1, len(argv), 2)}
    expected = {
        "--dataset": "fanout",
        "--mode": attempt.condition,
        "--agent": "sira",
        "--config_name": ("web_reactive" if attempt.condition == "reactive" else "web_simulative"),
        "--model": MODEL_REVISION,
        "--max_steps": str(contract.limits.max_browser_actions_per_attempt),
        "--timeout": str(contract.action_timeout_seconds),
        "--max_retry": "0",
        "--data_root": "/opt/sira/data",
        "--output_dir": f"/opt/giclab-artifacts/{attempt.raw_output_root}/sira-output",
        "--start_idx": str(attempt.task_index),
        "--end_idx": str(attempt.task_index + 1),
        "--seed": "42",
    }
    upstream_suffix = attempt.run_id.removeprefix("RUN-T09-").removesuffix("-0003")
    upstream_run_id = f"EXP-0001-PILOT-V5-{upstream_suffix}"
    if argv[0] != upstream_run_id or values != expected:
        raise T09PilotError("upstream argv drifted from the exact task/condition contract")
    return values


def render_command_manifest(
    contract: PilotExecutionContract,
    attempt: AttemptBinding,
    *,
    execution_contract_runtime_path: str,
    runtime_adaptation_path: str,
    runtime_adaptation_sha256: str,
    pilot_library_sha256: str,
    aggregate_ledger_path: str,
    pilot_state_path: str,
) -> dict[str, object]:
    """Render the exact argv and equality surface for one future attempt."""

    if any(
        _HEX64.fullmatch(value) is None
        for value in (runtime_adaptation_sha256, pilot_library_sha256)
    ):
        raise T09PilotError("runtime and pilot-library hashes must be SHA-256")
    upstream_values = _validated_upstream_argv(contract, attempt)
    argv = [
        "/usr/bin/timeout",
        "--signal=TERM",
        "--kill-after=30s",
        f"{contract.limits.max_condition_wall_seconds}s",
        "/opt/sira/.venv/bin/python",
        runtime_adaptation_path,
        "--gate-upstream-runner",
        "/opt/sira/scripts/run_web_agent.py",
        "--gate-attempt-root",
        f"/opt/giclab-artifacts/{attempt.raw_output_root}",
        "--gate-mode",
        attempt.condition,
        "--gate-adaptation-sha256",
        runtime_adaptation_sha256,
        "--gate-pilot-contract",
        execution_contract_runtime_path,
        "--gate-pilot-contract-sha256",
        contract.sha256,
        "--gate-pilot-library-sha256",
        pilot_library_sha256,
        "--gate-pilot-attempt-id",
        attempt.run_id,
        "--gate-condition-plan",
        f"/opt/giclab-contracts/conditions/{Path(attempt.condition_plan_path).name}",
        "--gate-aggregate-ledger",
        aggregate_ledger_path,
        "--gate-pilot-state",
        pilot_state_path,
        "--",
        *attempt.upstream_argv,
    ]
    equality_surface = {
        "task_id": attempt.task_id,
        "model": MODEL_REVISION,
        "runtime": "T09-V5-python-3.11.14-preentry-bound-replacement-image",
        "giclab_commit": attempt.giclab_commit,
        "protocol_sha256": attempt.protocol_sha256,
        "config_sha256": attempt.config_sha256,
        "environment_sha256": attempt.environment_sha256,
        "tools": ["browsergym-openended", "playwright-1.39.0", "chromium-1084"],
        "max_browser_steps": contract.limits.max_browser_actions_per_attempt,
        "action_timeout_seconds": contract.action_timeout_seconds,
        "condition_wall_seconds": contract.limits.max_condition_wall_seconds,
        "evaluator_contract_sha256": contract.evaluator_contract_sha256,
        "instrumentation": "t09-post-action-provider-receipt-lineage-v1",
        "evidence_handling": (
            "immutable-raw-attempt-before-network-none-versioned-downstream-finalization"
        ),
        "budgets": {
            "max_model_calls": contract.limits.max_model_calls_per_attempt,
            "max_model_tokens": contract.limits.max_model_tokens_per_attempt,
            "max_openai_cost_usd": contract.limits.max_openai_cost_usd_per_attempt,
            "max_browser_actions": contract.limits.max_browser_actions_per_attempt,
            "max_output_bytes": contract.limits.max_output_bytes_per_attempt,
        },
        "actual_upstream_common_argv": {
            key: value
            for key, value in upstream_values.items()
            if key not in {"--mode", "--config_name", "--output_dir"}
        },
    }
    return {
        "schema_version": "0.1.0",
        "plan_id": PLAN_ID,
        "run_id": attempt.run_id,
        "pair_id": attempt.pair_id,
        "task_id": attempt.task_id,
        "condition": attempt.condition,
        "order_index": attempt.order_index,
        "condition_plan_path": attempt.condition_plan_path,
        "condition_plan_sha256": attempt.condition_plan_sha256,
        "execution_contract_sha256": contract.sha256,
        "argv": argv,
        "argv_sha256": canonical_sha256(argv),
        "equality_surface": equality_surface,
        "permitted_condition_owned": {
            "condition_mode": attempt.condition,
            "run_id": attempt.run_id,
            "order_index": attempt.order_index,
            "output_root": attempt.output_root,
            "raw_output_root": attempt.raw_output_root,
            "finalized_output_root": attempt.finalized_output_root,
            "condition_plan_path": attempt.condition_plan_path,
            "condition_plan_sha256": attempt.condition_plan_sha256,
            "source_declared_treatment_config": (
                "web_reactive" if attempt.condition == "reactive" else "web_simulative"
            ),
        },
    }


def _normalized_actual_argv(manifest: Mapping[str, object]) -> tuple[str, ...] | None:
    raw_argv = manifest.get("argv")
    condition = manifest.get("condition")
    run_id = manifest.get("run_id")
    condition_plan_path = manifest.get("condition_plan_path")
    condition_owned = manifest.get("permitted_condition_owned")
    if (
        not isinstance(raw_argv, list)
        or not all(isinstance(item, str) for item in raw_argv)
        or condition not in {"reactive", "simulative"}
        or not isinstance(run_id, str)
        or not isinstance(condition_plan_path, str)
        or not isinstance(condition_owned, Mapping)
    ):
        return None
    raw_output_root = condition_owned.get("raw_output_root")
    if not isinstance(raw_output_root, str) or raw_argv.count("--") != 1:
        return None
    argv = cast(list[str], list(raw_argv))
    separator = argv.index("--")
    replacements = {
        "--gate-attempt-root": (
            f"/opt/giclab-artifacts/{raw_output_root}",
            "<CONDITION-OWNED-ATTEMPT-ROOT>",
        ),
        "--gate-mode": (str(condition), "<SOURCE-DECLARED-TREATMENT>"),
        "--gate-pilot-attempt-id": (run_id, "<RUN-ID>"),
        "--gate-condition-plan": (
            f"/opt/giclab-contracts/conditions/{Path(condition_plan_path).name}",
            "<CONDITION-PLAN>",
        ),
    }
    for flag, (expected, replacement) in replacements.items():
        indexes = [index for index, item in enumerate(argv[:separator]) if item == flag]
        if len(indexes) != 1 or indexes[0] + 1 >= separator:
            return None
        if argv[indexes[0] + 1] != expected:
            return None
        argv[indexes[0] + 1] = replacement
    downstream = argv[separator + 1 :]
    upstream_suffix = run_id.removeprefix("RUN-T09-").removesuffix("-0003")
    expected_upstream_run_id = f"EXP-0001-PILOT-V5-{upstream_suffix}"
    if not downstream or downstream[0] != expected_upstream_run_id:
        return None
    downstream[0] = "<UPSTREAM-RUN-ID>"
    downstream_replacements = {
        "--mode": (str(condition), "<SOURCE-DECLARED-TREATMENT>"),
        "--config_name": (
            "web_reactive" if condition == "reactive" else "web_simulative",
            "<SOURCE-DECLARED-TREATMENT-CONFIG>",
        ),
        "--output_dir": (
            f"/opt/giclab-artifacts/{raw_output_root}/sira-output",
            "<CONDITION-OWNED-OUTPUT>",
        ),
    }
    for flag, (expected, replacement) in downstream_replacements.items():
        indexes = [index for index, item in enumerate(downstream) if item == flag]
        if len(indexes) != 1 or indexes[0] + 1 >= len(downstream):
            return None
        if downstream[indexes[0] + 1] != expected:
            return None
        downstream[indexes[0] + 1] = replacement
    return tuple([*argv[: separator + 1], *downstream])


def diff_pair_manifests(
    left: Mapping[str, object],
    right: Mapping[str, object],
) -> dict[str, object]:
    """Verify equality of the predeclared pair surface and enumerate allowed drift."""

    left_surface = left.get("equality_surface")
    right_surface = right.get("equality_surface")
    surface_equal = left_surface == right_surface
    left_argv = _normalized_actual_argv(left)
    right_argv = _normalized_actual_argv(right)
    argv_equal = left_argv is not None and left_argv == right_argv
    return {
        "schema_version": "0.1.0",
        "pair_id": left.get("pair_id"),
        "task_id_equal": left.get("task_id") == right.get("task_id"),
        "required_equality_surface_equal": surface_equal,
        "normalized_actual_argv_equal": argv_equal,
        "permitted_differences": [
            "condition_mode",
            "run_id",
            "order_index",
            "condition_owned_output_root",
            "condition_plan_path_and_sha256",
            "source_declared_treatment_config",
        ],
        "valid": surface_equal
        and argv_equal
        and left.get("pair_id") == right.get("pair_id")
        and left.get("task_id") == right.get("task_id")
        and left.get("condition") != right.get("condition"),
    }
