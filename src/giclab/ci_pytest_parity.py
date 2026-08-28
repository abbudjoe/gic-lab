"""Compare pull-request pytest failures with an exact detached base checkout.

This is deliberately narrower than ``make check``.  Formatting, linting, typing,
repository validation, and site generation remain strict gates.  Only the inherited
pytest failure set may use baseline parity, and a head-only failure always fails CI.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Final


class PytestParityError(RuntimeError):
    """The base/head pytest comparison was incomplete or introduced a failure."""


PRIVATE_LOCAL_NODE_IDS: Final = (
    "tests/test_t09_retry4.py::test_retry4_private_postrun_union_reconstructs_the_frozen_runtime",
    "tests/test_t09_retry4.py::test_retry4_private_clock_reconciliation_uses_the_frozen_empirical_origin",
    "tests/test_t09_retry4.py::test_retry4_private_postrun_overlay_is_exact_and_reconstructable",
    "tests/test_t09_retry4.py::test_retry4_exact_slot1_preentry_stage_is_source_reconstructable",
    "tests/test_t09_retry5.py::test_autonomous_slot2_authority_uses_distinct_nested_and_tree_hashes",
)


@dataclass(frozen=True, slots=True)
class PytestOutcome:
    total: int
    passed: int
    failed: int
    skipped: int
    errors: int
    collected_node_ids: frozenset[str]
    failing_node_ids: frozenset[str]


def _node_id(testcase: ET.Element) -> str:
    classname = testcase.attrib.get("classname")
    name = testcase.attrib.get("name")
    if not classname or not name:
        raise PytestParityError("pytest JUnit testcase lacks its identity")
    module = classname.replace(".", "/")
    if module.startswith("tests/"):
        module = f"{module}.py"
    return f"{module}::{name}"


def load_pytest_outcome(path: Path) -> PytestOutcome:
    """Load counts and the exact failed/error node set from pytest JUnit XML."""

    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    if not suites:
        raise PytestParityError("pytest JUnit report contains no test suite")
    total = sum(int(suite.attrib.get("tests", "0")) for suite in suites)
    failed = sum(int(suite.attrib.get("failures", "0")) for suite in suites)
    errors = sum(int(suite.attrib.get("errors", "0")) for suite in suites)
    skipped = sum(int(suite.attrib.get("skipped", "0")) for suite in suites)
    testcases = [testcase for suite in suites for testcase in suite.findall("testcase")]
    collected_node_ids = frozenset(_node_id(testcase) for testcase in testcases)
    failing_node_ids = frozenset(
        _node_id(testcase)
        for testcase in testcases
        if testcase.find("failure") is not None or testcase.find("error") is not None
    )
    if len(collected_node_ids) != total:
        raise PytestParityError("pytest JUnit collection identities are incomplete or duplicated")
    if len(failing_node_ids) != failed + errors:
        raise PytestParityError("pytest JUnit failure identities are incomplete or duplicated")
    return PytestOutcome(
        total=total,
        passed=total - failed - errors - skipped,
        failed=failed,
        skipped=skipped,
        errors=errors,
        collected_node_ids=collected_node_ids,
        failing_node_ids=failing_node_ids,
    )


def compare_outcomes(base: PytestOutcome, head: PytestOutcome) -> dict[str, object]:
    """Return a deterministic comparison and reject every head-only failure."""

    newly_failing = sorted(head.failing_node_ids - base.failing_node_ids)
    newly_passing = sorted(base.failing_node_ids - head.failing_node_ids)
    unchanged_failing = sorted(base.failing_node_ids & head.failing_node_ids)
    missing_base_failures = sorted(base.failing_node_ids - head.collected_node_ids)
    return {
        "schema_version": "1.0.0",
        "base": {
            "total": base.total,
            "passed": base.passed,
            "failed": base.failed,
            "errors": base.errors,
            "skipped": base.skipped,
            "failing_node_ids": sorted(base.failing_node_ids),
        },
        "head": {
            "total": head.total,
            "passed": head.passed,
            "failed": head.failed,
            "errors": head.errors,
            "skipped": head.skipped,
            "failing_node_ids": sorted(head.failing_node_ids),
        },
        "newly_failing": newly_failing,
        "newly_passing": newly_passing,
        "unchanged_failing": unchanged_failing,
        "missing_base_failures": missing_base_failures,
        "parity_passed": not newly_failing and not missing_base_failures,
    }


def _run_pytest(repository: Path, report: Path, basetemp: Path) -> PytestOutcome:
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(repository / "src")
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment.pop("GICLAB_RUN_PRIVATE_T09_TESTS", None)
    command = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "--tb=short",
        f"--junitxml={report}",
        f"--basetemp={basetemp}",
    ]
    for node_id in PRIVATE_LOCAL_NODE_IDS:
        command.extend(("--deselect", node_id))
    completed = subprocess.run(
        command,
        cwd=repository,
        env=environment,
        stdin=subprocess.DEVNULL,
        check=False,
    )
    if completed.returncode not in {0, 1} or not report.is_file():
        raise PytestParityError(
            f"pytest did not produce a comparable report (exit {completed.returncode})"
        )
    return load_pytest_outcome(report)


def run_parity(
    repository: Path,
    base_sha: str,
    *,
    expected_head_sha: str | None = None,
) -> dict[str, object]:
    """Run base and head pytest in one interpreter/dependency environment."""

    root = repository.resolve(strict=True)
    verified_base = subprocess.run(
        ["git", "-C", str(root), "rev-parse", f"{base_sha}^{{commit}}"],
        capture_output=True,
        check=True,
        text=True,
    ).stdout.strip()
    verified_head = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD^{commit}"],
        capture_output=True,
        check=True,
        text=True,
    ).stdout.strip()
    if expected_head_sha is not None:
        resolved_expected_head = subprocess.run(
            ["git", "-C", str(root), "rev-parse", f"{expected_head_sha}^{{commit}}"],
            capture_output=True,
            check=True,
            text=True,
        ).stdout.strip()
        if verified_head != resolved_expected_head:
            raise PytestParityError("checked-out HEAD differs from the exact pull-request head")
    with tempfile.TemporaryDirectory(prefix="giclab-pytest-parity-") as temporary:
        temporary_root = Path(temporary)
        base_root = temporary_root / "base"
        subprocess.run(
            ["git", "-C", str(root), "worktree", "add", "--detach", str(base_root), verified_base],
            stdin=subprocess.DEVNULL,
            check=True,
        )
        try:
            base = _run_pytest(
                base_root,
                temporary_root / "base.xml",
                temporary_root / "base-pytest",
            )
            head = _run_pytest(
                root,
                temporary_root / "head.xml",
                temporary_root / "head-pytest",
            )
        finally:
            subprocess.run(
                ["git", "-C", str(root), "worktree", "remove", "--force", str(base_root)],
                stdin=subprocess.DEVNULL,
                check=False,
            )
    comparison = compare_outcomes(base, head)
    comparison["base_sha"] = verified_base
    comparison["head_sha"] = verified_head
    return comparison


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--base-sha", required=True)
    parser.add_argument("--head-sha")
    return parser


def main() -> int:
    args = _parser().parse_args()
    comparison = run_parity(
        args.repository,
        args.base_sha,
        expected_head_sha=args.head_sha,
    )
    print(json.dumps(comparison, indent=2, sort_keys=True))
    return 0 if comparison["parity_passed"] is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
