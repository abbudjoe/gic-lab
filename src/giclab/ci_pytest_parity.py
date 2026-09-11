"""Compare pull-request pytest outcomes with an exact detached base checkout.

This is deliberately narrower than ``make check``. Formatting, linting, typing,
repository validation, and site generation remain strict gates. Only exact inherited
pytest failures may use baseline parity; missing or weakened base coverage and every
head-only failure fail CI.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from collections.abc import Iterator, Mapping
from contextlib import contextmanager, nullcontext
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Final, Literal


class PytestParityError(RuntimeError):
    """The base/head pytest comparison was incomplete or introduced a regression."""


PRIVATE_LOCAL_NODE_IDS: Final = (
    "tests/test_t09_retry4.py::test_retry4_private_postrun_union_reconstructs_the_frozen_runtime",
    "tests/test_t09_retry4.py::test_retry4_private_clock_reconciliation_uses_the_frozen_empirical_origin",
    "tests/test_t09_retry4.py::test_retry4_private_postrun_overlay_is_exact_and_reconstructable",
    "tests/test_t09_retry4.py::test_retry4_exact_slot1_preentry_stage_is_source_reconstructable",
    "tests/test_t09_retry5.py::test_autonomous_slot2_authority_uses_distinct_nested_and_tree_hashes",
)

PytestNodeStatus = Literal[
    "passed",
    "failed",
    "error",
    "skipped",
    "xfailed",
    "xpassed",
]
PYTEST_NODE_STATUSES: Final[frozenset[str]] = frozenset(
    {"passed", "failed", "error", "skipped", "xfailed", "xpassed"}
)
FAILING_STATUSES: Final[frozenset[PytestNodeStatus]] = frozenset({"failed", "error", "xpassed"})
NEWLY_PASSING_BASE_STATUSES: Final[frozenset[PytestNodeStatus]] = frozenset({"failed", "error"})
WEAK_COVERAGE_STATUSES: Final[frozenset[PytestNodeStatus]] = frozenset({"skipped", "xfailed"})
STRICT_XPASS_JUNIT_PREFIX: Final = "[XPASS(strict)]"
TEARDOWN_ERROR_JUNIT_PREFIX: Final = 'failed on teardown with "'


@dataclass(frozen=True, slots=True, order=True)
class PytestNodeOutcome:
    """One exact collected pytest node and its terminal outcome."""

    node_id: str
    status: PytestNodeStatus

    def __post_init__(self) -> None:
        if not self.node_id or self.status not in PYTEST_NODE_STATUSES:
            raise PytestParityError("pytest outcome contains an invalid node identity or status")


@dataclass(frozen=True, slots=True)
class PytestOutcome:
    """A complete, deterministic set of per-node pytest outcomes."""

    node_outcomes: tuple[PytestNodeOutcome, ...]

    def __post_init__(self) -> None:
        ordered = tuple(sorted(self.node_outcomes, key=lambda item: item.node_id))
        if self.node_outcomes != ordered:
            raise PytestParityError(
                "pytest outcome node identities are not deterministically ordered"
            )
        node_ids = tuple(item.node_id for item in self.node_outcomes)
        if len(node_ids) != len(set(node_ids)):
            raise PytestParityError("pytest outcome contains duplicate node identities")

    @classmethod
    def from_statuses(cls, statuses: Mapping[str, PytestNodeStatus]) -> PytestOutcome:
        """Build a validated outcome from an exact node-to-status mapping."""

        return cls(
            tuple(
                PytestNodeOutcome(node_id=node_id, status=status)
                for node_id, status in sorted(statuses.items())
            )
        )

    @property
    def status_by_node_id(self) -> dict[str, PytestNodeStatus]:
        return {item.node_id: item.status for item in self.node_outcomes}

    @property
    def total(self) -> int:
        return len(self.node_outcomes)

    @property
    def collected_node_ids(self) -> frozenset[str]:
        return frozenset(item.node_id for item in self.node_outcomes)

    @property
    def failing_node_ids(self) -> frozenset[str]:
        return frozenset(
            item.node_id for item in self.node_outcomes if item.status in FAILING_STATUSES
        )

    def count(self, status: PytestNodeStatus) -> int:
        return sum(item.status == status for item in self.node_outcomes)

    @property
    def passed(self) -> int:
        return self.count("passed")

    @property
    def failed(self) -> int:
        return self.count("failed")

    @property
    def errors(self) -> int:
        return self.count("error")

    @property
    def skipped(self) -> int:
        return self.count("skipped")

    @property
    def xfailed(self) -> int:
        return self.count("xfailed")

    @property
    def xpassed(self) -> int:
        return self.count("xpassed")


def _suite_count(suite: ET.Element, attribute: str) -> int:
    raw = suite.attrib.get(attribute)
    try:
        value = int(raw) if raw is not None else -1
    except ValueError as error:
        raise PytestParityError("pytest JUnit report contains an invalid suite count") from error
    if value < 0:
        raise PytestParityError("pytest JUnit report lacks a complete nonnegative suite count")
    return value


def _node_id(testcase: ET.Element) -> str:
    file_attribute = testcase.attrib.get("file")
    classname = testcase.attrib.get("classname")
    name = testcase.attrib.get("name")
    if not file_attribute or not classname or not name:
        raise PytestParityError("pytest JUnit testcase lacks its exact identity")

    normalized_file = file_attribute.replace("\\", "/")
    path = PurePosixPath(normalized_file)
    if path.is_absolute() or ".." in path.parts or path.suffix != ".py":
        raise PytestParityError("pytest JUnit testcase has an unsafe or unsupported file identity")
    module = normalized_file.removesuffix(".py").replace("/", ".")
    if classname == module:
        containers: tuple[str, ...] = ()
    elif classname.startswith(f"{module}."):
        containers = tuple(classname.removeprefix(f"{module}.").split("."))
        if not all(containers):
            raise PytestParityError("pytest JUnit testcase has an incomplete class identity")
    else:
        raise PytestParityError("pytest JUnit testcase class does not match its exact file")
    return "::".join((normalized_file, *containers, name))


def _testcase_status(testcase: ET.Element) -> PytestNodeStatus:
    failure = testcase.find("failure")
    error = testcase.find("error")
    skipped = testcase.find("skipped")
    terminal_children = sum(child is not None for child in (failure, error, skipped))
    if terminal_children > 1:
        raise PytestParityError("pytest JUnit testcase contains contradictory terminal outcomes")
    if failure is not None:
        if failure.attrib.get("message", "").startswith(STRICT_XPASS_JUNIT_PREFIX):
            return "xpassed"
        return "failed"
    if error is not None:
        return "error"
    if skipped is None:
        return "passed"

    skipped_type = skipped.attrib.get("type")
    if skipped_type == "pytest.xfail":
        return "xfailed"
    if skipped_type in {None, "", "pytest.skip"}:
        return "skipped"
    raise PytestParityError("pytest JUnit testcase contains an unknown skipped outcome")


def _has_passing_call_followed_by_teardown_error(testcase: ET.Element) -> bool:
    """Identify pytest's one-node/two-phase count for pass then teardown error."""

    error = testcase.find("error")
    return error is not None and error.attrib.get("message", "").startswith(
        TEARDOWN_ERROR_JUNIT_PREFIX
    )


