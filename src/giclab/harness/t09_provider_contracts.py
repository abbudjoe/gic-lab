"""Immutable provider identities for every retained T09 campaign version.

The provider lifecycle accumulated several historical execution contracts in one
module.  Those contracts are evidence identities, not defaults: a caller must name
the exact version it is rendering, validating, or cleaning up.  This module therefore
has no notion of a current or latest contract.
"""

from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import Final, cast

import yaml


class T09ProviderContractError(ValueError):
    """A version-bound provider identity was missing, contradictory, or unsafe."""


_HEX64: Final = re.compile(r"^[a-f0-9]{64}$")
_SAFE_ID: Final = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$")


@dataclass(frozen=True, slots=True)
class T09ProviderContract:
    """One immutable provider/authority surface from a retained T09 version."""

    version: str
    source_commit: str
    plan_id: str
    host_run_id: str
    authorization_id: str | None
    authorization_prefix: str | None
    authorization_source_sha256: str | None
    instance_name: str
    plan_path: str
    expected_plan_bytes: int
    expected_plan_sha256: str
    provider_profile_id: str
    provider_profile_path: str
    expected_provider_profile_bytes: int
    expected_provider_profile_sha256: str
    execution_contract_path: str | None
    command_manifest_path: str | None
    science_projection_path: str | None
    frozen_run_manifest_id: str | None
    local_finalizer_qualification_id: str | None
    evaluator_run_ids: tuple[str, ...]
    control_root_name: str
    evidence_archive_id: str
    evidence_stage_id: str
    remote_root: str
    run_ids: tuple[str, ...]
    image_qualification_ids: tuple[str, ...]
    active_image_qualification_id: str | None
    replacement_image_tag: str | None
    container_prefix: str
    image_materialization_policy: str | None
    max_launch_count: int
    prior_t09_cost_usd: float
    preflight_lambda_cost_cap_usd: float
    campaign_lambda_cost_cap_usd: float
    campaign_openai_cost_cap_usd: float
    campaign_aggregate_cost_cap_usd: float
    cumulative_t09_cost_cap_usd: float

    def __post_init__(self) -> None:
        identifiers = (
            self.version,
            self.plan_id,
            self.host_run_id,
            self.instance_name,
            self.provider_profile_id,
        )
        if any(_SAFE_ID.fullmatch(value) is None for value in identifiers):
            raise T09ProviderContractError("provider contract contains an unsafe identity")
        if re.fullmatch(r"[a-f0-9]{40}", self.source_commit) is None:
            raise T09ProviderContractError("provider source commit is malformed")
        if any(
            _HEX64.fullmatch(value) is None
            for value in (self.expected_plan_sha256, self.expected_provider_profile_sha256)
        ):
            raise T09ProviderContractError("provider source hash is malformed")
        if self.authorization_source_sha256 is not None and (
            _HEX64.fullmatch(self.authorization_source_sha256) is None
        ):
            raise T09ProviderContractError("provider authority source hash is malformed")
        if (self.authorization_id is None) == (self.authorization_prefix is None):
            raise T09ProviderContractError(
                "provider contract must bind one exact authority or one fresh prefix"
            )
        if self.authorization_id is not None and _SAFE_ID.fullmatch(self.authorization_id) is None:
            raise T09ProviderContractError("provider authority identity is malformed")
        if self.authorization_prefix is not None and (
            not self.authorization_prefix.endswith("-")
            or _SAFE_ID.fullmatch(f"{self.authorization_prefix}X") is None
        ):
            raise T09ProviderContractError("provider authority prefix is malformed")
        if self.expected_plan_bytes <= 0 or self.expected_provider_profile_bytes <= 0:
            raise T09ProviderContractError("provider source byte identity is invalid")
        if self.max_launch_count <= 0:
            raise T09ProviderContractError("provider launch count is invalid")
        budget_values = (
            self.prior_t09_cost_usd,
            self.preflight_lambda_cost_cap_usd,
            self.campaign_lambda_cost_cap_usd,
            self.campaign_openai_cost_cap_usd,
            self.campaign_aggregate_cost_cap_usd,
            self.cumulative_t09_cost_cap_usd,
        )
        if (
            any(not math.isfinite(value) or value < 0 for value in budget_values)
            or min(budget_values[1:]) <= 0
            or self.campaign_aggregate_cost_cap_usd
            < self.campaign_lambda_cost_cap_usd + self.campaign_openai_cost_cap_usd
            or self.cumulative_t09_cost_cap_usd <= self.prior_t09_cost_usd
        ):
            raise T09ProviderContractError("provider budget identity is malformed")
        if (
            len(self.run_ids) != 4
            or len(set(self.run_ids)) != len(self.run_ids)
            or any(_SAFE_ID.fullmatch(run_id) is None for run_id in self.run_ids)
        ):
            raise T09ProviderContractError("provider run identities are malformed")
        if (
            len(self.evaluator_run_ids) != len(self.run_ids)
            or len(set(self.evaluator_run_ids)) != len(self.evaluator_run_ids)
            or any(_SAFE_ID.fullmatch(run_id) is None for run_id in self.evaluator_run_ids)
        ):
            raise T09ProviderContractError("provider evaluator identities are malformed")
        if (
            re.fullmatch(r"pilot-v[0-9]+", self.control_root_name) is None
            or _SAFE_ID.fullmatch(self.evidence_archive_id) is None
            or _SAFE_ID.fullmatch(self.evidence_stage_id) is None
        ):
            raise T09ProviderContractError("provider evidence identities are malformed")
        if (
            not self.container_prefix.endswith("-")
            or re.fullmatch(r"[a-z0-9][a-z0-9.-]+-", self.container_prefix) is None
        ):
            raise T09ProviderContractError("provider container prefix is malformed")
        if self.active_image_qualification_id is None:
            if self.image_qualification_ids or self.replacement_image_tag is not None:
                raise T09ProviderContractError("provider image identities are contradictory")
        elif (
            self.active_image_qualification_id not in self.image_qualification_ids
            or _SAFE_ID.fullmatch(self.active_image_qualification_id) is None
            or self.replacement_image_tag is None
            or re.fullmatch(r"[a-z0-9./:_-]+", self.replacement_image_tag) is None
        ):
            raise T09ProviderContractError("provider image identities are malformed")
        if self.image_materialization_policy not in {
            None,
            "retained-import-or-one-fallback-build",
        }:
            raise T09ProviderContractError("provider materialization policy is unsupported")
        for source_relative in (self.plan_path, self.provider_profile_path):
            path = PurePosixPath(source_relative)
            if path.is_absolute() or ".." in path.parts:
                raise T09ProviderContractError("provider source path is unsafe")
        if (self.execution_contract_path is None) != (self.command_manifest_path is None):
            raise T09ProviderContractError(
                "provider contract has a partial scientific package identity"
            )
        if self.execution_contract_path is None and self.science_projection_path is not None:
            raise T09ProviderContractError(
                "historical pragmatic contract unexpectedly has autonomous package paths"
            )
        if self.version in {"V3", "V4"}:
            if (
                self.frozen_run_manifest_id is not None
                or self.local_finalizer_qualification_id is not None
            ):
                raise T09ProviderContractError(
                    "pre-freeze provider contract unexpectedly has finalizer identities"
                )
        elif (
            self.frozen_run_manifest_id is None
            or self.local_finalizer_qualification_id is None
            or _SAFE_ID.fullmatch(self.frozen_run_manifest_id) is None
            or _SAFE_ID.fullmatch(self.local_finalizer_qualification_id) is None
        ):
            raise T09ProviderContractError(
                "provider contract lacks its frozen finalizer identities"
            )
        for scientific_relative in (
            self.execution_contract_path,
            self.command_manifest_path,
            self.science_projection_path,
        ):
            if scientific_relative is None:
                continue
            path = PurePosixPath(scientific_relative)
            if path.is_absolute() or ".." in path.parts:
                raise T09ProviderContractError("provider scientific source path is unsafe")
        remote = PurePosixPath(self.remote_root)
        if not remote.is_absolute() or ".." in remote.parts:
            raise T09ProviderContractError("provider remote root is unsafe")

    def validate_authority(self, authorization_id: str, source_sha256: str) -> None:
        """Reject an authority minted for any other provider contract."""

        if _HEX64.fullmatch(source_sha256) is None:
            raise T09ProviderContractError("provider authority source hash is malformed")
        if self.authorization_id is not None:
            if (
                authorization_id != self.authorization_id
                or source_sha256 != self.authorization_source_sha256
            ):
                raise T09ProviderContractError("provider authority belongs to another version")
            return
        prefix = cast(str, self.authorization_prefix)
        if not authorization_id.startswith(prefix) or _SAFE_ID.fullmatch(authorization_id) is None:
            raise T09ProviderContractError("provider authority belongs to another version")

    def validate_owner(self, *, plan_id: str, host_run_id: str, instance_name: str) -> None:
        """Bind destructive cleanup to the selected contract's exact owned resource."""

        if (plan_id, host_run_id, instance_name) != (
            self.plan_id,
            self.host_run_id,
            self.instance_name,
        ):
            raise T09ProviderContractError("provider cleanup ownership crosses versions")

    def validate_image_qualification(
        self,
        *,
        plan_id: str,
        host_run_id: str,
        qualification_id: str,
    ) -> None:
        """Reject a retained image qualification from another campaign version."""

        if (
            plan_id != self.plan_id
            or host_run_id != self.host_run_id
            or qualification_id not in self.image_qualification_ids
        ):
            raise T09ProviderContractError("image qualification belongs to another version")

    def validate_run_id(self, run_id: str) -> None:
        """Reject a condition identity minted for a different campaign version."""

        if run_id not in self.run_ids:
            raise T09ProviderContractError("condition run identity belongs to another version")

    @property
    def attempt_order(self) -> tuple[str, ...]:
        """Expose the selected contract's immutable empirical attempt order."""

        return self.run_ids

    def validate_evaluator_run_id(self, evaluator_run_id: str) -> None:
        """Reject an evaluator identity minted for a different campaign version."""

        if evaluator_run_id not in self.evaluator_run_ids:
            raise T09ProviderContractError("evaluator run identity belongs to another version")


