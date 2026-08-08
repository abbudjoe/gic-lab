from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, cast

import pytest
from harness_test_support import valid_plan_data

from giclab.harness.models import (
    AdapterEventType,
    BudgetUsage,
    CommandSpec,
    EventProvenance,
    EventType,
    ExecutionAuthorization,
    HarnessEvent,
    IncrementalLimitEnforcement,
    InheritedEnvironmentBinding,
    NormalizedEvent,
    ResourceProjection,
    inherited_environment_binding,
    thaw_json,
)
from giclab.harness.plan import (
    RunPlanError,
    load_run_plan,
    run_plan_from_mapping,
    validate_run_plan_data,
)
from giclab.validation import ROOT


def test_smoke_cannot_allow_interpretation_in_schema_or_typed_model() -> None:
    data = valid_plan_data(interpretation_allowed=True)
    errors = validate_run_plan_data(data, schema_root=ROOT)
    assert any("False was expected" in error for error in errors)
    with pytest.raises(ValueError, match="smoke runs"):
        run_plan_from_mapping(data)


def test_authorized_run_requires_nonempty_reference() -> None:
    data = valid_plan_data(authorized=True)
    data["execution"]["authorization"]["authorization_reference"] = ""
    errors = validate_run_plan_data(data, schema_root=ROOT)
    assert any("non-empty" in error or "should be non-empty" in error for error in errors)
    with pytest.raises(ValueError, match="authorization_reference"):
        run_plan_from_mapping(data)


def test_authorized_run_requires_a_canonical_command_binding() -> None:
    data = valid_plan_data(authorized=True)
    data["execution"]["authorization"]["command_sha256"] = None
    assert validate_run_plan_data(data, schema_root=ROOT)
    with pytest.raises(ValueError, match="command_sha256"):
        run_plan_from_mapping(data)


def test_unauthorized_run_cannot_claim_authorization_reference() -> None:
    data = valid_plan_data()
    data["execution"]["authorization"]["authorization_reference"] = "AUTH-STALE"
    errors = validate_run_plan_data(data, schema_root=ROOT)
    assert errors
    assert any("null" in error for error in errors)


def test_unknown_model_and_dataset_revisions_remain_explicit() -> None:
    plan = run_plan_from_mapping(valid_plan_data())
    assert plan.sources.model_revision is None
    assert plan.sources.dataset_revision is None


def test_unavailable_source_commits_and_digests_are_explicit_but_not_invented() -> None:
    data = valid_plan_data()
    for field in (
        "giclab_commit",
        "upstream_commit",
        "protocol_sha256",
        "config_sha256",
        "environment_sha256",
    ):
        data["sources"][field] = "unknown"
    assert validate_run_plan_data(data, schema_root=ROOT) == []
    plan = run_plan_from_mapping(data)
    assert plan.sources.unknown_fields == (
        "giclab_commit",
        "upstream_commit",
        "protocol_sha256",
        "config_sha256",
        "environment_sha256",
    )


def test_malformed_source_identity_is_neither_a_pin_nor_unknown() -> None:
    data = valid_plan_data()
    data["sources"]["upstream_commit"] = "UNKNOWN"
    assert validate_run_plan_data(data, schema_root=ROOT)
    with pytest.raises(ValueError, match="or 'unknown'"):
        run_plan_from_mapping(data)


def test_artifact_root_must_be_relative_and_confined() -> None:
    data = valid_plan_data(artifact_root="../escape")
    assert validate_run_plan_data(data, schema_root=ROOT)
    with pytest.raises(ValueError, match="parent"):
        run_plan_from_mapping(data)


@pytest.mark.parametrize(
    "argv",
    [
        ("tool", "--api-key=plain-text"),
        ("tool", "--token"),
        ("tool", "sk-" + "a" * 26),
    ],
)
def test_secret_like_command_arguments_are_refused(argv: tuple[str, ...]) -> None:
    with pytest.raises(ValueError, match="secret"):
        CommandSpec(argv=(sys.executable, *argv[1:]), cwd=Path.cwd(), timeout_seconds=1)


def test_secret_environment_is_named_without_a_value() -> None:
    command = CommandSpec(
        argv=(sys.executable,),
        cwd=Path.cwd(),
        timeout_seconds=1,
        secret_environment=("SYNTHETIC_API_KEY",),
    )
    assert command.secret_environment == ("SYNTHETIC_API_KEY",)


def test_literal_secret_environment_name_is_refused() -> None:
    with pytest.raises(ValueError, match="secret-bearing"):
        CommandSpec(
            argv=(sys.executable,),
            cwd=Path.cwd(),
            timeout_seconds=1,
            environment={"SYNTHETIC_TOKEN": "plain"},
        )


def test_secret_like_environment_name_cannot_bypass_redaction_by_inheritance() -> None:
    with pytest.raises(ValueError, match="secret-bearing"):
        InheritedEnvironmentBinding("SYNTHETIC_API_KEY", "f" * 64)


def test_command_requires_an_absolute_resolved_executable() -> None:
    with pytest.raises(ValueError, match="absolute resolved executable"):
        CommandSpec(argv=("python",), cwd=Path.cwd(), timeout_seconds=1)


