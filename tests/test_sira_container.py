from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import time
from copy import deepcopy
from dataclasses import replace
from pathlib import Path, PurePosixPath
from types import ModuleType
from typing import Any

import pytest

from giclab.harness.sira_container import (
    BASE_IMAGE_AMD64_MANIFEST_DIGEST,
    BASE_IMAGE_ARM64_MANIFEST_DIGEST,
    BASE_IMAGE_INDEX_DIGEST,
    BASE_IMAGE_REFERENCE,
    CHROMIUM_REVISION,
    CONTAINER_ATTEMPT_TARGET,
    CONTAINER_CONFIGURATION_TARGET,
    CONTAINER_SECRET_TARGET,
    MAX_DOCKER_LIFECYCLE_OPERATIONS_PER_ATTEMPT,
    PLAYWRIGHT_VERSION,
    UPSTREAM_UV_LOCK_SHA256,
    ApprovedReadOnlyInput,
    AttemptRootContract,
    BindMount,
    BoundedMaterializationExecutor,
    CommandResult,
    ContainerAttemptIdentity,
    ContainerAttemptSpec,
    ContainerBuildContract,
    ContainerContractError,
    ContainerFixture,
    ContainerImageProvenance,
    ContainerLifecycleError,
    ContainerPlatform,
    ContainerRuntimeOptions,
    DockerAttemptExecutor,
    DockerCommandRenderer,
    ImmutableImageReference,
    LifecycleState,
    LocalImageIdentity,
    MaterializationAction,
    MaterializationPlan,
    MountPurpose,
    PlatformCompatibility,
    PlatformDecision,
    SubprocessMaterializationCommandRunner,
    WaitResult,
    assemble_image_provenance,
    assert_dummy_secret_absent,
    browser_preflight_limits,
    capture_local_image_identity,
    fixture_attempt_spec,
    load_local_image_identity,
    load_materialization_plan,
    synthetic_limits,
    validate_container_attempt,
    verify_exact_file,
    write_dummy_secret_file,
)
from giclab.harness.sira_container import (
    main as sira_container_main,
)
from giclab.harness.sira_gate_a import SIRA_UPSTREAM_COMMIT
from giclab.validation import ROOT, validate_instance

BASELINE_COMMIT = "38e27ef20637471325ec15be216b4274bed5be49"
IMAGE_ID = "sha256:" + "a" * 64
CONTAINER_ID = "b" * 64
ATTEMPT_UUID = "c" * 32
DOCKER = Path("/Applications/Docker.app/Contents/Resources/bin/docker")


def _identity(*, attempt_uuid: str = ATTEMPT_UUID) -> ContainerAttemptIdentity:
    return ContainerAttemptIdentity(
        experiment_id="EXP-0001",
        profile_plan_id="PLAN-EXP0001-SMOKE",
        condition="SIRA-REACTIVE",
        attempt=1,
        attempt_uuid=attempt_uuid,
        repository_commit=BASELINE_COMMIT,
        source_commit=SIRA_UPSTREAM_COMMIT,
        authorization_reference="AUTH-T07-GATE-B2-SYNTHETIC",
    )


def _root(tmp_path: Path, *, name: str = "attempt-c") -> AttemptRootContract:
    owned = tmp_path / "owned"
    owned.mkdir(exist_ok=True)
    owned.chmod(0o700)
    return AttemptRootContract(owned_base=owned, attempt_root=owned / name)


def _spec(root: AttemptRootContract, **changes: Any) -> ContainerAttemptSpec:
    default: dict[str, Any] = {
        "identity": _identity(),
        "image": ImmutableImageReference(IMAGE_ID),
        "platform": ContainerPlatform.LINUX_ARM64,
        "fixture": ContainerFixture.ADVERSARIAL_CONTAINMENT,
        "resources": synthetic_limits(),
        "mounts": (
            BindMount(
                source=root.attempt_root,
                target=CONTAINER_ATTEMPT_TARGET,
                purpose=MountPurpose.ATTEMPT_ROOT,
                read_only=False,
            ),
        ),
        "command": (
            "/opt/sira/.venv/bin/python",
            "/opt/giclab/fixtures/adversarial_containment.py",
        ),
        "ready_artifact": "adversarial-reparented.json",
    }
    default.update(changes)
    return ContainerAttemptSpec(**default)


def _inspect(spec: ContainerAttemptSpec, state: str, exit_code: int = 0) -> str:
    resources = spec.resources
    value = [
        {
            "Id": CONTAINER_ID,
            "Name": "/" + spec.identity.container_name,
            "Image": spec.image.value,
            "State": {"Status": state, "ExitCode": exit_code},
            "Config": {
                "Labels": dict(spec.identity.labels(spec.image.digest)),
                "Env": [
                    "PATH=/usr/local/bin:/usr/bin:/bin",
                    *(f"{name}={value}" for name, value in spec.runtime.environment),
                ],
                "Cmd": list(spec.command),
                "User": spec.runtime.user,
            },
            "HostConfig": {
                "Privileged": False,
                "NetworkMode": "none",
                "PidMode": "",
                "CgroupnsMode": "private",
                "IpcMode": "private",
                "RestartPolicy": {"Name": "no"},
                "ReadonlyRootfs": True,
                "CapDrop": ["ALL"],
                "CapAdd": None,
                "SecurityOpt": ["no-new-privileges=true"],
                "PidsLimit": resources.pids,
                "Memory": resources.memory_bytes,
                "MemorySwap": resources.memory_bytes,
                "NanoCpus": resources.cpu_millis * 1_000_000,
                "ShmSize": resources.shm_bytes,
                "Init": True,
                "AutoRemove": False,
                "Tmpfs": {
                    "/tmp": (
                        f"rw,noexec,nosuid,nodev,size={resources.tmpfs_bytes},"
                        f"mode=1777,uid={spec.runtime.user.split(':', 1)[0]},"
                        f"gid={spec.runtime.user.split(':', 1)[1]}"
                    ),
                    "/run/secrets": (
                        f"rw,noexec,nosuid,nodev,size={resources.tmpfs_bytes},"
                        f"mode=0700,uid={spec.runtime.user.split(':', 1)[0]},"
                        f"gid={spec.runtime.user.split(':', 1)[1]}"
                    ),
                },
                "LogConfig": {
                    "Type": "local",
                    "Config": {
                        "max-size": f"{resources.log_output_bytes // 1024**2}m",
                        "max-file": "1",
                    },
                },
            },
            "Mounts": [
                {
                    "Type": "bind",
                    "Source": str(mount.source),
                    "Destination": str(mount.target),
                    "RW": not mount.read_only,
                }
                for mount in spec.mounts
            ],
        }
    ]
    return json.dumps(value)