_EXPERIMENT_ROOT: Final = "experiments/EXP-0001-sira-simulative-vs-reactive"
_PROPOSAL_ROOT: Final = f"{_EXPERIMENT_ROOT}/run-plans/proposals"
_ACTIVE_PROFILE: Final = f"{_EXPERIMENT_ROOT}/run-plans/pilot.yaml"
_AUTONOMOUS_REMOTE_ROOT: Final = "/home/ubuntu/t09-artifacts-autonomous"


def _contract(
    *,
    version: str,
    source_commit: str,
    host_run_id: str,
    authorization_id: str | None,
    authorization_prefix: str | None,
    authorization_source_sha256: str | None,
    instance_name: str,
    plan_path: str,
    plan_bytes: int,
    plan_sha256: str,
    profile_path: str,
    profile_bytes: int,
    profile_sha256: str,
    run_ids: tuple[str, ...],
    image_qualification_ids: tuple[str, ...],
    active_image_qualification_id: str | None,
    replacement_image_tag: str | None,
    container_prefix: str,
    image_materialization_policy: str | None,
    max_launch_count: int,
    prior_t09_cost_usd: float,
    preflight_lambda_cost_cap_usd: float,
    campaign_lambda_cost_cap_usd: float,
    campaign_openai_cost_cap_usd: float,
    campaign_aggregate_cost_cap_usd: float,
    cumulative_t09_cost_cap_usd: float,
    frozen_run_manifest_id: str | None = None,
    local_finalizer_qualification_id: str | None = None,
    execution_contract_path: str | None = None,
    command_manifest_path: str | None = None,
    science_projection_path: str | None = None,
) -> T09ProviderContract:
    plan_id = f"PLAN-EXP0001-PILOT-{version}"
    evaluator_run_ids = tuple(
        run_id.replace("RUN-T09-TASK-", "RUN-T09-EVAL-TASK-", 1) for run_id in run_ids
    )
    host_family = host_run_id.removeprefix("RUN-T09-PILOT-HOST-")
    control_root_name = f"pilot-{version.lower()}" if version in {"V12", "V13"} else "pilot-v7"
    return T09ProviderContract(
        version=version,
        source_commit=source_commit,
        plan_id=plan_id,
        host_run_id=host_run_id,
        authorization_id=authorization_id,
        authorization_prefix=authorization_prefix,
        authorization_source_sha256=authorization_source_sha256,
        instance_name=instance_name,
        plan_path=plan_path,
        expected_plan_bytes=plan_bytes,
        expected_plan_sha256=plan_sha256,
        provider_profile_id=plan_id,
        provider_profile_path=profile_path,
        expected_provider_profile_bytes=profile_bytes,
        expected_provider_profile_sha256=profile_sha256,
        execution_contract_path=execution_contract_path,
        command_manifest_path=command_manifest_path,
        science_projection_path=science_projection_path,
        frozen_run_manifest_id=frozen_run_manifest_id,
        local_finalizer_qualification_id=local_finalizer_qualification_id,
        evaluator_run_ids=evaluator_run_ids,
        control_root_name=control_root_name,
        evidence_archive_id=f"ARCHIVE-EXP0001-PILOT-{version}-{host_family}",
        evidence_stage_id=f"STAGE-EXP0001-PILOT-{version}-{host_family}",
        remote_root=_AUTONOMOUS_REMOTE_ROOT,
        run_ids=run_ids,
        image_qualification_ids=image_qualification_ids,
        active_image_qualification_id=active_image_qualification_id,
        replacement_image_tag=replacement_image_tag,
        container_prefix=container_prefix,
        image_materialization_policy=image_materialization_policy,
        max_launch_count=max_launch_count,
        prior_t09_cost_usd=prior_t09_cost_usd,
        preflight_lambda_cost_cap_usd=preflight_lambda_cost_cap_usd,
        campaign_lambda_cost_cap_usd=campaign_lambda_cost_cap_usd,
        campaign_openai_cost_cap_usd=campaign_openai_cost_cap_usd,
        campaign_aggregate_cost_cap_usd=campaign_aggregate_cost_cap_usd,
        cumulative_t09_cost_cap_usd=cumulative_t09_cost_cap_usd,
    )