def load_pytest_outcome(path: Path) -> PytestOutcome:
    """Load a complete exact per-node outcome model from pinned pytest JUnit XML."""

    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    if not suites:
        raise PytestParityError("pytest JUnit report contains no test suite")

    expected_total = sum(_suite_count(suite, "tests") for suite in suites)
    expected_failed = sum(_suite_count(suite, "failures") for suite in suites)
    expected_errors = sum(_suite_count(suite, "errors") for suite in suites)
    expected_junit_skipped = sum(_suite_count(suite, "skipped") for suite in suites)
    testcases = tuple(testcase for suite in suites for testcase in suite.findall("testcase"))
    outcome = PytestOutcome(
        tuple(
            sorted(
                (
                    PytestNodeOutcome(
                        node_id=_node_id(testcase),
                        status=_testcase_status(testcase),
                    )
                    for testcase in testcases
                ),
                key=lambda item: item.node_id,
            )
        )
    )
    observed_junit_failures = outcome.failed + outcome.xpassed
    observed_junit_skipped = outcome.skipped + outcome.xfailed
    passing_call_teardown_errors = sum(
        _has_passing_call_followed_by_teardown_error(testcase) for testcase in testcases
    )
    observed_junit_passes = outcome.passed + passing_call_teardown_errors
    if (
        outcome.total + passing_call_teardown_errors != expected_total
        or observed_junit_failures != expected_failed
        or outcome.errors != expected_errors
        or observed_junit_skipped != expected_junit_skipped
        or observed_junit_passes
        != expected_total - expected_failed - expected_errors - expected_junit_skipped
    ):
        raise PytestParityError("pytest JUnit outcome identities or counts are inconsistent")
    return outcome


