from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from giclab import ci_pytest_parity
from giclab.ci_pytest_parity import (
    PRIVATE_LOCAL_NODE_IDS,
    PytestNodeOutcome,
    PytestNodeStatus,
    PytestOutcome,
    PytestParityError,
    build_pytest_command,
    build_pytest_environment,
    compare_outcomes,
    load_pytest_outcome,
    run_parity,
)

OLD = "tests/test_old.py::test_one"
STABLE = "tests/test_old.py::test_two"
NEW = "tests/test_new.py::test_regression"


def _outcome(
    *,
    passed: tuple[str, ...] = (),
    failed: tuple[str, ...] = (),
    errors: tuple[str, ...] = (),
    skipped: tuple[str, ...] = (),
    xfailed: tuple[str, ...] = (),
    xpassed: tuple[str, ...] = (),
) -> PytestOutcome:
    statuses: dict[str, PytestNodeStatus] = {}
    for status, node_ids in (
        ("passed", passed),
        ("failed", failed),
        ("error", errors),
        ("skipped", skipped),
        ("xfailed", xfailed),
        ("xpassed", xpassed),
    ):
        for node_id in node_ids:
            assert node_id not in statuses
            statuses[node_id] = status
    return PytestOutcome.from_statuses(statuses)


def _invalid_transition(comparison: dict[str, object]) -> dict[str, str]:
    transitions = comparison["invalid_outcome_transitions"]
    assert isinstance(transitions, list)
    assert len(transitions) == 1
    transition = transitions[0]
    assert isinstance(transition, dict)
    return transition


def test_base_failure_to_actual_head_pass_is_the_only_newly_passing_form() -> None:
    comparison = compare_outcomes(
        _outcome(failed=(OLD, STABLE)),
        _outcome(passed=(OLD,), failed=(STABLE,)),
    )
    assert comparison["schema_version"] == "2.0.0"
    assert comparison["parity_passed"] is True
    assert comparison["newly_failing"] == []
    assert comparison["newly_passing"] == [OLD]
    assert comparison["unchanged_failing"] == [STABLE]
    assert comparison["missing_base_collected_node_ids"] == []
    assert comparison["invalid_outcome_transitions"] == []


def test_base_failure_to_head_failure_remains_unchanged_failing() -> None:
    comparison = compare_outcomes(_outcome(failed=(OLD,)), _outcome(errors=(OLD,)))
    assert comparison["parity_passed"] is True
    assert comparison["newly_passing"] == []
    assert comparison["unchanged_failing"] == [OLD]


@pytest.mark.parametrize("head_status", ["skipped", "xfailed"])
def test_base_failure_to_nonexecuted_head_outcome_is_rejected(
    head_status: PytestNodeStatus,
) -> None:
    head = _outcome(**{head_status: (OLD,)})
    comparison = compare_outcomes(_outcome(failed=(OLD,)), head)
    assert comparison["parity_passed"] is False
    assert comparison["newly_passing"] == []
    assert _invalid_transition(comparison) == {
        "node_id": OLD,
        "base_status": "failed",
        "head_status": head_status,
        "reason": "base coverage weakened to a nonexecuted outcome",
    }


def test_base_failure_to_missing_node_is_rejected_and_not_newly_passing() -> None:
    comparison = compare_outcomes(_outcome(failed=(OLD,)), _outcome())
    assert comparison["parity_passed"] is False
    assert comparison["newly_passing"] == []
    assert comparison["missing_base_collected_node_ids"] == [OLD]
    assert comparison["missing_base_failures"] == [OLD]


def test_base_passing_node_missing_at_head_is_rejected() -> None:
    comparison = compare_outcomes(
        _outcome(passed=(OLD, STABLE)),
        _outcome(passed=(STABLE,)),
    )
    assert comparison["parity_passed"] is False
    assert comparison["missing_base_collected_node_ids"] == [OLD]
    assert comparison["missing_base_failures"] == []