V3_PROVIDER_CONTRACT: Final = _contract(
    version="V3",
    source_commit="6f7c3112777a8b253f085d058972259fad30778f",
    host_run_id="RUN-T09-PILOT-HOST-0001",
    authorization_id="AUTH-T09-PRAGMATIC-PILOT-2026-08-13",
    authorization_prefix=None,
    authorization_source_sha256="1f8285ea3fc52f4084a945f1712870203463cb7fb92cc61ac2eeae47d119e4c7",
    instance_name="giclab-t09-pilot-v3-0001",
    plan_path=f"{_PROPOSAL_ROOT}/PLAN-EXP0001-PILOT-V3.yaml",
    plan_bytes=5_270,
    plan_sha256="0b17da814f9b20326a7220cec5f41e84c968a46c9d38e913f327afe267c26210",
    profile_path=f"{_PROPOSAL_ROOT}/PLAN-EXP0001-PILOT-V3.yaml",
    profile_bytes=5_270,
    profile_sha256="0b17da814f9b20326a7220cec5f41e84c968a46c9d38e913f327afe267c26210",
    run_ids=(
        "RUN-T09-TASK-A-REACTIVE-0001",
        "RUN-T09-TASK-A-SIMULATIVE-0001",
        "RUN-T09-TASK-B-SIMULATIVE-0001",
        "RUN-T09-TASK-B-REACTIVE-0001",
    ),
    image_qualification_ids=(),
    active_image_qualification_id=None,
    replacement_image_tag=None,
    container_prefix="giclab-t09-pilot-v3-",
    image_materialization_policy=None,
    max_launch_count=1,
    prior_t09_cost_usd=0.0,
    preflight_lambda_cost_cap_usd=5.16,
    campaign_lambda_cost_cap_usd=5.16,
    campaign_openai_cost_cap_usd=40.0,
    campaign_aggregate_cost_cap_usd=45.16,
    cumulative_t09_cost_cap_usd=45.16,
)
V4_PROVIDER_CONTRACT: Final = _contract(
    version="V4",
    source_commit="626860b77184db09da059e923a6c8b4803b8560a",
    host_run_id="RUN-T09-PILOT-HOST-0002",
    authorization_id="AUTH-T09-PRAGMATIC-RETRY2-2026-08-13",
    authorization_prefix=None,
    authorization_source_sha256="3852fe8dabb9ee6b10e40cbc6dc1ab964ea6fce11f71f81f0966e927cadddeb9",
    instance_name="giclab-t09-pilot-v4-0002",
    plan_path=f"{_PROPOSAL_ROOT}/PLAN-EXP0001-PILOT-V4.yaml",
    plan_bytes=6_465,
    plan_sha256="1ebfbb645ce337d9e99afa5654cddff84a612508d21b70d54cf21dfb99604b77",
    profile_path=f"{_PROPOSAL_ROOT}/PLAN-EXP0001-PILOT-V4.yaml",
    profile_bytes=6_465,
    profile_sha256="1ebfbb645ce337d9e99afa5654cddff84a612508d21b70d54cf21dfb99604b77",
    run_ids=(
        "RUN-T09-TASK-A-REACTIVE-0002",
        "RUN-T09-TASK-A-SIMULATIVE-0002",
        "RUN-T09-TASK-B-SIMULATIVE-0002",
        "RUN-T09-TASK-B-REACTIVE-0002",
    ),
    image_qualification_ids=(
        "QUAL-T09-PILOT-V4-IMAGE-0002",
        "QUAL-T09-PILOT-V4-IMAGE-0003",
        "QUAL-T09-PILOT-V4-IMAGE-0004",
    ),
    active_image_qualification_id="QUAL-T09-PILOT-V4-IMAGE-0002",
    replacement_image_tag="giclab/t09-pilot-v4:93fb8d72de71-0002",
    container_prefix="giclab-t09-pilot-v4-",
    image_materialization_policy=None,
    max_launch_count=1,
    prior_t09_cost_usd=0.414064252316667,
    preflight_lambda_cost_cap_usd=5.16,
    campaign_lambda_cost_cap_usd=5.16,
    campaign_openai_cost_cap_usd=40.0,
    campaign_aggregate_cost_cap_usd=45.16,
    cumulative_t09_cost_cap_usd=46.0,
)
V5_PROVIDER_CONTRACT: Final = _contract(
    version="V5",
    source_commit="a36c3c9720611cdf730ef1ce7f83224eacd72851",
    host_run_id="RUN-T09-PILOT-HOST-0003",
    authorization_id="AUTH-T09-PRAGMATIC-RETRY3-2026-08-13",
    authorization_prefix=None,
    authorization_source_sha256="5731b3ccdad25f5d656272841d47f93418ae1535802602a9856c97552ac0b8b8",
    instance_name="giclab-t09-pilot-v5-0003",
    plan_path=f"{_PROPOSAL_ROOT}/PLAN-EXP0001-PILOT-V5.yaml",
    plan_bytes=9_051,
    plan_sha256="e7e214500348c8b876beb034df7b592c84f5ab79788ab6f310ef187fd797613c",
    profile_path=f"{_PROPOSAL_ROOT}/PLAN-EXP0001-PILOT-V5.yaml",
    profile_bytes=9_051,
    profile_sha256="e7e214500348c8b876beb034df7b592c84f5ab79788ab6f310ef187fd797613c",
    run_ids=(
        "RUN-T09-TASK-A-REACTIVE-0003",
        "RUN-T09-TASK-A-SIMULATIVE-0003",
        "RUN-T09-TASK-B-SIMULATIVE-0003",
        "RUN-T09-TASK-B-REACTIVE-0003",
    ),
    image_qualification_ids=(
        "QUAL-T09-PILOT-V5-IMAGE-0001",
        "QUAL-T09-PILOT-V5-IMAGE-0002",
    ),
    active_image_qualification_id="QUAL-T09-PILOT-V5-IMAGE-0002",
    replacement_image_tag="giclab/t09-pilot-v5:93fb8d72de71-0002",
    container_prefix="giclab-t09-pilot-v5-",
    image_materialization_policy=None,
    max_launch_count=2,
    prior_t09_cost_usd=2.5308164556905757,
    preflight_lambda_cost_cap_usd=5.16,
    campaign_lambda_cost_cap_usd=5.16,
    campaign_openai_cost_cap_usd=40.0,
    campaign_aggregate_cost_cap_usd=45.16,
    cumulative_t09_cost_cap_usd=48.0,
    frozen_run_manifest_id="RUN-MANIFEST-EXP0001-PILOT-V5-0003",
    local_finalizer_qualification_id="QUAL-T09-PILOT-V5-LOCAL-FINALIZER-0001",
)
V6_PROVIDER_CONTRACT: Final = _contract(
    version="V6",
    source_commit="afea34c1d796765c25bed320d3a8852ee23af380",
    host_run_id="RUN-T09-PILOT-HOST-0004",
    authorization_id="AUTH-T09-PRAGMATIC-RETRY4-2026-08-14",
    authorization_prefix=None,
    authorization_source_sha256="e3222d38c9b21091a51839122d42594d691577716bc87fd3e09296c6b766df51",
    instance_name="giclab-t09-pilot-v6-0004",
    plan_path=f"{_PROPOSAL_ROOT}/PLAN-EXP0001-PILOT-V6.yaml",
    plan_bytes=9_366,
    plan_sha256="d0294b3a1535c4fe4ddfcc856a6b923731a7fb0c7840dd161c5784db61f35d8c",
    profile_path=f"{_PROPOSAL_ROOT}/PLAN-EXP0001-PILOT-V6.yaml",
    profile_bytes=9_366,
    profile_sha256="d0294b3a1535c4fe4ddfcc856a6b923731a7fb0c7840dd161c5784db61f35d8c",
    run_ids=(
        "RUN-T09-TASK-A-REACTIVE-0004",
        "RUN-T09-TASK-A-SIMULATIVE-0004",
        "RUN-T09-TASK-B-SIMULATIVE-0004",
        "RUN-T09-TASK-B-REACTIVE-0004",
    ),
    image_qualification_ids=("QUAL-T09-PILOT-V6-IMAGE-0001",),
    active_image_qualification_id="QUAL-T09-PILOT-V6-IMAGE-0001",
    replacement_image_tag="giclab/t09-pilot-v6:93fb8d72de71-0001",
    container_prefix="giclab-t09-pilot-v6-",
    image_materialization_policy="retained-import-or-one-fallback-build",
    max_launch_count=2,
    prior_t09_cost_usd=4.04142013524027,
    preflight_lambda_cost_cap_usd=8.0,
    campaign_lambda_cost_cap_usd=8.0,
    campaign_openai_cost_cap_usd=40.0,
    campaign_aggregate_cost_cap_usd=48.0,
    cumulative_t09_cost_cap_usd=55.0,
    frozen_run_manifest_id="RUN-MANIFEST-EXP0001-PILOT-V6-0004",
    local_finalizer_qualification_id="QUAL-T09-PILOT-V6-LOCAL-FINALIZER-0001",
)
V7_PROVIDER_CONTRACT: Final = _contract(
    version="V7",
    source_commit="465927b62904e3bde55724ea00c79502dd2ce5a6",
    host_run_id="RUN-T09-PILOT-HOST-0005",
    authorization_id="AUTH-T09-PRAGMATIC-RETRY5-2026-08-14",
    authorization_prefix=None,
    authorization_source_sha256="97539fa4b65f627880b159e0f40c9a7efab26cd2a746c7c12ddbe15e44684346",
    instance_name="giclab-t09-pilot-v7-0005",
    plan_path=f"{_PROPOSAL_ROOT}/PLAN-EXP0001-PILOT-V7.yaml",
    plan_bytes=14_046,
    plan_sha256="9f66f8f6ee9e137d27e86c5362187fe46d94b26a322994e55222e34c0c4c004e",
    profile_path=f"{_PROPOSAL_ROOT}/PLAN-EXP0001-PILOT-V7.yaml",
    profile_bytes=14_046,
    profile_sha256="9f66f8f6ee9e137d27e86c5362187fe46d94b26a322994e55222e34c0c4c004e",
    run_ids=(
        "RUN-T09-TASK-A-REACTIVE-0005",
        "RUN-T09-TASK-A-SIMULATIVE-0005",
        "RUN-T09-TASK-B-SIMULATIVE-0005",
        "RUN-T09-TASK-B-REACTIVE-0005",
    ),
    image_qualification_ids=("QUAL-T09-PILOT-V7-IMAGE-0001",),
    active_image_qualification_id="QUAL-T09-PILOT-V7-IMAGE-0001",
    replacement_image_tag="giclab/t09-pilot-v7:93fb8d72de71-0001",
    container_prefix="giclab-t09-pilot-v7-",
    image_materialization_policy="retained-import-or-one-fallback-build",
    max_launch_count=2,
    prior_t09_cost_usd=5.7424506112,
    preflight_lambda_cost_cap_usd=8.0,
    campaign_lambda_cost_cap_usd=8.0,
    campaign_openai_cost_cap_usd=40.0,
    campaign_aggregate_cost_cap_usd=48.0,
    cumulative_t09_cost_cap_usd=60.0,
    frozen_run_manifest_id="RUN-MANIFEST-EXP0001-PILOT-V7-0005",
    local_finalizer_qualification_id="QUAL-T09-PILOT-V7-LOCAL-FINALIZER-0001",
)
V8_PROVIDER_CONTRACT: Final = _contract(
    version="V8",
    source_commit="1e5f1f9524fe57443d4a3ba5c0353290e0cfda5e",
    host_run_id="RUN-T09-PILOT-HOST-AUTONOMOUS-0001",
    authorization_id="AUTH-T09-AUTONOMOUS-PREFLIGHT-TO-PILOT-2026-08-27",
    authorization_prefix=None,
    authorization_source_sha256="80ded0e246b4f070c3992ae872111c19c64d1ef30115d65a8641709f06e1a484",
    instance_name="giclab-t09-pilot-v8-autonomous-0001",
    plan_path=f"{_PROPOSAL_ROOT}/PLAN-EXP0001-PILOT-V8.yaml",
    plan_bytes=13_456,
    plan_sha256="5b77e29e1005979128fa24dbe809bd8b7f92139aa9a49afd68d1daf3de256125",
    profile_path=f"{_PROPOSAL_ROOT}/PLAN-EXP0001-PILOT-V8.yaml",
    profile_bytes=13_456,
    profile_sha256="5b77e29e1005979128fa24dbe809bd8b7f92139aa9a49afd68d1daf3de256125",
    run_ids=(
        "RUN-T09-TASK-A-REACTIVE-AUTONOMOUS-0001",
        "RUN-T09-TASK-A-SIMULATIVE-AUTONOMOUS-0001",
        "RUN-T09-TASK-B-SIMULATIVE-AUTONOMOUS-0001",
        "RUN-T09-TASK-B-REACTIVE-AUTONOMOUS-0001",
    ),
    image_qualification_ids=("QUAL-T09-PILOT-V8-IMAGE-AUTONOMOUS-0001",),
    active_image_qualification_id="QUAL-T09-PILOT-V8-IMAGE-AUTONOMOUS-0001",
    replacement_image_tag="giclab/t09-pilot-v8:93fb8d72de71-autonomous-0001",
    container_prefix="giclab-t09-pilot-v8-autonomous-",
    image_materialization_policy="retained-import-or-one-fallback-build",
    max_launch_count=8,
    prior_t09_cost_usd=6.813138735,
    preflight_lambda_cost_cap_usd=20.0,
    campaign_lambda_cost_cap_usd=8.0,
    campaign_openai_cost_cap_usd=40.0,
    campaign_aggregate_cost_cap_usd=68.0,
    cumulative_t09_cost_cap_usd=75.0,
    frozen_run_manifest_id="RUN-MANIFEST-EXP0001-PILOT-V8-AUTONOMOUS-0001",
    local_finalizer_qualification_id=("QUAL-T09-PILOT-V8-LOCAL-FINALIZER-AUTONOMOUS-0001"),
    execution_contract_path=f"{_EXPERIMENT_ROOT}/contracts/T09_PILOT_EXECUTION_CONTRACT.json",
    command_manifest_path=f"{_EXPERIMENT_ROOT}/contracts/T09_PILOT_COMMAND_MANIFESTS.json",
    science_projection_path=f"{_EXPERIMENT_ROOT}/contracts/T09_PILOT_V8_SCIENCE_PROJECTION.json",
)
V9_PROVIDER_CONTRACT: Final = _contract(
    version="V9",
    source_commit="736f1065804c2236ea1be9ad28216b829396d22a",
    host_run_id="RUN-T09-PILOT-HOST-AUTONOMOUS-0002",
    authorization_id="AUTH-T09-AUTONOMOUS-RETRY2-2026-08-27",
    authorization_prefix=None,
    authorization_source_sha256="aea63a42cf0270ad0a41a929b4b8eb19dd1c3af73abfe97163c1d90e6077d3da",
    instance_name="giclab-t09-pilot-v9-autonomous-0002",
    plan_path=_ACTIVE_PROFILE,
    plan_bytes=13_478,
    plan_sha256="28d41a2c2ba8e4b2e0460f78e348064847565e4287f07b685433cd99416c25f5",
    profile_path=_ACTIVE_PROFILE,
    profile_bytes=13_478,
    profile_sha256="28d41a2c2ba8e4b2e0460f78e348064847565e4287f07b685433cd99416c25f5",
    run_ids=(
        "RUN-T09-TASK-A-REACTIVE-AUTONOMOUS-0002",
        "RUN-T09-TASK-A-SIMULATIVE-AUTONOMOUS-0002",
        "RUN-T09-TASK-B-SIMULATIVE-AUTONOMOUS-0002",
        "RUN-T09-TASK-B-REACTIVE-AUTONOMOUS-0002",
    ),
    image_qualification_ids=("QUAL-T09-PILOT-V9-IMAGE-AUTONOMOUS-0002",),
    active_image_qualification_id="QUAL-T09-PILOT-V9-IMAGE-AUTONOMOUS-0002",
    replacement_image_tag="giclab/t09-pilot-v9:93fb8d72de71-autonomous-0002",
    container_prefix="giclab-t09-pilot-v9-autonomous-",
    image_materialization_policy="retained-import-or-one-fallback-build",
    max_launch_count=8,
    prior_t09_cost_usd=29.3502995579,
    preflight_lambda_cost_cap_usd=10.0,
    campaign_lambda_cost_cap_usd=8.0,
    campaign_openai_cost_cap_usd=40.0,
    campaign_aggregate_cost_cap_usd=58.0,
    cumulative_t09_cost_cap_usd=90.0,
    frozen_run_manifest_id="RUN-MANIFEST-EXP0001-PILOT-V9-AUTONOMOUS-0002",
    local_finalizer_qualification_id=("QUAL-T09-PILOT-V9-LOCAL-FINALIZER-AUTONOMOUS-0002"),
    execution_contract_path=f"{_EXPERIMENT_ROOT}/contracts/T09_PILOT_EXECUTION_CONTRACT.json",
    command_manifest_path=f"{_EXPERIMENT_ROOT}/contracts/T09_PILOT_COMMAND_MANIFESTS.json",
    science_projection_path=f"{_EXPERIMENT_ROOT}/contracts/T09_PILOT_V9_SCIENCE_PROJECTION.json",
)
V10_PROVIDER_CONTRACT: Final = _contract(
    version="V10",
    source_commit="091fa6e690beeb628af54cec1e0a2849dd189e3b",
    host_run_id="RUN-T09-PILOT-HOST-AUTONOMOUS-0003",
    authorization_id=None,
    authorization_prefix="AUTH-T09-V10-",
    authorization_source_sha256=None,
    instance_name="giclab-t09-pilot-v10-autonomous-0003",
    # The provider contract binds the executable runtime profile.  The broader
    # preauthorization plan separately binds this implementation; embedding that
    # plan's hash here would create a circular source/plan identity.
    plan_path=f"{_PROPOSAL_ROOT}/T09_PILOT_RUNTIME_PROFILE_V10.yaml",
    plan_bytes=13_521,
    plan_sha256="ef16e0d01227482cd5a99694dd71a0cec53ef28894d80f8665c3b5b1a5c30695",
    profile_path=f"{_PROPOSAL_ROOT}/T09_PILOT_RUNTIME_PROFILE_V10.yaml",
    profile_bytes=13_521,
    profile_sha256="ef16e0d01227482cd5a99694dd71a0cec53ef28894d80f8665c3b5b1a5c30695",
    run_ids=(
        "RUN-T09-TASK-A-REACTIVE-AUTONOMOUS-0003",
        "RUN-T09-TASK-A-SIMULATIVE-AUTONOMOUS-0003",
        "RUN-T09-TASK-B-SIMULATIVE-AUTONOMOUS-0003",
        "RUN-T09-TASK-B-REACTIVE-AUTONOMOUS-0003",
    ),
    image_qualification_ids=("QUAL-T09-PILOT-V10-IMAGE-AUTONOMOUS-0003",),
    active_image_qualification_id="QUAL-T09-PILOT-V10-IMAGE-AUTONOMOUS-0003",
    replacement_image_tag="giclab/t09-pilot-v10:93fb8d72de71-autonomous-0003",
    container_prefix="giclab-t09-pilot-v10-autonomous-",
    image_materialization_policy="retained-import-or-one-fallback-build",
    max_launch_count=8,
    prior_t09_cost_usd=29.3502995579,
    preflight_lambda_cost_cap_usd=10.0,
    campaign_lambda_cost_cap_usd=8.0,
    campaign_openai_cost_cap_usd=40.0,
    campaign_aggregate_cost_cap_usd=58.0,
    cumulative_t09_cost_cap_usd=90.0,
    frozen_run_manifest_id="RUN-MANIFEST-EXP0001-PILOT-V10-AUTONOMOUS-0003",
    local_finalizer_qualification_id=("QUAL-T09-PILOT-V10-LOCAL-FINALIZER-AUTONOMOUS-0003"),
    execution_contract_path=(
        f"{_EXPERIMENT_ROOT}/contracts/proposals/T09_PILOT_EXECUTION_CONTRACT_V10.json"
    ),
    command_manifest_path=(
        f"{_EXPERIMENT_ROOT}/contracts/proposals/T09_PILOT_COMMAND_MANIFESTS_V10.json"
    ),
)
V11_PROVIDER_CONTRACT: Final = _contract(
    version="V11",
    source_commit="1c6b093699288f37aa23526fe1e1672e50280093",
    host_run_id="RUN-T09-PILOT-HOST-AUTONOMOUS-0004",
    authorization_id=None,
    authorization_prefix="AUTH-T09-V11-",
    authorization_source_sha256=None,
    instance_name="giclab-t09-pilot-v11-autonomous-0004",
    # The provider contract binds the executable runtime profile.  The broader
    # preauthorization plan separately binds the reviewed implementation and
    # pending merge, avoiding a circular source/plan identity.
    plan_path=f"{_PROPOSAL_ROOT}/T09_PILOT_RUNTIME_PROFILE_V11.yaml",
    plan_bytes=13_826,
    plan_sha256="726eeef3be208ad22b3279f8192fa55cfba259d14bf85424716b4f3e71a4a850",
    profile_path=f"{_PROPOSAL_ROOT}/T09_PILOT_RUNTIME_PROFILE_V11.yaml",
    profile_bytes=13_826,
    profile_sha256="726eeef3be208ad22b3279f8192fa55cfba259d14bf85424716b4f3e71a4a850",
    run_ids=(
        "RUN-T09-TASK-A-REACTIVE-AUTONOMOUS-0004",
        "RUN-T09-TASK-A-SIMULATIVE-AUTONOMOUS-0004",
        "RUN-T09-TASK-B-SIMULATIVE-AUTONOMOUS-0004",
        "RUN-T09-TASK-B-REACTIVE-AUTONOMOUS-0004",
    ),
    image_qualification_ids=("QUAL-T09-PILOT-V11-IMAGE-AUTONOMOUS-0004",),
    active_image_qualification_id="QUAL-T09-PILOT-V11-IMAGE-AUTONOMOUS-0004",
    replacement_image_tag="giclab/t09-pilot-v11:93fb8d72de71-autonomous-0004",
    container_prefix="giclab-t09-pilot-v11-autonomous-",
    image_materialization_policy="retained-import-or-one-fallback-build",
    max_launch_count=8,
    prior_t09_cost_usd=33.14878958732642,
    preflight_lambda_cost_cap_usd=10.0,
    campaign_lambda_cost_cap_usd=8.0,
    campaign_openai_cost_cap_usd=40.0,
    campaign_aggregate_cost_cap_usd=58.0,
    cumulative_t09_cost_cap_usd=90.0,
    frozen_run_manifest_id="RUN-MANIFEST-EXP0001-PILOT-V11-AUTONOMOUS-0004",
    local_finalizer_qualification_id=("QUAL-T09-PILOT-V11-LOCAL-FINALIZER-AUTONOMOUS-0004"),
    execution_contract_path=(
        f"{_EXPERIMENT_ROOT}/contracts/proposals/T09_PILOT_EXECUTION_CONTRACT_V11.json"
    ),
    command_manifest_path=(
        f"{_EXPERIMENT_ROOT}/contracts/proposals/T09_PILOT_COMMAND_MANIFESTS_V11.json"
    ),
)
V12_PROVIDER_CONTRACT: Final = _contract(
    version="V12",
    source_commit="42a8ce6945c29f4221e03bb836f18421e50f3b1e",
    host_run_id="RUN-T09-PILOT-HOST-AUTONOMOUS-0005",
    authorization_id=None,
    authorization_prefix="AUTH-T09-V12-",
    authorization_source_sha256=None,
    instance_name="giclab-t09-pilot-v12-autonomous-0005",
    # The executable profile is independently hashed here.  The private
    # Category 3 overlay and receipt bind the eventual reviewed merge commit.
    plan_path=f"{_PROPOSAL_ROOT}/T09_PILOT_RUNTIME_PROFILE_V12.yaml",
    plan_bytes=14_485,
    plan_sha256="0fd1ce4cd0fbeef41405ac4773d8d2a67b6c0414013b8c4fb4293c5d234446ba",
    profile_path=f"{_PROPOSAL_ROOT}/T09_PILOT_RUNTIME_PROFILE_V12.yaml",
    profile_bytes=14_485,
    profile_sha256="0fd1ce4cd0fbeef41405ac4773d8d2a67b6c0414013b8c4fb4293c5d234446ba",
    run_ids=(
        "RUN-T09-TASK-A-REACTIVE-AUTONOMOUS-0005",
        "RUN-T09-TASK-A-SIMULATIVE-AUTONOMOUS-0005",
        "RUN-T09-TASK-B-SIMULATIVE-AUTONOMOUS-0005",
        "RUN-T09-TASK-B-REACTIVE-AUTONOMOUS-0005",
    ),
    image_qualification_ids=("QUAL-T09-PILOT-V12-IMAGE-AUTONOMOUS-0005",),
    active_image_qualification_id="QUAL-T09-PILOT-V12-IMAGE-AUTONOMOUS-0005",
    replacement_image_tag="giclab/t09-pilot-v12:93fb8d72de71-autonomous-0005",
    container_prefix="giclab-t09-pilot-v12-autonomous-",
    image_materialization_policy="retained-import-or-one-fallback-build",
    max_launch_count=8,
    prior_t09_cost_usd=33.14878958732642,
    preflight_lambda_cost_cap_usd=10.0,
    campaign_lambda_cost_cap_usd=8.0,
    campaign_openai_cost_cap_usd=40.0,
    campaign_aggregate_cost_cap_usd=58.0,
    cumulative_t09_cost_cap_usd=90.0,
    frozen_run_manifest_id="RUN-MANIFEST-EXP0001-PILOT-V12-AUTONOMOUS-0005",
    local_finalizer_qualification_id=("QUAL-T09-PILOT-V12-LOCAL-FINALIZER-AUTONOMOUS-0005"),
    execution_contract_path=(
        f"{_EXPERIMENT_ROOT}/contracts/proposals/T09_PILOT_EXECUTION_CONTRACT_V12.json"
    ),
    command_manifest_path=(
        f"{_EXPERIMENT_ROOT}/contracts/proposals/T09_PILOT_COMMAND_MANIFESTS_V12.json"
    ),
)
V13_PROVIDER_CONTRACT: Final = _contract(
    version="V13",
    source_commit="1097d640a7d319ef14a5f4bc79392b46ea09091d",
    host_run_id="RUN-T09-PILOT-HOST-AUTONOMOUS-0006",
    authorization_id=None,
    authorization_prefix="AUTH-T09-V13-",
    authorization_source_sha256=None,
    instance_name="giclab-t09-pilot-v13-autonomous-0006",
    plan_path=f"{_PROPOSAL_ROOT}/T09_PILOT_RUNTIME_PROFILE_V13.yaml",
    plan_bytes=14_487,
    plan_sha256="58159df775f8e3a30debdc327e8be29574ec68a5c34167012866382a09b75ca4",
    profile_path=f"{_PROPOSAL_ROOT}/T09_PILOT_RUNTIME_PROFILE_V13.yaml",
    profile_bytes=14_487,
    profile_sha256="58159df775f8e3a30debdc327e8be29574ec68a5c34167012866382a09b75ca4",
    run_ids=(
        "RUN-T09-TASK-A-REACTIVE-AUTONOMOUS-0006",
        "RUN-T09-TASK-A-SIMULATIVE-AUTONOMOUS-0006",
        "RUN-T09-TASK-B-SIMULATIVE-AUTONOMOUS-0006",
        "RUN-T09-TASK-B-REACTIVE-AUTONOMOUS-0006",
    ),
    image_qualification_ids=("QUAL-T09-PILOT-V13-IMAGE-AUTONOMOUS-0006",),
    active_image_qualification_id="QUAL-T09-PILOT-V13-IMAGE-AUTONOMOUS-0006",
    replacement_image_tag="giclab/t09-pilot-v13:93fb8d72de71-autonomous-0006",
    container_prefix="giclab-t09-pilot-v13-autonomous-",
    image_materialization_policy="retained-import-or-one-fallback-build",
    max_launch_count=8,
    prior_t09_cost_usd=33.528475082734792,
    preflight_lambda_cost_cap_usd=10.0,
    campaign_lambda_cost_cap_usd=8.0,
    campaign_openai_cost_cap_usd=40.0,
    campaign_aggregate_cost_cap_usd=58.0,
    cumulative_t09_cost_cap_usd=90.0,
    frozen_run_manifest_id="RUN-MANIFEST-EXP0001-PILOT-V13-AUTONOMOUS-0006",
    local_finalizer_qualification_id=("QUAL-T09-PILOT-V13-LOCAL-FINALIZER-AUTONOMOUS-0006"),
    execution_contract_path=(
        f"{_EXPERIMENT_ROOT}/contracts/proposals/T09_PILOT_EXECUTION_CONTRACT_V13.json"
    ),
    command_manifest_path=(
        f"{_EXPERIMENT_ROOT}/contracts/proposals/T09_PILOT_COMMAND_MANIFESTS_V13.json"
    ),
)


