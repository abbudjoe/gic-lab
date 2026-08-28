from __future__ import annotations

from pathlib import Path

import pytest

from giclab.ci_pytest_parity import (
    PytestOutcome,
    PytestParityError,
    compare_outcomes,
    load_pytest_outcome,
)


def _outcome(*failures: str, passing: tuple[str, ...] = ()) -> PytestOutcome:
    collected = set(failures) | set(passing)
    index = 0
    while len(collected) < 10:
        collected.add(f"tests/test_ok.py::test_{index}")
        index += 1
    return PytestOutcome(
        total=10,
        passed=10 - len(failures),
        failed=len(failures),
        skipped=0,
        errors=0,
        collected_node_ids=frozenset(collected),
        failing_node_ids=frozenset(failures),
    )


def test_pytest_parity_accepts_only_unchanged_or_newly_passing_failures() -> None:
    comparison = compare_outcomes(
        _outcome("tests/test_old.py::test_one", "tests/test_old.py::test_two"),
        _outcome("tests/test_old.py::test_two", passing=("tests/test_old.py::test_one",)),
    )
    assert comparison["parity_passed"] is True
    assert comparison["newly_failing"] == []
    assert comparison["newly_passing"] == ["tests/test_old.py::test_one"]
    assert comparison["unchanged_failing"] == ["tests/test_old.py::test_two"]
    assert comparison["missing_base_failures"] == []


def test_pytest_parity_rejects_one_head_only_failure() -> None:
    comparison = compare_outcomes(
        _outcome("tests/test_old.py::test_one"),
        _outcome("tests/test_old.py::test_one", "tests/test_new.py::test_regression"),
    )
    assert comparison["parity_passed"] is False
    assert comparison["newly_failing"] == ["tests/test_new.py::test_regression"]


def test_pytest_parity_rejects_deleting_an_inherited_failure() -> None:
    base = _outcome("tests/test_old.py::test_one")
    head = _outcome()
    comparison = compare_outcomes(base, head)
    assert comparison["parity_passed"] is False
    assert comparison["missing_base_failures"] == ["tests/test_old.py::test_one"]


def test_junit_loader_retains_exact_parameterized_node_ids(tmp_path: Path) -> None:
    report = tmp_path / "pytest.xml"
    report.write_text(
        """<?xml version="1.0" encoding="utf-8"?>
<testsuites>
  <testsuite name="pytest" errors="0" failures="1" skipped="1" tests="3">
    <testcase classname="tests.test_sample" name="test_ok" />
    <testcase classname="tests.test_sample" name="test_bad[value-2]"><failure /></testcase>
    <testcase classname="tests.test_sample" name="test_skip"><skipped /></testcase>
  </testsuite>
</testsuites>
""",
        encoding="utf-8",
    )
    outcome = load_pytest_outcome(report)
    assert outcome == PytestOutcome(
        total=3,
        passed=1,
        failed=1,
        skipped=1,
        errors=0,
        collected_node_ids=frozenset(
            {
                "tests/test_sample.py::test_ok",
                "tests/test_sample.py::test_bad[value-2]",
                "tests/test_sample.py::test_skip",
            }
        ),
        failing_node_ids=frozenset({"tests/test_sample.py::test_bad[value-2]"}),
    )


def test_junit_loader_rejects_duplicate_failure_identity(tmp_path: Path) -> None:
    report = tmp_path / "pytest.xml"
    report.write_text(
        """<testsuite errors="0" failures="2" skipped="0" tests="2">
<testcase classname="tests.test_sample" name="test_bad"><failure /></testcase>
<testcase classname="tests.test_sample" name="test_bad"><failure /></testcase>
</testsuite>""",
        encoding="utf-8",
    )
    with pytest.raises(PytestParityError, match="incomplete or duplicated"):
        load_pytest_outcome(report)