@pytest.mark.parametrize("head_status", ["skipped", "xfailed"])
def test_base_pass_to_nonexecuted_head_outcome_is_rejected(
    head_status: PytestNodeStatus,
) -> None:
    comparison = compare_outcomes(
        _outcome(passed=(OLD,)),
        _outcome(**{head_status: (OLD,)}),
    )
    assert comparison["parity_passed"] is False
    assert _invalid_transition(comparison)["head_status"] == head_status


def test_head_only_failure_is_rejected() -> None:
    comparison = compare_outcomes(
        _outcome(passed=(STABLE,)),
        _outcome(passed=(STABLE,), failed=(NEW,)),
    )
    assert comparison["parity_passed"] is False
    assert comparison["newly_failing"] == [NEW]
    assert comparison["head_only_node_ids"] == [NEW]


def test_head_only_pass_is_allowed() -> None:
    comparison = compare_outcomes(
        _outcome(passed=(STABLE,)),
        _outcome(passed=(STABLE, NEW)),
    )
    assert comparison["parity_passed"] is True
    assert comparison["newly_failing"] == []
    assert comparison["head_only_node_ids"] == [NEW]


def test_head_only_skip_and_xfail_are_allowed_but_not_newly_passing() -> None:
    comparison = compare_outcomes(
        _outcome(passed=(STABLE,)),
        _outcome(passed=(STABLE,), skipped=("tests/test_new.py::test_skip",), xfailed=(NEW,)),
    )
    assert comparison["parity_passed"] is True
    assert comparison["newly_passing"] == []


def test_base_skip_and_xfail_to_pass_are_improved_coverage_not_newly_passing() -> None:
    skipped_node = "tests/test_old.py::test_skipped"
    comparison = compare_outcomes(
        _outcome(skipped=(skipped_node,), xfailed=(OLD,)),
        _outcome(passed=(skipped_node, OLD)),
    )
    assert comparison["parity_passed"] is True
    assert comparison["improved_coverage"] == [OLD, skipped_node]
    assert comparison["newly_passing"] == []


def test_failure_and_error_are_both_newly_failing_outcomes() -> None:
    error_node = "tests/test_new.py::test_error"
    comparison = compare_outcomes(
        _outcome(passed=(OLD, STABLE)),
        _outcome(failed=(OLD,), errors=(STABLE, error_node)),
    )
    assert comparison["parity_passed"] is False
    assert comparison["newly_failing"] == [error_node, OLD, STABLE]


def test_exposed_strict_xpass_is_explicit_and_fails_closed() -> None:
    comparison = compare_outcomes(_outcome(passed=(OLD,)), _outcome(xpassed=(OLD,)))
    assert comparison["parity_passed"] is False
    assert comparison["newly_failing"] == [OLD]


def test_duplicate_node_identities_are_rejected() -> None:
    duplicate = PytestNodeOutcome(node_id=OLD, status="passed")
    with pytest.raises(PytestParityError, match="duplicate node identities"):
        PytestOutcome((duplicate, duplicate))


def _case(node_id: str, terminal: str) -> str:
    file_path, name = node_id.split("::", maxsplit=1)
    classname = file_path.removesuffix(".py").replace("/", ".")
    return (
        f'<testcase classname="{classname}" name="{name}" file="{file_path}">{terminal}</testcase>'
    )


@pytest.mark.parametrize(
    ("suite_counts", "testcases"),
    [
        ('errors="0" failures="0" skipped="0" tests="2"', _case(OLD, "")),
        ('errors="0" failures="1" skipped="0" tests="1"', _case(OLD, "")),
        ('errors="0" failures="0" skipped="1" tests="1"', _case(OLD, "")),
    ],
)
def test_incomplete_or_count_inconsistent_junit_is_rejected(
    tmp_path: Path,
    suite_counts: str,
    testcases: str,
) -> None:
    report = tmp_path / "pytest.xml"
    report.write_text(
        f"<testsuite {suite_counts}>{testcases}</testsuite>",
        encoding="utf-8",
    )
    with pytest.raises(PytestParityError, match="inconsistent"):
        load_pytest_outcome(report)