def _serialized_outcome(outcome: PytestOutcome) -> dict[str, object]:
    return {
        "total": outcome.total,
        "passed": outcome.passed,
        "failed": outcome.failed,
        "errors": outcome.errors,
        "skipped": outcome.skipped,
        "xfailed": outcome.xfailed,
        "xpassed": outcome.xpassed,
        "collected_node_ids": sorted(outcome.collected_node_ids),
        "failing_node_ids": sorted(outcome.failing_node_ids),
        "node_outcomes": [
            {"node_id": item.node_id, "status": item.status} for item in outcome.node_outcomes
        ],
    }


def compare_outcomes(
    base: PytestOutcome,
    head: PytestOutcome,
    *,
    symmetrically_deselected_node_ids: tuple[str, ...] = (),
) -> dict[str, object]:
    """Return a deterministic fail-closed comparison of exact per-node outcomes."""

    if len(symmetrically_deselected_node_ids) != len(set(symmetrically_deselected_node_ids)):
        raise PytestParityError("symmetric pytest deselection identities are duplicated")

    base_statuses = base.status_by_node_id
    head_statuses = head.status_by_node_id
    base_node_ids = set(base_statuses)
    head_node_ids = set(head_statuses)
    common_node_ids = sorted(base_node_ids & head_node_ids)

    newly_failing = sorted(
        node_id
        for node_id, head_status in head_statuses.items()
        if head_status in FAILING_STATUSES and base_statuses.get(node_id) not in FAILING_STATUSES
    )
    newly_passing = sorted(
        node_id
        for node_id, base_status in base_statuses.items()
        if base_status in NEWLY_PASSING_BASE_STATUSES and head_statuses.get(node_id) == "passed"
    )
    unchanged_failing = sorted(
        node_id
        for node_id in common_node_ids
        if base_statuses[node_id] in FAILING_STATUSES and head_statuses[node_id] in FAILING_STATUSES
    )
    improved_coverage = sorted(
        node_id
        for node_id in common_node_ids
        if base_statuses[node_id] in WEAK_COVERAGE_STATUSES and head_statuses[node_id] == "passed"
    )
    resolved_xpassed = sorted(
        node_id
        for node_id in common_node_ids
        if base_statuses[node_id] == "xpassed" and head_statuses[node_id] == "passed"
    )
    missing_base_collected_node_ids = sorted(base_node_ids - head_node_ids)
    missing_base_failures = sorted(
        node_id
        for node_id in missing_base_collected_node_ids
        if base_statuses[node_id] in FAILING_STATUSES
    )
    invalid_outcome_transitions = [
        {
            "node_id": node_id,
            "base_status": base_statuses[node_id],
            "head_status": head_statuses[node_id],
            "reason": "base coverage weakened to a nonexecuted outcome",
        }
        for node_id in common_node_ids
        if base_statuses[node_id] not in WEAK_COVERAGE_STATUSES
        and head_statuses[node_id] in WEAK_COVERAGE_STATUSES
    ]
    complete_outcome_records = True
    parity_passed = (
        not newly_failing
        and not invalid_outcome_transitions
        and not missing_base_collected_node_ids
        and complete_outcome_records
    )
    return {
        "schema_version": "2.0.0",
        "base": _serialized_outcome(base),
        "head": _serialized_outcome(head),
        "newly_failing": newly_failing,
        "newly_passing": newly_passing,
        "unchanged_failing": unchanged_failing,
        "improved_coverage": improved_coverage,
        "resolved_xpassed": resolved_xpassed,
        "invalid_outcome_transitions": invalid_outcome_transitions,
        "missing_base_collected_node_ids": missing_base_collected_node_ids,
        "missing_base_failures": missing_base_failures,
        "head_only_node_ids": sorted(head_node_ids - base_node_ids),
        "symmetrically_deselected_node_ids": sorted(symmetrically_deselected_node_ids),
        "complete_outcome_records": complete_outcome_records,
        "parity_passed": parity_passed,
    }