class FakeDockerRunner:
    def __init__(
        self,
        spec: ContainerAttemptSpec,
        *,
        wait_mode: str = "complete",
        stop_fails: bool = False,
        logs: str = "synthetic fixture log\n",
    ) -> None:
        self.spec = spec
        self.wait_mode = wait_mode
        self.stop_fails = stop_fails
        self.logs = logs
        self.state = "created"
        self.exit_code = 0
        self.calls: list[tuple[str, ...]] = []
        self.wait_wall_seconds: list[float] = []

    def _write_ready_record(self) -> None:
        attempt_mount = next(
            mount for mount in self.spec.mounts if mount.purpose is MountPurpose.ATTEMPT_ROOT
        )
        common = {
            "schema_version": "0.1.0",
            "runtime_uid": int(self.spec.runtime.user.split(":", 1)[0]),
            "runtime_gid": int(self.spec.runtime.user.split(":", 1)[1]),
        }
        if self.spec.fixture is ContainerFixture.ADVERSARIAL_CONTAINMENT:
            record = {
                **common,
                "role": "reparented-session-spawner",
                "spawned_before_limit": 60,
                "term_ignored": True,
            }
        elif self.spec.fixture is ContainerFixture.BROWSER_PREFLIGHT:
            record = {
                **common,
                "source": "local-static-file",
                "page_uri": "file:///opt/giclab/fixtures/static.html",
                "browser_actions": 1,
                "screenshot_captures": 1,
                "browser_closed": True,
                "playwright_version": PLAYWRIGHT_VERSION,
                "chromium_revision": CHROMIUM_REVISION,
                "installed_package_manifest_sha256": "1" * 64,
                "chromium_executable_sha256": "2" * 64,
            }
        else:
            record = {
                **common,
                "required_secret_name": "SIRA_API_KEY",
                "required_secret_present": True,
                "forbidden_fallback_present": False,
            }
        (attempt_mount.source / self.spec.ready_artifact).write_text(
            json.dumps(record),
            encoding="utf-8",
        )

    def run(self, argv: Any, *, timeout_seconds: int) -> CommandResult:
        del timeout_seconds
        args = tuple(argv)
        self.calls.append(args)
        operation = args[2] if len(args) > 2 else args[1]
        if operation == "create":
            return CommandResult(args, 0, CONTAINER_ID + "\n")
        if operation == "inspect":
            return CommandResult(args, 0, _inspect(self.spec, self.state, self.exit_code))
        if operation == "start":
            self.state = "running"
            self._write_ready_record()
            return CommandResult(args, 0, CONTAINER_ID + "\n")
        if operation == "top":
            return CommandResult(
                args,
                0,
                "PID PPID PGID SID STAT COMMAND ARGS\n1 0 1 1 Ss python fixture\n",
            )
        if operation == "stop":
            if self.stop_fails:
                return CommandResult(args, 1, stderr="synthetic stop failure")
            self.state = "exited"
            self.exit_code = 143
            return CommandResult(args, 0, CONTAINER_ID + "\n")
        if operation == "kill":
            self.state = "dead"
            self.exit_code = 137
            return CommandResult(args, 0, CONTAINER_ID + "\n")
        if operation == "wait":
            return CommandResult(args, 0, f"{self.exit_code}\n")
        if operation == "logs":
            return CommandResult(args, 0, self.logs)
        if operation == "rm":
            self.state = "removed"
            return CommandResult(args, 0, CONTAINER_ID + "\n")
        if operation == "ls":
            return CommandResult(args, 0, "")
        raise AssertionError(f"unexpected fake runtime argv: {args}")

    def wait(
        self,
        argv: Any,
        *,
        wall_seconds: float,
        output_root: Path,
        output_limit_bytes: int,
        ready_path: Path,
    ) -> WaitResult:
        del output_root, ready_path
        args = tuple(argv)
        self.calls.append(args)
        self.wait_wall_seconds.append(wall_seconds)
        if self.wait_mode == "complete":
            return WaitResult(None, True, False, False, 0)
        if self.wait_mode == "timeout":
            return WaitResult(None, False, True, False, 0)
        if self.wait_mode == "output":
            return WaitResult(None, False, False, True, output_limit_bytes + 1)
        raise AssertionError("unknown fake wait mode")


class FakeImageRunner:
    def __init__(self, document: object) -> None:
        self.document = document
        self.calls: list[tuple[str, ...]] = []

    def run(self, argv: Any, *, timeout_seconds: int) -> CommandResult:
        del timeout_seconds
        args = tuple(argv)
        self.calls.append(args)
        return CommandResult(args, 0, json.dumps(self.document))

    def wait(self, *_args: Any, **_kwargs: Any) -> WaitResult:
        raise AssertionError("image inspection must not wait on a container")


def test_missing_or_floating_image_digest_is_rejected() -> None:
    with pytest.raises(ContainerContractError, match="repository@sha256"):
        ImmutableImageReference("mcr.microsoft.com/playwright/python:v1.39.0-jammy")
    assert ImmutableImageReference(BASE_IMAGE_REFERENCE).digest == BASE_IMAGE_INDEX_DIGEST


def _materialization_plan(
    actions: tuple[MaterializationAction, ...],
) -> MaterializationPlan:
    return MaterializationPlan(
        plan_id="PLAN-T07-GATE-B2-MATERIALIZATION",
        authorization_reference="AUTH-T07-GATE-B2-2026-08-08",
        aggregate_wall_seconds=3_600,
        aggregate_output_bytes=16 * 1024**2,
        transfer_reservation_bytes=2 * 1024**3,
        incremental_disk_limit_bytes=12 * 1024**3,
        actions=actions,
    )


class FakeMaterializationRunner:
    def __init__(self) -> None:
        self.calls: list[tuple[str, ...]] = []
        self.deadlines: list[float] = []
        self.output_limits: list[int] = []

    def run(
        self,
        argv: Any,
        *,
        deadline: float,
        output_limit_bytes: int,
    ) -> CommandResult:
        args = tuple(argv)
        self.calls.append(args)
        self.deadlines.append(deadline)
        self.output_limits.append(output_limit_bytes)
        return CommandResult(args, 0, "")


def test_historical_materialization_plan_is_preserved_but_non_executable() -> None:
    path = (ROOT / "containers/sira-smoke/materialization-plan.json").resolve(strict=True)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(ContainerContractError, match="superseded and non-executable"):
        load_materialization_plan(path, expected_sha256=digest)

    with pytest.raises(ContainerContractError, match="hash does not match"):
        load_materialization_plan(path, expected_sha256="0" * 64)


def test_historical_materialization_executor_is_disabled(
    tmp_path: Path,
) -> None:
    actions = (
        MaterializationAction("first-action", ("/bin/test", "-e", "/bin/test"), 60, ""),
        MaterializationAction("second-action", ("/bin/test", "-e", "/bin/test"), 60, ""),
    )
    runner = FakeMaterializationRunner()
    with pytest.raises(ContainerContractError, match="superseded and non-executable"):
        BoundedMaterializationExecutor(runner=runner).execute(
            _materialization_plan(actions), ledger_path=tmp_path / "ledger.json"
        )
    assert runner.calls == []


@pytest.mark.parametrize(
    "argv",
    [
        (
            "capture-image-identity",
            "--repository-root",
            str(ROOT),
            "--runtime",
            "/Applications/Docker.app/Contents/Resources/bin/docker",
            "--local-tag",
            "giclab/sira-smoke:stale",
            "--output",
            "/tmp/stale-image.json",
        ),
        (
            "execute-fixture",
            "--repository-root",
            str(ROOT),
            "--runtime",
            "/Applications/Docker.app/Contents/Resources/bin/docker",
            "--image-identity",
            "/tmp/stale-image.json",
            "--owned-base",
            "/tmp/stale-owned",
            "--repository-commit",
            "a" * 40,
            "--attempt-uuid",
            "b" * 32,
            "--authorization-reference",
            "AUTH-T07-GATE-B2-STALE",
            "--fixture",
            "adversarial-containment",
        ),
    ],
)
def test_b2b_image_and_fixture_cli_paths_are_disabled(argv: tuple[str, ...]) -> None:
    with pytest.raises(ContainerContractError, match="B2b is undesigned and unauthorized"):
        sira_container_main(argv)


