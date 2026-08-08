from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from dataclasses import replace
from pathlib import Path, PurePosixPath
from typing import Any

import pytest
from harness_test_support import bind_plan, project_state, valid_plan_data

import giclab.harness.adapters.sira as sira_module
from giclab.harness.adapters.base import AdapterNoticeSeverity
from giclab.harness.adapters.sira import (
    SIRA_DATASET_REVISIONS,
    SIRA_FIELD_RULES,
    SIRA_REGULATION_EVENT_SOURCE,
    SIRA_REGULATION_FIELD_RULES,
    SIRA_REGULATION_POLICY_ID,
    SIRA_SECRET_NAME,
    SIRA_SOURCE_ID,
    SIRA_UPSTREAM_COMMIT,
    SiRAAdapter,
    SiRACommandConfig,
    SiRAContractError,
    SiRADataset,
    SiRAMode,
    SiRAPairMismatch,
    SiRATask,
    SiRATraceError,
    assert_sira_matched_pair,
    sira_config_sha256,
    sira_regulation_policy_metadata,
)
from giclab.harness.artifacts import ArtifactWorkspace
from giclab.harness.executor import LocalRunExecutor
from giclab.harness.models import (
    AdapterEventType,
    CommandSpec,
    EventProvenance,
    EventType,
    NonWallResource,
    ResourceProjection,
    RunPlan,
    RunProfile,
    command_document,
    command_from_document,
    input_tree_binding,
    thaw_json,
)
from giclab.harness.plan import run_plan_from_mapping
from giclab.harness.policy import ExecutionDisallowed
from giclab.harness.regulation import regulation_decision_from_mapping
from giclab.registry import load_json, load_yaml
from giclab.validation import ROOT

FIXTURE_ROOT = ROOT / "tests/fixtures/sira/synthetic-contract-fixture"
SESSION_NAME = "SYNTHETIC-SIRA-PAIR-SIMULATIVE_2026-08-08-00-00-00.json"
SCHEMA_GAPS = ROOT / "docs/harness/sira/SCHEMA_GAP_REPORT.yaml"
DRY_RUN_EXAMPLES = ROOT / "docs/harness/sira/DRY_RUN_EXAMPLES.yaml"
H2K_REGULATION_ADDENDUM = ROOT / "docs/harness/sira/H2K_REGULATION_DECISION_ADDENDUM.yaml"
TRACE_FIELD_MAP = ROOT / "docs/audits/sira/TRACE_FIELD_MAP.yaml"
_REAL_VERIFY_PINNED_CHECKOUT = sira_module._verify_pinned_git_checkout


