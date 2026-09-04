from __future__ import annotations

import copy
import inspect
import json
from pathlib import Path
from typing import cast

import pytest
from _synthetic_successor import copy_working_repository
from jsonschema import Draft202012Validator, RefResolver

from giclab.control.effects import EFFECT_PROTOCOL_VERSION, LowLevelEffects
from giclab.control.live_method_viability import (
    EXPECTED_PHASE_ORDER,
    validate_live_method_viability,
)
from giclab.control.proofs import ControlProofError, _validate_schema
from giclab.registry import load_json

ROOT = Path(__file__).resolve().parents[2]


def _method_names() -> tuple[str, ...]:
    return tuple(
        name
        for name, value in LowLevelEffects.__dict__.items()
        if not name.startswith("_") and (inspect.isfunction(value) or isinstance(value, property))
    )


def test_live_method_viability_has_one_launch_seam_and_zero_gaps() -> None:
    receipt = validate_live_method_viability(ROOT)
    schema_path = ROOT / "schemas/t09-live-method-viability.schema.json"
    schema = load_json(schema_path)
    method_schema = load_json(ROOT / "schemas/t09-live-method-map.schema.json")
    resolver = RefResolver(
        base_uri=schema_path.resolve().as_uri(),
        referrer=schema,
        store={str(method_schema["$id"]): method_schema},
    )
    Draft202012Validator(schema, resolver=resolver).validate(receipt)
    assert receipt["effect_protocol_version"] == EFFECT_PROTOCOL_VERSION == "2.0.0"
    methods = receipt["methods"]
    assert isinstance(methods, list)
    assert tuple(item["method_name"] for item in methods) == _method_names()
    assert all(item["live_mapping_complete"] is True for item in methods)
    assert receipt["shared_phase_order"] == list(EXPECTED_PHASE_ORDER)
    assert receipt["unresolved_methods"] == []
    assert receipt["findings"] == []
    assert receipt["real_effects_performed"] == 0
    assert receipt["complete"] is True


def test_control_proof_validator_resolves_the_local_method_schema_without_network() -> None:
    receipt = validate_live_method_viability(ROOT)
    _validate_schema(ROOT, "schemas/t09-live-method-viability.schema.json", receipt)

    invalid = copy.deepcopy(receipt)
    methods = invalid["methods"]
    assert isinstance(methods, list)
    methods[0]["method_name"] = "not-a-python-method"
    with pytest.raises(ControlProofError, match="validation failed"):
        _validate_schema(ROOT, "schemas/t09-live-method-viability.schema.json", invalid)


def test_viability_fails_when_one_live_method_mapping_is_removed(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    copy_working_repository(ROOT, repository)
    map_path = repository / "control/live-method-map.json"
    method_map = load_json(map_path)
    methods = method_map["methods"]
    assert isinstance(methods, list)
    removed = methods.pop()
    assert isinstance(removed, dict)
    map_path.write_text(json.dumps(method_map), encoding="utf-8")
    receipt = validate_live_method_viability(repository)
    unresolved = cast(list[str], receipt["unresolved_methods"])
    findings = cast(list[str], receipt["findings"])
    assert removed["method_name"] in unresolved
    assert receipt["complete"] is False
    assert any("protocol-surface" in finding for finding in findings)


def test_viability_source_rejects_a_secondary_provider_launch_method() -> None:
    source = (ROOT / "src/giclab/control/effects.py").read_text(encoding="utf-8")
    synthetic = (ROOT / "tests/control/_synthetic_successor.py").read_text(encoding="utf-8")
    production = (ROOT / "src/giclab/control/production.py").read_text(encoding="utf-8")
    assert "def provider_launch(" not in source
    assert "def provider_launch(" not in synthetic
    assert production.count("launch_campaign(") == 1
    assert "campaign_transport(" in production


def test_synthetic_successor_declares_repaired_protocol_without_live_artifacts() -> None:
    source = (ROOT / "tests/control/_synthetic_successor.py").read_text(encoding="utf-8")
    assert 'effect_protocol_version="2.0.0"' in source
    assert "build_live_shaped_no_network_effects" in source
    assert "provider_launch" not in source
    assert not list(ROOT.rglob("*AUTONOMOUS-0010*"))
