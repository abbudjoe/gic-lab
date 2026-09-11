from __future__ import annotations

import copy
import subprocess
from pathlib import Path

import pytest

from giclab.control import incidents as incidents_module
from giclab.control.incidents import validate_incident_document, validate_incidents
from giclab.registry import load_json

ROOT = Path(__file__).resolve().parents[2]
INCIDENT_PATH = ROOT / "control/incidents/INC-T09-V16-LIFECYCLE-REGISTRY.json"


@pytest.mark.parametrize("exit_code", [0, 1])
def test_incident_diagnostics_remain_private_without_changing_exit(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    exit_code: int,
) -> None:
    stdout = b"fixture diagnostic /Users/synthetic/report\n"
    stderr = b"fixture diagnostic /tmp/synthetic/report\n"
    original_run = incidents_module.subprocess.run

    def run(*args, **kwargs):
        if args[0][1:3] == ["-m", "pytest"]:
            home = Path(kwargs["env"]["HOME"])
            assert home.is_dir() and home.stat().st_mode & 0o777 == 0o700
            assert home.parent.name.startswith("incident-regressions-")
            return subprocess.CompletedProcess(args[0], exit_code, stdout, stderr)
        return original_run(*args, **kwargs)

    monkeypatch.setattr(incidents_module.subprocess, "run", run)
    passed, public_output = incidents_module._run_regressions(
        tmp_path, ["tests/example.py::test_example"]
    )
    assert passed is (exit_code == 0)
    assert public_output == f"pytest exit {exit_code}; 1 requested regression nodes"
    captured = capsys.readouterr()
    assert captured.out == ""
    assert stdout.decode() + stderr.decode() in captured.err
    assert "/Users/" not in public_output and "/tmp/" not in public_output

    receipt = validate_incidents(ROOT, execute_regressions=True)
    assert receipt["complete"] is (exit_code == 0)
    assert all(
        incident["regressions_passed"] is (exit_code == 0) for incident in receipt["incidents"]
    )
    assert "/Users/" not in str(receipt) and "/tmp/" not in str(receipt)
    assert stdout.decode() + stderr.decode() in capsys.readouterr().err


def test_incident_regression_child_runs_the_pinned_offline_evaluator() -> None:
    passed, output = incidents_module._run_regressions(
        ROOT,
        [
            "tests/control/test_production_coupling.py::"
            "test_effect_produced_answer_changes_retained_evaluator_output"
        ],
    )
    assert passed, output
    assert output == "pytest exit 0; 1 requested regression nodes"


def test_v16_incident_validates_and_named_regressions_pass() -> None:
    receipt = validate_incidents(ROOT, execute_regressions=True)
    assert receipt["complete"] is True
    assert receipt["incident_count"] == 8
    incidents = {
        incident["incident_id"]: incident
        for incident in receipt["incidents"]  # type: ignore[union-attr]
    }
    assert set(incidents) == {
        "INC-T09-CONTROL-FIXED-TARGET-SELECTION",
        "INC-T09-CONTROL-LIVE-BOUNDARY-EXACT-HEAD-REVIEW",
        "INC-T09-CONTROL-SECOND-EXACT-HEAD-RESIDUAL-BOUNDARY",
        "INC-T09-CONTROL-SHADOW-SHAPED-LIVE-BOUNDARY",
        "INC-T09-CONTROL-THIRD-EXACT-HEAD-RESIDUAL-BOUNDARY",
        "INC-T09-V16-LIFECYCLE-REGISTRY",
        "INC-T09-V17-PACKAGE-VIABILITY-SHARED-BRIDGE",
        "INC-T09-RETAINED-REMOTE-TRANSACTION-REVIEW",
    }
    assert all(incident["regressions_passed"] is True for incident in incidents.values())
    assert len(incidents["INC-T09-RETAINED-REMOTE-TRANSACTION-REVIEW"]["regression_nodes"]) == 21
    assert len(incidents["INC-T09-V16-LIFECYCLE-REGISTRY"]["regression_nodes"]) == 3
    assert len(incidents["INC-T09-CONTROL-FIXED-TARGET-SELECTION"]["regression_nodes"]) == 4
    assert len(incidents["INC-T09-CONTROL-SHADOW-SHAPED-LIVE-BOUNDARY"]["regression_nodes"]) == 8
    assert (
        len(incidents["INC-T09-CONTROL-LIVE-BOUNDARY-EXACT-HEAD-REVIEW"]["regression_nodes"]) >= 12
    )
    assert (
        len(incidents["INC-T09-CONTROL-SECOND-EXACT-HEAD-RESIDUAL-BOUNDARY"]["regression_nodes"])
        >= 13
    )
    assert (
        len(incidents["INC-T09-CONTROL-THIRD-EXACT-HEAD-RESIDUAL-BOUNDARY"]["regression_nodes"])
        >= 12
    )
    assert len(incidents["INC-T09-V17-PACKAGE-VIABILITY-SHARED-BRIDGE"]["regression_nodes"]) == 6


def test_resolved_incident_with_missing_regression_fails() -> None:
    document = copy.deepcopy(load_json(INCIDENT_PATH))
    document["regressions"] = [
        {"kind": "test-node", "reference": "tests/control/missing.py::test_missing"}
    ]
    errors = validate_incident_document(ROOT, document)
    assert any("unavailable" in error for error in errors)


def test_offline_incident_without_composition_or_shadow_coverage_fails() -> None:
    document = copy.deepcopy(load_json(INCIDENT_PATH))
    document["coverage"] = []
    errors = validate_incident_document(ROOT, document)
    assert any("offline incident lacks" in error for error in errors)


def test_incident_facts_are_hash_bound_and_cannot_claim_science() -> None:
    document = copy.deepcopy(load_json(INCIDENT_PATH))
    facts = document["immutable_facts"]
    assert isinstance(facts, dict)
    facts["empirical_attempts"] = 1
    document["scientific_result"] = "negative-result"
    document["scientific_interpretation_allowed"] = True
    errors = validate_incident_document(ROOT, document)
    assert "immutable facts hash drifted" in errors
    assert "incident claims a scientific result" in errors