@pytest.fixture(autouse=True)
def _attest_synthetic_source_checkout(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unit fixtures are source-shaped, not forged upstream Git evidence."""

    monkeypatch.setattr(sira_module, "_verify_pinned_git_checkout", lambda *_: None)


def _uv_executable() -> Path:
    executable = shutil.which("uv")
    if executable is None:
        raise AssertionError("uv executable is unavailable")
    return Path(executable)


def _source_root(tmp_path: Path, *, marker: Path | None = None) -> Path:
    root = tmp_path / "pinned-sira-source"
    runner = root / "scripts/run_web_agent.py"
    runner.parent.mkdir(parents=True)
    body = (
        f"from pathlib import Path\nPath({str(marker)!r}).touch()\n"
        if marker is not None
        else "# synthetic-contract-fixture; never executed\n"
    )
    runner.write_text(body, encoding="utf-8")
    return root


def _config(mode: SiRAMode, **changes: Any) -> SiRACommandConfig:
    values: dict[str, Any] = {
        "profile": RunProfile.SMOKE,
        "job_name": f"SYNTHETIC-SIRA-PAIR-{mode.value.upper()}",
        "mode": mode,
        "task": SiRATask.open_query("go to google flights"),
        "max_steps": 1,
        "action_timeout_seconds": 30,
        "max_retry": 0,
        "seed": 42,
    }
    values.update(changes)
    return SiRACommandConfig(**values)


def _plan_for_config(
    config: SiRACommandConfig,
    *,
    condition: str | None = None,
    config_sha256: str | None = None,
    model_revision: str | None = None,
    dataset_revision: str | None | object = ...,
    max_tool_calls: int | None = None,
) -> RunPlan:
    data = valid_plan_data(
        max_wall_seconds=60,
        max_cost_usd=1.0,
        max_model_tokens=100_000,
        max_tool_calls=config.max_steps if max_tool_calls is None else max_tool_calls,
    )
    data["profile"] = config.profile.value
    data["run_id"] = f"RUN-SYNTHETIC-SIRA-{config.mode.value.upper()}"
    data["condition"] = condition or config.mode.condition
    data["seed"] = config.seed
    data["sources"]["upstream_source_id"] = SIRA_SOURCE_ID
    data["sources"]["upstream_commit"] = SIRA_UPSTREAM_COMMIT
    data["sources"]["config_sha256"] = config_sha256 or sira_config_sha256(config)
    data["sources"]["model_revision"] = model_revision
    data["sources"]["dataset_revision"] = (
        config.task.dataset_revision if dataset_revision is ... else dataset_revision
    )
    return run_plan_from_mapping(data)


def _plan(mode: SiRAMode) -> RunPlan:
    return _plan_for_config(_config(mode))


def _adapter(mode: SiRAMode, **changes: Any) -> SiRAAdapter:
    return SiRAAdapter(_config(mode, **changes), _uv_executable())


def _copy_fixture(tmp_path: Path) -> Path:
    attempt = tmp_path / "attempt"
    shutil.copytree(FIXTURE_ROOT, attempt)
    return attempt


def _session_path(attempt: Path) -> Path:
    return attempt / "sira-output" / SESSION_NAME


def _write_session(attempt: Path, value: dict[str, Any]) -> None:
    _session_path(attempt).write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _assert_pair(
    reactive: SiRAAdapter,
    reactive_plan: RunPlan,
    reactive_command: CommandSpec,
    simulative: SiRAAdapter,
    simulative_plan: RunPlan,
    simulative_command: CommandSpec,
    source_root: Path,
    reactive_output_root: Path,
    simulative_output_root: Path,
) -> Any:
    return assert_sira_matched_pair(
        reactive,
        reactive_plan,
        reactive_command,
        simulative,
        simulative_plan,
        simulative_command,
        reactive_upstream_root=source_root,
        reactive_output_root=reactive_output_root,
        simulative_upstream_root=source_root,
        simulative_output_root=simulative_output_root,
    )


def test_builds_source_bound_matched_commands_without_side_effects(tmp_path: Path) -> None:
    source_root = _source_root(tmp_path)
    reactive_output = tmp_path / "attempt-reactive"
    simulative_output = tmp_path / "attempt-simulative"
    reactive = _adapter(SiRAMode.REACTIVE)
    simulative = _adapter(SiRAMode.SIMULATIVE)
    reactive_plan = _plan_for_config(reactive.config)
    simulative_plan = _plan_for_config(simulative.config)

    reactive_command = reactive.build_command(reactive_plan, source_root, reactive_output)
    simulative_command = simulative.build_command(simulative_plan, source_root, simulative_output)
    report = _assert_pair(
        reactive,
        reactive_plan,
        reactive_command,
        simulative,
        simulative_plan,
        simulative_command,
        source_root,
        reactive_output,
        simulative_output,
    )

    rendered = command_document(reactive_command)
    assert rendered["shell"] is False
    assert reactive_command.secret_environment == (SIRA_SECRET_NAME,)
    assert dict(reactive_command.environment) == {}
    assert reactive_command.cwd == source_root.resolve()
    assert len(reactive_command.input_trees) == 1
    assert reactive_command.input_trees[0].root == source_root.resolve()
    assert [item.root for item in reactive_command.owned_output_roots] == [
        reactive_output.resolve() / "sira-output"
    ]
    assert [path.as_posix() for path in reactive_command.unowned_output_patterns] == [
        "logs/sira_*.log",
        "src/sira/web/logs/*.log",
    ]
    assert reactive_command.resource_projection.tool_calls == 1
    assert reactive_command.resource_projection.unbounded_applicable == (
        NonWallResource.COST_USD,
        NonWallResource.MODEL_TOKENS,
    )
    assert [item.field for item in report.config_differences] == ["job_name", "mode"]
    assert [item.owner for item in report.command_differences] == [
        "source-contract",
        "source-contract",
        "harness-evidence-isolation",
        "harness-evidence-isolation",
    ]
    assert not reactive_output.exists()
    assert not simulative_output.exists()


def test_command_document_round_trip_preserves_source_and_execution_gaps(
    tmp_path: Path,
) -> None:
    command = _adapter(SiRAMode.REACTIVE).build_command(
        _plan(SiRAMode.REACTIVE),
        _source_root(tmp_path),
        tmp_path / "attempt",
    )
    reconstructed = command_from_document(command_document(command))
    assert reconstructed.input_trees == command.input_trees
    assert reconstructed.owned_output_roots == command.owned_output_roots
    assert reconstructed.unowned_output_patterns == command.unowned_output_patterns
    assert reconstructed.resource_projection.unbounded_applicable == (
        NonWallResource.COST_USD,
        NonWallResource.MODEL_TOKENS,
    )
    with pytest.raises(ValueError, match="both finitely projected"):
        ResourceProjection(
            cost_usd=1.0,
            unbounded_applicable=(NonWallResource.COST_USD,),
        )


def test_source_and_attempt_output_ownership_cannot_overlap(tmp_path: Path) -> None:
    source_root = _source_root(tmp_path)
    adapter = _adapter(SiRAMode.REACTIVE)
    with pytest.raises(SiRAContractError, match="must not overlap"):
        adapter.build_command(
            _plan_for_config(adapter.config),
            source_root,
            source_root / "attempt",
        )


def test_pinned_checkout_verifier_accepts_only_exact_clean_git_root(tmp_path: Path) -> None:
    root = tmp_path / "source"
    root.mkdir()
    subprocess.run(("git", "init", "-q", str(root)), check=True)
    subprocess.run(
        ("git", "-C", str(root), "config", "user.email", "test@example.invalid"), check=True
    )
    subprocess.run(("git", "-C", str(root), "config", "user.name", "Contract Test"), check=True)
    (root / "tracked.txt").write_text("pinned\n", encoding="utf-8")
    subprocess.run(("git", "-C", str(root), "add", "tracked.txt"), check=True)
    subprocess.run(("git", "-C", str(root), "commit", "-qm", "fixture"), check=True)
    head = subprocess.run(
        ("git", "-C", str(root), "rev-parse", "HEAD"),
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    _REAL_VERIFY_PINNED_CHECKOUT(root.resolve(), head)
    with pytest.raises(SiRAContractError, match="audited commit"):
        _REAL_VERIFY_PINNED_CHECKOUT(root.resolve(), "f" * 40)
    (root / "untracked.txt").write_text("drift\n", encoding="utf-8")
    with pytest.raises(SiRAContractError, match="must be clean"):
        _REAL_VERIFY_PINNED_CHECKOUT(root.resolve(), head)
    with pytest.raises(SiRAContractError, match="valid Git checkout"):
        _REAL_VERIFY_PINNED_CHECKOUT(tmp_path.resolve(), head)


def test_adapter_wires_git_attestation_before_command_creation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        sira_module,
        "_verify_pinned_git_checkout",
        _REAL_VERIFY_PINNED_CHECKOUT,
    )
    source_root = _source_root(tmp_path)
    adapter = _adapter(SiRAMode.REACTIVE)
    with pytest.raises(SiRAContractError, match="valid Git checkout"):
        adapter.build_command(
            _plan_for_config(adapter.config),
            source_root,
            tmp_path / "attempt",
        )
    assert not (tmp_path / "attempt").exists()


def test_bound_git_head_is_rechecked_even_when_tree_bytes_are_unchanged(
    tmp_path: Path,
) -> None:
    root = tmp_path / "source"
    root.mkdir()
    subprocess.run(("git", "init", "-q", str(root)), check=True)
    subprocess.run(
        ("git", "-C", str(root), "config", "user.email", "test@example.invalid"),
        check=True,
    )
    subprocess.run(
        ("git", "-C", str(root), "config", "user.name", "Contract Test"),
        check=True,
    )
    (root / "tracked.txt").write_text("pinned\n", encoding="utf-8")
    subprocess.run(("git", "-C", str(root), "add", "tracked.txt"), check=True)
    subprocess.run(("git", "-C", str(root), "commit", "-qm", "fixture"), check=True)
    head = subprocess.run(
        ("git", "-C", str(root), "rev-parse", "HEAD"),
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    command = CommandSpec(
        argv=(sys.executable, "-c", "pass"),
        cwd=root,
        timeout_seconds=2,
        input_trees=(
            input_tree_binding(
                root,
                excluded_roots=(PurePosixPath(".git"),),
                git_commit=head,
            ),
        ),
    )
    plan = bind_plan(run_plan_from_mapping(valid_plan_data()), command)
    workspace = ArtifactWorkspace.open(tmp_path / "artifacts", create=True)
    executor = LocalRunExecutor(workspace)
    assert executor.dry_run(plan, command, project_state()).execution_allowed

    subprocess.run(
        ("git", "-C", str(root), "commit", "--allow-empty", "-qm", "identity drift"),
        check=True,
    )
    report = executor.dry_run(plan, command, project_state())
    assert not report.execution_allowed
    assert any("bound Git checkout commit changed" in item for item in report.blockers)
    with pytest.raises(ExecutionDisallowed, match="bound Git checkout commit changed"):
        executor.execute(plan, command, project_state())
    assert list(workspace.root.iterdir()) == []


def test_bound_source_tree_is_rechecked_before_any_execution(tmp_path: Path) -> None:
    marker = tmp_path / "must-not-exist"
    source_root = _source_root(tmp_path, marker=marker)
    workspace = ArtifactWorkspace.open(tmp_path / "artifacts", create=True)
    initial_plan = _plan(SiRAMode.REACTIVE)
    output_root = workspace.attempt_directory(
        initial_plan.artifacts, initial_plan.identity, create=False
    )
    command = _adapter(SiRAMode.REACTIVE).build_command(initial_plan, source_root, output_root)
    plan = bind_plan(initial_plan, command)
    (source_root / "injected.py").write_text("drift = True\n", encoding="utf-8")

    executor = LocalRunExecutor(workspace)
    report = executor.dry_run(plan, command, project_state(prototype=True, paid=True))
    assert any("bound input tree content changed" in item for item in report.blockers)
    with pytest.raises(ExecutionDisallowed, match="bound input tree content changed"):
        executor.execute(plan, command, project_state(prototype=True, paid=True))
    assert not marker.exists()
    assert list(workspace.root.iterdir()) == []


def test_pair_assertion_rejects_config_single_side_and_symmetric_command_drift(
    tmp_path: Path,
) -> None:
    source_root = _source_root(tmp_path)
    reactive = _adapter(SiRAMode.REACTIVE)
    simulative = _adapter(
        SiRAMode.SIMULATIVE,
        output_subdirectory=PurePosixPath("different-output"),
    )
    reactive_plan = _plan_for_config(reactive.config)
    simulative_plan = _plan_for_config(simulative.config)
    reactive_command = reactive.build_command(reactive_plan, source_root, tmp_path / "reactive")
    simulative_command = simulative.build_command(
        simulative_plan, source_root, tmp_path / "simulative"
    )
    with pytest.raises(SiRAPairMismatch, match="configurations"):
        _assert_pair(
            reactive,
            reactive_plan,
            reactive_command,
            simulative,
            simulative_plan,
            simulative_command,
            source_root,
            tmp_path / "reactive",
            tmp_path / "simulative",
        )

    simulative = _adapter(SiRAMode.SIMULATIVE)
    simulative_plan = _plan_for_config(simulative.config)
    simulative_command = simulative.build_command(
        simulative_plan, source_root, tmp_path / "matched-simulative"
    )
    drifted_one_side = replace(
        simulative_command,
        environment={"SIRA_TEST_MODE": "drift"},
    )
    with pytest.raises(SiRAPairMismatch, match="exactly match"):
        _assert_pair(
            reactive,
            reactive_plan,
            reactive_command,
            simulative,
            simulative_plan,
            drifted_one_side,
            source_root,
            tmp_path / "reactive",
            tmp_path / "matched-simulative",
        )

    with pytest.raises(SiRAPairMismatch, match="exactly match"):
        _assert_pair(
            reactive,
            reactive_plan,
            reactive_command,
            simulative,
            simulative_plan,
            simulative_command,
            source_root,
            tmp_path / "wrong-reactive-owner",
            tmp_path / "matched-simulative",
        )

    def mutate_model(command: CommandSpec) -> CommandSpec:
        argv = list(command.argv)
        argv[argv.index("--model") + 1] = "o1"
        return replace(command, argv=tuple(argv))

    with pytest.raises(SiRAPairMismatch, match="exactly match"):
        _assert_pair(
            reactive,
            reactive_plan,
            mutate_model(reactive_command),
            simulative,
            simulative_plan,
            mutate_model(simulative_command),
            source_root,
            tmp_path / "reactive",
            tmp_path / "matched-simulative",
        )


def test_sira_pair_emits_identical_regulation_policy_and_source_metadata(
    tmp_path: Path,
) -> None:
    reactive_attempt = _copy_fixture(tmp_path / "reactive-fixture")
    reactive_session = _session_path(reactive_attempt)
    reactive_session.rename(
        reactive_session.with_name("SYNTHETIC-SIRA-PAIR-REACTIVE_2026-08-08-00-00-00.json")
    )
    simulative_attempt = _copy_fixture(tmp_path / "simulative-fixture")
    reactive = _adapter(SiRAMode.REACTIVE)
    simulative = _adapter(SiRAMode.SIMULATIVE)
    reactive_plan = _plan_for_config(reactive.config)
    simulative_plan = _plan_for_config(simulative.config)

    def assignment_payload(adapter: SiRAAdapter, plan: RunPlan, attempt: Path) -> dict[str, Any]:
        event = next(
            event
            for event in adapter.normalize(plan, attempt).events
            if event.event_type is AdapterEventType.REGULATION_DECISION
        )
        return {key: thaw_json(value) for key, value in event.payload.items()}

    reactive_payload = assignment_payload(reactive, reactive_plan, reactive_attempt)
    simulative_payload = assignment_payload(simulative, simulative_plan, simulative_attempt)
    invariant_fields = {
        "decision_id",
        "source_kind",
        "policy_id",
        "policy_revision",
        "available_modes",
        "confidence",
        "override",
        "fallback",
        "input_event_sequences",
        "resolved_configuration_refs",
        "field_provenance",
    }
    assert {key: reactive_payload[key] for key in invariant_fields} == {
        key: simulative_payload[key] for key in invariant_fields
    }
    assert reactive_payload["selected_mode"] == "reactive"
    assert simulative_payload["selected_mode"] == "simulative"
    assert reactive_payload["raw_artifact_refs"] != simulative_payload["raw_artifact_refs"]
    assert sira_regulation_policy_metadata(reactive_plan) == sira_regulation_policy_metadata(
        simulative_plan
    )

    source_root = _source_root(tmp_path)
    reactive_output = tmp_path / "reactive-output"
    simulative_output = tmp_path / "simulative-output"
    reactive_command = reactive.build_command(reactive_plan, source_root, reactive_output)
    simulative_command = simulative.build_command(
        simulative_plan,
        source_root,
        simulative_output,
    )
    drifted_plan = replace(
        simulative_plan,
        sources=replace(simulative_plan.sources, protocol_sha256="f" * 64),
    )
    with pytest.raises(SiRAPairMismatch, match="regulation policy/source metadata"):
        _assert_pair(
            reactive,
            reactive_plan,
            reactive_command,
            simulative,
            drifted_plan,
            simulative_command,
            source_root,
            reactive_output,
            simulative_output,
        )


@pytest.mark.parametrize(
    "plan_changes,match",
    [
        ({"config_sha256": "f" * 64}, "config_sha256"),
        ({"model_revision": "provider-revision"}, "immutable model revision"),
        ({"dataset_revision": "f" * 64}, "dataset revision"),
        ({"max_tool_calls": 2}, "tool-call limit"),
        ({"condition": "SIRA-REACTIVE"}, "condition"),
    ],
)
def test_adapter_rejects_plan_contract_mismatch(
    tmp_path: Path,
    plan_changes: dict[str, Any],
    match: str,
) -> None:
    config = _config(SiRAMode.SIMULATIVE)
    plan = _plan_for_config(config, **plan_changes)
    with pytest.raises(SiRAContractError, match=match):
        SiRAAdapter(config, _uv_executable()).build_command(
            plan,
            _source_root(tmp_path),
            tmp_path / "attempt",
        )


def test_source_config_rejects_symmetric_contract_drift() -> None:
    with pytest.raises(SiRAContractError, match="model alias"):
        _config(SiRAMode.REACTIVE, model="o1")
    with pytest.raises(SiRAContractError, match="max_steps"):
        _config(SiRAMode.REACTIVE, max_steps=2)
    with pytest.raises(SiRAContractError, match="README query"):
        _config(
            SiRAMode.REACTIVE,
            task=SiRATask.open_query("different task"),
        )


def test_unreviewed_pilot_datasets_are_normalizable_but_not_command_authorized(
    tmp_path: Path,
) -> None:
    tasks = (
        SiRATask.dataset_slice(
            SiRADataset.FLIGHTQA,
            start_idx=0,
            end_idx=1,
            expected_goal="synthetic FlightQA goal",
            dataset_revision=SIRA_DATASET_REVISIONS["flightqa"],
            data_root=PurePosixPath("data"),
        ),
        SiRATask.dataset_slice(
            SiRADataset.WEBARENA,
            start_idx=7,
            end_idx=8,
            expected_goal="synthetic WebArena goal",
            dataset_revision="a" * 64,
            expected_instance_id="browsergym/webarena.7",
        ),
    )
    for task in tasks:
        dataset = task.dataset
        assert dataset is not None
        config = _config(
            SiRAMode.SIMULATIVE,
            profile=RunProfile.PILOT,
            task=task,
            max_steps=30,
            job_name=f"SYNTHETIC-{dataset.value.upper()}-SIMULATIVE",
        )
        with pytest.raises(SiRAContractError, match=f"no reviewed {dataset.value} pilot command"):
            SiRAAdapter(config, _uv_executable()).build_command(
                _plan_for_config(config),
                tmp_path / "source-is-never-read",
                tmp_path / "attempt-is-never-created",
            )


def test_unbounded_resources_and_unowned_logs_block_even_authorized_plan(
    tmp_path: Path,
) -> None:
    marker = tmp_path / "must-not-exist"
    source_root = _source_root(tmp_path, marker=marker)
    workspace = ArtifactWorkspace.open(tmp_path / "artifacts", create=True)
    initial_plan = _plan(SiRAMode.REACTIVE)
    output_root = workspace.attempt_directory(
        initial_plan.artifacts,
        initial_plan.identity,
        create=False,
    )
    command = _adapter(SiRAMode.REACTIVE).build_command(
        initial_plan,
        source_root,
        output_root,
    )
    plan = bind_plan(initial_plan, command)
    executor = LocalRunExecutor(workspace)
    state = project_state(prototype=True, paid=True)

    report = executor.dry_run(plan, command, state)
    assert not report.execution_allowed
    assert any("without finite command-enforced upper bounds" in item for item in report.blockers)
    assert any("outside harness attempt ownership" in item for item in report.blockers)
    with pytest.raises(ExecutionDisallowed, match="without finite command-enforced"):
        executor.execute(plan, command, state)
    assert not marker.exists()
    assert list(workspace.root.iterdir()) == []


def test_normalizes_fixture_with_field_contracts_and_preserves_all_raw_bytes(
    tmp_path: Path,
) -> None:
    attempt = _copy_fixture(tmp_path)
    raw_before = {
        path.relative_to(attempt).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in attempt.rglob("*")
        if path.is_file()
    }
    raw_session = load_json(_session_path(attempt))
    result = _adapter(SiRAMode.SIMULATIVE).normalize(_plan(SiRAMode.SIMULATIVE), attempt)
    raw_after = {
        path.relative_to(attempt).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in attempt.rglob("*")
        if path.is_file()
    }

    event_types = [event.event_type for event in result.events]
    assert event_types.count(AdapterEventType.REGULATION_DECISION) == 1
    assert event_types.count(AdapterEventType.OBSERVATION) == 1
    assert event_types.count(AdapterEventType.BELIEF_STATE) == 1
    assert event_types.count(AdapterEventType.PLAN) == 1
    assert event_types.count(AdapterEventType.EXECUTED_ACTION) == 1
    assert event_types.count(AdapterEventType.OUTCOME) == 1
    assert AdapterEventType.CANDIDATE_ACTION not in event_types
    assert AdapterEventType.PREDICTED_FUTURE not in event_types
    assert AdapterEventType.CRITIC_EVALUATION not in event_types
    regulation = next(
        event for event in result.events if event.event_type is AdapterEventType.REGULATION_DECISION
    )
    assert regulation.source == SIRA_REGULATION_EVENT_SOURCE
    assert regulation.provenance is EventProvenance.DERIVED
    regulation_payload = {key: thaw_json(value) for key, value in regulation.payload.items()}
    regulation_decision_from_mapping(regulation_payload)
    assert regulation_payload["source_kind"] == "experiment_assignment"
    assert regulation_payload["policy_id"] == SIRA_REGULATION_POLICY_ID
    assert regulation_payload["selected_mode"] == "simulative"
    assert regulation_payload["available_modes"] == ["reactive", "simulative"]
    assert regulation_payload["confidence"] is None
    assert regulation_payload["override"] == {
        "applied": None,
        "source": None,
        "reason": None,
    }
    assert regulation_payload["fallback"] == {
        "triggered": None,
        "target": None,
        "reason": None,
    }
    assert regulation_payload["raw_artifact_refs"] == [
        "sira-output/SYNTHETIC-SIRA-PAIR-SIMULATIVE_2026-08-08-00-00-00.json"
    ]
    assert regulation_payload["resolved_configuration_refs"] == [
        "run-plan.json",
        "command.json",
    ]
    assert all(
        event.provenance is EventProvenance.OBSERVED
        for event in result.events
        if event.event_type is not AdapterEventType.REGULATION_DECISION
    )
    first_observation = next(
        event for event in result.events if event.event_type is AdapterEventType.OBSERVATION
    )
    payload = {key: thaw_json(value) for key, value in first_observation.payload.items()}
    field_contracts = payload["field_contracts"]
    assert isinstance(field_contracts, dict)
    assert field_contracts["raw_observation"] == {
        "direct_source_path": "history[0][0]",
        "normalization_rule": (
            "copy the complete structured observation mapping without semantic inference"
        ),
        "provenance": "observed",
        "status": "available",
    }
    step_contract = field_contracts["step_index"]
    assert isinstance(step_contract, dict)
    assert step_contract["provenance"] == "derived"
    assert payload["raw_observation"] == raw_session["history"][0][0]
    outcome = next(event for event in result.events if event.event_type is AdapterEventType.OUTCOME)
    assert set(outcome.payload) == {"source_is_complete", "source_error", "field_contracts"}
    assert "critic_evaluation.structured_per_candidate_scores" in result.unavailable_fields
    assert "outcome.webarena_rewards" in result.unavailable_fields
    assert result.accounting.cost_usd is None
    assert result.accounting.gpu_hours == 0.0
    assert result.accounting.model_tokens is None
    assert result.accounting.tool_calls is None
    assert {path.relative_to(attempt).as_posix() for path in result.raw_artifacts} == {
        "sira-output/SYNTHETIC-SIRA-PAIR-SIMULATIVE_2026-08-08-00-00-00.json",
        "sira-output/debug/1700000000.log",
        "sira-output/isolated-source-logs/agent/2026-08-08-00-00-00-000000.log",
        "sira-output/isolated-source-logs/global/sira_2026-08-08.log",
    }
    assert raw_after == raw_before


def test_missing_belief_is_explicitly_unavailable(tmp_path: Path) -> None:
    attempt = _copy_fixture(tmp_path)
    session = load_json(_session_path(attempt))
    del session["history"][0][2]["state"]
    _write_session(attempt, session)
    result = _adapter(SiRAMode.SIMULATIVE).normalize(_plan(SiRAMode.SIMULATIVE), attempt)
    assert not any(event.event_type is AdapterEventType.BELIEF_STATE for event in result.events)
    assert "belief_state[0].upstream_state" in result.unavailable_fields


def test_missing_plan_is_explicitly_unavailable(tmp_path: Path) -> None:
    attempt = _copy_fixture(tmp_path)
    session = load_json(_session_path(attempt))
    del session["history"][0][2]["plan"]
    del session["history"][0][2]["intent"]
    _write_session(attempt, session)
    result = _adapter(SiRAMode.SIMULATIVE).normalize(_plan(SiRAMode.SIMULATIVE), attempt)
    assert not any(event.event_type is AdapterEventType.PLAN for event in result.events)
    assert "plan[0].selected_plan_text" in result.unavailable_fields
    assert "plan[0].upstream_policy_output_alias" in result.unavailable_fields


def test_absent_critic_score_stays_unavailable_and_emits_no_event(tmp_path: Path) -> None:
    result = _adapter(SiRAMode.SIMULATIVE).normalize(
        _plan(SiRAMode.SIMULATIVE), _copy_fixture(tmp_path)
    )
    assert not any(
        event.event_type is AdapterEventType.CRITIC_EVALUATION for event in result.events
    )
    assert "critic_evaluation.structured_per_candidate_scores" in result.unavailable_fields


def test_malformed_upstream_control_like_field_stays_raw_and_unnormalized(
    tmp_path: Path,
) -> None:
    attempt = _copy_fixture(tmp_path)
    session = load_json(_session_path(attempt))
    session["history"][0][2]["regulation_decision"] = {
        "source_kind": "model_explicit_output",
        "selected_mode": ["malformed", "not-a-string"],
        "confidence": "high",
    }
    _write_session(attempt, session)
    raw_before = _session_path(attempt).read_bytes()

    result = _adapter(SiRAMode.SIMULATIVE).normalize(
        _plan(SiRAMode.SIMULATIVE),
        attempt,
    )

    regulation_events = [
        event for event in result.events if event.event_type is AdapterEventType.REGULATION_DECISION
    ]
    assert len(regulation_events) == 1
    payload = {key: thaw_json(value) for key, value in regulation_events[0].payload.items()}
    assert payload["source_kind"] == "experiment_assignment"
    assert payload["selected_mode"] == "simulative"
    assert "regulation_decision" not in payload
    assert _session_path(attempt).read_bytes() == raw_before
    assert _session_path(attempt) in result.raw_artifacts


def test_source_warnings_and_errors_use_typed_harness_notice_channel(tmp_path: Path) -> None:
    attempt = _copy_fixture(tmp_path)
    session = load_json(_session_path(attempt))
    session["history"][0][0]["last_action_error"] = "prior action failed"
    session["history"][0][2]["obs_info"]["error_prefix"] = "retry warning"
    session["history"][0][2]["obs_info"]["return_action"] = "limit reached"
    session["error"] = "session exception"
    _write_session(attempt, session)

    result = _adapter(SiRAMode.SIMULATIVE).normalize(_plan(SiRAMode.SIMULATIVE), attempt)
    assert [notice.severity for notice in result.notices] == [
        AdapterNoticeSeverity.WARNING,
        AdapterNoticeSeverity.WARNING,
        AdapterNoticeSeverity.ERROR,
        AdapterNoticeSeverity.ERROR,
    ]
    assert [notice.provenance for notice in result.notices] == [
        EventProvenance.DERIVED,
        EventProvenance.DERIVED,
        EventProvenance.OBSERVED,
        EventProvenance.OBSERVED,
    ]
    assert result.notices[-1].source_paths == ("error",)


@pytest.mark.parametrize("kind", ["wrong-shape", "duplicate-key"])
def test_malformed_trace_is_refused(tmp_path: Path, kind: str) -> None:
    attempt = _copy_fixture(tmp_path)
    session_path = _session_path(attempt)
    if kind == "wrong-shape":
        session = load_json(session_path)
        session["history"][0] = [{}, "missing-step-info"]
        _write_session(attempt, session)
    else:
        encoded = session_path.read_text(encoding="utf-8")
        session_path.write_text(
            encoded.replace(
                '"goal": "go to google flights",',
                '"goal": "duplicate",\n  "goal": "go to google flights",',
                1,
            ),
            encoding="utf-8",
        )
    with pytest.raises(SiRATraceError, match="malformed SiRA"):
        _adapter(SiRAMode.SIMULATIVE).normalize(_plan(SiRAMode.SIMULATIVE), attempt)


@pytest.mark.parametrize(
    "mutation,match",
    [
        (lambda session: session.update(goal="wrong goal"), "trace goal"),
        (
            lambda session: session["history"][0][0].update(goal="wrong goal"),
            "observation goal mismatch",
        ),
        (
            lambda session: session["history"][0][2]["obs_info"].update(goal="wrong goal"),
            "obs_info goal mismatch",
        ),
        (
            lambda session: session["history"][0][2].update(action="different action"),
            "duplicate action mismatch",
        ),
        (
            lambda session: session["history"][0][2].pop("action"),
            "step_info.action",
        ),
        (
            lambda session: session["history"][0][2].update(intent="different plan"),
            "plan/intent mismatch",
        ),
        (
            lambda session: session["history"][0][2].pop("intent"),
            "plan/intent presence mismatch",
        ),
        (
            lambda session: session.update(is_complete=True),
            "is_complete contradicts",
        ),
        (
            lambda session: session["history"].append(session["history"][0]),
            "exceeds the configured max_steps",
        ),
    ],
)
def test_trace_task_and_step_identity_mismatch_is_refused(
    tmp_path: Path,
    mutation: Any,
    match: str,
) -> None:
    attempt = _copy_fixture(tmp_path)
    session = load_json(_session_path(attempt))
    mutation(session)
    _write_session(attempt, session)
    with pytest.raises(SiRATraceError, match=match):
        _adapter(SiRAMode.SIMULATIVE).normalize(_plan(SiRAMode.SIMULATIVE), attempt)


def test_webarena_identity_and_outcome_fields_are_profile_reconciled(tmp_path: Path) -> None:
    goal = "synthetic WebArena goal"
    task = SiRATask.dataset_slice(
        SiRADataset.WEBARENA,
        start_idx=7,
        end_idx=8,
        expected_goal=goal,
        dataset_revision="a" * 64,
        expected_instance_id="browsergym/webarena.7",
    )
    config = _config(
        SiRAMode.SIMULATIVE,
        profile=RunProfile.PILOT,
        task=task,
        max_steps=30,
        job_name="SYNTHETIC-WEBARENA-SIMULATIVE",
    )
    adapter = SiRAAdapter(config, _uv_executable())
    plan = _plan_for_config(config)
    attempt = _copy_fixture(tmp_path)
    old_path = _session_path(attempt)
    new_path = old_path.with_name("SYNTHETIC-WEBARENA-SIMULATIVE_2026-08-08-00-00-00.json")
    session = load_json(old_path)
    session["goal"] = goal
    session["instance_id"] = "browsergym/webarena.7"
    session["history"][0][0]["goal"] = goal
    session["history"][0][2]["obs_info"]["goal"] = goal
    session["rewards"] = [0.0, 1.0]
    session["test_result"] = 1.0
    old_path.unlink()
    new_path.write_text(json.dumps(session), encoding="utf-8")
    redundant_path = attempt / "sira-output/output.jsonl"
    redundant_path.write_text(
        json.dumps(
            {
                "instance_id": session["instance_id"],
                "goal": session["goal"],
                "test_result": session["test_result"],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = adapter.normalize(plan, attempt)
    assert redundant_path in result.raw_artifacts
    outcome = next(event for event in result.events if event.event_type is AdapterEventType.OUTCOME)
    assert thaw_json(outcome.payload["webarena_rewards"]) == [0.0, 1.0]
    metric_fields = [
        set(event.payload) - {"field_contracts"}
        for event in result.events
        if event.event_type is AdapterEventType.METRIC
    ]
    assert metric_fields == [{"webarena_rewards"}, {"webarena_test_result"}]

    session["instance_id"] = "wrong-instance"
    new_path.write_text(json.dumps(session), encoding="utf-8")
    with pytest.raises(SiRATraceError, match="instance_id"):
        adapter.normalize(plan, attempt)

    session["instance_id"] = "browsergym/webarena.7"
    session["test_result"] = 0.0
    new_path.write_text(json.dumps(session), encoding="utf-8")
    with pytest.raises(SiRATraceError, match="reward derivation"):
        adapter.normalize(plan, attempt)

    session["rewards"] = []
    new_path.write_text(json.dumps(session), encoding="utf-8")
    with pytest.raises(SiRATraceError, match="rewards must be nonempty"):
        adapter.normalize(plan, attempt)

    session["rewards"] = [0.0, 1.0]
    session["test_result"] = 1.0
    new_path.write_text(json.dumps(session), encoding="utf-8")
    redundant_path.write_text(
        json.dumps(
            {
                "instance_id": session["instance_id"],
                "goal": session["goal"],
                "test_result": 0.0,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    with pytest.raises(SiRATraceError, match=r"output\.jsonl test_result contradicts"):
        adapter.normalize(plan, attempt)

    row = {
        "instance_id": session["instance_id"],
        "goal": session["goal"],
        "test_result": session["test_result"],
    }
    redundant_path.write_text(
        json.dumps(row) + "\n" + json.dumps(row) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(SiRATraceError, match="exactly one row"):
        adapter.normalize(plan, attempt)

    redundant_path.unlink()
    with pytest.raises(SiRATraceError, match=r"output\.jsonl is missing"):
        adapter.normalize(plan, attempt)


def test_non_webarena_trace_rejects_webarena_summary_artifact(tmp_path: Path) -> None:
    attempt = _copy_fixture(tmp_path)
    (attempt / "sira-output/output.jsonl").write_text(
        '{"instance_id":"synthetic","goal":"synthetic","test_result":0.0}\n',
        encoding="utf-8",
    )
    with pytest.raises(SiRATraceError, match="non-WebArena"):
        _adapter(SiRAMode.SIMULATIVE).normalize(_plan(SiRAMode.SIMULATIVE), attempt)


def test_repeated_attempt_artifacts_are_refused(tmp_path: Path) -> None:
    attempt = _copy_fixture(tmp_path)
    second = attempt / "sira-output" / ("SYNTHETIC-SIRA-PAIR-SIMULATIVE_2026-08-08-00-00-01.json")
    shutil.copyfile(_session_path(attempt), second)
    with pytest.raises(SiRATraceError, match="repeated attempts"):
        _adapter(SiRAMode.SIMULATIVE).normalize(_plan(SiRAMode.SIMULATIVE), attempt)


def test_path_traversal_and_symlinked_output_are_refused(tmp_path: Path) -> None:
    with pytest.raises(SiRAContractError, match="parent"):
        _config(
            SiRAMode.SIMULATIVE,
            output_subdirectory=PurePosixPath("../escape"),
        )
    attempt = tmp_path / "attempt"
    outside = tmp_path / "outside"
    attempt.mkdir()
    outside.mkdir()
    (attempt / "sira-output").symlink_to(outside, target_is_directory=True)
    with pytest.raises(SiRATraceError, match="symlink"):
        _adapter(SiRAMode.SIMULATIVE).normalize(_plan(SiRAMode.SIMULATIVE), attempt)


def test_condition_mismatch_is_refused_before_trace_access(tmp_path: Path) -> None:
    missing_output = tmp_path / "missing-output"
    config = _config(SiRAMode.SIMULATIVE)
    plan = _plan_for_config(config, condition=SiRAMode.REACTIVE.condition)
    with pytest.raises(SiRAContractError, match="condition"):
        SiRAAdapter(config, _uv_executable()).normalize(plan, missing_output)
    assert not missing_output.exists()


def test_fixture_is_machine_labeled_synthetic_and_not_upstream_evidence() -> None:
    manifest = load_yaml(FIXTURE_ROOT / "fixture-manifest.yaml")
    assert manifest["provenance_class"] == "synthetic-contract-fixture"
    assert manifest["upstream_evidence"] is False
    assert manifest["scientific_evidence"] is False
    assert manifest["source_contract"]["commit"] == SIRA_UPSTREAM_COMMIT
    assert {item["role"] for item in manifest["files"]} >= {
        "isolated-raw-only-agent-log-shape",
        "isolated-raw-only-global-log-shape",
    }


def test_schema_gap_report_matches_runtime_rules_and_all_canonical_events(
    tmp_path: Path,
) -> None:
    report = load_yaml(SCHEMA_GAPS)
    assert report["adapter_scope"]["upstream_sample_trace_available"] is False
    canonical = report["canonical_events"]
    assert set(canonical) == {
        event.value for event in EventType if event is not EventType.REGULATION_DECISION
    }
    required_field_keys = {
        "field",
        "direct_source_path",
        "normalization_rule",
        "provenance",
        "status",
        "missing_behavior",
    }
    for event_name, contract in canonical.items():
        assert contract["fields"], event_name
        for field_contract in contract["fields"]:
            assert set(field_contract) == required_field_keys
            assert field_contract["provenance"] in {
                provenance.value for provenance in EventProvenance
            }
            assert field_contract["missing_behavior"]
            assert field_contract["normalization_rule"]
    for event_name, runtime_rules in SIRA_FIELD_RULES.items():
        report_rules = {item["field"]: item for item in canonical[event_name]["fields"]}
        for field, rule in runtime_rules.items():
            assert field in report_rules
            assert report_rules[field]["direct_source_path"] == rule.direct_source_path
            assert report_rules[field]["normalization_rule"] == rule.normalization_rule
            assert report_rules[field]["provenance"] == rule.provenance.value
            assert report_rules[field]["status"] == rule.status
    gaps = {item["unit"]: item for item in report["execution_gaps"]}
    assert gaps["cost_usd"]["status"] == "applicable-unbounded"
    assert gaps["model_tokens"]["execution_effect"] == "hard-preflight-blocker"
    raw_gaps = {item["artifact"]: item for item in report["raw_only_gaps"]}
    assert raw_gaps["agent_text_log"]["execution_effect"] == "hard-preflight-blocker"
    assert raw_gaps["global_text_log"]["execution_effect"] == "hard-preflight-blocker"

    t01 = load_yaml(TRACE_FIELD_MAP)["canonical_events"]
    normalized = _adapter(SiRAMode.SIMULATIVE).normalize(
        _plan(SiRAMode.SIMULATIVE),
        _copy_fixture(tmp_path),
    )
    for event_name in (
        "observation",
        "belief_state",
        "plan",
        "executed_action",
        "outcome",
        "metric",
    ):
        report_rules = {item["field"]: item for item in canonical[event_name]["fields"]}
        for field, source_path in t01[event_name]["payload_map"].items():
            assert field in report_rules, f"missing T01 {event_name}.{field}"
            assert report_rules[field]["direct_source_path"] == source_path
        for field in t01[event_name].get("unavailable_fields", {}):
            assert field in report_rules, f"missing T01 unavailable {event_name}.{field}"
            assert report_rules[field]["status"] == "unavailable"
            assert f"{event_name}.{field}" in normalized.unavailable_fields
    assert canonical["warning"]["fields"][1]["provenance"] == t01["warning"]["provenance"]
    assert canonical["error"]["fields"][0]["provenance"] == t01["error"]["provenance"]


def test_h2k_regulation_mapping_addendum_matches_runtime_rules() -> None:
    addendum = load_yaml(H2K_REGULATION_ADDENDUM)
    assert addendum["track_id"] == "RQ-H2K"
    assert addendum["event_schema"] == {
        "emitted_version": "0.2.0",
        "legacy_read_version": "0.1.0",
        "compatibility": "existing-v0.1-streams-remain-readable-without-reinterpretation",
    }
    event = addendum["event"]
    assert event["event_type"] == EventType.REGULATION_DECISION.value
    assert event["source"] == SIRA_REGULATION_EVENT_SOURCE
    report_rules = {item["field"]: item for item in event["fields"]}
    assert set(report_rules) == {*SIRA_REGULATION_FIELD_RULES, "field_provenance"}
    for field, rule in SIRA_REGULATION_FIELD_RULES.items():
        report_rule = report_rules[field]
        assert report_rule["direct_source_path"] == rule.direct_source_path
        assert report_rule["normalization_rule"] == rule.normalization_rule
        assert report_rule["provenance"] == rule.provenance.value
        assert report_rule["status"] == rule.status
        assert report_rule["missing_behavior"]
    assert addendum["per_step_control_mapping"]["status"] == "unavailable"
    assert "no_internalization_boolean_or_category" in addendum["prohibitions"]


def test_dataset_revision_is_part_of_task_and_plan_identity() -> None:
    task = SiRATask.dataset_slice(
        SiRADataset.FANOUT,
        start_idx=0,
        end_idx=1,
        expected_goal=(
            "What is the batting hand of each of the first five picks in the 1998 MLB draft?"
        ),
        dataset_revision=SIRA_DATASET_REVISIONS["fanout"],
        data_root=PurePosixPath("data"),
    )
    config = _config(
        SiRAMode.REACTIVE,
        profile=RunProfile.PILOT,
        task=task,
        max_steps=30,
        job_name="SYNTHETIC-FANOUT-0000-REACTIVE",
    )
    assert _plan_for_config(config).sources.dataset_revision == SIRA_DATASET_REVISIONS["fanout"]
    with pytest.raises(SiRAContractError, match="audited dataset revision"):
        SiRATask.dataset_slice(
            SiRADataset.FANOUT,
            start_idx=0,
            end_idx=1,
            expected_goal=task.expected_goal or "",
            dataset_revision="f" * 64,
            data_root=PurePosixPath("data"),
        )
    with pytest.raises(SiRAContractError, match="audited data_root"):
        SiRATask.dataset_slice(
            SiRADataset.FANOUT,
            start_idx=0,
            end_idx=1,
            expected_goal=task.expected_goal or "",
            dataset_revision=SIRA_DATASET_REVISIONS["fanout"],
            data_root=PurePosixPath("not-data"),
        )
    with pytest.raises(SiRAContractError, match="exact reviewed FanOut pilot rows"):
        SiRATask.dataset_slice(
            SiRADataset.FANOUT,
            start_idx=0,
            end_idx=1,
            expected_goal="not the audited row zero",
            dataset_revision=SIRA_DATASET_REVISIONS["fanout"],
            data_root=PurePosixPath("data"),
        )


def test_committed_dry_run_examples_match_rendered_pair(tmp_path: Path) -> None:
    examples = load_yaml(DRY_RUN_EXAMPLES)
    assert examples["executed"] is False
    assert examples["authorized"] is False
    source_root = _source_root(tmp_path)
    workspace = ArtifactWorkspace.open(tmp_path / "artifacts", create=True)
    reactive = _adapter(SiRAMode.REACTIVE)
    simulative = _adapter(SiRAMode.SIMULATIVE)
    reactive_plan = _plan_for_config(reactive.config)
    simulative_plan = _plan_for_config(simulative.config)
    reactive_output = workspace.attempt_directory(
        reactive_plan.artifacts, reactive_plan.identity, create=False
    )
    simulative_output = workspace.attempt_directory(
        simulative_plan.artifacts, simulative_plan.identity, create=False
    )
    reactive_command = reactive.build_command(reactive_plan, source_root, reactive_output)
    simulative_command = simulative.build_command(simulative_plan, source_root, simulative_output)
    _assert_pair(
        reactive,
        reactive_plan,
        reactive_command,
        simulative,
        simulative_plan,
        simulative_command,
        source_root,
        reactive_output,
        simulative_output,
    )

    def portable(command: CommandSpec, attempt_placeholder: str) -> list[str]:
        argv = list(command.argv)
        argv[0] = "<UV>"
        output_index = argv.index("--output_dir") + 1
        argv[output_index] = f"<{attempt_placeholder}>/sira-output"
        return argv

    assert portable(reactive_command, "REACTIVE_ATTEMPT") == examples["pair"]["reactive"]["argv"]
    assert examples["pair"]["reactive"]["config_sha256"] == sira_config_sha256(reactive.config)
    assert (
        portable(simulative_command, "SIMULATIVE_ATTEMPT") == examples["pair"]["simulative"]["argv"]
    )
    assert examples["pair"]["simulative"]["config_sha256"] == sira_config_sha256(simulative.config)
    report = LocalRunExecutor(workspace).dry_run(
        reactive_plan,
        reactive_command,
        project_state(prototype=False),
    )
    assert not report.execution_allowed
    assert any("not authorized" in blocker for blocker in report.blockers)
    assert any("disallows prototype" in blocker for blocker in report.blockers)
    assert any("without finite command-enforced" in blocker for blocker in report.blockers)
    assert any("outside harness attempt ownership" in blocker for blocker in report.blockers)
    assert list(workspace.root.iterdir()) == []
