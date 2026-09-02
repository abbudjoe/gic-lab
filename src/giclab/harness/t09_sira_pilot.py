"""Offline contracts and runtime guards for the T09 SiRA calibration pilot.

This module has no cloud, browser, or model-provider client.  Its command and
budget helpers are inert until a separately authorized supervisor passes the
frozen contract to the T07 pragmatic runtime adaptation.
"""

from __future__ import annotations

import contextlib
import copy
import hashlib
import importlib.util
import json
import math
import os
import re
import stat
import subprocess
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
from giclab.harness.t09_provider_contracts import (
    PROVIDER_CONTRACTS,
    ProviderSelectorPolicy,
    T09ProviderContract,
    T09ProviderContractError,
    provider_contract_for_plan_id,
)

EXPERIMENT_ID: Final = "EXP-0001"
SIRA_COMMIT: Final = "93fb8d72de71f9a4a13419670adeb34d93cf7acd"
MODEL_REVISION: Final = "gpt-4o-2024-11-20"
SERVICE_TIER: Final = "default"
AUTHORIZATION_REFERENCE: Final[None] = None
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
_AUTONOMOUS_ATTEMPT_IDS: Final = frozenset(
    run_id
    for provider in PROVIDER_CONTRACTS.values()
    if provider.execution_contract_path is not None
    for run_id in provider.run_ids
)
HISTORICAL_IMAGE_ID: Final = (
    "sha256:035edf61718e84a8156f4f0f7817b134b0ce31488d3f0b50bbfba2b4a30cc61c"
)
PREENTRY_RESUME_FROM_PACKAGE_COMMIT: Final = "3640f061ea6c0f0f3d24bf2a346d4beda1a400cf"
PREENTRY_RESUME_FROM_PLAN_SHA256: Final = (
    "e7e214500348c8b876beb034df7b592c84f5ab79788ab6f310ef187fd797613c"
)

_HEX64 = re.compile(r"^[a-f0-9]{64}$")
_SAFE_EVENT_ID = re.compile(r"^[A-Z0-9][A-Z0-9._-]{2,127}$")


class T09PilotError(ValueError):
    """Raised when frozen T09 pilot material violates its machine contract."""


class T09BudgetExceeded(RuntimeError):
    """Raised before the next empirical operation would exceed a hard cap."""


def _state_provider_contract(state: Mapping[str, object]) -> T09ProviderContract:
    """Resolve lifecycle authority from the durable state's exact plan identity."""

    plan_id = state.get("plan_id")
    if not isinstance(plan_id, str):
        raise T09PilotError("pilot attempt-state plan identity is missing")
    try:
        return provider_contract_for_plan_id(plan_id)
    except T09ProviderContractError as exc:
        raise T09PilotError("pilot attempt-state plan identity is unsupported") from exc