def build_pytest_command(report: Path, basetemp: Path) -> tuple[str, ...]:
    """Build the one deterministic pytest command shared by base and head."""

    command = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "--tb=short",
        "-o",
        "junit_family=legacy",
        f"--junitxml={report}",
        f"--basetemp={basetemp}",
    ]
    if os.environ.get("GICLAB_CI_GUARD_JOURNAL"):
        command.extend(("-p", "offline_guard"))
    for node_id in PRIVATE_LOCAL_NODE_IDS:
        command.extend(("--deselect", node_id))
    return tuple(command)


def build_pytest_environment(repository: Path) -> dict[str, str]:
    """Return an environment that cannot broaden pytest selection implicitly."""

    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(repository / "src")
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    for variable in ("GICLAB_RUN_PRIVATE_T09_TESTS", "PYTEST_ADDOPTS", "PYTEST_PLUGINS"):
        environment.pop(variable, None)
    return environment


def _run_pytest(repository: Path, report: Path, basetemp: Path) -> PytestOutcome:
    command = build_pytest_command(report, basetemp)
    completed = subprocess.run(
        command,
        cwd=repository,
        env=build_pytest_environment(repository),
        stdin=subprocess.DEVNULL,
        check=False,
    )
    report.with_suffix(".execution.json").write_text(
        json.dumps({"command": command, "exit_code": completed.returncode}, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if completed.returncode not in {0, 1} or not report.is_file():
        raise PytestParityError(
            f"pytest did not produce a comparable report (exit {completed.returncode})"
        )
    outcome = load_pytest_outcome(report)
    if (completed.returncode == 0) != (not outcome.failing_node_ids):
        raise PytestParityError("pytest exit status contradicts its per-node outcome report")
    return outcome


def _resolve_commit(repository: Path, revision: str, identity: str) -> str:
    """Resolve one required commit identity or fail with parity-specific context."""

    try:
        completed = subprocess.run(
            ["git", "-C", str(repository), "rev-parse", "--verify", f"{revision}^{{commit}}"],
            capture_output=True,
            check=True,
            text=True,
        )
    except subprocess.CalledProcessError as error:
        raise PytestParityError(f"unable to resolve exact {identity} commit") from error
    resolved = completed.stdout.strip()
    if len(resolved) != 40 or any(character not in "0123456789abcdef" for character in resolved):
        raise PytestParityError(f"exact {identity} commit did not resolve to a full SHA")
    return resolved


def _require_clean_repository(repository: Path) -> None:
    """Reject tracked or untracked bytes outside the exact tested head commit."""

    try:
        completed = subprocess.run(
            [
                "git",
                "-C",
                str(repository),
                "status",
                "--porcelain=v1",
                "--untracked-files=all",
            ],
            capture_output=True,
            check=True,
            text=True,
        )
    except subprocess.CalledProcessError as error:
        raise PytestParityError("unable to verify exact-head repository cleanliness") from error
    if completed.stdout:
        raise PytestParityError(
            "exact-head pytest parity requires a clean repository, including untracked files"
        )


def _registered_worktree_paths(repository: Path) -> frozenset[Path]:
    """Return canonical paths for every worktree registered by this repository."""

    try:
        completed = subprocess.run(
            ["git", "-C", str(repository), "worktree", "list", "--porcelain", "-z"],
            capture_output=True,
            check=True,
            text=True,
        )
    except subprocess.CalledProcessError as error:
        raise PytestParityError("unable to verify detached parity worktree cleanup") from error
    return frozenset(
        Path(field.removeprefix("worktree ")).resolve(strict=False)
        for field in completed.stdout.split("\0")
        if field.startswith("worktree ")
    )


def _remove_detached_worktree(repository: Path, worktree: Path) -> None:
    """Remove one exact parity worktree and prove its registration is gone."""

    completed = subprocess.run(
        ["git", "-C", str(repository), "worktree", "remove", "--force", str(worktree)],
        capture_output=True,
        check=False,
        stdin=subprocess.DEVNULL,
        text=True,
    )
    still_registered = worktree.resolve(strict=False) in _registered_worktree_paths(repository)
    if completed.returncode != 0 or still_registered:
        detail = completed.stderr.strip() or "worktree remains registered"
        raise PytestParityError(f"detached parity worktree cleanup failed: {detail}")


@contextmanager
def _checked_detached_worktree(
    repository: Path,
    worktree: Path,
    commit_sha: str,
) -> Iterator[None]:
    """Create and durably remove one exact detached parity worktree."""

    try:
        subprocess.run(
            [
                "git",
                "-C",
                str(repository),
                "worktree",
                "add",
                "--detach",
                str(worktree),
                commit_sha,
            ],
            capture_output=True,
            check=True,
            stdin=subprocess.DEVNULL,
            text=True,
        )
    except BaseException as error:
        if isinstance(error, subprocess.CalledProcessError):
            materialization_error: BaseException = PytestParityError(
                "unable to materialize the exact detached base commit"
            )
        else:
            materialization_error = error
        try:
            if worktree.resolve(strict=False) in _registered_worktree_paths(repository):
                _remove_detached_worktree(repository, worktree)
        except PytestParityError as cleanup_error:
            materialization_error.add_note(
                f"partial detached-worktree cleanup also failed: {cleanup_error}"
            )
        if materialization_error is error:
            raise
        raise materialization_error from error

    primary_error: BaseException | None = None
    try:
        yield
    except BaseException as error:
        primary_error = error
        raise
    finally:
        try:
            _remove_detached_worktree(repository, worktree)
        except PytestParityError as cleanup_error:
            if primary_error is None:
                raise
            primary_error.add_note(f"detached parity cleanup also failed: {cleanup_error}")


def run_parity(
    repository: Path,
    base_sha: str,
    *,
    expected_head_sha: str | None = None,
    evidence_root: Path | None = None,
) -> dict[str, object]:
    """Run base and head pytest in one interpreter/dependency environment."""

    root = repository.resolve(strict=True)
    verified_base = _resolve_commit(root, base_sha, "base")
    verified_head = _resolve_commit(root, "HEAD", "checked-out HEAD")
    if expected_head_sha is not None:
        resolved_expected_head = _resolve_commit(root, expected_head_sha, "expected head")
        if verified_head != resolved_expected_head:
            raise PytestParityError("checked-out HEAD differs from the exact pull-request head")
    _require_clean_repository(root)
    if evidence_root is not None:
        evidence_root = evidence_root.absolute()
        if ".." in evidence_root.parts:
            raise PytestParityError("parity evidence path contains parent traversal")
        if any(path.is_symlink() for path in (evidence_root, *evidence_root.parents)):
            raise PytestParityError("parity evidence path contains a symlink")
        if evidence_root.is_relative_to(root) or root.is_relative_to(evidence_root):
            raise PytestParityError("parity evidence must be separate from the source")
        evidence_root.parent.resolve(strict=True)
        evidence_root.mkdir(mode=0o700)
    lifetime = (
        nullcontext(str(evidence_root))
        if evidence_root is not None
        else tempfile.TemporaryDirectory(prefix="giclab-pytest-parity-")
    )
    with lifetime as temporary:
        temporary_root = Path(temporary)
        base_root = temporary_root / "base"
        with _checked_detached_worktree(root, base_root, verified_base):
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
    comparison = compare_outcomes(
        base,
        head,
        symmetrically_deselected_node_ids=PRIVATE_LOCAL_NODE_IDS,
    )
    comparison["base_sha"] = verified_base
    comparison["head_sha"] = verified_head
    if evidence_root is not None:
        (evidence_root / "parity.json").write_text(
            json.dumps(comparison, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    return comparison


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--base-sha", required=True)
    parser.add_argument("--head-sha")
    parser.add_argument("--evidence-root", type=Path)
    return parser


def main() -> int:
    args = _parser().parse_args()
    comparison = run_parity(
        args.repository,
        args.base_sha,
        expected_head_sha=args.head_sha,
        evidence_root=args.evidence_root,
    )
    print(json.dumps(comparison, indent=2, sort_keys=True))
    return 0 if comparison["parity_passed"] is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
