from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from giclab.harness.lambda_l2m_checkpoints import CheckpointBinding
from giclab.harness.lambda_l2m_observer import (
    InstanceMatchState,
    ObserverPhase,
    ReadOnlyObserverTransport,
)
from giclab.harness.lambda_l23_manual_plan import (
    AUTHORIZATION_PLACEHOLDER,
    PLAN_RELATIVE,
    SUPERVISOR_BOOTSTRAP_RELATIVE,
)
from giclab.harness.lambda_l23_manual_supervisor import (
    CheckpointContract,
    HeldPrivateDirectory,
    L23SupervisorError,
    SupervisorAuthorization,
    SupervisorPreflight,
    _await_checkpoint,
    _bind_exact_launch_instance,
    _concrete_qualification_argv,
    _create_private_directory,
    _validate_plan_start_time,
    _verify_loaded_module_origins,
    _wait_for_qualification_archive,
    execute_authorized_manual_observer,
)

ROOT = Path(__file__).resolve().parents[1]


def test_loaded_control_plane_modules_are_repository_bound() -> None:
    loaded = Path(_verify_loaded_module_origins.__code__.co_filename).resolve()
    expected = ROOT / "src/giclab/harness/lambda_l23_manual_supervisor.py"
    if loaded == expected:
        _verify_loaded_module_origins(ROOT)
    else:
        with pytest.raises(L23SupervisorError, match="module origin"):
            _verify_loaded_module_origins(ROOT)


def test_isolated_bootstrap_loads_repository_source_and_stops_pending_authorization() -> None:
    completed = subprocess.run(
        [
            str(ROOT / ".venv/bin/python"),
            "-I",
            str(ROOT / SUPERVISOR_BOOTSTRAP_RELATIVE),
            "--repository-root",
            ".",
            "--plan",
            str(PLAN_RELATIVE),
            "--plan-sha256",
            "b" * 64,
            "--expected-commit",
            "a" * 40,
            "--authorization-reference",
            AUTHORIZATION_PLACEHOLDER,
            "--authorization-sha256",
            "c" * 64,
        ],
        cwd=ROOT,
        env={"PATH": os.environ.get("PATH", "")},
        capture_output=True,
        check=False,
        timeout=10,
    )
    output = completed.stdout + completed.stderr
    assert completed.returncode == 1
    assert b"ModuleNotFoundError" not in output
    assert b"giclab-l2m-supervisor: stopped" in output


def test_pending_authorization_stops_before_credential_or_transport() -> None:
    credential_calls = 0

    def credential() -> str:
        nonlocal credential_calls
        credential_calls += 1
        return "dummy-canary-not-a-secret"

    authorization = SupervisorAuthorization(
        "a" * 40,
        AUTHORIZATION_PLACEHOLDER,
        "b" * 64,
    )
    with pytest.raises(L23SupervisorError, match="authorization"):
        execute_authorized_manual_observer(
            ROOT,
            plan_path=ROOT / PLAN_RELATIVE,
            plan_sha256="c" * 64,
            authorization=authorization,
            credential_provider=credential,
            transport=cast(ReadOnlyObserverTransport, object()),
        )
    assert credential_calls == 0


def test_public_metadata_expiry_stops_before_any_runtime_setup() -> None:
    latest = dt.datetime(2026, 8, 12, 5, 15, 19, 646016, tzinfo=dt.UTC)
    _validate_plan_start_time(lambda: latest)
    with pytest.raises(L23SupervisorError, match="expired"):
        _validate_plan_start_time(lambda: latest + dt.timedelta(microseconds=1))