def test_materialization_streaming_runner_stops_at_output_cap() -> None:
    runner = SubprocessMaterializationCommandRunner()
    with pytest.raises(ContainerLifecycleError, match="output cap"):
        runner.run(
            ("/usr/bin/python3", "-c", "print('x' * 4096)"),
            deadline=time.monotonic() + 5,
            output_limit_bytes=128,
        )


def test_exact_file_verifier_fails_closed_on_same_size_digest_drift(tmp_path: Path) -> None:
    artifact = (tmp_path / "artifact.bin").resolve()
    artifact.write_bytes(b"abcd")
    verify_exact_file(
        artifact,
        expected_bytes=4,
        expected_sha256=hashlib.sha256(b"abcd").hexdigest(),
    )
    with pytest.raises(ContainerContractError, match="size or SHA-256"):
        verify_exact_file(
            artifact,
            expected_bytes=4,
            expected_sha256=hashlib.sha256(b"wxyz").hexdigest(),
        )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("privileged", True, "privileged"),
        ("pid_mode", "host", "PID namespace"),
        ("cgroupns_mode", "host", "cgroup namespace"),
        ("network_mode", "host", "networking"),
        ("ipc_mode", "host", "IPC namespace"),
        ("cap_drop", (), "capabilities"),
        ("cap_add", ("SYS_ADMIN",), "capabilities"),
        ("no_new_privileges", False, "no-new-privileges"),
        ("init", False, "init process"),
        ("read_only_root", False, "read-only"),
        ("restart_policy", "always", "restart policy"),
        ("pull_policy", "missing", "never pull"),
        ("user", "0:0", "non-root"),
        ("environment", (("OPENAI_API_KEY", "forbidden"),), "environment"),
    ],
)
def test_unsafe_runtime_policy_is_rejected(
    tmp_path: Path,
    field: str,
    value: object,
    message: str,
) -> None:
    root = _root(tmp_path)
    options = replace(ContainerRuntimeOptions(), **{field: value})
    with pytest.raises(ContainerContractError, match=message):
        validate_container_attempt(_spec(root, runtime=options), root, repository_root=ROOT)


@pytest.mark.parametrize(
    "field",
    (
        "cpu_millis",
        "memory_bytes",
        "pids",
        "wall_seconds",
        "output_bytes",
        "shm_bytes",
        "tmpfs_bytes",
        "stop_grace_seconds",
    ),
)
def test_every_finite_resource_limit_is_required(tmp_path: Path, field: str) -> None:
    root = _root(tmp_path)
    limits = replace(synthetic_limits(), **{field: None})
    with pytest.raises(ContainerContractError, match=field):
        validate_container_attempt(_spec(root, resources=limits), root, repository_root=ROOT)


def test_output_limit_must_render_to_an_exact_supported_docker_log_unit(
    tmp_path: Path,
) -> None:
    root = _root(tmp_path)
    resources = replace(_spec(root).resources, output_bytes=1024 * 1024 + 1)
    with pytest.raises(ContainerContractError, match="exact Docker log allocation"):
        validate_container_attempt(
            _spec(root, resources=resources),
            root,
            repository_root=ROOT,
        )


def test_pre_readiness_control_timeout_never_rounds_past_wall_deadline(
    tmp_path: Path,
) -> None:
    root = _root(tmp_path)
    spec = _spec(root, resources=replace(synthetic_limits(), wall_seconds=1))
    runner = FakeDockerRunner(spec)
    observed_timeouts: list[float] = []
    original_run = runner.run

    def recording_run(argv: Any, *, timeout_seconds: float) -> CommandResult:
        observed_timeouts.append(timeout_seconds)
        return original_run(argv, timeout_seconds=timeout_seconds)

    runner.run = recording_run  # type: ignore[method-assign]
    clock_values = iter((0.0, 0.75, 1.01))
    executor = DockerAttemptExecutor(
        renderer=DockerCommandRenderer(DOCKER),
        runner=runner,
        clock=lambda: next(clock_values),
    )
    with pytest.raises(ContainerLifecycleError, match="wall limit expired"):
        executor.execute(spec, root, repository_root=ROOT)
    assert observed_timeouts[0] == pytest.approx(0.25)


def test_host_mount_expansion_is_rejected(tmp_path: Path) -> None:
    root = _root(tmp_path)
    expanded = (
        *_spec(root).mounts,
        BindMount(
            source=ROOT,
            target=PurePosixPath("/giclab/repository"),
            purpose=MountPurpose.CONFIGURATION_INPUT,
            read_only=True,
        ),
    )
    with pytest.raises(ContainerContractError, match="broad host mounts"):
        validate_container_attempt(_spec(root, mounts=expanded), root, repository_root=ROOT)


def test_host_mount_ancestor_expansion_is_rejected(tmp_path: Path) -> None:
    root = _root(tmp_path)
    repository_parent = ROOT.parent
    expanded = (
        *_spec(root).mounts,
        BindMount(
            source=repository_parent,
            target=PurePosixPath("/opt/giclab/configuration"),
            purpose=MountPurpose.CONFIGURATION_INPUT,
            read_only=True,
        ),
    )
    with pytest.raises(ContainerContractError, match="broad host mounts"):
        validate_container_attempt(_spec(root, mounts=expanded), root, repository_root=ROOT)


@pytest.mark.parametrize("host_directory", (Path("/private/etc"), Path("/private/var")))
def test_arbitrary_host_directories_are_rejected_even_as_read_only_configuration(
    tmp_path: Path,
    host_directory: Path,
) -> None:
    root = _root(tmp_path)
    canonical = host_directory.resolve(strict=True)
    mount = BindMount(
        source=canonical,
        target=CONTAINER_CONFIGURATION_TARGET,
        purpose=MountPurpose.CONFIGURATION_INPUT,
        read_only=True,
    )
    with pytest.raises(ContainerContractError, match="exact regular files"):
        validate_container_attempt(
            _spec(root, mounts=(*_spec(root).mounts, mount)),
            root,
            repository_root=ROOT,
        )


def test_configuration_file_requires_and_matches_external_exact_allowlist(
    tmp_path: Path,
) -> None:
    root = _root(tmp_path)
    configuration = (
        ROOT
        / "experiments"
        / "EXP-0001-sira-simulative-vs-reactive"
        / "run-plans"
        / "conditions"
        / "smoke-reactive.yaml"
    ).resolve(strict=True)
    mount = BindMount(
        source=configuration,
        target=CONTAINER_CONFIGURATION_TARGET,
        purpose=MountPurpose.CONFIGURATION_INPUT,
        read_only=True,
    )
    spec = _spec(root, mounts=(*_spec(root).mounts, mount))
    with pytest.raises(ContainerContractError, match="exact approved-file allowlist"):
        validate_container_attempt(spec, root, repository_root=ROOT)

    validate_container_attempt(
        spec,
        root,
        repository_root=ROOT,
        approved_read_only_inputs=(
            ApprovedReadOnlyInput(
                source=configuration,
                target=CONTAINER_CONFIGURATION_TARGET,
                purpose=MountPurpose.CONFIGURATION_INPUT,
            ),
        ),
    )


