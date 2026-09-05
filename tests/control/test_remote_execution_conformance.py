from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, ValidationError

from giclab.control.live_conformance import run_live_effect_conformance
from giclab.control.remote_execution_conformance import (
    run_remote_execution_bridge_conformance,
)
from giclab.registry import load_json

ROOT = Path(__file__).resolve().parents[2]


def _controller_receipt() -> dict[str, object]:
    return {
        "complete": True,
        "semantic_sha256": "a" * 64,
        "shared_controller_entry_point": ("giclab.control.category3.execute_category3_transaction"),
        "production_assembly_entry_point": (
            "giclab.control.production.build_production_adapter_assembly"
        ),
        "temporary_package": {
            "controller_terminal_state": "category3-live-complete-clean",
            "condition_traces": {f"condition-{index}": {} for index in range(4)},
            "first_pair_checkpoint": {
                "retained_first_pair_decision_invoked": True,
            },
            "raw_finalizer_evaluator_chain": {
                "finalizer_consumed_raw_manifests": True,
                "evaluator_consumed_finalized_sessions": True,
            },
            "cleanup": {
                "state": "complete",
                "resumed": False,
                "provider_resources_zero": True,
                "security_restored": True,
                "privacy_clean": True,
            },
            "review_failure_subreceipts": {
                "ambiguous-send-essential-failure": {"cleanup_complete": True},
            },
        },
    }


def test_remote_execution_bridge_conformance_is_deterministic_and_schema_exact() -> None:
    first = run_remote_execution_bridge_conformance(
        ROOT,
        live_effect_conformance_receipt=_controller_receipt(),
    )
    second = run_remote_execution_bridge_conformance(
        ROOT,
        live_effect_conformance_receipt=_controller_receipt(),
    )
    assert first == second
    semantic = first.pop("semantic_sha256")
    assert (
        semantic
        == hashlib.sha256(
            json.dumps(first, allow_nan=False, separators=(",", ":"), sort_keys=True).encode()
        ).hexdigest()
    )
    first["semantic_sha256"] = semantic
    Draft202012Validator(
        load_json(ROOT / "schemas/t09-remote-execution-bridge-conformance.schema.json")
    ).validate(first)
    assert first["complete"] is True
    assert first["host_phase_entrypoints"]["operations"] == [  # type: ignore[index]
        "host-transfer-verify",
        "host-preflight",
        "host-qualify",
        "host-freeze",
        "host-cleanup",
    ]
    assert first["host_phase_entrypoints"]["subprocess_count"] == 5  # type: ignore[index]
    assert (  # type: ignore[index]
        first["host_phase_entrypoints"]["process_model"] == "forked-selected-contract-child"
    )
    assert first["host_phase_entrypoints"]["tracked_runner_loaded"] is True  # type: ignore[index]
    assert (  # type: ignore[index]
        first["host_phase_entrypoints"]["serialized_contract_override"] is False
    )
    assert first["duplex_condition_sessions"]["session_count"] == 4  # type: ignore[index]
    assert first["duplex_condition_sessions"]["model_call_count"] == 8  # type: ignore[index]
    assert first["duplex_condition_sessions"]["browser_action_count"] == 8  # type: ignore[index]


def test_remote_execution_bridge_conformance_schema_rejects_missing_coupling() -> None:
    document = run_remote_execution_bridge_conformance(
        ROOT,
        live_effect_conformance_receipt=_controller_receipt(),
    )
    document["sole_accountant"]["coupling_probe_passed"] = False  # type: ignore[index]
    with pytest.raises(ValidationError):
        Draft202012Validator(
            load_json(ROOT / "schemas/t09-remote-execution-bridge-conformance.schema.json")
        ).validate(document)


def test_remote_execution_bridge_conformance_uses_full_shared_controller() -> None:
    live = run_live_effect_conformance(ROOT)
    receipt = run_remote_execution_bridge_conformance(
        ROOT,
        live_effect_conformance_receipt=live,
    )
    assert receipt["controller_conformance"] == {
        "receipt_semantic_sha256": live["semantic_sha256"],
        "terminal_state": "category3-live-complete-clean",
        "condition_session_count": 4,
        "first_pair_checkpoint_retained": True,
        "raw_finalizer_evaluator_chain": True,
        "cleanup_to_zero": True,
        "shared_controller_used": True,
        "shared_production_assembly_used": True,
    }
    assert receipt["zero_real_effects"] == {
        "secret_reads": 0,
        "authenticated_metadata_requests": 0,
        "provider_requests": 0,
        "cloud_mutations": 0,
        "live_ssh": 0,
        "docker": 0,
        "browser": 0,
        "scientific_actions": 0,
        "condition_reservations": 0,
        "new_cost_usd": "0.00",
    }