def test_junit_loader_rejects_duplicate_identity_even_when_counts_match(tmp_path: Path) -> None:
    report = tmp_path / "pytest.xml"
    duplicate = _case(OLD, "")
    report.write_text(
        f'<testsuite errors="0" failures="0" skipped="0" tests="2">'
        f"{duplicate}{duplicate}</testsuite>",
        encoding="utf-8",
    )
    with pytest.raises(PytestParityError, match="duplicate node identities"):
        load_pytest_outcome(report)


def test_pinned_pytest_junit_preserves_exact_outcomes_and_parameterized_ids(
    tmp_path: Path,
) -> None:
    test_file = tmp_path / "test_outcomes.py"
    report = tmp_path / "pytest.xml"
    test_file.write_text(
        """import pytest

def test_pass():
    pass

def test_fail():
    assert False

@pytest.fixture
def broken_fixture():
    raise RuntimeError("setup failed")

def test_error(broken_fixture):
    pass

@pytest.fixture
def broken_teardown():
    yield
    raise RuntimeError("teardown failed")

def test_teardown_error(broken_teardown):
    pass

@pytest.mark.skip(reason="ordinary skip")
def test_skip():
    pass

@pytest.mark.xfail(reason="expected failure")
def test_xfail():
    assert False

@pytest.mark.xfail(reason="strict unexpected pass", strict=True)
def test_xpass():
    pass

@pytest.mark.parametrize("value", ["value-2"])
def test_parameterized(value):
    assert value

class TestGroup:
    def test_method(self):
        pass
""",
        encoding="utf-8",
    )
    environment = dict(os.environ)
    environment["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-o",
            "junit_family=legacy",
            f"--junitxml={report}",
            f"--basetemp={tmp_path / 'basetemp'}",
            str(test_file),
        ],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 1, completed.stdout + completed.stderr
    outcome = load_pytest_outcome(report)
    assert outcome.status_by_node_id == {
        "test_outcomes.py::TestGroup::test_method": "passed",
        "test_outcomes.py::test_error": "error",
        "test_outcomes.py::test_fail": "failed",
        "test_outcomes.py::test_parameterized[value-2]": "passed",
        "test_outcomes.py::test_pass": "passed",
        "test_outcomes.py::test_skip": "skipped",
        "test_outcomes.py::test_teardown_error": "error",
        "test_outcomes.py::test_xfail": "xfailed",
        "test_outcomes.py::test_xpass": "xpassed",
    }
    assert (outcome.passed, outcome.failed, outcome.errors) == (3, 1, 2)
    assert (outcome.skipped, outcome.xfailed, outcome.xpassed) == (1, 1, 1)