def test_second_writable_host_mount_is_rejected(tmp_path: Path) -> None:
    root = _root(tmp_path)
    extra = tmp_path / "extra"
    extra.mkdir()
    mounts = (
        *_spec(root).mounts,
        BindMount(
            source=extra.resolve(),
            target=PurePosixPath("/giclab/extra"),
            purpose=MountPurpose.CONFIGURATION_INPUT,
            read_only=False,
        ),
    )
    with pytest.raises(ContainerContractError, match="only the attempt root"):
        validate_container_attempt(_spec(root, mounts=mounts), root, repository_root=ROOT)


@pytest.mark.parametrize(
    "socket_path",
    (Path("/var/run/docker.sock"), Path("/run/user/501/podman/podman.sock")),
)
def test_container_runtime_socket_mount_is_rejected(tmp_path: Path, socket_path: Path) -> None:
    root = _root(tmp_path)
    mounts = (
        *_spec(root).mounts,
        BindMount(
            source=socket_path.resolve(strict=False),
            target=PurePosixPath("/run/forbidden.sock"),
            purpose=MountPurpose.CONFIGURATION_INPUT,
            read_only=True,
        ),
    )
    with pytest.raises(ContainerContractError, match="socket mounts"):
        validate_container_attempt(_spec(root, mounts=mounts), root, repository_root=ROOT)


def test_secret_mount_is_rejected_for_non_secret_fixture(tmp_path: Path) -> None:
    root = _root(tmp_path)
    canary_path = tmp_path / "dummy-secret"
    canary_path.write_text("public-test-data\n", encoding="utf-8")
    canary_path.chmod(0o600)
    mounts = (
        *_spec(root).mounts,
        BindMount(
            source=canary_path.resolve(),
            target=CONTAINER_SECRET_TARGET,
            purpose=MountPurpose.SECRET_FILE,
            read_only=True,
        ),
    )
    with pytest.raises(ContainerContractError, match="forbidden for non-secret"):
        validate_container_attempt(_spec(root, mounts=mounts), root, repository_root=ROOT)


def test_exact_create_and_lifecycle_argument_arrays(tmp_path: Path) -> None:
    root = _root(tmp_path)
    spec = _spec(root)
    renderer = DockerCommandRenderer(DOCKER)
    create = renderer.create(spec)
    assert create[:3] == (str(DOCKER), "container", "create")
    for sequence in (
        ("--platform", "linux/arm64"),
        ("--pull", "never"),
        ("--network", "none"),
        ("--cgroupns", "private"),
        ("--ipc", "private"),
        ("--restart", "no"),
        ("--cap-drop", "ALL"),
        ("--security-opt", "no-new-privileges=true"),
        ("--pids-limit", "64"),
        ("--memory", str(512 * 1024**2)),
        ("--memory-swap", str(512 * 1024**2)),
        ("--cpus", "1.000"),
        ("--read-only", "--user"),
    ):
        left, right = sequence
        index = create.index(left)
        assert create[index + 1] == right
    assert "--privileged" not in create
    assert "--pid" not in create
    assert "--cap-add" not in create
    assert "SIRA_API_KEY" not in create and "OPENAI_API_KEY" not in create
    assert create[create.index("--env") + 1] == "HOME=/tmp"
    assert create[create.index("--log-opt") + 1] == "max-size=2m"
    assert create[-len(spec.command) :] == spec.command
    assert renderer.start(CONTAINER_ID) == (str(DOCKER), "container", "start", CONTAINER_ID)
    assert renderer.stop(CONTAINER_ID, 1)[2:5] == ("stop", "--time", "1")
    assert renderer.kill(CONTAINER_ID)[2:5] == ("kill", "--signal", "KILL")
    assert renderer.remove(CONTAINER_ID) == (str(DOCKER), "container", "rm", CONTAINER_ID)


def test_attempt_root_must_be_fresh_owned_and_direct(tmp_path: Path) -> None:
    root = _root(tmp_path)
    root.allocate()
    assert root.attempt_root.is_dir()
    assert root.attempt_root.stat().st_mode & 0o077 == 0
    with pytest.raises(ContainerContractError, match="must not already exist"):
        root.validate_planned()
    nested = AttemptRootContract(root.owned_base, root.owned_base / "nested" / "attempt")
    with pytest.raises(ContainerContractError, match="direct immutable child"):
        nested.validate_planned()


def test_attempt_owned_base_rejects_broad_permissions(tmp_path: Path) -> None:
    root = _root(tmp_path)
    root.owned_base.chmod(0o755)
    with pytest.raises(ContainerContractError, match="exact mode 0700"):
        root.validate_planned()


def test_runtime_user_matches_host_owned_bind_and_secret_permissions(tmp_path: Path) -> None:
    root = _root(tmp_path)
    assert _spec(root).runtime.user == f"{os.getuid()}:{os.getgid()}"
    canary_path = tmp_path / "dummy-secret-permissions"
    canary_path.write_text("public-test-data\n", encoding="utf-8")
    canary_path.chmod(0o644)
    mounts = (
        *_spec(root).mounts,
        BindMount(
            source=canary_path.resolve(),
            target=CONTAINER_SECRET_TARGET,
            purpose=MountPurpose.SECRET_FILE,
            read_only=True,
        ),
    )
    with pytest.raises(ContainerContractError, match="mode 0600"):
        validate_container_attempt(
            _spec(
                root,
                fixture=ContainerFixture.DUMMY_SECRET_PREFLIGHT,
                mounts=mounts,
            ),
            root,
            repository_root=ROOT,
        )


def test_secret_parent_rejects_broad_permissions(tmp_path: Path) -> None:
    root = _root(tmp_path)
    secret_parent = tmp_path / "broad-secret-parent"
    secret_parent.mkdir(mode=0o755)
    secret_parent.chmod(0o755)
    canary_path = secret_parent / "dummy-input"
    canary_path.write_text("public-test-data\n", encoding="utf-8")
    canary_path.chmod(0o600)
    mounts = (
        *_spec(root).mounts,
        BindMount(
            source=canary_path.resolve(),
            target=CONTAINER_SECRET_TARGET,
            purpose=MountPurpose.SECRET_FILE,
            read_only=True,
        ),
    )
    with pytest.raises(ContainerContractError, match=r"secret parent.*0700"):
        validate_container_attempt(
            _spec(
                root,
                fixture=ContainerFixture.DUMMY_SECRET_PREFLIGHT,
                mounts=mounts,
            ),
            root,
            repository_root=ROOT,
        )