PROVIDER_CONTRACTS: Final[Mapping[str, T09ProviderContract]] = MappingProxyType(
    {
        contract.version: contract
        for contract in (
            V3_PROVIDER_CONTRACT,
            V4_PROVIDER_CONTRACT,
            V5_PROVIDER_CONTRACT,
            V6_PROVIDER_CONTRACT,
            V7_PROVIDER_CONTRACT,
            V8_PROVIDER_CONTRACT,
            V9_PROVIDER_CONTRACT,
            V10_PROVIDER_CONTRACT,
            V11_PROVIDER_CONTRACT,
            V12_PROVIDER_CONTRACT,
            V13_PROVIDER_CONTRACT,
        )
    }
)
PROVIDER_CONTRACTS_BY_PLAN_ID: Final[Mapping[str, T09ProviderContract]] = MappingProxyType(
    {contract.plan_id: contract for contract in PROVIDER_CONTRACTS.values()}
)


def provider_contract(version: str) -> T09ProviderContract:
    """Resolve one explicitly named contract; there is intentionally no default."""

    try:
        return PROVIDER_CONTRACTS[version]
    except KeyError:
        raise T09ProviderContractError(f"unsupported provider contract: {version}") from None


def provider_contract_for_plan_id(plan_id: str) -> T09ProviderContract:
    """Resolve an exact retained plan identity without a current/latest fallback."""

    try:
        return PROVIDER_CONTRACTS_BY_PLAN_ID[plan_id]
    except KeyError:
        raise T09ProviderContractError(f"unsupported provider plan identity: {plan_id}") from None