@dataclass(frozen=True, slots=True)
class CampaignLifecycleLimits:
    """Separated autonomous preflight and empirical lifecycle authority."""

    preflight_iteration_wall_seconds: int
    maximum_preflight_instance_active_seconds: int
    maximum_cumulative_preflight_active_seconds: int
    maximum_preflight_provider_cost_usd: float
    max_preflight_launch_count: int
    failed_preflight_termination_dispatch_seconds: int
    empirical_campaign_wall_seconds: int
    evidence_export_reserve_seconds: int
    provider_termination_handoff_seconds: int
    empirical_cleanup_reserve_seconds: int
    empirical_termination_cutoff_seconds: int
    maximum_empirical_provider_cost_usd: float
    max_empirical_launch_count: int
    max_lambda_instances: int
    persistent_filesystems: int

    def __post_init__(self) -> None:
        values = (
            self.preflight_iteration_wall_seconds,
            self.maximum_preflight_instance_active_seconds,
            self.maximum_cumulative_preflight_active_seconds,
            self.max_preflight_launch_count,
            self.failed_preflight_termination_dispatch_seconds,
            self.empirical_campaign_wall_seconds,
            self.evidence_export_reserve_seconds,
            self.provider_termination_handoff_seconds,
            self.empirical_cleanup_reserve_seconds,
            self.empirical_termination_cutoff_seconds,
            self.max_empirical_launch_count,
            self.max_lambda_instances,
            self.persistent_filesystems,
        )
        if any(type(value) is not int or value < 0 for value in values):
            raise T09PilotError("campaign lifecycle limits must be non-negative integers")
        if self.preflight_iteration_wall_seconds != 3_600:
            raise T09PilotError("preflight iteration wall must remain 3,600 seconds")
        if self.maximum_preflight_instance_active_seconds != 21_600:
            raise T09PilotError("preflight instance active cap must remain 21,600 seconds")
        if self.maximum_cumulative_preflight_active_seconds != 43_200:
            raise T09PilotError("cumulative preflight cap must remain 43,200 seconds")
        if self.maximum_preflight_provider_cost_usd != 10.0:
            raise T09PilotError("preflight provider cost cap must remain USD 10")
        if self.max_preflight_launch_count != 8:
            raise T09PilotError("preflight launch cap must remain eight")
        if self.failed_preflight_termination_dispatch_seconds != 300:
            raise T09PilotError("failed-preflight termination dispatch must remain 300 seconds")
        if self.empirical_campaign_wall_seconds != 14_400:
            raise T09PilotError("empirical campaign wall must remain 14,400 seconds")
        if self.evidence_export_reserve_seconds != 600:
            raise T09PilotError("evidence export reserve must remain 600 seconds")
        if self.provider_termination_handoff_seconds != 60:
            raise T09PilotError("provider termination handoff must remain 60 seconds")
        if self.empirical_cleanup_reserve_seconds != 900:
            raise T09PilotError("empirical cleanup reserve must remain 900 seconds")
        if (
            self.empirical_termination_cutoff_seconds
            != self.empirical_campaign_wall_seconds - self.empirical_cleanup_reserve_seconds
        ):
            raise T09PilotError("provider termination cutoff must preserve the cleanup reserve")
        if self.maximum_empirical_provider_cost_usd != 8.0:
            raise T09PilotError("empirical provider cost cap must remain USD 8")
        if (
            self.max_lambda_instances != 1
            or self.max_empirical_launch_count != 1
            or self.persistent_filesystems != 0
        ):
            raise T09PilotError(
                "campaign requires one simultaneous instance, one empirical launch, "
                "and no filesystem"
            )

    def elapsed_seconds(self, *, billable_started_at: float, now: float) -> float:
        elapsed = now - billable_started_at
        if not math.isfinite(elapsed) or elapsed < 0:
            raise T09PilotError("campaign clock is unavailable or in the future")
        return elapsed

    def remaining_seconds(self, *, billable_started_at: float, now: float) -> float:
        return max(
            0.0,
            self.empirical_campaign_wall_seconds
            - self.elapsed_seconds(billable_started_at=billable_started_at, now=now),
        )

    def required_attempt_seconds(self, *, attempt_hard_wall_seconds: int) -> int:
        """Return the empirical admission envelope required by the Retry 5 contract."""

        if type(attempt_hard_wall_seconds) is not int or attempt_hard_wall_seconds <= 0:
            raise T09PilotError("attempt hard wall must be a positive integer")
        return (
            attempt_hard_wall_seconds
            + self.evidence_export_reserve_seconds
            + self.provider_termination_handoff_seconds
            + self.empirical_cleanup_reserve_seconds
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
            >= self.empirical_termination_cutoff_seconds
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


def git_file_sha256(
    repository: Path,
    commit: str,
    relative_path: str,
    *,
    maximum_bytes: int = 4_194_304,
) -> str:
    """Hash one finite Git blob without consulting the mutable working tree."""

    if re.fullmatch(r"[0-9a-f]{40}", commit) is None:
        raise T09PilotError("Git source commit is malformed")
    relative = Path(relative_path)
    if relative.is_absolute() or ".." in relative.parts:
        raise T09PilotError("Git source path is unsafe")
    object_name = f"{commit}:{relative.as_posix()}"
    try:
        size_result = subprocess.run(
            ["git", "cat-file", "-s", object_name],
            cwd=repository,
            check=True,
            capture_output=True,
            timeout=30,
        )
        size = int(size_result.stdout.decode("ascii").strip())
    except (OSError, subprocess.SubprocessError, UnicodeError, ValueError) as exc:
        raise T09PilotError("Git source blob size is unavailable") from exc
    if size <= 0 or size > maximum_bytes:
        raise T09PilotError("Git source blob exceeds its finite hash boundary")
    try:
        blob = subprocess.run(
            ["git", "cat-file", "blob", object_name],
            cwd=repository,
            check=True,
            capture_output=True,
            timeout=30,
        ).stdout
    except (OSError, subprocess.SubprocessError) as exc:
        raise T09PilotError("Git source blob is unavailable") from exc
    if len(blob) != size:
        raise T09PilotError("Git source blob size changed during hashing")
    return hashlib.sha256(blob).hexdigest()


def canonical_sha256(value: object) -> str:
    """Hash JSON-compatible data using the pilot canonicalization rule."""

    encoded = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def command_argv_sha256(argv: Sequence[str]) -> str:
    """Hash one exact ordered command argv using the frozen argv-only contract.

    The digest input is the UTF-8 encoding of the argv JSON array rendered with
    ``ensure_ascii=False``, no insignificant whitespace, and JSON key sorting enabled.
    Key sorting is inert for the declared array-of-strings surface but is retained to
    make this helper exactly reproduce the historical V11-V14 pilot canonicalizer.
    """

    if isinstance(argv, (str, bytes, bytearray)) or not isinstance(argv, Sequence):
        raise T09PilotError("command argv must be a nonempty sequence of strings")
    frozen_argv = tuple(argv)
    if not frozen_argv or any(not isinstance(item, str) for item in frozen_argv):
        raise T09PilotError("command argv must be a nonempty sequence of strings")
    if any("\0" in item for item in frozen_argv):
        raise T09PilotError("command argv members must not contain NUL bytes")
    encoded = json.dumps(
        list(frozen_argv),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def scientific_attempt_projection(evidence: Mapping[str, object]) -> dict[str, object]:
    """Project only deterministic scientific/evaluator evidence, not packaging metadata."""

    required = {
        "identity",
        "runtime",
        "timing",
        "command",
        "provider_calls",
        "browser_actions",
        "outcome",
        "evaluator",
        "cleanup",
        "h2k_optional_fields",
        "redaction",
    }
    if not required.issubset(evidence):
        raise T09PilotError("attempt evidence lacks its scientific projection surface")
    runtime = _strict_object(evidence["runtime"], context="attempt runtime projection")
    runtime_fields = (
        "giclab_commit",
        "reviewed_implementation_ancestor",
        "sira_commit",
        "python_version",
        "python_interpreter_path",
        "python_interpreter_sha256",
        "container_image_digest",
        "frozen_run_manifest_sha256",
        "qualification_id",
        "build_context_manifest_sha256",
        "installed_package_manifest_sha256",
        "chromium_executable_sha256",
        "patched_upstream_runner_sha256",
        "evaluator_overlay_manifest_sha256",
        "evaluator_overlay_entries_sha256",
        "evaluator_overlay_packages_sha256",
        "model_revision",
        "requested_service_tier",
        "returned_service_tiers",
        "browser_identity",
        "gpu_accounting",
    )
    if any(field not in runtime for field in runtime_fields):
        raise T09PilotError("attempt runtime projection is incomplete")
    return {
        "identity": evidence["identity"],
        "runtime": {field: runtime[field] for field in runtime_fields},
        "timing": evidence["timing"],
        "command": evidence["command"],
        "provider_calls": evidence["provider_calls"],
        "browser_actions": evidence["browser_actions"],
        "outcome": evidence["outcome"],
        "evaluator": evidence["evaluator"],
        "cleanup": evidence["cleanup"],
        "h2k_optional_fields": evidence["h2k_optional_fields"],
        "redaction": evidence["redaction"],
    }


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
    """The source-derived pre-entry binding for the one accepted V7 runtime."""

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
    regression_archive_staging_sha256: str
    qualified_real_evidence_regression_sha256: str
    local_finalizer_qualification_sha256: str
    local_finalizer_interpreter_dependency_manifest_sha256: str
    local_finalizer_interpreter_dependency_tree_sha256: str
    local_finalizer_evaluator_dependency_tree_sha256: str
    model_metadata_request_count: int
    model_task_request_count: int
    task_browser_action_count: int
    image_materialization_policy: Literal[
        "retained-import-or-one-fallback-build",
        "retained-import-only",
    ]
    build_count: int
    qualification_count: int
    empirical_entry_crossed: bool
    preflight_transition_mode: Literal["fresh", "replacement-launch"]
    preflight_resume_source_sha256: str | None
    preflight_resume_argv_sha256: str | None
    preflight_resume_transition_sha256: str | None
    preflight_failure_prefix_manifest_sha256: str | None
    preflight_prior_package_commit: str | None
    preflight_prior_plan_sha256: str | None
    preflight_prior_state_sha256: str | None
    preflight_transition_state_sha256: str | None
    preflight_prior_aggregate_sha256: str | None
    preflight_transition_aggregate_sha256: str | None
    preflight_retained_materialization_sha256: str | None
    launch_slot: int
    launch_count: int
    campaign_started_at_epoch: float
    owned_lambda_started_at_epoch: float
    first_pair_started_at_epoch: float
    prior_lambda_duration_seconds: float
    prior_lambda_cost_usd: float
    replacement_eligibility_sha256: str | None
    replacement_eligibility_preempirical_source_manifest_sha256: str | None
    normalized_slot2_authority_tree_manifest_sha256: str | None
    slot2_authority_sha256: str | None
    provider_entry_package_commit: str
    provider_package_transition_sha256: str | None
    slot1_failure_archive_sha256: str | None
    slot1_image_archive_sha256: str | None
    slot1_entry_receipt_sha256: str | None
    slot1_closeout_receipt_sha256: str | None
    image_import_count: int
    additional_build_count: int

    @classmethod
    def from_document(cls, value: object) -> RuntimeQualification:
        document = _strict_object(value, context="frozen runtime qualification")
        raw_plan_id = document.get("plan_id")
        if not isinstance(raw_plan_id, str):
            raise T09PilotError("frozen runtime qualification plan identity is missing")
        try:
            selected_provider_contract = provider_contract_for_plan_id(raw_plan_id)
        except T09ProviderContractError as exc:
            raise T09PilotError(
                "frozen runtime qualification plan identity is unsupported"
            ) from exc
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
            regression_archive_staging_sha256=_required_string(
                document.get("regression_archive_staging_sha256"),
                context="regression archive staging hash",
            ),
            qualified_real_evidence_regression_sha256=_required_string(
                document.get("qualified_real_evidence_regression_sha256"),
                context="qualified real-evidence regression hash",
            ),
            local_finalizer_qualification_sha256=_required_string(
                document.get("local_finalizer_qualification_sha256"),
                context="local finalizer qualification hash",
            ),
            local_finalizer_interpreter_dependency_manifest_sha256=_required_string(
                document.get("local_finalizer_interpreter_dependency_manifest_sha256"),
                context="local finalizer interpreter dependency-manifest hash",
            ),
            local_finalizer_interpreter_dependency_tree_sha256=_required_string(
                document.get("local_finalizer_interpreter_dependency_tree_sha256"),
                context="local finalizer interpreter dependency-tree hash",
            ),
            local_finalizer_evaluator_dependency_tree_sha256=_required_string(
                document.get("local_finalizer_evaluator_dependency_tree_sha256"),
                context="local finalizer evaluator dependency-tree hash",
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
            image_materialization_policy=cast(
                Literal[
                    "retained-import-or-one-fallback-build",
                    "retained-import-only",
                ],
                _required_string(
                    document.get("image_materialization_policy"),
                    context="image materialization policy",
                ),
            ),
            build_count=_required_int(document.get("build_count"), context="build count"),
            qualification_count=_required_int(
                document.get("qualification_count"), context="qualification count"
            ),
            empirical_entry_crossed=document.get("empirical_entry_crossed") is True,
            preflight_transition_mode=cast(
                Literal["fresh", "replacement-launch"],
                _required_string(
                    document.get("preflight_transition_mode"),
                    context="preflight transition mode",
                ),
            ),
            preflight_resume_source_sha256=cast(
                str | None, document.get("preflight_resume_source_sha256")
            ),
            preflight_resume_argv_sha256=cast(
                str | None, document.get("preflight_resume_argv_sha256")
            ),
            preflight_resume_transition_sha256=cast(
                str | None, document.get("preflight_resume_transition_sha256")
            ),
            preflight_failure_prefix_manifest_sha256=cast(
                str | None, document.get("preflight_failure_prefix_manifest_sha256")
            ),
            preflight_prior_package_commit=cast(
                str | None, document.get("preflight_prior_package_commit")
            ),
            preflight_prior_plan_sha256=cast(
                str | None, document.get("preflight_prior_plan_sha256")
            ),
            preflight_prior_state_sha256=cast(
                str | None, document.get("preflight_prior_state_sha256")
            ),
            preflight_transition_state_sha256=cast(
                str | None, document.get("preflight_transition_state_sha256")
            ),
            preflight_prior_aggregate_sha256=cast(
                str | None, document.get("preflight_prior_aggregate_sha256")
            ),
            preflight_transition_aggregate_sha256=cast(
                str | None, document.get("preflight_transition_aggregate_sha256")
            ),
            preflight_retained_materialization_sha256=cast(
                str | None, document.get("preflight_retained_materialization_sha256")
            ),
            launch_slot=_required_int(document.get("launch_slot"), context="launch slot"),
            launch_count=_required_int(document.get("launch_count"), context="launch count"),
            campaign_started_at_epoch=_required_number(
                document.get("campaign_started_at_epoch"), context="campaign start"
            ),
            owned_lambda_started_at_epoch=_required_number(
                document.get("owned_lambda_started_at_epoch"), context="owned Lambda start"
            ),
            first_pair_started_at_epoch=_required_number(
                document.get("first_pair_started_at_epoch"), context="first-pair start"
            ),
            prior_lambda_duration_seconds=_required_number(
                document.get("prior_lambda_duration_seconds"),
                context="prior Lambda duration",
            ),
            prior_lambda_cost_usd=_required_number(
                document.get("prior_lambda_cost_usd"), context="prior Lambda cost"
            ),
            replacement_eligibility_sha256=cast(
                str | None, document.get("replacement_eligibility_sha256")
            ),
            replacement_eligibility_preempirical_source_manifest_sha256=cast(
                str | None,
                document.get("replacement_eligibility_preempirical_source_manifest_sha256"),
            ),
            normalized_slot2_authority_tree_manifest_sha256=cast(
                str | None,
                document.get("normalized_slot2_authority_tree_manifest_sha256"),
            ),
            slot2_authority_sha256=cast(str | None, document.get("slot2_authority_sha256")),
            provider_entry_package_commit=_required_string(
                document.get("provider_entry_package_commit"),
                context="provider entry package commit",
            ),
            provider_package_transition_sha256=cast(
                str | None, document.get("provider_package_transition_sha256")
            ),
            slot1_failure_archive_sha256=cast(
                str | None, document.get("slot1_failure_archive_sha256")
            ),
            slot1_image_archive_sha256=cast(str | None, document.get("slot1_image_archive_sha256")),
            slot1_entry_receipt_sha256=cast(str | None, document.get("slot1_entry_receipt_sha256")),
            slot1_closeout_receipt_sha256=cast(
                str | None, document.get("slot1_closeout_receipt_sha256")
            ),
            image_import_count=_required_int(
                document.get("image_import_count"), context="image import count"
            ),
            additional_build_count=_required_int(
                document.get("additional_build_count"), context="additional build count"
            ),
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
            result.regression_archive_staging_sha256,
            result.qualified_real_evidence_regression_sha256,
            result.local_finalizer_qualification_sha256,
            result.local_finalizer_interpreter_dependency_manifest_sha256,
            result.local_finalizer_interpreter_dependency_tree_sha256,
            result.local_finalizer_evaluator_dependency_tree_sha256,
        )
        if (
            document.get("schema_version") != "0.1.0"
            or document.get("plan_id") != selected_provider_contract.plan_id
            or result.manifest_id != selected_provider_contract.frozen_run_manifest_id
            or result.qualification_id != selected_provider_contract.active_image_qualification_id
            or re.fullmatch(r"[a-f0-9]{40}", result.clean_package_commit) is None
            or re.fullmatch(r"sha256:[a-f0-9]{64}", result.replacement_image_id) is None
            or result.historical_image_id != HISTORICAL_IMAGE_ID
            or result.python_interpreter_path != "/opt/sira/.venv/bin/python"
            or any(_HEX64.fullmatch(item) is None for item in hashes)
            or result.model_metadata_request_count != 1
            or result.model_task_request_count != 0
            or result.task_browser_action_count != 0
            or result.image_materialization_policy
            not in {
                "retained-import-or-one-fallback-build",
                "retained-import-only",
            }
            or result.build_count not in {0, 1}
            or result.qualification_count != 1
            or document.get("empirical_entry_crossed") is not False
            or document.get("post_entry_code_science_image_freeze") is not True
            or result.preflight_transition_mode not in {"fresh", "replacement-launch"}
            or result.launch_slot not in range(1, 9)
            or result.launch_count != result.launch_slot
            or re.fullmatch(r"[a-f0-9]{40}", result.provider_entry_package_commit) is None
            or result.campaign_started_at_epoch <= 0
            or result.owned_lambda_started_at_epoch > result.campaign_started_at_epoch
            or result.first_pair_started_at_epoch < result.campaign_started_at_epoch
            or result.prior_lambda_duration_seconds < 0
            or result.prior_lambda_cost_usd < 0
        ):
            raise T09PilotError("frozen runtime qualification contract drifted")
        recovery_hashes = (
            result.preflight_resume_source_sha256,
            result.preflight_resume_argv_sha256,
            result.preflight_resume_transition_sha256,
            result.preflight_failure_prefix_manifest_sha256,
            result.preflight_prior_plan_sha256,
            result.preflight_prior_state_sha256,
            result.preflight_transition_state_sha256,
            result.preflight_prior_aggregate_sha256,
            result.preflight_transition_aggregate_sha256,
            result.preflight_retained_materialization_sha256,
        )
        if result.preflight_transition_mode == "fresh":
            if (
                result.launch_slot != 1
                or result.image_materialization_policy != "retained-import-or-one-fallback-build"
                or result.prior_lambda_duration_seconds != 0
                or result.prior_lambda_cost_usd != 0
                or result.replacement_eligibility_sha256 is not None
                or result.replacement_eligibility_preempirical_source_manifest_sha256 is not None
                or result.normalized_slot2_authority_tree_manifest_sha256 is not None
                or result.slot2_authority_sha256 is not None
                or (
                    result.provider_entry_package_commit != result.clean_package_commit
                    and (
                        not isinstance(result.provider_package_transition_sha256, str)
                        or _HEX64.fullmatch(result.provider_package_transition_sha256) is None
                    )
                )
                or (
                    result.provider_entry_package_commit == result.clean_package_commit
                    and result.provider_package_transition_sha256 is not None
                )
                or result.preflight_prior_package_commit is not None
                or any(item is not None for item in recovery_hashes)
            ):
                raise T09PilotError("fresh preflight retained resume authority")
        else:
            replacement_hashes = (
                result.replacement_eligibility_sha256,
                result.replacement_eligibility_preempirical_source_manifest_sha256,
                result.normalized_slot2_authority_tree_manifest_sha256,
            )
            if (
                result.launch_slot not in range(2, 9)
                or result.launch_count != result.launch_slot
                or result.image_materialization_policy != "retained-import-only"
                or result.build_count != 0
                or result.image_import_count != 1
                or result.prior_lambda_duration_seconds <= 0
                or result.prior_lambda_cost_usd <= 0
                or result.preflight_prior_package_commit is not None
                or any(item is not None for item in recovery_hashes)
                or any(
                    not isinstance(item, str) or _HEX64.fullmatch(item) is None
                    for item in replacement_hashes
                )
                or not isinstance(result.slot2_authority_sha256, str)
                or _HEX64.fullmatch(result.slot2_authority_sha256) is None
                or (
                    result.provider_entry_package_commit != result.clean_package_commit
                    and (
                        not isinstance(result.provider_package_transition_sha256, str)
                        or _HEX64.fullmatch(result.provider_package_transition_sha256) is None
                    )
                )
                or (
                    result.provider_entry_package_commit == result.clean_package_commit
                    and result.provider_package_transition_sha256 is not None
                )
            ):
                raise T09PilotError("replacement-launch qualification binding drifted")
        if (
            result.additional_build_count != 0
            or (result.build_count == 0 and result.image_import_count != 1)
            or (result.build_count == 1 and result.image_import_count != 0)
        ):
            raise T09PilotError("V7 image load/build selection drifted")
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
        if self.run_id not in _AUTONOMOUS_ATTEMPT_IDS:
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
        if self.max_lambda_duration_seconds != 14_400:
            raise T09PilotError("empirical Lambda wall must remain 14,400 seconds")
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
    plan_id: str
    provider_contract_version: str
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
    raw_plan_id = document.get("plan_id")
    if not isinstance(raw_plan_id, str):
        raise T09PilotError("execution contract plan identity is missing")
    try:
        selected_provider_contract = provider_contract_for_plan_id(raw_plan_id)
    except T09ProviderContractError as exc:
        raise T09PilotError("execution contract plan identity is unsupported") from exc
    expected_identity = {
        "schema_version": "0.5.0",
        "plan_id": selected_provider_contract.plan_id,
        "experiment_id": EXPERIMENT_ID,
        "sira_commit": SIRA_COMMIT,
        "model_revision": MODEL_REVISION,
        "service_tier": SERVICE_TIER,
        "authorized": False,
        "authorization_reference": AUTHORIZATION_REFERENCE,
        "execution_eligibility": "blocked-until-fresh-category-3-authorization",
    }
    for field, expected in expected_identity.items():
        if document.get(field) != expected:
            raise T09PilotError(f"execution contract {field} drifted")

    identities = _strict_object(document.get("identities"), context="pilot identities")
    expected_pilot_identities: dict[str, object] = {
        "host_run_id": selected_provider_contract.host_run_id,
        "evaluator_run_ids": list(selected_provider_contract.evaluator_run_ids),
        "runtime_qualification_id": selected_provider_contract.active_image_qualification_id,
        "local_finalizer_qualification_id": (
            selected_provider_contract.local_finalizer_qualification_id
        ),
        "frozen_run_manifest_id": selected_provider_contract.frozen_run_manifest_id,
        "evidence_archive_id": selected_provider_contract.evidence_archive_id,
        "evidence_stage_id": selected_provider_contract.evidence_stage_id,
    }
    for field, expected in expected_pilot_identities.items():
        if identities.get(field) != expected:
            raise T09PilotError(f"execution contract {field} identity drifted")

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
    if tuple(item.run_id for item in attempts) != selected_provider_contract.run_ids:
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
        preflight_iteration_wall_seconds=_required_int(
            raw_campaign.get("preflight_iteration_wall_seconds"),
            context="preflight iteration wall",
        ),
        maximum_preflight_instance_active_seconds=_required_int(
            raw_campaign.get("maximum_preflight_instance_active_seconds"),
            context="preflight instance active cap",
        ),
        maximum_cumulative_preflight_active_seconds=_required_int(
            raw_campaign.get("maximum_cumulative_preflight_active_seconds"),
            context="cumulative preflight active cap",
        ),
        maximum_preflight_provider_cost_usd=_required_number(
            raw_campaign.get("maximum_preflight_provider_cost_usd"),
            context="preflight provider cost cap",
        ),
        max_preflight_launch_count=_required_int(
            raw_campaign.get("max_preflight_launch_count"),
            context="preflight launch cap",
        ),
        failed_preflight_termination_dispatch_seconds=_required_int(
            raw_campaign.get("failed_preflight_termination_dispatch_seconds"),
            context="failed-preflight termination dispatch",
        ),
        empirical_campaign_wall_seconds=_required_int(
            raw_campaign.get("empirical_campaign_wall_seconds"),
            context="empirical campaign wall",
        ),
        evidence_export_reserve_seconds=_required_int(
            raw_campaign.get("evidence_export_reserve_seconds"),
            context="evidence export reserve",
        ),
        provider_termination_handoff_seconds=_required_int(
            raw_campaign.get("provider_termination_handoff_seconds"),
            context="provider termination handoff",
        ),
        empirical_cleanup_reserve_seconds=_required_int(
            raw_campaign.get("empirical_cleanup_reserve_seconds"),
            context="empirical cleanup reserve",
        ),
        empirical_termination_cutoff_seconds=_required_int(
            raw_campaign.get("empirical_termination_cutoff_seconds"),
            context="empirical termination cutoff",
        ),
        maximum_empirical_provider_cost_usd=_required_number(
            raw_campaign.get("maximum_empirical_provider_cost_usd"),
            context="empirical provider cost cap",
        ),
        max_empirical_launch_count=_required_int(
            raw_campaign.get("max_empirical_launch_count"), context="empirical launch cap"
        ),
        max_lambda_instances=_required_int(
            raw_campaign.get("max_lambda_instances"), context="Lambda instance cap"
        ),
        persistent_filesystems=_required_int(
            raw_campaign.get("persistent_filesystems"), context="persistent filesystem cap"
        ),
    )
    if limits.max_total_wall_seconds != campaign.empirical_campaign_wall_seconds:
        raise T09PilotError("runtime limits and three-clock lifecycle disagree")
    return PilotExecutionContract(
        path=path.resolve(strict=True),
        sha256=expected_sha256,
        plan_id=selected_provider_contract.plan_id,
        provider_contract_version=selected_provider_contract.version,
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


def load_aggregate_usage(
    path: Path,
    *,
    contract_sha256: str,
    plan_id: str,
) -> ProviderBudgetUsage:
    """Load the prior sequential-attempt aggregate or return a typed zero state."""

    if not path.exists():
        return ProviderBudgetUsage()
    document = load_json_object(path, context="aggregate budget ledger")
    if (
        document.get("schema_version") not in {"0.1.0", "0.2.0"}
        or document.get("plan_id") != plan_id
    ):
        raise T09PilotError("aggregate budget ledger identity drifted")
    if document.get("execution_contract_sha256") != contract_sha256:
        raise T09PilotError("aggregate budget ledger contract binding drifted")
    if document.get("unreconciled_provider_attempts") != 0:
        raise T09PilotError("an unreconciled provider attempt forbids another condition")
    if document.get("schema_version") == "0.2.0" and document.get("unknown_outcomes") != 0:
        raise T09PilotError("an unknown provider outcome forbids another condition")
    return usage_from_document(document.get("usage"))


def load_aggregate_observed_usage(
    path: Path,
    *,
    contract_sha256: str,
    plan_id: str,
) -> ProviderBudgetUsage:
    """Load the response-backed aggregate lower bound from the durable ledger."""

    if not path.exists():
        return ProviderBudgetUsage()
    document = load_json_object(path, context="aggregate budget ledger")
    if (
        document.get("schema_version") not in {"0.1.0", "0.2.0"}
        or document.get("plan_id") != plan_id
    ):
        raise T09PilotError("aggregate budget ledger identity drifted")
    if document.get("execution_contract_sha256") != contract_sha256:
        raise T09PilotError("aggregate budget ledger contract binding drifted")
    if document.get("schema_version") == "0.1.0":
        return usage_from_document(document.get("usage"))
    return usage_from_document(document.get("observed_lower_bound"))


def write_aggregate_usage(
    path: Path,
    *,
    contract_sha256: str,
    plan_id: str,
    usage: ProviderBudgetUsage,
    unreconciled_provider_attempts: int,
    observed_usage: ProviderBudgetUsage | None = None,
    unknown_outcomes: int = 0,
) -> None:
    """Durably persist aggregate usage after every provider/action transition."""

    if unreconciled_provider_attempts < 0 or unknown_outcomes < 0:
        raise T09PilotError("provider outcome counts cannot be negative")
    observed = observed_usage if observed_usage is not None else usage
    document = {
        "schema_version": "0.2.0",
        "plan_id": plan_id,
        "execution_contract_sha256": contract_sha256,
        "unreconciled_provider_attempts": unreconciled_provider_attempts,
        "unknown_outcomes": unknown_outcomes,
        "accounting_basis": {
            "usage": "reservation-inclusive-charged-upper-bound",
            "observed_lower_bound": "response-receipt-backed-lower-bound",
        },
        "usage": usage_to_document(usage),
        "observed_lower_bound": usage_to_document(observed),
    }
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    _write_json_atomic(path, document)


def initialize_pilot_state(
    path: Path,
    *,
    provider_contract: T09ProviderContract,
    execution_contract_sha256: str,
    pilot_started_at_epoch: float,
    lambda_started_at_epoch: float,
) -> None:
    """Create the one sequential attempt ledger during an authorized preflight."""

    try:
        retained_contract = provider_contract_for_plan_id(provider_contract.plan_id)
    except T09ProviderContractError as exc:
        raise T09PilotError("pilot initialization contract is unsupported") from exc
    if retained_contract is not provider_contract:
        raise T09PilotError("pilot initialization requires an exact retained contract")
    if path.exists():
        raise T09PilotError("pilot state already exists; it cannot be reset for a retry")
    for value in (pilot_started_at_epoch, lambda_started_at_epoch):
        if not math.isfinite(value) or value <= 0:
            raise T09PilotError("pilot and Lambda start epochs must be positive and finite")
    document = {
        "schema_version": "0.2.0",
        "plan_id": provider_contract.plan_id,
        "execution_contract_sha256": execution_contract_sha256,
        "pilot_started_at_epoch": pilot_started_at_epoch,
        "lambda_started_at_epoch": lambda_started_at_epoch,
        "campaign_started_at_epoch": pilot_started_at_epoch,
        "owned_lambda_started_at_epoch": lambda_started_at_epoch,
        "prior_campaign_lambda_duration_seconds": 0.0,
        "prior_campaign_lambda_cost_usd": 0.0,
        "first_pair_started_at_epoch": pilot_started_at_epoch,
        "second_pair_started_at_epoch": None,
        "empirical_attempts_entered": [],
        "supervised_release_bindings": {},
        "unreleased_supervised_release_reclassifications": {},
        "condition_start_reservation": None,
        "nonempirical_infrastructure_attempts_consumed": [],
        "raw_attempts_complete": [],
        "raw_attempt_bindings": {},
        "attempts_completed": [],
        "attempt_finalizations": {},
        "attempt_finalization_history": {},
        "first_pair_decision": None,
        "first_pair_checkpoint_binding": None,
        "first_pair_selection_drift_detected": False,
        "actual_credential_exposure_detected": False,
        "credential_safety_stop_detected": False,
        "core_safety_stop_detected": False,
        "essential_failure_seals": {},
    }
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    _write_json_atomic(path, document)


def transition_zero_usage_preflight_state(
    state: object,
    aggregate: object,
    *,
    prior_execution_contract_sha256: str,
    next_execution_contract_sha256: str,
) -> tuple[dict[str, object], dict[str, object]]:
    """Rebind an exact zero-use preflight prefix without resetting its clocks."""

    prior_state = _strict_object(state, context="prior preflight pilot state")
    prior_aggregate = _strict_object(aggregate, context="prior aggregate ledger")
    selected_contract = _state_provider_contract(prior_state)
    state_keys = {
        "schema_version",
        "plan_id",
        "execution_contract_sha256",
        "pilot_started_at_epoch",
        "lambda_started_at_epoch",
        "first_pair_started_at_epoch",
        "second_pair_started_at_epoch",
        "empirical_attempts_entered",
        "raw_attempts_complete",
        "raw_attempt_bindings",
        "attempts_completed",
        "attempt_finalizations",
        "attempt_finalization_history",
        "first_pair_decision",
        "first_pair_checkpoint_binding",
        "first_pair_selection_drift_detected",
    }
    started = prior_state.get("lambda_started_at_epoch")
    pilot_started = prior_state.get("pilot_started_at_epoch")
    if (
        set(prior_state) != state_keys
        or prior_state.get("schema_version") != "0.2.0"
        or prior_state.get("plan_id") != selected_contract.plan_id
        or prior_state.get("execution_contract_sha256") != prior_execution_contract_sha256
        or not isinstance(started, (int, float))
        or isinstance(started, bool)
        or not math.isfinite(float(started))
        or not isinstance(pilot_started, (int, float))
        or isinstance(pilot_started, bool)
        or float(pilot_started) != float(started)
        or prior_state.get("first_pair_started_at_epoch") is not None
        or prior_state.get("second_pair_started_at_epoch") is not None
        or prior_state.get("empirical_attempts_entered") != []
        or prior_state.get("raw_attempts_complete") != []
        or prior_state.get("raw_attempt_bindings") != {}
        or prior_state.get("attempts_completed") != []
        or prior_state.get("attempt_finalizations") != {}
        or prior_state.get("attempt_finalization_history") != {}
        or prior_state.get("first_pair_decision") is not None
        or prior_state.get("first_pair_checkpoint_binding") is not None
        or prior_state.get("first_pair_selection_drift_detected") is not False
    ):
        raise T09PilotError("prior preflight state is not an exact zero-use prefix")
    zero_usage = usage_to_document(ProviderBudgetUsage())
    if prior_aggregate != {
        "schema_version": "0.1.0",
        "plan_id": selected_contract.plan_id,
        "execution_contract_sha256": prior_execution_contract_sha256,
        "unreconciled_provider_attempts": 0,
        "usage": zero_usage,
    }:
        raise T09PilotError("prior aggregate ledger is not exact zero usage")
    next_state = copy.deepcopy(prior_state)
    next_state["execution_contract_sha256"] = next_execution_contract_sha256
    next_aggregate = copy.deepcopy(prior_aggregate)
    next_aggregate["execution_contract_sha256"] = next_execution_contract_sha256
    return next_state, next_aggregate


def _write_json_atomic(path: Path, document: Mapping[str, object]) -> None:
    """Replace one mutable control document and durably commit its directory entry."""

    encoded = (json.dumps(document, indent=2, sort_keys=True) + "\n").encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.parent / f".{path.name}.{os.getpid()}.{time.time_ns()}.tmp"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(temporary, flags, 0o600)
    published = False
    try:
        offset = 0
        while offset < len(encoded):
            written = os.write(descriptor, encoded[offset:])
            if written <= 0:
                raise OSError("atomic control write made no progress")
            offset += written
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = -1
        os.replace(temporary, path)
        published = True
        parent_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
        parent_descriptor = os.open(path.parent, parent_flags)
        try:
            os.fsync(parent_descriptor)
        finally:
            os.close(parent_descriptor)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        if not published:
            with contextlib.suppress(FileNotFoundError):
                temporary.unlink()


_FINALIZATION_SELECTION_FIELDS = {
    "finalizer_execution_mode",
    "finalizer_runtime_qualification_sha256",
    "finalizer_source_sha256",
    "finalizer_projection_source_sha256",
    "finalizer_commit",
    "finalizer_dependency_manifest_sha256",
    "evaluator_contract_sha256",
    "interpreter",
    "interpreter_sha256",
    "semantic_projection_sha256",
    "finalized_output_root",
    "finalization_complete_sha256",
}

_FINALIZER_UNIFORMITY_FIELDS = (
    "finalizer_execution_mode",
    "finalizer_runtime_qualification_sha256",
    "finalizer_source_sha256",
    "finalizer_projection_source_sha256",
    "finalizer_commit",
    "finalizer_dependency_manifest_sha256",
    "evaluator_contract_sha256",
    "interpreter",
    "interpreter_sha256",
)


def _selection_receipt_directory(
    path: Path,
    run_id: str,
    *,
    contract: T09ProviderContract,
) -> Path:
    if run_id not in contract.run_ids:
        raise T09PilotError("selection receipt run identity is unknown")
    return path.parent / "finalization-selections" / run_id


def _write_json_exclusive(path: Path, document: Mapping[str, object]) -> None:
    encoded = (json.dumps(document, allow_nan=False, indent=2, sort_keys=True) + "\n").encode()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        offset = 0
        while offset < len(encoded):
            written = os.write(descriptor, encoded[offset:])
            if written <= 0:
                raise T09PilotError("selection receipt write made no progress")
            offset += written
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    directory = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def _selection_receipts(
    path: Path,
    *,
    contract: T09ProviderContract,
) -> dict[str, list[tuple[dict[str, object], str]]]:
    result: dict[str, list[tuple[dict[str, object], str]]] = {}
    for run_id in contract.run_ids:
        directory = _selection_receipt_directory(path, run_id, contract=contract)
        if not directory.exists():
            continue
        if directory.is_symlink() or not directory.is_dir():
            raise T09PilotError("selection receipt directory is unsafe")
        receipts: list[tuple[dict[str, object], str]] = []
        for ordinal, receipt_path in enumerate(sorted(directory.iterdir()), start=1):
            metadata = receipt_path.stat(follow_symlinks=False)
            if (
                receipt_path.name != f"selection-{ordinal:04d}.json"
                or receipt_path.is_symlink()
                or not stat.S_ISREG(metadata.st_mode)
                or metadata.st_uid != os.getuid()
                or metadata.st_nlink != 1
                or stat.S_IMODE(metadata.st_mode) != 0o600
            ):
                raise T09PilotError("selection receipt metadata or sequence is unsafe")
            receipt = load_json_object(receipt_path, context="finalization selection receipt")
            selection = receipt.get("selection")
            if (
                set(receipt) != {"schema_version", "plan_id", "run_id", "ordinal", "selection"}
                or receipt.get("schema_version") != "0.1.0"
                or receipt.get("plan_id") != contract.plan_id
                or receipt.get("run_id") != run_id
                or receipt.get("ordinal") != ordinal
                or not isinstance(selection, dict)
                or set(selection) != _FINALIZATION_SELECTION_FIELDS
            ):
                raise T09PilotError("selection receipt content is malformed")
            receipts.append((receipt, file_sha256(receipt_path)))
        if receipts:
            result[run_id] = receipts
    return result


def _selection_closure_sha256(selection: Mapping[str, object]) -> str:
    if any(field not in selection for field in _FINALIZER_UNIFORMITY_FIELDS):
        raise T09PilotError("selected finalizer closure is incomplete")
    return canonical_sha256({field: selection[field] for field in _FINALIZER_UNIFORMITY_FIELDS})


def _current_selection_receipt_hashes(
    path: Path,
    *,
    run_ids: Sequence[str],
    contract: T09ProviderContract,
) -> dict[str, str]:
    receipts = _selection_receipts(path, contract=contract)
    result: dict[str, str] = {}
    for run_id in run_ids:
        retained = receipts.get(run_id)
        if not retained:
            raise T09PilotError("selected finalization lacks its append-only receipt")
        result[run_id] = retained[-1][1]
    return result


def _load_pilot_state(
    path: Path,
    *,
    contract_sha256: str,
    allow_one_pending_selection_receipt: bool = False,
) -> dict[str, object]:
    state = load_json_object(path, context="pilot attempt state")
    contract = _state_provider_contract(state)
    attempt_order = contract.run_ids
    if (
        state.get("schema_version") != "0.2.0"
        or state.get("plan_id") != contract.plan_id
        or state.get("execution_contract_sha256") != contract_sha256
    ):
        raise T09PilotError("pilot attempt-state identity drifted")
    for field in ("empirical_attempts_entered", "raw_attempts_complete", "attempts_completed"):
        value = state.get(field)
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise T09PilotError(f"pilot state {field} is malformed")
        if len(value) != len(set(value)) or any(item not in attempt_order for item in value):
            raise T09PilotError(f"pilot state {field} is not a unique frozen-order subset")
        if value != [item for item in attempt_order if item in value]:
            raise T09PilotError(f"pilot state {field} is not in frozen order")
    supervised_release_bindings = state.get("supervised_release_bindings")
    entered_with_release = cast(list[str], state["empirical_attempts_entered"])
    if (
        not isinstance(supervised_release_bindings, dict)
        or set(supervised_release_bindings) != set(entered_with_release)
        or any(
            run_id not in attempt_order
            or not isinstance(digest, str)
            or _HEX64.fullmatch(digest) is None
            for run_id, digest in supervised_release_bindings.items()
        )
    ):
        raise T09PilotError("pilot supervised-release bindings are malformed")
    unreleased_reclassifications = state.get("unreleased_supervised_release_reclassifications")
    if not isinstance(unreleased_reclassifications, dict) or any(
        run_id not in attempt_order
        or not isinstance(binding, dict)
        or set(binding) != {"start_intent_sha256", "supervised_release_receipt_sha256"}
        or any(
            not isinstance(digest, str) or _HEX64.fullmatch(digest) is None
            for digest in binding.values()
        )
        for run_id, binding in unreleased_reclassifications.items()
    ):
        raise T09PilotError("pilot unreleased-entry reclassification bindings are malformed")
    start_reservation = state.get("condition_start_reservation")
    if start_reservation is not None:
        reserved_run_id = (
            start_reservation.get("run_id") if isinstance(start_reservation, dict) else None
        )
        start_digest = (
            start_reservation.get("start_intent_sha256")
            if isinstance(start_reservation, dict)
            else None
        )
        pending_empirical_commit = (
            isinstance(start_reservation, dict)
            and set(start_reservation)
            == {
                "run_id",
                "start_intent_sha256",
                "phase",
                "supervised_release_receipt_sha256",
            }
            and start_reservation.get("phase") == "empirical-state-committed"
            and entered_with_release
            and reserved_run_id == entered_with_release[-1]
            and start_reservation.get("supervised_release_receipt_sha256")
            == supervised_release_bindings.get(reserved_run_id)
        )
        pending_start = (
            isinstance(start_reservation, dict)
            and set(start_reservation) == {"run_id", "start_intent_sha256"}
            and len(entered_with_release) < len(attempt_order)
            and reserved_run_id == attempt_order[len(entered_with_release)]
            and reserved_run_id not in entered_with_release
        )
        if (
            not (pending_start or pending_empirical_commit)
            or not isinstance(start_digest, str)
            or _HEX64.fullmatch(start_digest) is None
        ):
            raise T09PilotError("pilot condition-start reservation is malformed")
    nonempirical_consumed = state.get("nonempirical_infrastructure_attempts_consumed")
    if (
        not isinstance(nonempirical_consumed, list)
        or not all(
            isinstance(item, str) and item in attempt_order for item in nonempirical_consumed
        )
        or len(nonempirical_consumed) > 1
        or len(nonempirical_consumed) != len(set(nonempirical_consumed))
    ):
        raise T09PilotError("pilot non-empirical consumed-attempt state is malformed")
    entered_for_failure = cast(list[str], state["empirical_attempts_entered"])
    if nonempirical_consumed and (
        nonempirical_consumed[0] != attempt_order[len(entered_for_failure)]
        or nonempirical_consumed[0] in entered_for_failure
    ):
        raise T09PilotError("pilot non-empirical failure is not the next frozen attempt")
    if set(unreleased_reclassifications) - set(nonempirical_consumed):
        raise T09PilotError("unreleased-entry reclassification lacks consumed failure state")
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
    if any(
        set(selection) != _FINALIZATION_SELECTION_FIELDS for selection in finalizations.values()
    ):
        raise T09PilotError("pilot selected finalization closure is malformed")
    history = state.get("attempt_finalization_history")
    if not isinstance(history, dict) or not all(
        isinstance(key, str)
        and isinstance(value, list)
        and all(isinstance(item, str) and _HEX64.fullmatch(item) is not None for item in value)
        for key, value in history.items()
    ):
        raise T09PilotError("pilot state finalization history is malformed")
    if set(history) != set(finalizations):
        raise T09PilotError("pilot state is not the projection of its selection history")
    receipts = _selection_receipts(path, contract=contract)
    pending_count = 0
    for run_id in set(history) | set(receipts):
        state_hashes = history.get(run_id, [])
        receipt_items = receipts.get(run_id, [])
        receipt_hashes = [digest for _document, digest in receipt_items]
        if receipt_hashes == state_hashes:
            continue
        if (
            allow_one_pending_selection_receipt
            and receipt_hashes[:-1] == state_hashes
            and len(receipt_hashes) == len(state_hashes) + 1
        ):
            pending_count += 1
            continue
        raise T09PilotError("pilot finalization history drifted from append-only receipts")
    if pending_count > 1:
        raise T09PilotError("multiple unprojected selection receipts are not recoverable")
    for run_id, selection in finalizations.items():
        receipt_items = receipts.get(run_id, [])
        projected_count = len(history.get(run_id, []))
        if (
            projected_count < 1
            or receipt_items[projected_count - 1][0].get("selection") != selection
        ):
            raise T09PilotError("selected finalization is not receipt-backed")
    if not isinstance(state.get("first_pair_selection_drift_detected"), bool):
        raise T09PilotError("pilot checkpoint drift state is malformed")
    if not isinstance(state.get("actual_credential_exposure_detected", False), bool):
        raise T09PilotError("pilot credential-exposure state is malformed")
    if not isinstance(state.get("credential_safety_stop_detected", False), bool):
        raise T09PilotError("pilot credential-safety-stop state is malformed")
    if not isinstance(state.get("core_safety_stop_detected", False), bool):
        raise T09PilotError("pilot core-safety-stop state is malformed")
    essential_failure_seals = state.get("essential_failure_seals", {})
    if not isinstance(essential_failure_seals, dict) or any(
        run_id not in attempt_order
        or not isinstance(binding, dict)
        or set(binding) != {"manifest_sha256", "receipt_sha256"}
        or any(
            not isinstance(value, str) or _HEX64.fullmatch(value) is None
            for value in binding.values()
        )
        for run_id, binding in essential_failure_seals.items()
    ):
        raise T09PilotError("pilot essential-failure seal state is malformed")
    if not set(essential_failure_seals).issubset(
        set(cast(list[str], state["empirical_attempts_entered"]))
        | set(cast(list[str], nonempirical_consumed))
    ):
        raise T09PilotError("pilot essential-failure seal lacks a consumed attempt authority")
    checkpoint_binding = state.get("first_pair_checkpoint_binding")
    if checkpoint_binding is not None and not isinstance(checkpoint_binding, dict):
        raise T09PilotError("pilot checkpoint binding is malformed")
    checkpoint_decision = state.get("first_pair_decision")
    checkpoint_decision_sha256 = state.get("first_pair_decision_sha256")
    if checkpoint_decision is None:
        if checkpoint_binding is not None or checkpoint_decision_sha256 is not None:
            raise T09PilotError("pilot checkpoint state exists without a decision")
    elif (
        checkpoint_decision not in {"continue-to-task-b", "stop-before-task-b"}
        or not isinstance(checkpoint_binding, dict)
        or not isinstance(checkpoint_decision_sha256, str)
        or _HEX64.fullmatch(checkpoint_decision_sha256) is None
        or cast(list[str], state["attempts_completed"])[:2] != list(attempt_order[:2])
    ):
        raise T09PilotError("pilot checkpoint decision lacks its typed Task A binding")
    if checkpoint_binding is not None:
        if set(checkpoint_binding) != {
            "selection_receipt_sha256s",
            "selection_complete_sha256s",
            "semantic_projection_sha256s",
            "selected_closure_sha256",
            "finalizer_closure_valid",
            "decision_sha256",
            "decision_receipt_path",
            "decision_receipt_sha256",
            "first_pair_started_at_epoch",
            "second_pair_started_at_epoch",
            "decided_at_epoch",
        }:
            raise T09PilotError("pilot checkpoint binding field set drifted")
        checkpoint_receipt_hashes = checkpoint_binding.get("selection_receipt_sha256s")
        completion_hashes = checkpoint_binding.get("selection_complete_sha256s")
        semantic_hashes = checkpoint_binding.get("semantic_projection_sha256s")
        if not all(
            isinstance(value, dict) and set(value) == set(attempt_order[:2])
            for value in (checkpoint_receipt_hashes, completion_hashes, semantic_hashes)
        ):
            raise T09PilotError("pilot checkpoint attempt binding is malformed")
        assert isinstance(checkpoint_receipt_hashes, dict)
        assert isinstance(completion_hashes, dict)
        assert isinstance(semantic_hashes, dict)
        bound_checkpoint_selections: list[dict[str, object]] = []
        for run_id in attempt_order[:2]:
            receipt_sha256 = checkpoint_receipt_hashes.get(run_id)
            matching = [
                document
                for document, digest in receipts.get(run_id, [])
                if digest == receipt_sha256
            ]
            matching_selection = matching[0].get("selection") if len(matching) == 1 else None
            if (
                not isinstance(receipt_sha256, str)
                or _HEX64.fullmatch(receipt_sha256) is None
                or len(matching) != 1
                or not isinstance(matching_selection, dict)
                or matching_selection.get("finalization_complete_sha256")
                != completion_hashes.get(run_id)
                or matching_selection.get("semantic_projection_sha256")
                != semantic_hashes.get(run_id)
            ):
                raise T09PilotError("pilot checkpoint is not backed by exact selection receipts")
            bound_checkpoint_selections.append(cast(dict[str, object], matching_selection))
        for field in (
            "selected_closure_sha256",
            "decision_sha256",
            "decision_receipt_sha256",
        ):
            value = checkpoint_binding.get(field)
            if not isinstance(value, str) or _HEX64.fullmatch(value) is None:
                raise T09PilotError("pilot checkpoint hash binding is malformed")
        closure_valid = checkpoint_binding.get("finalizer_closure_valid")
        selected_closures = {
            _selection_closure_sha256(selection) for selection in bound_checkpoint_selections
        }
        if (
            type(closure_valid) is not bool
            or closure_valid is not (len(selected_closures) == 1)
            or (checkpoint_decision == "continue-to-task-b" and not closure_valid)
        ):
            raise T09PilotError("pilot checkpoint finalizer closure binding drifted")
        decision_receipt_name = checkpoint_binding.get("decision_receipt_path")
        if decision_receipt_name != "first-pair-checkpoint-decision.json" or not isinstance(
            decision_receipt_name, str
        ):
            raise T09PilotError("pilot checkpoint decision receipt path drifted")
        decision_receipt = path.parent / decision_receipt_name
        try:
            decision_metadata = decision_receipt.stat(follow_symlinks=False)
        except OSError as exc:
            raise T09PilotError("pilot checkpoint decision receipt is unavailable") from exc
        if (
            decision_receipt.is_symlink()
            or not stat.S_ISREG(decision_metadata.st_mode)
            or decision_metadata.st_uid != os.getuid()
            or decision_metadata.st_nlink != 1
            or stat.S_IMODE(decision_metadata.st_mode) != 0o600
            or file_sha256(decision_receipt) != checkpoint_binding.get("decision_receipt_sha256")
        ):
            raise T09PilotError("pilot checkpoint decision receipt identity drifted")
        decision_document = load_json_object(
            decision_receipt,
            context="first-pair checkpoint decision receipt",
        )
        if (
            canonical_sha256(decision_document) != checkpoint_binding.get("decision_sha256")
            or (
                state.get("first_pair_selection_drift_detected") is False
                and decision_document.get("decision") != checkpoint_decision
            )
            or (
                state.get("first_pair_selection_drift_detected") is True
                and (
                    decision_document.get("decision") != "continue-to-task-b"
                    or checkpoint_decision != "stop-before-task-b"
                )
            )
        ):
            raise T09PilotError("pilot checkpoint decision receipt content drifted")
        first_pair_started = state.get("first_pair_started_at_epoch")
        second_pair_started = state.get("second_pair_started_at_epoch")
        decided_at = checkpoint_binding.get("decided_at_epoch")
        if (
            not isinstance(first_pair_started, (int, float))
            or isinstance(first_pair_started, bool)
            or not isinstance(decided_at, (int, float))
            or isinstance(decided_at, bool)
            or checkpoint_binding.get("first_pair_started_at_epoch") != float(first_pair_started)
            or checkpoint_binding.get("second_pair_started_at_epoch") != second_pair_started
            or float(decided_at) < float(first_pair_started)
            or (
                state.get("first_pair_decision") == "continue-to-task-b"
                and (
                    not isinstance(second_pair_started, (int, float))
                    or isinstance(second_pair_started, bool)
                    or float(second_pair_started) != float(decided_at)
                )
            )
            or (
                state.get("first_pair_decision") == "stop-before-task-b"
                and state.get("first_pair_selection_drift_detected") is False
                and second_pair_started is not None
            )
            or (
                state.get("first_pair_selection_drift_detected") is True
                and (
                    not isinstance(second_pair_started, (int, float))
                    or isinstance(second_pair_started, bool)
                    or float(second_pair_started) != float(decided_at)
                )
            )
        ):
            raise T09PilotError("pilot checkpoint pair-wall origins drifted")
    return state


def load_validated_pilot_state(
    path: Path,
    *,
    execution_contract_sha256: str,
) -> dict[str, object]:
    """Return the receipt-backed typed state used by reconstruction gates."""

    return _load_pilot_state(path, contract_sha256=execution_contract_sha256)


def mark_empirical_entry(
    path: Path,
    *,
    execution_contract_sha256: str,
    run_id: str,
    supervised_release_receipt_sha256: str,
) -> None:
    """Consume one identity before releasing its credential-free entrypoint."""

    state = _load_pilot_state(path, contract_sha256=execution_contract_sha256)
    attempt_order = _state_provider_contract(state).run_ids
    if _HEX64.fullmatch(supervised_release_receipt_sha256) is None:
        raise T09PilotError("supervised-release receipt hash is malformed")
    if state.get("credential_safety_stop_detected") is True:
        raise T09BudgetExceeded("a credential safety failure permanently stops the campaign")
    if state.get("core_safety_stop_detected") is True:
        raise T09BudgetExceeded("a core artifact permanently stops the campaign")
    if state.get("nonempirical_infrastructure_attempts_consumed"):
        raise T09BudgetExceeded("a consumed pre-empirical infrastructure failure stops campaign")
    entered = cast(list[str], state["empirical_attempts_entered"])
    raw_complete = cast(list[str], state["raw_attempts_complete"])
    if run_id in entered:
        raise T09BudgetExceeded("zero-retry rule forbids re-entering an empirical attempt")
    if (
        entered != list(attempt_order[: len(entered)])
        or raw_complete != entered[: len(raw_complete)]
        or len(raw_complete) != len(entered)
    ):
        raise T09PilotError("pilot attempt history is not a valid prefix of the frozen order")
    if len(entered) >= len(attempt_order) or run_id != attempt_order[len(entered)]:
        raise T09BudgetExceeded("attempt count or frozen attempt order would be violated")
    reservation = state.get("condition_start_reservation")
    if not isinstance(reservation, dict) or reservation.get("run_id") != run_id:
        raise T09BudgetExceeded("empirical entry lacks its durable condition-start reservation")
    if len(entered) == 2:
        checkpoint_binding = state.get("first_pair_checkpoint_binding")
        finalizations = state.get("attempt_finalizations")
        if (
            state.get("first_pair_decision") != "continue-to-task-b"
            or state.get("first_pair_selection_drift_detected") is not False
            or not isinstance(checkpoint_binding, dict)
            or not isinstance(finalizations, dict)
            or checkpoint_binding.get("first_pair_started_at_epoch")
            != state.get("first_pair_started_at_epoch")
            or checkpoint_binding.get("second_pair_started_at_epoch")
            != state.get("second_pair_started_at_epoch")
        ):
            raise T09BudgetExceeded("Task B is blocked until the first-pair checkpoint passes")
        bound_semantics = checkpoint_binding.get("semantic_projection_sha256s")
        selected = [finalizations.get(attempt) for attempt in attempt_order[:2]]
        if (
            not isinstance(bound_semantics, dict)
            or not all(isinstance(item, dict) for item in selected)
            or any(
                cast(dict[str, object], item).get("semantic_projection_sha256")
                != bound_semantics.get(attempt)
                for attempt, item in zip(attempt_order[:2], selected, strict=True)
            )
            or len({_selection_closure_sha256(cast(dict[str, object], item)) for item in selected})
            != 1
        ):
            raise T09BudgetExceeded(
                "Task B is blocked because Task A selections drifted after the checkpoint"
            )
    entered.append(run_id)
    state["empirical_attempts_entered"] = entered
    bindings = cast(dict[str, str], state["supervised_release_bindings"])
    bindings[run_id] = supervised_release_receipt_sha256
    state["supervised_release_bindings"] = bindings
    state["condition_start_reservation"] = {
        "run_id": run_id,
        "start_intent_sha256": cast(str, reservation["start_intent_sha256"]),
        "phase": "empirical-state-committed",
        "supervised_release_receipt_sha256": supervised_release_receipt_sha256,
    }
    _write_json_atomic(path, state)


def reserve_condition_start(
    path: Path,
    *,
    execution_contract_sha256: str,
    run_id: str,
    start_intent_sha256: str,
) -> None:
    """Durably reserve one identity immediately before Docker start."""

    if _HEX64.fullmatch(start_intent_sha256) is None:
        raise T09PilotError("condition-start intent hash is malformed")
    state = _load_pilot_state(path, contract_sha256=execution_contract_sha256)
    attempt_order = _state_provider_contract(state).run_ids
    entered = cast(list[str], state["empirical_attempts_entered"])
    if state.get("condition_start_reservation") is not None:
        raise T09BudgetExceeded("a condition-start reservation already exists")
    if state.get("nonempirical_infrastructure_attempts_consumed"):
        raise T09BudgetExceeded("a prior infrastructure failure closed condition admission")
    if cast(list[str], state["raw_attempts_complete"]) != entered:
        raise T09PilotError("prior empirical attempts are not all raw-sealed")
    if len(entered) >= len(attempt_order) or attempt_order[len(entered)] != run_id:
        raise T09BudgetExceeded("condition-start reservation violates frozen order")
    state["condition_start_reservation"] = {
        "run_id": run_id,
        "start_intent_sha256": start_intent_sha256,
    }
    _write_json_atomic(path, state)


def rollback_never_started_condition_reservation(
    path: Path,
    *,
    execution_contract_sha256: str,
    run_id: str,
    start_intent_sha256: str,
) -> None:
    """Clear only an exact reservation after Docker absence and non-start are proven."""

    state = _load_pilot_state(path, contract_sha256=execution_contract_sha256)
    reservation = state.get("condition_start_reservation")
    if reservation is None:
        return
    if (
        reservation
        != {
            "run_id": run_id,
            "start_intent_sha256": start_intent_sha256,
        }
        or run_id in cast(list[str], state["empirical_attempts_entered"])
        or state.get("nonempirical_infrastructure_attempts_consumed") != []
        or cast(dict[str, object], state["essential_failure_seals"])
    ):
        raise T09PilotError("never-started reservation rollback authority drifted")
    state["condition_start_reservation"] = None
    _write_json_atomic(path, state)


def confirm_supervised_empirical_entry(
    path: Path,
    *,
    execution_contract_sha256: str,
    run_id: str,
    supervised_release_receipt: Path,
) -> None:
    """Confirm the host committed this exact attempt before making a task request."""

    state = _load_pilot_state(path, contract_sha256=execution_contract_sha256)
    contract = _state_provider_contract(state)
    receipt = load_json_object(
        supervised_release_receipt,
        context="supervised empirical release receipt",
    )
    bindings = cast(dict[str, str], state["supervised_release_bindings"])
    if (
        run_id not in cast(list[str], state["empirical_attempts_entered"])
        or bindings.get(run_id) != file_sha256(supervised_release_receipt)
        or receipt.get("schema_version") != "0.1.0"
        or receipt.get("plan_id") != contract.plan_id
        or receipt.get("run_id") != run_id
        or receipt.get("release_precedes_first_credential_read") is not True
        or receipt.get("core_artifact_count") != 0
        or receipt.get("exact_credential_match_count") != 0
    ):
        raise T09BudgetExceeded("empirical operation lacks its exact supervised release")


def mark_nonempirical_infrastructure_attempt_consumed(
    path: Path,
    *,
    execution_contract_sha256: str,
    run_id: str,
) -> None:
    """Consume a started condition identity whose cap failed before a task action."""

    state = _load_pilot_state(path, contract_sha256=execution_contract_sha256)
    attempt_order = _state_provider_contract(state).run_ids
    entered = cast(list[str], state["empirical_attempts_entered"])
    raw_complete = cast(list[str], state["raw_attempts_complete"])
    seals = cast(dict[str, dict[str, str]], state["essential_failure_seals"])
    consumed = cast(list[str], state["nonempirical_infrastructure_attempts_consumed"])
    reservation = state.get("condition_start_reservation")
    if consumed:
        if consumed == [run_id]:
            return
        raise T09BudgetExceeded("a different pre-empirical failure already consumed the campaign")
    if run_id in entered or len(entered) >= len(attempt_order):
        raise T09PilotError("non-empirical failure cannot consume an entered or unknown attempt")
    if not isinstance(reservation, dict) or reservation.get("run_id") != run_id:
        raise T09PilotError("non-empirical failure does not match the start reservation")
    if raw_complete != entered or seals:
        raise T09PilotError("prior attempts are not fully sealed before infrastructure failure")
    if run_id != attempt_order[len(entered)]:
        raise T09BudgetExceeded("non-empirical failure would violate frozen attempt order")
    state["nonempirical_infrastructure_attempts_consumed"] = [run_id]
    state["condition_start_reservation"] = None
    _write_json_atomic(path, state)


def reclassify_unreleased_empirical_entry(
    path: Path,
    *,
    execution_contract_sha256: str,
    run_id: str,
    start_intent_sha256: str,
    supervised_release_receipt_sha256: str,
) -> None:
    """Close the crash window where state committed but release never became visible."""

    state = _load_pilot_state(path, contract_sha256=execution_contract_sha256)
    entered = cast(list[str], state["empirical_attempts_entered"])
    raw_complete = cast(list[str], state["raw_attempts_complete"])
    bindings = cast(dict[str, str], state["supervised_release_bindings"])
    reservation = state.get("condition_start_reservation")
    if (
        not entered
        or entered[-1] != run_id
        or run_id in raw_complete
        or bindings.get(run_id) != supervised_release_receipt_sha256
        or not isinstance(reservation, dict)
        or reservation
        != {
            "run_id": run_id,
            "start_intent_sha256": start_intent_sha256,
            "phase": "empirical-state-committed",
            "supervised_release_receipt_sha256": supervised_release_receipt_sha256,
        }
        or state.get("nonempirical_infrastructure_attempts_consumed") != []
        or cast(dict[str, object], state["essential_failure_seals"]).get(run_id) is not None
    ):
        raise T09PilotError("unreleased empirical-entry transaction cannot be reclassified")
    entered.pop()
    bindings.pop(run_id)
    state["empirical_attempts_entered"] = entered
    state["supervised_release_bindings"] = bindings
    state["condition_start_reservation"] = None
    state["nonempirical_infrastructure_attempts_consumed"] = [run_id]
    reclassifications = cast(
        dict[str, dict[str, str]],
        state["unreleased_supervised_release_reclassifications"],
    )
    if run_id in reclassifications:
        raise T09PilotError("unreleased empirical-entry transaction was already reclassified")
    reclassifications[run_id] = {
        "start_intent_sha256": start_intent_sha256,
        "supervised_release_receipt_sha256": supervised_release_receipt_sha256,
    }
    state["unreleased_supervised_release_reclassifications"] = reclassifications
    _write_json_atomic(path, state)


def consume_published_unreleased_condition(
    path: Path,
    *,
    execution_contract_sha256: str,
    run_id: str,
    start_intent_sha256: str,
    supervised_release_receipt_sha256: str,
) -> None:
    """Consume a started condition whose release receipt preceded a failed state commit."""

    state = _load_pilot_state(path, contract_sha256=execution_contract_sha256)
    entered = cast(list[str], state["empirical_attempts_entered"])
    raw_complete = cast(list[str], state["raw_attempts_complete"])
    reservation = state.get("condition_start_reservation")
    if (
        run_id in entered
        or raw_complete != entered
        or reservation
        != {
            "run_id": run_id,
            "start_intent_sha256": start_intent_sha256,
        }
        or state.get("nonempirical_infrastructure_attempts_consumed") != []
        or cast(dict[str, object], state["essential_failure_seals"]).get(run_id) is not None
        or _HEX64.fullmatch(supervised_release_receipt_sha256) is None
    ):
        raise T09PilotError("published unreleased condition cannot be consumed")
    state["condition_start_reservation"] = None
    state["nonempirical_infrastructure_attempts_consumed"] = [run_id]
    reclassifications = cast(
        dict[str, dict[str, str]],
        state["unreleased_supervised_release_reclassifications"],
    )
    if run_id in reclassifications:
        raise T09PilotError("published unreleased condition was already consumed")
    reclassifications[run_id] = {
        "start_intent_sha256": start_intent_sha256,
        "supervised_release_receipt_sha256": supervised_release_receipt_sha256,
    }
    state["unreleased_supervised_release_reclassifications"] = reclassifications
    _write_json_atomic(path, state)


def mark_actual_credential_exposure(
    path: Path,
    *,
    execution_contract_sha256: str,
) -> None:
    """Monotonically close campaign admission after an exact secret match."""

    state = _load_pilot_state(path, contract_sha256=execution_contract_sha256)
    if (
        state.get("actual_credential_exposure_detected") is True
        and state.get("credential_safety_stop_detected") is True
    ):
        return
    state["actual_credential_exposure_detected"] = True
    state["credential_safety_stop_detected"] = True
    _write_json_atomic(path, state)


def mark_credential_cleanup_integrity_failure(
    path: Path,
    *,
    execution_contract_sha256: str,
) -> None:
    """Stop admission when credential cleanup cannot be reconstructed."""

    state = _load_pilot_state(path, contract_sha256=execution_contract_sha256)
    if state.get("credential_safety_stop_detected") is True:
        return
    state["credential_safety_stop_detected"] = True
    _write_json_atomic(path, state)


def mark_core_safety_stop(
    path: Path,
    *,
    execution_contract_sha256: str,
) -> None:
    """Monotonically close campaign admission after any prohibited core artifact."""

    state = _load_pilot_state(path, contract_sha256=execution_contract_sha256)
    if state.get("core_safety_stop_detected") is True:
        return
    state["core_safety_stop_detected"] = True
    _write_json_atomic(path, state)


def mark_essential_failure_sealed(
    path: Path,
    *,
    execution_contract_sha256: str,
    run_id: str,
    manifest_sha256: str,
    receipt_sha256: str,
) -> None:
    """Bind one reconstructable failure seal without making it evaluator-valid."""

    state = _load_pilot_state(path, contract_sha256=execution_contract_sha256)
    attempt_order = _state_provider_contract(state).run_ids
    if (
        run_id not in attempt_order
        or _HEX64.fullmatch(manifest_sha256) is None
        or _HEX64.fullmatch(receipt_sha256) is None
    ):
        raise T09PilotError("essential-failure seal identity is malformed")
    entered = cast(list[str], state["empirical_attempts_entered"])
    nonempirical = cast(list[str], state["nonempirical_infrastructure_attempts_consumed"])
    if run_id not in entered and run_id not in nonempirical:
        raise T09PilotError("an unconsumed attempt cannot receive an essential-failure seal")
    seals = cast(dict[str, dict[str, str]], state["essential_failure_seals"])
    binding = {"manifest_sha256": manifest_sha256, "receipt_sha256": receipt_sha256}
    if run_id in seals:
        if seals[run_id] != binding:
            raise T09PilotError("essential-failure seal binding changed")
    else:
        seals[run_id] = binding
    state["essential_failure_seals"] = seals
    release_transaction = state.get("condition_start_reservation")
    if isinstance(release_transaction, dict) and release_transaction.get("run_id") == run_id:
        if release_transaction.get("phase") != "empirical-state-committed":
            raise T09PilotError("essential seal found an incomplete condition-start transaction")
        state["condition_start_reservation"] = None
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
    attempt_order = _state_provider_contract(state).run_ids
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
        or run_id != attempt_order[len(raw_complete)]
        or entered[: len(raw_complete) + 1] != list(attempt_order[: len(raw_complete) + 1])
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
    release_transaction = state.get("condition_start_reservation")
    if not isinstance(release_transaction, dict) or (
        release_transaction.get("run_id") != run_id
        or release_transaction.get("phase") != "empirical-state-committed"
    ):
        raise T09PilotError("raw completion lacks its empirical release transaction")
    state["condition_start_reservation"] = None
    _write_json_atomic(path, state)


def mark_attempt_completed(
    path: Path,
    *,
    execution_contract_sha256: str,
    run_id: str,
    finalizer_execution_mode: str,
    finalizer_runtime_qualification_sha256: str,
    finalizer_source_sha256: str,
    finalizer_projection_source_sha256: str,
    finalizer_commit: str,
    finalizer_dependency_manifest_sha256: str,
    evaluator_contract_sha256: str,
    interpreter: str,
    interpreter_sha256: str,
    semantic_projection_sha256: str,
    finalized_output_root: str,
    finalization_complete_sha256: str,
) -> None:
    """Select one downstream finalization without reopening the condition attempt."""

    if (
        finalizer_execution_mode not in {"qualified-image", "qualified-local"}
        or _HEX64.fullmatch(finalizer_runtime_qualification_sha256) is None
        or _HEX64.fullmatch(finalizer_source_sha256) is None
        or _HEX64.fullmatch(finalizer_projection_source_sha256) is None
        or _HEX64.fullmatch(finalizer_dependency_manifest_sha256) is None
        or _HEX64.fullmatch(evaluator_contract_sha256) is None
        or _HEX64.fullmatch(interpreter_sha256) is None
        or _HEX64.fullmatch(semantic_projection_sha256) is None
        or _HEX64.fullmatch(finalization_complete_sha256) is None
        or re.fullmatch(r"[a-f0-9]{40}", finalizer_commit) is None
        or not Path(interpreter).is_absolute()
        or (
            finalizer_execution_mode == "qualified-image"
            and interpreter != "/opt/sira/.venv/bin/python"
        )
    ):
        raise T09PilotError("finalizer code identity is malformed")

    state = _load_pilot_state(
        path,
        contract_sha256=execution_contract_sha256,
        allow_one_pending_selection_receipt=True,
    )
    contract = _state_provider_contract(state)
    attempt_order = contract.run_ids
    entered = cast(list[str], state["empirical_attempts_entered"])
    raw_complete = cast(list[str], state["raw_attempts_complete"])
    finalizations = cast(dict[str, dict[str, object]], state["attempt_finalizations"])
    history = cast(dict[str, list[str]], state["attempt_finalization_history"])
    if run_id not in entered or run_id not in raw_complete:
        raise T09PilotError("attempt completion is missing, duplicated, or out of order")
    selection: dict[str, object] = {
        "finalizer_execution_mode": finalizer_execution_mode,
        "finalizer_runtime_qualification_sha256": finalizer_runtime_qualification_sha256,
        "finalizer_source_sha256": finalizer_source_sha256,
        "finalizer_projection_source_sha256": finalizer_projection_source_sha256,
        "finalizer_commit": finalizer_commit,
        "finalizer_dependency_manifest_sha256": finalizer_dependency_manifest_sha256,
        "evaluator_contract_sha256": evaluator_contract_sha256,
        "interpreter": interpreter,
        "interpreter_sha256": interpreter_sha256,
        "semantic_projection_sha256": semantic_projection_sha256,
        "finalized_output_root": finalized_output_root,
        "finalization_complete_sha256": finalization_complete_sha256,
    }
    retained_history = history.setdefault(run_id, [])
    checkpoint_binding = state.get("first_pair_checkpoint_binding")
    if run_id in attempt_order[:2] and isinstance(checkpoint_binding, dict):
        bound_semantics = checkpoint_binding.get("semantic_projection_sha256s")
        if (
            not isinstance(bound_semantics, dict)
            or bound_semantics.get(run_id) != semantic_projection_sha256
        ):
            state["first_pair_decision"] = "stop-before-task-b"
            state["first_pair_selection_drift_detected"] = True
            _write_json_atomic(path, state)
            raise T09PilotError(
                "post-checkpoint Task A finalization changed the bound semantic projection"
            )
    if finalizations.get(run_id) == selection:
        return
    receipts = _selection_receipts(path, contract=contract).get(run_id, [])
    projected_count = len(retained_history)
    if len(receipts) == projected_count + 1:
        pending_receipt, pending_sha256 = receipts[-1]
        if pending_receipt.get("selection") != selection:
            raise T09PilotError("pending selection receipt disagrees with requested selection")
        retained_history.append(pending_sha256)
    elif len(receipts) == projected_count:
        ordinal = projected_count + 1
        receipt_path = _selection_receipt_directory(path, run_id, contract=contract) / (
            f"selection-{ordinal:04d}.json"
        )
        _write_json_exclusive(
            receipt_path,
            {
                "schema_version": "0.1.0",
                "plan_id": contract.plan_id,
                "run_id": run_id,
                "ordinal": ordinal,
                "selection": selection,
            },
        )
        retained_history.append(file_sha256(receipt_path))
    else:
        raise T09PilotError("selection receipt history has an unrecoverable gap")
    finalizations[run_id] = selection
    state["attempts_completed"] = [
        attempt_run_id for attempt_run_id in attempt_order if attempt_run_id in finalizations
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
    contract = _state_provider_contract(state)
    attempt_order = contract.run_ids
    if state.get("first_pair_decision") is not None:
        raise T09PilotError("the first-pair checkpoint cannot be repeated")
    if state["attempts_completed"] != list(attempt_order[:2]):
        raise T09PilotError("checkpoint requires both Task A attempts to be complete")
    finalizations = cast(dict[str, dict[str, object]], state["attempt_finalizations"])
    finalizer_closures = {
        _selection_closure_sha256(item)
        for run_id in attempt_order[:2]
        if (item := finalizations.get(run_id)) is not None
    }
    result = decision.get("decision")
    if result not in {"continue-to-task-b", "stop-before-task-b"}:
        raise T09PilotError("checkpoint decision is invalid")
    closure_valid = len(finalizer_closures) == 1
    evidence = decision.get("checkpoint_evidence")
    declared_closure = (
        evidence.get("finalizer_closure_valid") if isinstance(evidence, dict) else closure_valid
    )
    if declared_closure is not closure_valid or (
        result == "continue-to-task-b" and not closure_valid
    ):
        raise T09PilotError("checkpoint finalizer-closure evidence is invalid")
    first_pair_started = state.get("first_pair_started_at_epoch")
    second_pair_started: float | None = decided_at_epoch if result == "continue-to-task-b" else None
    if (
        not isinstance(first_pair_started, (int, float))
        or isinstance(first_pair_started, bool)
        or not math.isfinite(float(first_pair_started))
        or not math.isfinite(decided_at_epoch)
        or decided_at_epoch < float(first_pair_started)
        or decision.get("first_pair_started_at_epoch") != float(first_pair_started)
        or decision.get("second_pair_started_at_epoch") != second_pair_started
        or decision.get("decided_at_epoch") != decided_at_epoch
    ):
        raise T09PilotError("checkpoint pair-wall origin binding is invalid")
    decision_path = path.parent / "first-pair-checkpoint-decision.json"
    _write_json_exclusive(decision_path, decision)
    decision_sha256 = canonical_sha256(decision)
    decision_file_sha256 = file_sha256(decision_path)
    state["first_pair_decision"] = result
    state["first_pair_decision_sha256"] = decision_sha256
    state["first_pair_checkpoint_binding"] = {
        "selection_receipt_sha256s": _current_selection_receipt_hashes(
            path,
            run_ids=attempt_order[:2],
            contract=contract,
        ),
        "selection_complete_sha256s": {
            run_id: finalizations[run_id]["finalization_complete_sha256"]
            for run_id in attempt_order[:2]
        },
        "semantic_projection_sha256s": {
            run_id: finalizations[run_id]["semantic_projection_sha256"]
            for run_id in attempt_order[:2]
        },
        "selected_closure_sha256": (
            next(iter(finalizer_closures))
            if closure_valid
            else canonical_sha256({"nonuniform_closures": sorted(finalizer_closures)})
        ),
        "finalizer_closure_valid": closure_valid,
        "decision_sha256": decision_sha256,
        "decision_receipt_path": decision_path.name,
        "decision_receipt_sha256": decision_file_sha256,
        "first_pair_started_at_epoch": float(first_pair_started),
        "second_pair_started_at_epoch": second_pair_started,
        "decided_at_epoch": decided_at_epoch,
    }
    if result == "continue-to-task-b":
        state["second_pair_started_at_epoch"] = decided_at_epoch
    _write_json_atomic(path, state)


@dataclass(frozen=True, slots=True)
class PilotTimeOrigins:
    """Monotonic wall origins plus prior active-Lambda accounting."""

    pair_started: float
    campaign_started: float
    owned_lambda_started: float
    prior_lambda_duration_seconds: float
    prior_lambda_cost_usd: float


def pilot_state_time_origins(
    path: Path,
    *,
    execution_contract_sha256: str,
    run_id: str,
    wall_time: Callable[[], float] = time.time,
    monotonic: Callable[[], float] = time.monotonic,
) -> PilotTimeOrigins:
    """Project distinct campaign, pair, and billable-Lambda timing authority."""

    state = _load_pilot_state(path, contract_sha256=execution_contract_sha256)
    attempt_index = _state_provider_contract(state).run_ids.index(run_id)
    pair_field = (
        "first_pair_started_at_epoch" if attempt_index < 2 else "second_pair_started_at_epoch"
    )
    epoch_values = (
        state.get(pair_field),
        state.get("campaign_started_at_epoch", state.get("pilot_started_at_epoch")),
        state.get("owned_lambda_started_at_epoch"),
    )
    prior_duration = state.get("prior_campaign_lambda_duration_seconds")
    prior_cost = state.get("prior_campaign_lambda_cost_usd")
    valid_epoch_types = all(
        isinstance(value, (int, float)) and not isinstance(value, bool) for value in epoch_values
    )
    if not valid_epoch_types or not all(
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
        and float(value) >= 0
        for value in (prior_duration, prior_cost)
    ):
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
    assert isinstance(prior_duration, (int, float))
    assert isinstance(prior_cost, (int, float))
    return PilotTimeOrigins(
        pair_started=result[0],
        campaign_started=result[1],
        owned_lambda_started=result[2],
        prior_lambda_duration_seconds=float(prior_duration),
        prior_lambda_cost_usd=float(prior_cost),
    )


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
        campaign_started: float,
        owned_lambda_started: float,
        prior_lambda_duration_seconds: float,
        prior_lambda_cost_usd: float,
        lambda_hourly_price_usd: float = 1.29,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self.limits = limits
        self.attempt_root = attempt_root
        self.pilot_root = pilot_root
        self.condition_started = condition_started
        self.pair_started = pair_started
        self.campaign_started = campaign_started
        self.owned_lambda_started = owned_lambda_started
        self.prior_lambda_duration_seconds = prior_lambda_duration_seconds
        self.prior_lambda_cost_usd = prior_lambda_cost_usd
        self.lambda_hourly_price_usd = lambda_hourly_price_usd
        self.monotonic = monotonic
        if (
            not all(
                math.isfinite(value)
                for value in (
                    condition_started,
                    pair_started,
                    campaign_started,
                    owned_lambda_started,
                    prior_lambda_duration_seconds,
                    prior_lambda_cost_usd,
                    lambda_hourly_price_usd,
                )
            )
            or not owned_lambda_started <= campaign_started <= pair_started <= condition_started
            or min(
                prior_lambda_duration_seconds,
                prior_lambda_cost_usd,
                lambda_hourly_price_usd,
            )
            < 0
        ):
            raise T09PilotError("resource guard timing or cost authority is invalid")

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
        owned_lambda_elapsed = max(0.0, now - self.owned_lambda_started)
        lambda_elapsed = self.prior_lambda_duration_seconds + owned_lambda_elapsed
        return ResourceSnapshot(
            condition_elapsed_seconds=max(0.0, now - self.condition_started),
            pair_elapsed_seconds=max(0.0, now - self.pair_started),
            total_elapsed_seconds=max(0.0, now - self.campaign_started),
            attempt_output_bytes=self._tree_bytes(self.attempt_root),
            pilot_disk_bytes=self._tree_bytes(self.pilot_root),
            lambda_elapsed_seconds=lambda_elapsed,
            lambda_cost_usd=(
                self.prior_lambda_cost_usd
                + owned_lambda_elapsed * self.lambda_hourly_price_usd / 3600.0
            ),
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

    plan_id: str
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
    next_attempt_hard_wall_seconds: int
    prior_t09_cost_usd: float
    cumulative_t09_cost_cap_usd: float
    valid_scored_attempt: tuple[bool, bool] = (True, True)
    finalizer_closure_valid: bool = True


def first_pair_decision(value: PairCheckpointInput) -> dict[str, object]:
    """Apply the predeclared pass/stop checkpoint without scientific inference."""

    reasons: list[str] = []
    try:
        selected_contract = provider_contract_for_plan_id(value.plan_id)
    except T09ProviderContractError as exc:
        raise T09PilotError("checkpoint plan identity is unsupported") from exc
    if value.attempt_run_ids != selected_contract.attempt_order[:2]:
        reasons.append("task_a_attempt_identity_or_order_invalid")
    if (
        value.prior_t09_cost_usd != selected_contract.prior_t09_cost_usd
        or value.cumulative_t09_cost_cap_usd != selected_contract.cumulative_t09_cost_cap_usd
    ):
        reasons.append("provider_cost_identity_invalid")
    if not all(value.valid_evidence):
        reasons.append("task_a_valid_evidence_missing")
    if not all(value.evaluator_succeeded):
        reasons.append("task_a_evaluator_failed")
    if not all(value.valid_scored_attempt):
        reasons.append("task_a_valid_scored_attempt_missing")
    if not value.finalizer_closure_valid:
        reasons.append("task_a_finalizer_closure_invalid")
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
        "lambda_cost_usd": 4.0,
        "total_cost_usd": 24.0,
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
        value.projected_aggregate_cost_usd > selected_contract.campaign_aggregate_cost_cap_usd
    ):
        reasons.append("projected_aggregate_cost_exceeds_hard_cap")
    projected_cumulative = value.prior_t09_cost_usd + value.projected_aggregate_cost_usd
    if not math.isfinite(projected_cumulative) or (
        projected_cumulative > value.cumulative_t09_cost_cap_usd
    ):
        reasons.append("projected_cumulative_t09_cost_exceeds_hard_cap")
    lifecycle = CampaignLifecycleLimits(
        preflight_iteration_wall_seconds=3_600,
        maximum_preflight_instance_active_seconds=21_600,
        maximum_cumulative_preflight_active_seconds=43_200,
        maximum_preflight_provider_cost_usd=10.0,
        max_preflight_launch_count=8,
        failed_preflight_termination_dispatch_seconds=300,
        empirical_campaign_wall_seconds=14_400,
        evidence_export_reserve_seconds=600,
        provider_termination_handoff_seconds=60,
        empirical_cleanup_reserve_seconds=900,
        empirical_termination_cutoff_seconds=13_500,
        maximum_empirical_provider_cost_usd=8.0,
        max_empirical_launch_count=1,
        max_lambda_instances=1,
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
        "plan_id": selected_contract.plan_id,
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
        "checkpoint_evidence": {
            "attempt_run_ids": list(value.attempt_run_ids),
            "valid_evidence": list(value.valid_evidence),
            "evaluator_succeeded": list(value.evaluator_succeeded),
            "valid_scored_attempt": list(value.valid_scored_attempt),
            "finalizer_closure_valid": value.finalizer_closure_valid,
            "pair_match_valid": value.pair_match_valid,
            "credential_issue": value.credential_issue,
            "cleanup_issue": value.cleanup_issue,
            "severe_floor_or_ceiling_failure": value.severe_floor_or_ceiling_failure,
            "actual_usage": usage_to_document(value.actual_usage),
            "actual_pair_wall_seconds": value.actual_pair_wall_seconds,
            "actual_lambda_cost_usd": value.actual_lambda_cost_usd,
            "next_attempt_hard_wall_seconds": value.next_attempt_hard_wall_seconds,
        },
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
    task_label = "TASK-A" if attempt.task_index == 0 else "TASK-B"
    upstream_run_id = (
        f"{EXPERIMENT_ID}-PILOT-{contract.provider_contract_version}-"
        f"{task_label}-{attempt.condition.upper()}"
    )
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
    final_argv = (
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
    )
    argv_sha256 = command_argv_sha256(final_argv)
    equality_surface = {
        "task_id": attempt.task_id,
        "model": MODEL_REVISION,
        "runtime": (
            f"T09-{contract.provider_contract_version}-python-3.11.14-"
            "core-suppressed-preentry-bound-image"
        ),
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
    provider_identity = provider_contract_for_plan_id(contract.plan_id)
    if provider_identity.capabilities.provider_selector_policy is ProviderSelectorPolicy.EXPLICIT:
        equality_surface["provider_contract_selector"] = {
            "argument": "--provider-contract",
            "value": contract.provider_contract_version,
        }
    return {
        "schema_version": "0.1.0",
        "plan_id": contract.plan_id,
        "run_id": attempt.run_id,
        "pair_id": attempt.pair_id,
        "task_id": attempt.task_id,
        "condition": attempt.condition,
        "order_index": attempt.order_index,
        "condition_plan_path": attempt.condition_plan_path,
        "condition_plan_sha256": attempt.condition_plan_sha256,
        "execution_contract_sha256": contract.sha256,
        "argv": list(final_argv),
        "argv_sha256": argv_sha256,
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
    task_id = manifest.get("task_id")
    task_label = (
        "TASK-A" if task_id == TASK_IDS[0] else "TASK-B" if task_id == TASK_IDS[1] else None
    )
    plan_id = manifest.get("plan_id")
    try:
        version = (
            provider_contract_for_plan_id(plan_id).version if isinstance(plan_id, str) else None
        )
    except T09ProviderContractError:
        version = None
    expected_upstream_run_id = (
        f"{EXPERIMENT_ID}-PILOT-{version}-{task_label}-{str(condition).upper()}"
        if task_label is not None and version is not None
        else None
    )
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