def test_lifecycle_evidence_is_captured_before_removal_and_cleanup_sealed(
    tmp_path: Path,
) -> None:
    root = _root(tmp_path)
    spec = _spec(root)
    runner = FakeDockerRunner(spec)
    evidence = DockerAttemptExecutor(
        renderer=DockerCommandRenderer(DOCKER),
        runner=runner,
    ).execute(spec, root, repository_root=ROOT)
    assert evidence.sealed
    assert evidence.states == (
        LifecycleState.PLANNED,
        LifecycleState.CREATED,
        LifecycleState.STARTED,
        LifecycleState.PROCESS_EVIDENCE_CAPTURED,
        LifecycleState.STOP_REQUESTED,
        LifecycleState.TERMINAL_VERIFIED,
        LifecycleState.EVIDENCE_CAPTURED,
        LifecycleState.REMOVED,
        LifecycleState.CLEANUP_VERIFIED,
        LifecycleState.SEALED,
    )
    assert evidence.fixture_ready
    assert evidence.probe_succeeded
    assert len(runner.calls) <= MAX_DOCKER_LIFECYCLE_OPERATIONS_PER_ATTEMPT
    assert evidence.retained_output_bytes <= spec.resources.output_bytes  # type: ignore[operator]
    operations = [call[2] if len(call) > 2 else call[1] for call in runner.calls]
    assert operations.index("logs") < operations.index("rm")
    assert operations.index("inspect") < operations.index("rm")
    assert (root.attempt_root / "container-evidence-before-removal.json").is_file()
    assert (root.attempt_root / "container-cleanup-seal.json").is_file()
    assert (
        validate_instance(evidence.document(), ROOT / "schemas/container-attempt.schema.json") == []
    )


@pytest.mark.parametrize(
    "mutation",
    (
        "reordered",
        "kill-without-state",
        "retained-over-cap",
        "observed-below-retained",
        "unflagged-observed-over-cap",
        "false-success",
    ),
)
def test_attempt_schema_rejects_contradictory_lifecycle_and_quota_evidence(
    tmp_path: Path,
    mutation: str,
) -> None:
    root = _root(tmp_path)
    spec = _spec(root)
    evidence = DockerAttemptExecutor(
        renderer=DockerCommandRenderer(DOCKER),
        runner=FakeDockerRunner(spec),
    ).execute(spec, root, repository_root=ROOT)
    document = deepcopy(evidence.document())
    resources = document["resource_limits"]
    assert isinstance(resources, dict)
    if mutation == "reordered":
        states = document["lifecycle_states"]
        assert isinstance(states, list)
        states[0], states[1] = states[1], states[0]
    elif mutation == "kill-without-state":
        document["kill_sent"] = True
    elif mutation == "retained-over-cap":
        document["retained_output_bytes"] = resources["output_bytes"] + 1
    elif mutation == "observed-below-retained":
        document["observed_output_bytes"] = document["retained_output_bytes"] - 1
    elif mutation == "unflagged-observed-over-cap":
        document["output_limit_exceeded"] = False
        document["observed_output_bytes"] = resources["output_bytes"] + 1
    else:
        document["probe_succeeded"] = False
    assert validate_instance(document, ROOT / "schemas/container-attempt.schema.json")


def test_failed_stop_escalates_to_kill_for_the_container_boundary(tmp_path: Path) -> None:
    root = _root(tmp_path)
    spec = _spec(root)
    runner = FakeDockerRunner(spec, wait_mode="timeout", stop_fails=True)
    evidence = DockerAttemptExecutor(
        renderer=DockerCommandRenderer(DOCKER),
        runner=runner,
    ).execute(spec, root, repository_root=ROOT)
    assert evidence.wall_timed_out
    assert evidence.stop_sent
    assert evidence.kill_sent
    assert evidence.terminal_state == "dead"
    operations = [call[2] if len(call) > 2 else call[1] for call in runner.calls]
    assert operations.index("stop") < operations.index("kill") < operations.index("rm")


def test_output_quota_breach_stops_the_whole_container_boundary(tmp_path: Path) -> None:
    root = _root(tmp_path)
    spec = _spec(root)
    runner = FakeDockerRunner(spec, wait_mode="output")
    evidence = DockerAttemptExecutor(
        renderer=DockerCommandRenderer(DOCKER),
        runner=runner,
    ).execute(spec, root, repository_root=ROOT)
    assert evidence.output_limit_exceeded
    assert evidence.observed_output_bytes >= spec.resources.payload_output_bytes + 1
    assert evidence.retained_output_bytes <= spec.resources.output_bytes  # type: ignore[operator]
    assert evidence.stop_sent
    assert not evidence.probe_succeeded
    assert not evidence.kill_sent


def test_pre_wait_lifecycle_time_is_deducted_from_the_wall_budget(tmp_path: Path) -> None:
    root = _root(tmp_path)
    spec = _spec(root)
    runner = FakeDockerRunner(spec)
    observed_times = iter((100.0, 102.0, 104.0, 106.0, 108.0))
    evidence = DockerAttemptExecutor(
        renderer=DockerCommandRenderer(DOCKER),
        runner=runner,
        clock=lambda: next(observed_times),
    ).execute(spec, root, repository_root=ROOT)
    assert evidence.probe_succeeded
    assert runner.wait_wall_seconds == [22.0]


def test_log_capture_is_bounded_inside_the_retained_output_cap(tmp_path: Path) -> None:
    root = _root(tmp_path)
    spec = _spec(root)
    runner = FakeDockerRunner(spec, logs="L" * (spec.resources.log_output_bytes + 1))
    evidence = DockerAttemptExecutor(
        renderer=DockerCommandRenderer(DOCKER),
        runner=runner,
    ).execute(spec, root, repository_root=ROOT)
    assert evidence.output_limit_exceeded
    assert not evidence.evidence_complete
    assert not evidence.probe_succeeded
    assert evidence.retained_output_bytes <= spec.resources.output_bytes  # type: ignore[operator]
    assert sum(path.stat().st_size for path in root.attempt_root.rglob("*") if path.is_file()) == (
        evidence.retained_output_bytes
    )


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("PidMode", "host"),
        ("CgroupnsMode", "host"),
        ("MemorySwap", 0),
    ),
)
def test_runtime_inspect_cannot_silently_drop_containment_limits(
    tmp_path: Path,
    field: str,
    value: object,
) -> None:
    root = _root(tmp_path)
    spec = _spec(root)
    runner = FakeDockerRunner(spec)
    original_run = runner.run

    def drifted_inspect(argv: Any, *, timeout_seconds: int) -> CommandResult:
        result = original_run(argv, timeout_seconds=timeout_seconds)
        args = tuple(argv)
        if len(args) > 2 and args[2] == "inspect":
            document = json.loads(result.stdout)
            document[0]["HostConfig"][field] = value
            return CommandResult(args, 0, json.dumps(document))
        return result

    runner.run = drifted_inspect  # type: ignore[method-assign]
    with pytest.raises(ContainerLifecycleError, match="runtime policy"):
        DockerAttemptExecutor(
            renderer=DockerCommandRenderer(DOCKER),
            runner=runner,
        ).execute(spec, root, repository_root=ROOT)