def test_checkpoint_challenge_separates_window_metadata_from_schema_template(
    tmp_path: Path,
) -> None:
    checkpoint_root = tmp_path / "checkpoints"
    challenge_root = tmp_path / "challenges"
    checkpoint_root.mkdir(mode=0o700)
    challenge_root.mkdir(mode=0o700)
    checkpoint_handle = HeldPrivateDirectory.open(checkpoint_root)
    challenge_handle = HeldPrivateDirectory.open(challenge_root)
    binding = CheckpointBinding(
        "RUN-T07-L2M-FIXTURE-CHALLENGE",
        "l2m-decision-0123456789ab",
        "l2m-marker-0123456789ab",
    )
    contract = CheckpointContract(
        1,
        "launch_wizard_image_offered",
        "CHECKPOINT-T07-L2M-01-0123456789ab",
        "1" * 64,
    )
    ticks = 0.0

    def monotonic() -> float:
        return ticks

    def sleeper(seconds: float) -> None:
        nonlocal ticks
        ticks += seconds
        if ticks == seconds:
            destination = checkpoint_root / "01-launch_wizard_image_offered.json"
            destination.write_text("{}", encoding="utf-8")
            destination.chmod(0o600)

    try:
        _await_checkpoint(
            checkpoint_root=checkpoint_handle,
            challenge_root=challenge_handle,
            binding=binding,
            contract=contract,
            details={"launch_wizard_image_offered": True},
            private_action_parameters={"launch_forbidden": True},
            now=lambda: __import__("datetime").datetime.now(__import__("datetime").UTC),
            monotonic=monotonic,
            sleeper=sleeper,
        )
    finally:
        checkpoint_handle.close()
        challenge_handle.close()
    challenge = json.loads((challenge_root / "01-launch_wizard_image_offered.json").read_bytes())
    assert set(challenge) == {
        "schema_version",
        "challenge_not_before_utc",
        "challenge_not_after_utc",
        "checkpoint_filename",
        "private_action_parameters",
        "checkpoint_template",
    }
    template = challenge["checkpoint_template"]
    assert "challenge_not_before_utc" not in template
    assert template["checkpoint_nonce"] == "1" * 64
    assert challenge["private_action_parameters"] == {"launch_forbidden": True}


def test_checkpoint_wait_rejects_existing_or_symlink_identity(tmp_path: Path) -> None:
    checkpoint_root = tmp_path / "checkpoints"
    challenge_root = tmp_path / "challenges"
    checkpoint_root.mkdir()
    challenge_root.mkdir()
    checkpoint_root.chmod(0o700)
    challenge_root.chmod(0o700)
    checkpoint_handle = HeldPrivateDirectory.open(checkpoint_root)
    challenge_handle = HeldPrivateDirectory.open(challenge_root)
    existing = checkpoint_root / "01-launch_wizard_image_offered.json"
    existing.write_text("{}", encoding="utf-8")
    try:
        with pytest.raises(L23SupervisorError, match="already exists"):
            _await_checkpoint(
                checkpoint_root=checkpoint_handle,
                challenge_root=challenge_handle,
                binding=CheckpointBinding(
                    "RUN-T07-L2M-FIXTURE-CHALLENGE",
                    "l2m-decision-0123456789ab",
                    "l2m-marker-0123456789ab",
                ),
                contract=CheckpointContract(
                    1,
                    "launch_wizard_image_offered",
                    "CHECKPOINT-T07-L2M-01-0123456789ab",
                    "1" * 64,
                ),
                details={"launch_wizard_image_offered": True},
                now=lambda: __import__("datetime").datetime.now(__import__("datetime").UTC),
                monotonic=lambda: 0.0,
                sleeper=lambda _seconds: None,
            )
    finally:
        checkpoint_handle.close()
        challenge_handle.close()


def test_qualification_archive_wait_rejects_multiple_or_symlink(tmp_path: Path) -> None:
    tmp_path.chmod(0o700)
    inbound_root = HeldPrivateDirectory.open(tmp_path)
    success = tmp_path / "success.zip"
    failure = tmp_path / "failure.zip"
    success.write_bytes(b"success")
    failure.write_bytes(b"failure")
    try:
        with pytest.raises(L23SupervisorError, match="multiple"):
            _wait_for_qualification_archive(
                inbound_root=inbound_root,
                success_path=success,
                failure_path=failure,
                monotonic=lambda: 0.0,
                sleeper=lambda _seconds: None,
            )
        failure.unlink()
        success.unlink()
        target = tmp_path / "target.zip"
        target.write_bytes(b"fixture")
        success.symlink_to(target)
        with pytest.raises(L23SupervisorError, match="unsafe"):
            _wait_for_qualification_archive(
                inbound_root=inbound_root,
                success_path=success,
                failure_path=failure,
                monotonic=lambda: 0.0,
                sleeper=lambda _seconds: None,
            )
    finally:
        inbound_root.close()


def test_held_private_directory_rejects_parent_path_swap(tmp_path: Path) -> None:
    original = tmp_path / "held"
    moved = tmp_path / "held-moved"
    replacement = tmp_path / "replacement"
    original.mkdir(mode=0o700)
    replacement.mkdir(mode=0o700)
    held = HeldPrivateDirectory.open(original)
    try:
        original.rename(moved)
        original.symlink_to(replacement, target_is_directory=True)
        with pytest.raises(L23SupervisorError, match="identity changed"):
            held.verify()
    finally:
        held.close()