def load_provider_profile(
    repository: Path,
    contract: T09ProviderContract,
) -> Mapping[str, object]:
    """Load the selected source-controlled profile only after exact byte validation."""

    root = repository.resolve(strict=True)
    path = root / contract.provider_profile_path
    encoded = path.read_bytes()
    if (
        len(encoded) != contract.expected_provider_profile_bytes
        or hashlib.sha256(encoded).hexdigest() != contract.expected_provider_profile_sha256
    ):
        raise T09ProviderContractError("provider profile bytes differ from the selected contract")
    loaded = yaml.safe_load(encoded)
    if not isinstance(loaded, dict) or loaded.get("plan_id") != contract.provider_profile_id:
        raise T09ProviderContractError(
            "provider profile identity differs from the selected contract"
        )
    return cast(Mapping[str, object], loaded)


def load_provider_plan(
    repository: Path,
    contract: T09ProviderContract,
) -> Mapping[str, object]:
    """Load the selected version's provider plan with its exact retained identity."""

    root = repository.resolve(strict=True)
    path = root / contract.plan_path
    encoded = path.read_bytes()
    if (
        len(encoded) != contract.expected_plan_bytes
        or hashlib.sha256(encoded).hexdigest() != contract.expected_plan_sha256
    ):
        raise T09ProviderContractError("provider plan bytes differ from the selected contract")
    loaded = yaml.safe_load(encoded)
    if not isinstance(loaded, dict) or loaded.get("plan_id") != contract.plan_id:
        raise T09ProviderContractError("provider plan identity differs from the selected contract")
    return cast(Mapping[str, object], loaded)