def test_stale_container_identity_is_rejected(tmp_path: Path) -> None:
    root = _root(tmp_path)
    spec = _spec(root)
    runner = FakeDockerRunner(spec)
    runner.state = "created"
    original_run = runner.run

    def stale_inspect(argv: Any, *, timeout_seconds: int) -> CommandResult:
        result = original_run(argv, timeout_seconds=timeout_seconds)
        args = tuple(argv)
        if len(args) > 2 and args[2] == "inspect":
            document = json.loads(result.stdout)
            document[0]["Id"] = "d" * 64
            return CommandResult(args, 0, json.dumps(document))
        return result

    runner.run = stale_inspect  # type: ignore[method-assign]
    with pytest.raises(ContainerLifecycleError, match="stale or substituted"):
        DockerAttemptExecutor(
            renderer=DockerCommandRenderer(DOCKER),
            runner=runner,
        ).execute(spec, root, repository_root=ROOT)
    cleanup = json.loads(
        (root.attempt_root / "container-failure-cleanup.json").read_text(encoding="utf-8")
    )
    assert cleanup["removed"] is False
    assert cleanup["cleanup_sealed"] is False
    assert cleanup["cleanup_error_types"] == ["failure-inspect-validation:ContainerLifecycleError"]
    assert cleanup["residuals"] == {"containers": [], "networks": [], "volumes": []}


def test_failure_cleanup_retained_output_is_hard_bounded(tmp_path: Path) -> None:
    root = _root(tmp_path)
    spec = _spec(root)
    runner = FakeDockerRunner(spec)
    original_run = runner.run

    def oversized_then_stale_inspect(argv: Any, *, timeout_seconds: int) -> CommandResult:
        result = original_run(argv, timeout_seconds=timeout_seconds)
        args = tuple(argv)
        if len(args) > 2 and args[2] == "inspect" and runner.state == "created":
            (root.attempt_root / "oversized.bin").write_bytes(
                b"x" * (spec.resources.output_bytes + 1)  # type: ignore[operator]
            )
            document = json.loads(result.stdout)
            document[0]["Id"] = "d" * 64
            return CommandResult(args, 0, json.dumps(document))
        return result

    runner.run = oversized_then_stale_inspect  # type: ignore[method-assign]
    with pytest.raises(ContainerLifecycleError, match="stale or substituted"):
        DockerAttemptExecutor(
            renderer=DockerCommandRenderer(DOCKER),
            runner=runner,
        ).execute(spec, root, repository_root=ROOT)
    cleanup = json.loads(
        (root.attempt_root / "container-failure-cleanup.json").read_text(encoding="utf-8")
    )
    assert cleanup["output_limit_exceeded"] is True
    assert cleanup["cleanup_sealed"] is False
    assert "retained-output:truncated" in cleanup["cleanup_error_types"]
    retained = sum(path.stat().st_size for path in root.attempt_root.rglob("*") if path.is_file())
    assert retained <= spec.resources.output_bytes  # type: ignore[operator]


def test_attempt_identity_cannot_be_reused(tmp_path: Path) -> None:
    first_root = _root(tmp_path, name="attempt-one")
    first_spec = _spec(first_root)
    runner = FakeDockerRunner(first_spec)
    executor = DockerAttemptExecutor(renderer=DockerCommandRenderer(DOCKER), runner=runner)
    executor.execute(first_spec, first_root, repository_root=ROOT)
    second_root = _root(tmp_path, name="attempt-two")
    second_spec = _spec(second_root)
    with pytest.raises(ContainerLifecycleError, match="already consumed"):
        executor.execute(second_spec, second_root, repository_root=ROOT)


def test_runtime_cannot_reuse_a_container_id_for_a_fresh_attempt(tmp_path: Path) -> None:
    first_root = _root(tmp_path, name="attempt-container-one")
    first_spec = _spec(first_root)
    runner = FakeDockerRunner(first_spec)
    executor = DockerAttemptExecutor(renderer=DockerCommandRenderer(DOCKER), runner=runner)
    executor.execute(first_spec, first_root, repository_root=ROOT)

    second_root = _root(tmp_path, name="attempt-container-two")
    second_identity = _identity(attempt_uuid="e" * 32)
    second_spec = _spec(second_root, identity=second_identity)
    runner.spec = second_spec
    with pytest.raises(ContainerLifecycleError, match="stale container identity"):
        executor.execute(second_spec, second_root, repository_root=ROOT)