def test_hash_first_argv_is_privately_completed_without_shell() -> None:
    template = [
        "/usr/bin/python3",
        "-I",
        "<PRIVATE-DECISION-ALIAS>",
        "<PRIVATE-MARKER-ALIAS>",
        "<PRIVATE-INSTANCE-BINDING-SHA256>",
        "<FRESH-AUTHORIZATION-REFERENCE>",
        "<FRESH-AUTHORIZATION-SHA256>",
    ]
    preflight = SupervisorPreflight(
        {"qualification_bootstrap_argv": template},
        "0" * 64,
        cast(object, None),
        {},
    )
    engine = SimpleNamespace(
        instance_binding_sha256="3" * 64,
        run_id="RUN-T07-L2M-FIXTURE-ARGV",
        authorization_reference="AUTH-T07-L2M-FIXTURE-ARGV",
        authorization_sha256="4" * 64,
        checkpoint_reader=SimpleNamespace(
            binding=CheckpointBinding(
                "RUN-T07-L2M-FIXTURE-ARGV",
                "l2m-decision-0123456789ab",
                "l2m-marker-0123456789ab",
            )
        ),
    )
    rendered = _concrete_qualification_argv(preflight, cast(object, engine))
    assert rendered[:2] == ["/usr/bin/python3", "-I"]
    assert not any("<" in value or ">" in value for value in rendered)
    assert "AUTH-T07-L2M-FIXTURE-ARGV" in rendered
    assert all(" " not in value for value in rendered)


def test_private_directory_creation_rejects_symlink_parent(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    outside = tmp_path / "outside"
    repository.mkdir()
    outside.mkdir()
    (repository / "artifacts").symlink_to(outside, target_is_directory=True)
    with pytest.raises(L23SupervisorError, match="could not be created"):
        _create_private_directory(repository, repository / "artifacts/t07/private")


@pytest.mark.parametrize(
    ("states", "expected_calls"),
    [
        ([InstanceMatchState.MULTIPLE], 1),
        ([InstanceMatchState.DRIFT], 1),
        ([InstanceMatchState.ZERO] * 9, 9),
    ],
)
def test_wrapper_never_retries_ambiguous_or_final_zero_instance_binding(
    states: list[InstanceMatchState],
    expected_calls: int,
) -> None:
    engine = SimpleNamespace(observations=0, binds=0)
    pending = list(states)

    def observe(*_args: object, **_kwargs: object) -> object:
        engine.observations += 1
        return object()

    def assess(_candidate: object, *, zero_is_terminal: bool) -> object:
        state = pending.pop(0)
        if state is InstanceMatchState.ZERO and not pending:
            assert zero_is_terminal
        return SimpleNamespace(state=state)

    def bind(_candidate: object) -> str:
        engine.binds += 1
        return "d" * 64

    engine.observe = observe
    engine.assess_instance_binding_observation = assess
    engine.bind_exact_instance_observation = bind
    with pytest.raises(L23SupervisorError, match="entered incident"):
        _bind_exact_launch_instance(engine, credential="dummy-canary-not-a-secret")
    assert engine.observations == expected_calls
    assert engine.binds == 0


def test_wrapper_polls_only_transient_zero_then_binds_exactly_once() -> None:
    states = [
        InstanceMatchState.ZERO,
        InstanceMatchState.ZERO,
        InstanceMatchState.EXACT_ONE,
    ]
    engine = SimpleNamespace(observations=0, binds=0)

    def observe(operation: object, *, phase: object, credential: str) -> object:
        assert phase is ObserverPhase.INSTANCE_BIND
        assert credential == "dummy-canary-not-a-secret"
        engine.observations += 1
        return object()

    def assess(_candidate: object, *, zero_is_terminal: bool) -> object:
        assert zero_is_terminal is False
        return SimpleNamespace(state=states.pop(0))

    def bind(_candidate: object) -> str:
        engine.binds += 1
        return "d" * 64

    engine.observe = observe
    engine.assess_instance_binding_observation = assess
    engine.bind_exact_instance_observation = bind
    assert _bind_exact_launch_instance(engine, credential="dummy-canary-not-a-secret") == "d" * 64
    assert engine.observations == 3
    assert engine.binds == 1