def test_nonwall_projection_requires_an_explicit_adapter_enforcement_contract() -> None:
    with pytest.raises(ValueError, match="adapter-command hard-limit"):
        ResourceProjection(tool_calls=1)
    projection = ResourceProjection(
        model_tokens=10,
        tool_calls=1,
        enforcement=IncrementalLimitEnforcement.ADAPTER_COMMAND,
    )
    assert projection.has_usage


@pytest.mark.parametrize(
    "argv",
    [
        (sys.executable, "bad\0argument"),
        (f"{sys.executable}\0suffix",),
    ],
)
def test_command_arguments_reject_nul_bytes(argv: tuple[str, ...]) -> None:
    with pytest.raises(ValueError, match="NUL"):
        CommandSpec(argv=argv, cwd=Path.cwd(), timeout_seconds=1)


def test_environment_values_reject_nul_bytes() -> None:
    with pytest.raises(ValueError, match="NUL"):
        CommandSpec(
            argv=(sys.executable,),
            cwd=Path.cwd(),
            timeout_seconds=1,
            environment={"SYNTHETIC_MODE": "bad\0value"},
        )
    with pytest.raises(ValueError, match="NUL"):
        inherited_environment_binding("PATH", "bad\0value")


def test_run_plan_schema_rejects_unknown_fields() -> None:
    data = deepcopy(valid_plan_data())
    data["source_specific_assumption"] = True
    assert any(
        "Additional properties" in error for error in validate_run_plan_data(data, schema_root=ROOT)
    )


@pytest.mark.parametrize(
    "needle,replacement",
    [
        ('"authorized": false', '"authorized": false, "authorized": true'),
        (
            '"max_wall_seconds": 10',
            '"max_wall_seconds": 10, "max_wall_seconds": 999',
        ),
    ],
)
def test_json_run_plan_rejects_nested_duplicate_control_keys(
    tmp_path: Path,
    needle: str,
    replacement: str,
) -> None:
    path = tmp_path / "plan.json"
    encoded = json.dumps(valid_plan_data())
    path.write_text(encoded.replace(needle, replacement), encoding="utf-8")
    with pytest.raises(RunPlanError, match="duplicate JSON key"):
        load_run_plan(path, schema_root=ROOT)


def test_event_payload_is_recursively_copied_and_immutable() -> None:
    original: dict[str, Any] = {"nested": {"items": ["stable"]}}
    event = HarnessEvent(
        run_id="RUN-SYNTHETIC-001",
        attempt=1,
        sequence=1,
        timestamp_utc="2026-08-07T12:00:00Z",
        event_type=EventType.OBSERVATION,
        source="synthetic-adapter",
        provenance=EventProvenance.OBSERVED,
        payload=original,
    )
    cast(list[str], cast(dict[str, Any], original["nested"])["items"]).append("mutated")
    assert thaw_json(event.payload) == {"nested": {"items": ["stable"]}}
    with pytest.raises(TypeError):
        cast(Any, event.payload)["new"] = True
    nested = cast(Any, event.payload["nested"])
    with pytest.raises(TypeError):
        nested["new"] = True
    with pytest.raises(AttributeError):
        nested["items"].append("changed")


def test_adapter_events_cannot_claim_harness_control_types_or_source() -> None:
    with pytest.raises(ValueError, match="scientific event type"):
        NormalizedEvent(
            event_type=EventType.RUN_STOPPED,  # type: ignore[arg-type]
            source="synthetic-adapter",
            provenance=EventProvenance.OBSERVED,
            payload={},
        )
    with pytest.raises(ValueError, match="reserved harness identity"):
        NormalizedEvent(
            event_type=AdapterEventType.METRIC,
            source="giclab-harness",
            provenance=EventProvenance.OBSERVED,
            payload={},
        )


def test_event_payload_rejects_nested_recognizable_credential() -> None:
    with pytest.raises(ValueError, match="credential material"):
        HarnessEvent(
            run_id="RUN-SYNTHETIC-001",
            attempt=1,
            sequence=1,
            timestamp_utc="2026-08-07T12:00:00Z",
            event_type=EventType.OBSERVATION,
            source="synthetic-adapter",
            provenance=EventProvenance.OBSERVED,
            payload={"nested": ["sk-" + "x" * 26]},
        )
    with pytest.raises(ValueError, match="credential material"):
        HarnessEvent(
            run_id="RUN-SYNTHETIC-001",
            attempt=1,
            sequence=1,
            timestamp_utc="2026-08-07T12:00:00Z",
            event_type=EventType.OBSERVATION,
            source="synthetic-adapter",
            provenance=EventProvenance.OBSERVED,
            payload={"ghp_" + "x" * 22: "nested-key"},
        )


def test_authorization_reference_is_a_secret_safe_stable_identifier() -> None:
    with pytest.raises(ValueError, match="credential material"):
        ExecutionAuthorization(True, "sk-" + "x" * 26, "f" * 64)
    with pytest.raises(ValueError, match="stable identifier"):
        ExecutionAuthorization(True, "https://example.invalid/?signature=value", "f" * 64)


@pytest.mark.parametrize(
    "field,value",
    [
        ("wall_seconds", -1),
        ("cost_usd", float("inf")),
        ("model_tokens", -1),
        ("output_bytes", -1),
    ],
)
def test_budget_usage_rejects_invalid_values(field: str, value: float | int) -> None:
    with pytest.raises(ValueError, match=field):
        BudgetUsage(**{field: value})