def _load_entrypoint() -> ModuleType:
    path = ROOT / "containers/sira-smoke/container_entrypoint.py"
    spec = importlib.util.spec_from_file_location("t07_container_entrypoint", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_dummy_secret_file_channel_and_retained_surfaces_do_not_leak(
    tmp_path: Path,
) -> None:
    dummy = "T07_DUMMY_CANARY_VALUE_NOT_A_REAL_CREDENTIAL"
    secret_file = tmp_path / "dummy-sira-secret"
    secret_file.write_text(dummy + "\n", encoding="utf-8")
    secret_file.chmod(0o600)
    entrypoint = _load_entrypoint()
    assert entrypoint.read_secret_file(secret_file) == dummy
    ambient = {"PATH": "/usr/bin"}
    ambient["OPENAI_" + "API_KEY"] = "forbidden-fallback"
    child = entrypoint.child_environment(dummy, ambient)
    assert child["SIRA_API_KEY"] == dummy
    assert "OPENAI_API_KEY" not in child

    root = _root(tmp_path)
    mounts = (
        *_spec(root).mounts,
        BindMount(
            source=secret_file.resolve(),
            target=CONTAINER_SECRET_TARGET,
            purpose=MountPurpose.SECRET_FILE,
            read_only=True,
        ),
    )
    spec = _spec(
        root,
        fixture=ContainerFixture.DUMMY_SECRET_PREFLIGHT,
        mounts=mounts,
        command=(
            "/opt/sira/.venv/bin/python",
            "/opt/giclab/container_entrypoint.py",
            "--",
            "/opt/sira/.venv/bin/python",
            "/opt/giclab/fixtures/secret_probe.py",
        ),
        ready_artifact="dummy-secret-probe.json",
    )
    runner = FakeDockerRunner(spec)
    renderer = DockerCommandRenderer(DOCKER)
    evidence = DockerAttemptExecutor(renderer=renderer, runner=runner).execute(
        spec,
        root,
        repository_root=ROOT,
    )
    assert_dummy_secret_absent(
        dummy,
        documents=(
            list(renderer.create(spec)),
            dict(spec.identity.labels(spec.image.digest)),
            evidence.document(),
        ),
        retained_paths=(
            root.attempt_root / "container-evidence-before-removal.json",
            root.attempt_root / "container-cleanup-seal.json",
        ),
    )


def test_public_dummy_secret_writer_is_exclusive_and_private(tmp_path: Path) -> None:
    path = (tmp_path / "gate-b2-dummy-secret").resolve()
    write_dummy_secret_file(path)
    assert path.read_text(encoding="utf-8") == (
        "T07_GATE_B2_DUMMY_CANARY_PUBLIC_NOT_A_CREDENTIAL\n"
    )
    assert path.stat().st_mode & 0o077 == 0
    with pytest.raises(ContainerContractError, match="must be fresh"):
        write_dummy_secret_file(path)


def _compatibility(platform: ContainerPlatform) -> PlatformCompatibility:
    native = platform is ContainerPlatform.LINUX_ARM64
    return PlatformCompatibility(
        platform=platform,
        execution_path="native Apple-silicon Linux VM" if native else "Rosetta/QEMU emulation",
        platform_manifest_digest=(
            BASE_IMAGE_ARM64_MANIFEST_DIGEST if native else BASE_IMAGE_AMD64_MANIFEST_DIGEST
        ),
        compressed_base_bytes=719_590_824 if native else 742_924_281,
        python_310_compatible=True,
        uv_frozen_eval_feasible=True,
        playwright_139_compatible=True,
        chromium_revision_1084_compatible=True,
        browsergym_compatible=True,
        expected_dependency_download_bytes=313_827_106,
        expected_runtime_memory_bytes=2 * 1024**3,
        reproducibility_risks=("authorized build probe still required",),
        performance_risks=(() if native else ("architecture emulation overhead",)),
    )


def test_architecture_decision_serialization_is_schema_valid() -> None:
    decision = PlatformDecision(
        candidates=(
            _compatibility(ContainerPlatform.LINUX_ARM64),
            _compatibility(ContainerPlatform.LINUX_AMD64),
        ),
        chosen_platform=ContainerPlatform.LINUX_ARM64,
        decision_status="chosen",
        rationale="Native arm64 is immutable, smaller, and avoids an emulation layer.",
    )
    document = decision.document()
    assert document["chosen_platform"] == "linux/arm64"
    assert (
        validate_instance(document, ROOT / "schemas/container-platform-decision.schema.json") == []
    )
    duplicated = deepcopy(document)
    duplicated["candidates"][1]["platform"] = "linux/arm64"  # type: ignore[index]
    assert validate_instance(
        duplicated,
        ROOT / "schemas/container-platform-decision.schema.json",
    )
    unresolved = deepcopy(document)
    unresolved["candidates"][0]["playwright_139_compatible"] = False  # type: ignore[index]
    assert validate_instance(
        unresolved,
        ROOT / "schemas/container-platform-decision.schema.json",
    )


def test_architecture_cannot_be_chosen_with_unresolved_compatibility() -> None:
    incompatible = replace(
        _compatibility(ContainerPlatform.LINUX_ARM64),
        playwright_139_compatible=False,
    )
    with pytest.raises(ContainerContractError, match="unresolved compatibility"):
        PlatformDecision(
            candidates=(incompatible, _compatibility(ContainerPlatform.LINUX_AMD64)),
            chosen_platform=ContainerPlatform.LINUX_ARM64,
            decision_status="chosen",
            rationale="invalid synthetic choice",
        )


def test_image_provenance_serialization_requires_complete_observed_identity() -> None:
    provenance = ContainerImageProvenance(
        base_image_reference=BASE_IMAGE_REFERENCE,
        base_image_index_digest=BASE_IMAGE_INDEX_DIGEST,
        base_image_platform_digest=BASE_IMAGE_ARM64_MANIFEST_DIGEST,
        containerfile_sha256="1" * 64,
        source_commit=SIRA_UPSTREAM_COMMIT,
        source_patch_sha256="2" * 64,
        runtime_adaptation_sha256="6" * 64,
        repository_build_assets_sha256="7" * 64,
        uv_lock_sha256=UPSTREAM_UV_LOCK_SHA256,
        installed_package_manifest_sha256="3" * 64,
        playwright_version=PLAYWRIGHT_VERSION,
        chromium_revision=CHROMIUM_REVISION,
        chromium_executable_sha256="4" * 64,
        browser_attempt_uuid="8" * 32,
        browser_record_sha256="9" * 64,
        browser_pre_removal_evidence_sha256="a" * 64,
        browser_cleanup_seal_sha256="b" * 64,
        final_image_id="sha256:" + "5" * 64,
        final_repo_digest=None,
        final_repo_digest_status="unavailable-local-build-not-pushed",
        platform=ContainerPlatform.LINUX_ARM64,
    )
    assert (
        validate_instance(
            provenance.document(),
            ROOT / "schemas/container-image-provenance.schema.json",
        )
        == []
    )


def test_build_contract_is_digest_pinned_and_applies_repository_owned_patch() -> None:
    contract = ContainerBuildContract(
        repository_root=ROOT,
        containerfile=ROOT / "containers/sira-smoke/Containerfile",
        source_patch=ROOT / "containers/sira-smoke/sira-immutable-model-routing.patch",
        runtime_adaptation=ROOT / "src/giclab/harness/sira_gate_a_runtime.py",
    )
    hashes = contract.artifact_hashes()
    assert set(hashes) == {
        "containerfile_sha256",
        "source_patch_sha256",
        "runtime_adaptation_sha256",
        "repository_build_assets_sha256",
    }
    containerfile = contract.containerfile.read_text(encoding="utf-8")
    assert f"FROM --platform=linux/arm64 {BASE_IMAGE_REFERENCE}" in containerfile
    assert "UV_HTTP_RETRIES=0" in containerfile
    assert "UV_PYTHON_DOWNLOADS=never" in containerfile
    assert (
        "git apply --check /opt/giclab/patches/sira-immutable-model-routing.patch" in containerfile
    )
    patch_text = contract.source_patch.read_text(encoding="utf-8")
    assert 'os.environ.pop("SIRA_API_KEY", None)' in patch_text
    added_patch_lines = "\n".join(
        line[1:] for line in patch_text.splitlines() if line.startswith("+")
    )
    assert 'os.environ.get("OPENAI_API_KEY")' not in added_patch_lines
    build = contract.build_argv(
        DOCKER,
        staged_context=Path("/private/tmp/t07-gate-b2-context"),
        local_tag="giclab/sira-smoke:t07-gate-b2-contract",
    )
    assert build[:3] == (str(DOCKER), "buildx", "build")
    assert build[build.index("--platform") + 1] == "linux/arm64"
    assert "--pull=false" in build and "--no-cache" in build
    inspect_commands = contract.source_inspection_argv(
        Path("/usr/bin/git"),
        Path("/Users/joseph/.local/share/gic-lab/t07/source"),
    )
    assert inspect_commands[0][-2:] == ("rev-parse", "HEAD")
    assert inspect_commands[1][-4:] == (
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
        "--ignored=matching",
    )
    archive = contract.source_archive_argv(
        Path("/usr/bin/git"),
        Path("/Users/joseph/.local/share/gic-lab/t07/source"),
        Path("/Users/joseph/.local/share/gic-lab/t07/build-context/upstream.tar"),
    )
    assert archive[-1] == SIRA_UPSTREAM_COMMIT
    staged = contract.staged_repository_files()
    assert "sira-immutable-model-routing.patch" in staged
    assert all(path.is_file() for path in staged.values())


def test_local_tag_is_resolved_once_to_a_label_verified_immutable_image(
    tmp_path: Path,
) -> None:
    contract = ContainerBuildContract(
        repository_root=ROOT,
        containerfile=ROOT / "containers/sira-smoke/Containerfile",
        source_patch=ROOT / "containers/sira-smoke/sira-immutable-model-routing.patch",
        runtime_adaptation=ROOT / "src/giclab/harness/sira_gate_a_runtime.py",
    )
    hashes = contract.artifact_hashes()
    local_tag = "giclab/sira-smoke:t07-gate-b2-contract"
    inspect = [
        {
            "Id": IMAGE_ID,
            "Os": "linux",
            "Architecture": "arm64",
            "RepoDigests": [],
            "Config": {
                "Labels": {
                    "org.giclab.t07.source-commit": SIRA_UPSTREAM_COMMIT,
                    "org.giclab.t07.source-patch-sha256": hashes["source_patch_sha256"],
                    "org.giclab.t07.containerfile-sha256": hashes["containerfile_sha256"],
                    "org.giclab.t07.runtime-adaptation-sha256": hashes["runtime_adaptation_sha256"],
                    "org.giclab.t07.repository-build-assets-sha256": hashes[
                        "repository_build_assets_sha256"
                    ],
                    "org.giclab.t07.base-image-index-digest": BASE_IMAGE_INDEX_DIGEST,
                    "org.giclab.t07.base-image-platform-digest": (BASE_IMAGE_ARM64_MANIFEST_DIGEST),
                    "org.giclab.t07.uv-lock-sha256": UPSTREAM_UV_LOCK_SHA256,
                    "org.giclab.t07.platform": "linux/arm64",
                    "org.giclab.t07.playwright-version": PLAYWRIGHT_VERSION,
                    "org.giclab.t07.chromium-revision": CHROMIUM_REVISION,
                }
            },
        }
    ]
    runner = FakeImageRunner(inspect)
    identity = capture_local_image_identity(
        local_tag=local_tag,
        build_contract=contract,
        renderer=DockerCommandRenderer(DOCKER),
        runner=runner,
    )
    assert identity.final_image_id == IMAGE_ID
    assert runner.calls == [(str(DOCKER), "image", "inspect", local_tag)]
    record = tmp_path / "image-identity.json"
    record.write_text(json.dumps(identity.document()), encoding="utf-8")
    assert load_local_image_identity(record, build_contract=contract) == identity
    browser_attempt_uuid = "d" * 32
    root = _root(tmp_path, name=f"browser-preflight-{browser_attempt_uuid}")
    browser_spec = fixture_attempt_spec(
        fixture=ContainerFixture.BROWSER_PREFLIGHT,
        image=identity,
        root=root,
        repository_commit=BASELINE_COMMIT,
        attempt_uuid=browser_attempt_uuid,
        authorization_reference="AUTH-T07-GATE-B2-PROVENANCE",
    )
    DockerAttemptExecutor(
        renderer=DockerCommandRenderer(DOCKER),
        runner=FakeDockerRunner(browser_spec),
    ).execute(browser_spec, root, repository_root=ROOT)
    browser_record = root.attempt_root / "browser-preflight.json"
    pre_removal = root.attempt_root / "container-evidence-before-removal.json"
    cleanup_seal = root.attempt_root / "container-cleanup-seal.json"
    provenance = assemble_image_provenance(
        image=identity,
        browser_attempt_uuid=browser_attempt_uuid,
        browser_record_path=browser_record,
        browser_pre_removal_evidence_path=pre_removal,
        browser_cleanup_seal_path=cleanup_seal,
    )
    assert provenance.final_image_id == IMAGE_ID
    assert provenance.browser_attempt_uuid == browser_attempt_uuid
    assert (
        validate_instance(
            provenance.document(),
            ROOT / "schemas/container-image-provenance.schema.json",
        )
        == []
    )

    browser_record.write_text(
        browser_record.read_text(encoding="utf-8").replace(
            '"chromium_executable_sha256": "' + "2" * 64,
            '"chromium_executable_sha256": "' + "3" * 64,
        ),
        encoding="utf-8",
    )
    with pytest.raises(ContainerContractError, match="exact fixture record"):
        assemble_image_provenance(
            image=identity,
            browser_attempt_uuid=browser_attempt_uuid,
            browser_record_path=browser_record,
            browser_pre_removal_evidence_path=pre_removal,
            browser_cleanup_seal_path=cleanup_seal,
        )


@pytest.mark.parametrize(
    "fixture",
    (
        ContainerFixture.ADVERSARIAL_CONTAINMENT,
        ContainerFixture.BROWSER_PREFLIGHT,
    ),
)
def test_gate_b2_fixture_specs_are_no_network_and_model_free(
    tmp_path: Path,
    fixture: ContainerFixture,
) -> None:
    contract = ContainerBuildContract(
        repository_root=ROOT,
        containerfile=ROOT / "containers/sira-smoke/Containerfile",
        source_patch=ROOT / "containers/sira-smoke/sira-immutable-model-routing.patch",
        runtime_adaptation=ROOT / "src/giclab/harness/sira_gate_a_runtime.py",
    )
    hashes = contract.artifact_hashes()
    image = LocalImageIdentity(
        local_tag="giclab/sira-smoke:t07-gate-b2-contract",
        final_image_id=IMAGE_ID,
        repo_digests=(),
        platform=ContainerPlatform.LINUX_ARM64,
        source_commit=SIRA_UPSTREAM_COMMIT,
        source_patch_sha256=hashes["source_patch_sha256"],
        containerfile_sha256=hashes["containerfile_sha256"],
        runtime_adaptation_sha256=hashes["runtime_adaptation_sha256"],
        repository_build_assets_sha256=hashes["repository_build_assets_sha256"],
        base_image_index_digest=BASE_IMAGE_INDEX_DIGEST,
        base_image_platform_digest=BASE_IMAGE_ARM64_MANIFEST_DIGEST,
        uv_lock_sha256=UPSTREAM_UV_LOCK_SHA256,
        playwright_version=PLAYWRIGHT_VERSION,
        chromium_revision=CHROMIUM_REVISION,
    )
    root = _root(tmp_path, name=fixture.value)
    spec = fixture_attempt_spec(
        fixture=fixture,
        image=image,
        root=root,
        repository_commit=BASELINE_COMMIT,
        attempt_uuid="f" * 32,
        authorization_reference="AUTH-T07-GATE-B2-FIXTURE",
    )
    validate_container_attempt(spec, root, repository_root=ROOT)
    create = DockerCommandRenderer(DOCKER).create(spec)
    assert create[create.index("--network") + 1] == "none"
    rendered = "\n".join(create).lower()
    assert "api.openai.com" not in rendered
    assert "gpt-4o" not in rendered


def test_fixtures_encode_adversarial_and_local_only_contracts() -> None:
    fixture_root = ROOT / "containers/sira-smoke/fixtures"
    adversarial = (fixture_root / "adversarial_containment.py").read_text(encoding="utf-8")
    assert "os.fork()" in adversarial
    assert "os.setsid()" in adversarial
    assert "signal.SIG_IGN" in adversarial
    assert "start_new_session=True" in adversarial
    browser = (fixture_root / "browser_preflight.py").read_text(encoding="utf-8")
    assert "static.html" in browser
    assert "page.screenshot" in browser
    assert "browser.close()" in browser
    assert "http://" not in browser and "https://" not in browser


def test_fixture_limits_are_finite_and_condition_specific() -> None:
    synthetic = synthetic_limits()
    browser = browser_preflight_limits()
    synthetic.validate()
    browser.validate()
    assert synthetic.pids == 64
    assert synthetic.wall_seconds == 30
    assert browser.pids == 256
    assert browser.wall_seconds == 60
    assert browser.memory_bytes > synthetic.memory_bytes  # type: ignore[operator]
