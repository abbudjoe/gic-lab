from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from giclab.control.category3 import (
    Category3Request,
    execute_category3_transaction,
    repository_identity,
)
from giclab.control.composition import compose_control_plane
from giclab.control.proofs import ValidatedShadowRehearsal, validate_shadow_rehearsal
from giclab.control.registry_validation import validate_registry_completeness
from giclab.control.shadow_effects import ShadowFaultPlan, build_production_shadow_assembly
from giclab.control.state_capsule import generate_state_capsule
from giclab.control.version_lint import validate_active_version_dispatch
from giclab.harness.t09_provider_contracts import T09ProviderContract


@lru_cache(maxsize=4)
def validated_rehearsal(
    repository_text: str,
    contract: T09ProviderContract,
) -> ValidatedShadowRehearsal:
    repository = Path(repository_text)
    lint = validate_active_version_dispatch(repository)
    registry = validate_registry_completeness(repository)
    composition = compose_control_plane(
        repository,
        contract=contract,
        registry_receipt=registry,
        version_lint_receipt=lint,
    )
    capsule = generate_state_capsule(
        repository,
        registry_complete=True,
        composition_valid=True,
        version_lint_valid=True,
        shadow_happy_path=False,
        failure_matrix_valid=False,
    )
    return validate_shadow_rehearsal(
        repository,
        contract,
        registry_receipt=registry,
        version_lint_receipt=lint,
        composition_receipt=composition,
        state_capsule=capsule,
    )


def execute_shadow_plan(
    repository: Path,
    contract: T09ProviderContract,
    plan: ShadowFaultPlan,
) -> dict[str, object]:
    rehearsal = validated_rehearsal(repository.as_posix(), contract)
    world = build_production_shadow_assembly(
        repository,
        contract,
        plan,
        rehearsal=rehearsal,
    )
    commit, tree = repository_identity(repository)
    return execute_category3_transaction(
        Category3Request(
            repository=repository,
            contract=contract,
            scenario=plan.name,
            expected_repository_commit=commit,
            expected_repository_tree=tree,
            control_proof=rehearsal,
        ),
        adapters=world.adapters(),
    )