def _deselected_node_ids(command: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(command[index + 1] for index, value in enumerate(command) if value == "--deselect")


def test_base_and_head_commands_use_the_same_exact_symmetric_deselection_list(
    tmp_path: Path,
) -> None:
    expected = (
        "tests/test_t09_retry4.py::test_retry4_private_postrun_union_reconstructs_the_frozen_runtime",
        "tests/test_t09_retry4.py::test_retry4_private_clock_reconciliation_uses_the_frozen_empirical_origin",
        "tests/test_t09_retry4.py::test_retry4_private_postrun_overlay_is_exact_and_reconstructable",
        "tests/test_t09_retry4.py::test_retry4_exact_slot1_preentry_stage_is_source_reconstructable",
        "tests/test_t09_retry5.py::test_autonomous_slot2_authority_uses_distinct_nested_and_tree_hashes",
    )
    base_command = build_pytest_command(tmp_path / "base.xml", tmp_path / "base-temp")
    head_command = build_pytest_command(tmp_path / "head.xml", tmp_path / "head-temp")
    assert expected == PRIVATE_LOCAL_NODE_IDS
    assert _deselected_node_ids(base_command) == expected
    assert _deselected_node_ids(head_command) == expected
    assert all("*" not in node_id and node_id.count("::") >= 1 for node_id in expected)


def test_pytest_environment_removes_selection_broadening_and_private_opt_in(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GICLAB_RUN_PRIVATE_T09_TESTS", "1")
    monkeypatch.setenv("PYTEST_ADDOPTS", "--ignore=tests")
    monkeypatch.setenv("PYTEST_PLUGINS", "untrusted_collection_plugin")
    monkeypatch.setenv("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "0")
    environment = build_pytest_environment(tmp_path)
    assert "GICLAB_RUN_PRIVATE_T09_TESTS" not in environment
    assert "PYTEST_ADDOPTS" not in environment
    assert "PYTEST_PLUGINS" not in environment
    assert environment["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] == "1"
    assert environment["PYTHONPATH"] == str(tmp_path / "src")


def test_guarded_parity_explicitly_loads_the_child_denial_consumer(tmp_path, monkeypatch):
    monkeypatch.setenv("GICLAB_CI_GUARD_JOURNAL", str(tmp_path / "journal"))
    command = build_pytest_command(tmp_path / "report.xml", tmp_path / "pytest")
    assert command[command.index("-p") + 1] == "offline_guard"
    monkeypatch.delenv("GICLAB_CI_GUARD_JOURNAL")
    assert "-p" not in build_pytest_command(tmp_path / "report.xml", tmp_path / "pytest")


def test_simulated_deselection_of_previously_passing_base_node_fails_parity() -> None:
    comparison = compare_outcomes(
        _outcome(passed=(OLD, STABLE)),
        _outcome(passed=(STABLE,)),
        symmetrically_deselected_node_ids=PRIVATE_LOCAL_NODE_IDS,
    )
    assert comparison["parity_passed"] is False
    assert comparison["missing_base_collected_node_ids"] == [OLD]
    assert comparison["symmetrically_deselected_node_ids"] == sorted(PRIVATE_LOCAL_NODE_IDS)


def test_duplicate_symmetric_exclusions_are_rejected() -> None:
    with pytest.raises(PytestParityError, match="deselection identities are duplicated"):
        compare_outcomes(
            _outcome(),
            _outcome(),
            symmetrically_deselected_node_ids=(OLD, OLD),
        )


def _git(repository: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repository), *arguments],
        capture_output=True,
        check=True,
        text=True,
    )
    return completed.stdout.strip()


def _two_commit_repository(tmp_path: Path) -> tuple[Path, str, str]:
    repository = tmp_path / "repository"
    repository.mkdir()
    _git(repository, "init", "--quiet")
    _git(repository, "config", "user.name", "Parity Fixture")
    _git(repository, "config", "user.email", "parity@example.invalid")
    tracked = repository / "tracked.txt"
    tracked.write_text("base\n", encoding="utf-8")
    _git(repository, "add", "tracked.txt")
    _git(repository, "commit", "--quiet", "-m", "base")
    base_sha = _git(repository, "rev-parse", "HEAD")
    tracked.write_text("head\n", encoding="utf-8")
    _git(repository, "add", "--", "tracked.txt")
    _git(repository, "commit", "--quiet", "-m", "head")
    head_sha = _git(repository, "rev-parse", "HEAD")
    return repository, base_sha, head_sha


def test_run_parity_uses_exact_commits_and_removes_its_detached_worktree(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, base_sha, head_sha = _two_commit_repository(tmp_path)
    observed_commits: list[str] = []

    def record_repository_commit(
        tested_repository: Path,
        report: Path,
        basetemp: Path,
    ) -> PytestOutcome:
        del report, basetemp
        observed_commits.append(_git(tested_repository, "rev-parse", "HEAD"))
        return _outcome(passed=(OLD,))

    monkeypatch.setattr(ci_pytest_parity, "_run_pytest", record_repository_commit)
    comparison = run_parity(repository, base_sha, expected_head_sha=head_sha)
    assert observed_commits == [base_sha, head_sha]
    assert comparison["base_sha"] == base_sha
    assert comparison["head_sha"] == head_sha
    assert ci_pytest_parity._registered_worktree_paths(repository) == frozenset(
        {repository.resolve()}
    )


def test_run_parity_rejects_an_unresolvable_base_commit(tmp_path: Path) -> None:
    repository, _, head_sha = _two_commit_repository(tmp_path)
    with pytest.raises(PytestParityError, match="unable to resolve exact base commit"):
        run_parity(repository, "f" * 40, expected_head_sha=head_sha)


def test_run_parity_rejects_a_wrong_expected_head(tmp_path: Path) -> None:
    repository, base_sha, _ = _two_commit_repository(tmp_path)
    with pytest.raises(
        PytestParityError,
        match="checked-out HEAD differs from the exact pull-request head",
    ):
        run_parity(repository, base_sha, expected_head_sha=base_sha)


@pytest.mark.parametrize("untracked", [False, True])
def test_run_parity_rejects_tracked_or_untracked_bytes_outside_the_exact_head(
    tmp_path: Path,
    untracked: bool,
) -> None:
    repository, base_sha, head_sha = _two_commit_repository(tmp_path)
    path = repository / ("untracked.txt" if untracked else "tracked.txt")
    path.write_text("not committed\n", encoding="utf-8")
    with pytest.raises(PytestParityError, match="requires a clean repository"):
        run_parity(repository, base_sha, expected_head_sha=head_sha)
    assert ci_pytest_parity._registered_worktree_paths(repository) == frozenset(
        {repository.resolve()}
    )


def test_detached_worktree_removal_failure_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = tmp_path / "repository"
    worktree = tmp_path / "base"

    def failed_removal(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        del kwargs
        return subprocess.CompletedProcess(args, 1, stdout="", stderr="simulated removal failure")

    monkeypatch.setattr(ci_pytest_parity.subprocess, "run", failed_removal)
    monkeypatch.setattr(
        ci_pytest_parity,
        "_registered_worktree_paths",
        lambda unused_repository: frozenset({worktree.resolve()}),
    )
    with pytest.raises(PytestParityError, match="simulated removal failure"):
        ci_pytest_parity._remove_detached_worktree(repository, worktree)


def test_primary_parity_failure_is_preserved_when_cleanup_also_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        ci_pytest_parity.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args, 0, stdout="", stderr=""),
    )

    def fail_cleanup(repository: Path, worktree: Path) -> None:
        del repository, worktree
        raise PytestParityError("simulated cleanup failure")

    monkeypatch.setattr(ci_pytest_parity, "_remove_detached_worktree", fail_cleanup)
    with (
        pytest.raises(RuntimeError, match="primary failure") as caught,
        ci_pytest_parity._checked_detached_worktree(
            tmp_path,
            tmp_path / "base",
            "a" * 40,
        ),
    ):
        raise RuntimeError("primary failure")
    assert caught.value.__notes__ == [
        "detached parity cleanup also failed: simulated cleanup failure"
    ]


def test_partial_worktree_registration_is_removed_when_materialization_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    worktree = tmp_path / "base"
    removal_calls: list[tuple[Path, Path]] = []

    def fail_materialization(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise subprocess.CalledProcessError(128, ["git", "worktree", "add"])

    monkeypatch.setattr(ci_pytest_parity.subprocess, "run", fail_materialization)
    monkeypatch.setattr(
        ci_pytest_parity,
        "_registered_worktree_paths",
        lambda unused_repository: frozenset({worktree.resolve()}),
    )
    monkeypatch.setattr(
        ci_pytest_parity,
        "_remove_detached_worktree",
        lambda repository, path: removal_calls.append((repository, path)),
    )
    with (
        pytest.raises(PytestParityError, match="unable to materialize"),
        ci_pytest_parity._checked_detached_worktree(
            tmp_path,
            worktree,
            "a" * 40,
        ),
    ):
        pytest.fail("failed materialization must not enter the worktree body")
    assert removal_calls == [(tmp_path, worktree)]


def test_materialization_error_retains_partial_cleanup_failure_note(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    worktree = tmp_path / "base"

    def fail_materialization(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise subprocess.CalledProcessError(128, ["git", "worktree", "add"])

    def fail_cleanup(repository: Path, path: Path) -> None:
        del repository, path
        raise PytestParityError("simulated partial cleanup failure")

    monkeypatch.setattr(ci_pytest_parity.subprocess, "run", fail_materialization)
    monkeypatch.setattr(
        ci_pytest_parity,
        "_registered_worktree_paths",
        lambda unused_repository: frozenset({worktree.resolve()}),
    )
    monkeypatch.setattr(ci_pytest_parity, "_remove_detached_worktree", fail_cleanup)
    with (
        pytest.raises(PytestParityError, match="unable to materialize") as caught,
        ci_pytest_parity._checked_detached_worktree(
            tmp_path,
            worktree,
            "a" * 40,
        ),
    ):
        pytest.fail("failed materialization must not enter the worktree body")
    assert caught.value.__notes__ == [
        "partial detached-worktree cleanup also failed: simulated partial cleanup failure"
    ]


def test_parity_retains_original_reports_and_scratch_on_failure(tmp_path, monkeypatch):
    repository, base_sha, head_sha = _two_commit_repository(tmp_path)
    evidence = tmp_path / "evidence"
    reports = []

    def produce_then_fail(tested_repository, report, basetemp):
        del tested_repository
        basetemp.mkdir()
        (basetemp / "original-receipt.json").write_bytes(b'{"original":true}\n')
        report.write_bytes(b"original-junit-bytes")
        reports.append(report)
        if report.name == "head.xml":
            raise PytestParityError("injected incomplete head")
        return _outcome(passed=(OLD,))

    monkeypatch.setattr(ci_pytest_parity, "_run_pytest", produce_then_fail)
    with pytest.raises(PytestParityError, match="injected incomplete head"):
        run_parity(repository, base_sha, expected_head_sha=head_sha, evidence_root=evidence)
    assert [p.name for p in reports] == ["base.xml", "head.xml"]
    assert all(p.read_bytes() == b"original-junit-bytes" for p in reports)
    for role in ("base", "head"):
        assert (
            evidence / f"{role}-pytest/original-receipt.json"
        ).read_bytes() == b'{"original":true}\n'
    assert not (evidence / "parity.json").exists()
    assert ci_pytest_parity._registered_worktree_paths(repository) == frozenset(
        {repository.resolve()}
    )


def test_parity_retains_complete_comparison_and_rejects_evidence_reuse(tmp_path, monkeypatch):
    import json

    repository, base_sha, head_sha = _two_commit_repository(tmp_path)
    evidence = tmp_path / "evidence"

    def produce(tested_repository, report, basetemp):
        del tested_repository, basetemp
        report.write_bytes(b"unchanged-original")
        return _outcome(passed=(OLD,))

    monkeypatch.setattr(ci_pytest_parity, "_run_pytest", produce)
    comparison = run_parity(
        repository, base_sha, expected_head_sha=head_sha, evidence_root=evidence
    )
    assert json.loads((evidence / "parity.json").read_bytes()) == comparison
    assert comparison["parity_passed"] is True
    with pytest.raises(FileExistsError):
        run_parity(repository, base_sha, expected_head_sha=head_sha, evidence_root=evidence)
    assert (evidence / "head.xml").read_bytes() == b"unchanged-original"


@pytest.mark.parametrize("unsafe", ["source", "symlink", "parent-traversal"])
def test_parity_evidence_cannot_alias_source_or_follow_links(tmp_path, unsafe):
    repository, base_sha, head_sha = _two_commit_repository(tmp_path)
    evidence = repository / "evidence"
    if unsafe == "symlink":
        link = tmp_path / "link"
        link.symlink_to(repository, target_is_directory=True)
        evidence = link / "evidence"
    elif unsafe == "parent-traversal":
        sibling = tmp_path / "sibling"
        sibling.mkdir()
        evidence = sibling / ".." / repository.name / "evidence"
    with pytest.raises(PytestParityError, match="evidence"):
        run_parity(repository, base_sha, expected_head_sha=head_sha, evidence_root=evidence)
    assert not (repository / "evidence").exists()