def render_provider_entry_command(
    contract: T09ProviderContract,
    *,
    interpreter: str,
    repository: str,
    package_commit: str,
    authorization_ledger: str,
    dotenv: str,
    private_root: str,
    public_ipv4_file: str,
    ssh_public_key_file: str,
    launch_slot: int,
    model_metadata_receipt: str | None = None,
) -> tuple[str, ...]:
    """Render the historical provider CLI without consulting a latest-version global."""

    if launch_slot not in range(1, contract.max_launch_count + 1):
        raise T09ProviderContractError("launch slot exceeds the selected provider contract")
    command: tuple[str, ...] = (
        interpreter,
        "-m",
        "giclab.harness.t09_pragmatic_provider",
        "--provider-contract",
        contract.version,
        "--repository",
        repository,
        "--package-commit",
        package_commit,
        "--authorization-ledger",
        authorization_ledger,
        "--dotenv",
        dotenv,
        "--private-root",
        private_root,
        "launch",
        "--public-ipv4-file",
        public_ipv4_file,
        "--ssh-public-key-file",
        ssh_public_key_file,
        "--launch-slot",
        str(launch_slot),
    )
    if contract.version in {"V12", "V13"}:
        if model_metadata_receipt is None:
            raise T09ProviderContractError(
                "selected provider entry command requires the model metadata receipt"
            )
        command += ("--model-metadata-receipt", model_metadata_receipt)
    elif model_metadata_receipt is not None:
        raise T09ProviderContractError(
            "model metadata receipt is only valid for a receipt-bound provider contract"
        )
    return command
