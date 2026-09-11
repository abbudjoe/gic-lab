"""Fake outer client tests: never contact an actual daemon from the test suite."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

SOURCE = Path(__file__).resolve().parents[2] / "scripts/ci/local_container.py"
SPEC = importlib.util.spec_from_file_location("local_container_ci", SOURCE)
assert SPEC and SPEC.loader
ci = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = ci
SPEC.loader.exec_module(ci)
CID = "a" * 64


@pytest.mark.parametrize("operation", ["start", "stop", "status", "ssh"])
def test_every_colima_operation_uses_global_gic_profile_selector(operation):
    argv = ci.colima_argv(Path("/protected/tools/colima"), operation)
    assert argv == ["/protected/tools/colima", "--profile", "gic-pr15-ci", operation]
    with pytest.raises(ci.LocalCIError, match="explicit GIC"):
        ci.colima_argv(Path("/protected/tools/colima"), operation, ["--profile=other"])


@pytest.mark.parametrize(
    "text",
    [
        "\nerror: no such object: " + CID + "\n",
        "Error response from daemon: No such container: " + CID,
    ],
)
def test_exact_container_absence_accepts_observed_cli_forms(text):
    assert ci.exact_container_absent({"exit_code": 1, "output": text}, CID)
    assert not ci.exact_container_absent({"exit_code": 0, "output": text}, CID)
    assert not ci.exact_container_absent({"exit_code": 1, "output": text}, "b" * 64)


@pytest.mark.parametrize("text", ["No such object", "permission denied", "connection refused", ""])
def test_container_absence_is_not_inferred_from_generic_failure(text):
    assert not ci.exact_container_absent({"exit_code": 1, "output": text}, CID)


def test_lima_effective_none_rule_requires_explicit_wildcard_and_exact_sockets(tmp_path):
    rules = [
        {
            "guestSocket": guest,
            "hostSocket": str(tmp_path / "colima/gic-pr15-ci" / host),
            "proto": "tcp",
        }
        for guest, host in (
            ("/var/run/docker.sock", "docker.sock"),
            ("/var/run/containerd/containerd.sock", "containerd.sock"),
        )
    ]
    observed_none = {"guestIP": "0.0.0.0", "proto": "any", "ignore": True}
    value = {
        "ssh": {"loadDotSSHPubKeys": False, "forwardAgent": False},
        "mounts": [],
        "portForwards": [*rules, observed_none],
    }
    with pytest.raises(ci.LocalCIError, match="all-interface"):
        ci.validate_lima_isolation(value, tmp_path)
    value["portForwards"] = [*ci.lima_isolation_override()["portForwards"], *rules, observed_none]
    ci.validate_lima_isolation(value, tmp_path)
    value["portForwards"][0]["guestIPMustBeZero"] = True
    with pytest.raises(ci.LocalCIError, match="all-interface"):
        ci.validate_lima_isolation(value, tmp_path)
    value["portForwards"][0]["guestIPMustBeZero"] = False
    rules[0]["hostSocket"] = "/forbidden-shared.sock"
    with pytest.raises(ci.LocalCIError, match="management socket"):
        ci.validate_lima_isolation(value, tmp_path)


@pytest.mark.parametrize("field", ["loadDotSSHPubKeys", "forwardAgent"])
def test_lima_effective_personal_identity_exposure_is_rejected(field, tmp_path):
    value = {"ssh": {"loadDotSSHPubKeys": False, "forwardAgent": False}}
    value["ssh"][field] = True
    with pytest.raises(ci.LocalCIError):
        ci.validate_lima_isolation(value, tmp_path)


@pytest.mark.parametrize(
    "field,value",
    [
        ("mounts", []),
        ("mounts", [{"location": "~"}]),
        ("autoActivate", True),
        ("sshConfig", True),
        ("forwardAgent", True),
        ("portForwarder", "ssh"),
        ("network", {"address": True}),
        ("kubernetes", {"enabled": True}),
        ("binfmt", True),
        ("rosetta", True),
        ("nestedVirtualization", True),
        ("provision", []),
        ("memory", 9),
        ("disk", 64),
        ("forceDiskImage", True),
    ],
)
def test_gic_colima_configuration_rejects_exposure_and_update_drift(field, value):
    document = ci.colima_configuration()
    ci.validate_colima_configuration(document)
    document[field] = value
    with pytest.raises(ci.LocalCIError):
        ci.validate_colima_configuration(document)


def test_colima_no_mount_selection_is_explicit_null_not_home_default():
    document = ci.colima_configuration()
    assert document["mounts"] is None
    ci.validate_colima_configuration(document)
    del document["mounts"]
    with pytest.raises(ci.LocalCIError, match="missing: mounts"):
        ci.validate_colima_configuration(document)


def test_gic_colima_environment_has_no_ambient_profile_or_credential_fallback(
    tmp_path, monkeypatch
):
    for name in ("home", "colima", "colima/_lima", "docker", "cache", "tmp"):
        (tmp_path / name).mkdir(mode=0o700, parents=True, exist_ok=True)
    monkeypatch.setenv("DOCKER_HOST", "unix:///forbidden-shared.sock")
    monkeypatch.setenv("DOCKER_CONTEXT", "forbidden-other-profile")
    monkeypatch.setenv("SSH_AUTH_SOCK", "/forbidden-agent")
    # Socket length is tested separately; this unit exercises the explicit env
    # construction without claiming ownership qualification of the host fixture.
    monkeypatch.setattr(ci.os, "fsencode", lambda _: b"short-test-socket")
    env = ci.colima_environment(tmp_path, tmp_path / "tools")
    assert env["DOCKER_HOST"] == "unix://" + str(tmp_path / "colima/gic-pr15-ci/docker.sock")
    assert env["LIMA_HOME"] == str(tmp_path / "colima/_lima")
    assert env["COLIMA_HOME"] == str(tmp_path / "colima")
    assert env["HOME"] == str(tmp_path / "home")
    assert "DOCKER_CONTEXT" not in env and "SSH_AUTH_SOCK" not in env
    (tmp_path / "home").chmod(0o755)
    with pytest.raises(ci.LocalCIError, match="private protected homes"):
        ci.colima_environment(tmp_path, tmp_path / "tools")


def test_gic_colima_missing_protected_root_never_materializes_internal_fallback(tmp_path):
    absent = tmp_path / "missing-volume"
    with pytest.raises((ci.LocalCIError, ValueError, OSError)):
        ci.colima_environment(absent, absent / "tools")
    assert not absent.exists()


@pytest.mark.parametrize("free", [6_328_016_896, 12_884_901_888, 100 * ci.GIB])
def test_storage_budget_does_not_certify_unmeasured_preparation(monkeypatch, tmp_path, free):
    from types import SimpleNamespace

    monkeypatch.setattr(ci.shutil, "disk_usage", lambda _: SimpleNamespace(free=free))
    value = ci.plan("unix:///test-owned/runtime.sock", tmp_path / "run")
    required = 8_589_934_592 + 4_294_967_296
    assert value["preparation_budget_required_free_bytes"] == required
    assert value["preparation_budget_deficit_bytes"] == max(0, required - free)
    assert value["preparation_budget_headroom_available"] == (free >= required)
    assert value["preparation_storage_admitted"] is False
    assert value["preparation_storage_status"] == "unqualified-image-peak-and-backing-filesystem"


def test_preflight_keeps_explicit_endpoint_and_reports_storage_separately(monkeypatch, tmp_path):
    from types import SimpleNamespace

    endpoint = "unix:///test-owned/approved.sock"
    record = tmp_path / "preflight"
    calls = []
    monkeypatch.setattr(
        ci.ProjectStorage,
        "load",
        lambda _: SimpleNamespace(
            recheck=lambda: 500 * ci.GIB,
            destination=lambda path, **_: path,
            external_retained_floor_bytes=200 * ci.GIB,
        ),
    )
    monkeypatch.setattr(ci, "local_endpoint", lambda path: endpoint)
    monkeypatch.setattr(ci.shutil, "which", lambda name: "/test-owned/docker-client")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "local_container.py",
            "--endpoint",
            "/test-owned/approved.sock",
            "--record-root",
            str(record),
            "--preflight",
        ],
    )

    def command(argv, *, environment, timeout):
        calls.append(argv)
        assert argv == [
            "/test-owned/docker-client",
            "--config",
            str(record / "docker-config"),
            "--host",
            endpoint,
            "version",
            "--format",
            "{{json .Server}}",
        ]
        assert set(environment) == {"PATH", "HOME", "DOCKER_CONFIG"}
        assert json.loads((record / "docker-config/config.json").read_bytes()) == {}
        assert timeout == 15
        return {"exit_code": 0, "output": json.dumps({"Os": "linux", "Arch": "arm64"})}

    monkeypatch.setattr(ci, "bounded_command", command)
    with pytest.raises(ci.LocalCIError, match="runtime metadata is usable; preparation storage"):
        ci.main()
    assert len(calls) == 1
    assert json.loads((record / "metadata.json").read_bytes())["exit_code"] == 0
    assert json.loads((record / "plan.json").read_bytes())["endpoint"] == endpoint


@pytest.fixture
def external_storage(tmp_path, monkeypatch):
    from types import SimpleNamespace

    mount = tmp_path / "Volume With Spaces"
    root = mount / "GIC-Lab"
    root.mkdir(parents=True)
    for role in ["tmp", "cache", "workspaces", "ci/inputs", "ci/results", "evidence/pr15"]:
        (root / role).mkdir(parents=True, exist_ok=True)
    value = {
        "MountPoint": str(mount),
        "VolumeUUID": "test-volume",
        "APFSContainerReference": "test-container",
        "FilesystemType": "apfs",
        "Internal": False,
        "Locked": False,
        "Writable": True,
        "WritableVolume": True,
        "GlobalPermissionsEnabled": False,
        "APFSContainerSize": 1_000_240_963_584,
        "APFSContainerFree": 500 * ci.GIB,
    }
    native_mount = ci.os.path.ismount
    monkeypatch.setattr(ci.os.path, "ismount", lambda p: p == mount or native_mount(p))
    monkeypatch.setattr(ci, "startup_device", lambda: -1)
    monkeypatch.setattr(ci, "observe_volume", lambda _: value)
    native_space = ci.os.statvfs
    monkeypatch.setattr(
        ci.os,
        "statvfs",
        lambda path: (
            SimpleNamespace(f_bavail=(500 * ci.GIB) // 4096, f_frsize=4096)
            if Path(path).is_relative_to(root)
            else native_space(path)
        ),
    )
    selected = ci.ProjectStorage(
        mount,
        root,
        "test-volume",
        "test-container",
        mount.stat().st_dev,
        mount.stat().st_ino,
        root.stat().st_ino,
        False,
        ci.retained_free_floor(value["APFSContainerSize"]),
    )
    return selected, value


def test_external_container_free_is_not_summed_or_replaced_by_host_free(external_storage):
    storage, observation = external_storage
    observation["APFSContainerFree"] = storage.external_retained_floor_bytes - 1
    with pytest.raises(ci.LocalCIError, match="external retained storage headroom"):
        storage.fresh("tmp", "must-not-exist")
    assert not (storage.root / "tmp/must-not-exist").exists()


def test_external_paths_with_spaces_and_environment_are_exact(external_storage):
    storage, _ = external_storage
    run = storage.fresh("tmp", "test-run")
    env = storage.environment(run)
    for key in (
        "TMPDIR",
        "TMP",
        "TEMP",
        "UV_CACHE_DIR",
        "PIP_CACHE_DIR",
        "DENO_DIR",
        "XDG_CACHE_HOME",
    ):
        assert Path(env[key]).is_relative_to(storage.root)
        assert Path(env[key]).is_dir()
    assert "HOME" not in env
    assert env["UV_OFFLINE"] == "1"
    with pytest.raises(FileExistsError):
        storage.fresh("tmp", "test-run")


@pytest.mark.parametrize(
    "field,value",
    [
        ("VolumeUUID", "replaced"),
        ("APFSContainerReference", "replaced"),
        ("Internal", True),
        ("Locked", True),
        ("WritableVolume", False),
        ("GlobalPermissionsEnabled", True),
    ],
)
def test_changed_external_volume_rejected(external_storage, field, value):
    storage, observation = external_storage
    observation[field] = value
    with pytest.raises(ci.LocalCIError, match="volume binding differs"):
        storage.fresh("tmp", "must-not-exist")
    assert not (storage.root / "tmp/must-not-exist").exists()


def test_absent_mount_and_plain_directory_never_fall_back(external_storage, monkeypatch):
    storage, _ = external_storage
    monkeypatch.setattr(ci.os.path, "ismount", lambda _: False)
    with pytest.raises(ci.LocalCIError, match="mount identity changed"):
        storage.fresh("tmp", "must-not-exist")
    assert not (storage.root / "tmp/must-not-exist").exists()


def test_missing_or_replaced_root_is_not_recreated(external_storage):
    storage, _ = external_storage
    storage.root.rename(storage.mount / "original-retained")
    with pytest.raises(ValueError, match="required path is missing"):
        storage.fresh("tmp", "must-not-exist")
    assert not storage.root.exists()
    storage.root.mkdir()
    with pytest.raises(ci.LocalCIError, match="mount identity changed"):
        storage.recheck()


def test_missing_storage_configuration_has_no_default(tmp_path):
    path = tmp_path / "absent.json"
    with pytest.raises(FileNotFoundError):
        ci.ProjectStorage.load(path)
    assert not path.exists()


def test_wrong_destination_and_symlink_rejected(external_storage, tmp_path):
    storage, _ = external_storage
    with pytest.raises(ci.LocalCIError, match="outside the bound"):
        storage.destination(tmp_path / "wrong", missing_leaf=True)
    (storage.root / "tmp/escape").symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        storage.destination(storage.root / "tmp/escape/new", missing_leaf=True)


def test_external_budget_is_not_charged_to_startup(external_storage, monkeypatch):
    from types import SimpleNamespace

    storage, _ = external_storage
    monkeypatch.setattr(ci.shutil, "disk_usage", lambda _: SimpleNamespace(free=ci.HOST_FLOOR + 1))
    result = ci.plan("unix:///test/runtime.sock", storage.root / "ci/results/new", storage=storage)
    assert result["host_headroom_available"] is True
    assert result["preparation_budget_filesystem"] == "bound-external"
    assert result["preparation_budget_deficit_bytes"] == 0
    assert result["runtime_backing_external_verified"] is False
    assert result["preparation_storage_admitted"] is False


def test_container_tool_writers_use_declared_linux_scratch_and_results():
    spec = importlib.util.spec_from_file_location(
        "local_ci_runner_paths", SOURCE.with_name("run_gates.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    value = module.offline_paths(Path("/work"), Path("/results"))
    for key, path in value.items():
        if key not in {"UV_OFFLINE", "UV_PYTHON_DOWNLOADS", "PYTHONDONTWRITEBYTECODE"}:
            assert Path(path).is_relative_to("/work") or Path(path).is_relative_to("/results")
    assert value["QUARTO_LOG"] == "/results/quarto.log"
    assert value["UV_OFFLINE"] == "1"


def test_ci_configuration_is_bounded_and_not_experimental(tmp_path):
    volumes = ci.GuestVolumes("gic-pr15-ci-" + "a" * 16)
    argv = ci.container_argv("sha256:" + "b" * 64, volumes)
    for flag in (
        "--network=none",
        "--read-only",
        "--cap-drop=ALL",
        "--init",
        "--user=10001:10001",
        "--security-opt=no-new-privileges:true",
        "--ipc=private",
        "--ulimit=core=0:0",
        "--restart=no",
    ):
        assert flag in argv
    assert not any("docker.sock" in value or "privileged" in value for value in argv)
    assert not any("type=bind" in value for value in argv)
    for role in ("input", "work", "results"):
        expected = f"type=volume,src={volumes.name(role)},dst=/{role}"
        assert any(value.startswith(expected) and "volume-nocopy" in value for value in argv)
    assert any("dst=/input,readonly," in value for value in argv)
    with pytest.raises(ci.LocalCIError, match="guest volumes"):
        ci.container_argv("sha256:" + "b" * 64, tmp_path)
    with pytest.raises(ci.LocalCIError, match="guest-volume transaction"):
        ci.GuestVolumes("some-existing-unrelated-volume")
    with pytest.raises(ci.LocalCIError):
        ci.container_argv("floating:latest", volumes)
    with pytest.raises(ci.LocalCIError):
        ci.Limits(cpus=5)
    with pytest.raises(ci.LocalCIError):
        ci.plan("ssh://remote", tmp_path / "run")


@pytest.mark.parametrize(
    "failure",
    [None, "admission", "start", "wait", "collect", "interruption", "wrong-id", "test-exit"],
)
def test_outer_cleanup_uses_exact_id_even_on_failure(failure):
    calls = []
    state = {"running": True, "removed": False}

    def command(argv, *, timeout):
        assert 0 < timeout <= 21600
        calls.append(argv)
        if argv[0] == "create":
            return {"exit_code": 0, "output": CID}
        assert argv[-1] == CID
        if argv[0] == "start" and failure == "start":
            return {"exit_code": 1, "output": "start acknowledgement unavailable"}
        if argv[0] == "wait":
            if failure == "wait":
                raise TimeoutError("stalled test")
            if failure == "interruption":
                raise KeyboardInterrupt
            return {"exit_code": 0, "output": "7" if failure == "test-exit" else "0"}
        if argv[0] == "inspect":
            if state["removed"]:
                return {"exit_code": 1, "output": "error: no such object: " + CID}
            return {
                "exit_code": 0,
                "output": json.dumps(
                    {
                        "Id": "c" * 64 if failure == "wrong-id" else CID,
                        "State": {"Running": state["running"]},
                    }
                ),
            }
        if argv[0] == "kill":
            state["running"] = False
        if argv[0] == "rm":
            state["removed"] = True
        return {"exit_code": 0, "output": ""}

    def collect(container_id):
        assert container_id == CID
        if failure == "collect":
            raise ValueError("unsafe result path")

    def admit(container_id):
        assert container_id == CID
        if failure == "admission":
            state["running"] = False
            raise ci.LocalCIError("unsafe container configuration")

    record = {}
    if failure is None:
        ci.run_owned_container(command, ["create"], admit=admit, collect=collect, record=record)
    else:
        with pytest.raises((TimeoutError, KeyboardInterrupt, ValueError, ci.LocalCIError)):
            ci.run_owned_container(command, ["create"], admit=admit, collect=collect, record=record)
    if failure == "admission":
        assert not any(call[0] == "start" for call in calls)
    assert sum(call[0] == "create" for call in calls) == 1
    if failure == "wrong-id":
        assert not any(call[0] in {"stop", "kill", "rm"} for call in calls)
        assert record["cleanup"] == "unresolved"
    elif failure in {"start", "wait", "interruption", "collect"}:
        assert not state["running"]
        assert not any(call[0] == "rm" for call in calls)
        assert record["cleanup"] == "exact-id-stopped-export-unresolved"
        assert record["export_verified"] is False
    else:
        assert record["cleanup"] == "exact-id-absent"
        assert record["export_verified"] is (failure != "admission")
    if failure == "test-exit":
        assert record["test_exit_code"] == 7


def test_ambiguous_creation_never_relaunches_or_deletes_by_name():
    calls, record = [], {}

    def command(argv, **kwargs):
        calls.append(argv)
        return {"exit_code": 1, "output": "partial creation"}

    with pytest.raises(ci.LocalCIError, match="ambiguous"):
        ci.run_owned_container(
            command, ["create"], admit=lambda _: None, collect=lambda _: None, record=record
        )
    assert calls == [["create"]]
    assert record["cleanup"] == "unresolved"


@pytest.mark.parametrize("exit_code,mutate", [(0, False), (7, False), (0, True), (7, True)])
def test_inner_gate_checks_source_and_retains_failed_outcome(tmp_path, exit_code, mutate):
    spec = importlib.util.spec_from_file_location(
        "checked_ci_gate", SOURCE.with_name("run_gates.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    source = tmp_path / "source.py"
    source.write_bytes(b"original")
    results = tmp_path / "results"
    results.mkdir()
    checks = []

    def verify():
        checks.append(True)
        if source.read_bytes() != b"original":
            raise RuntimeError("source changed")

    argv = [
        sys.executable,
        "-c",
        (
            "from pathlib import Path; import sys; "
            + ("Path('source.py').write_bytes(b'changed'); " if mutate else "")
            + f"print('bounded local gate output'); sys.exit({exit_code})"
        ),
    ]
    if exit_code or mutate:
        with pytest.raises((module.subprocess.CalledProcessError, RuntimeError)):
            module.execute_checked_gate(
                argv,
                checkout=tmp_path,
                results=results,
                verify_source=verify,
                identity={"classification": "unit-gate-regression"},
            )
    else:
        module.execute_checked_gate(
            argv,
            checkout=tmp_path,
            results=results,
            verify_source=verify,
            identity={"classification": "unit-gate-regression"},
        )
    assert checks == [True]
    receipt = json.loads((results / "gate.json").read_bytes())
    assert receipt["exit_code"] == exit_code
    assert receipt["source_unchanged"] is not mutate
    assert receipt["gate"] == ("failed" if exit_code or mutate else "passed")
    assert (results / "gate.log").read_text().strip() == "bounded local gate output"


@pytest.mark.parametrize("case", ["originals", "symlink", "oversized"])
def test_guard_journal_export_preserves_bytes_and_refuses_unsafe_growth(tmp_path, case):
    import hashlib

    spec = importlib.util.spec_from_file_location(
        "journal_export", SOURCE.with_name("run_gates.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    source, results = tmp_path / "journal", tmp_path / "results"
    source.mkdir()
    results.mkdir()
    data = b'{"operation":"process:docker","expected_by":"negative"}\n'
    journal = source / "123.jsonl"
    if case == "symlink":
        foreign = tmp_path / "foreign"
        foreign.write_bytes(data)
        journal.symlink_to(foreign)
    elif case == "oversized":
        with journal.open("wb") as stream:
            stream.truncate(1024**2 + 1)
    else:
        journal.write_bytes(data)
    if case != "originals":
        with pytest.raises(RuntimeError, match="metadata or byte cap"):
            module.export_guard_journals(source, results)
        assert list((results / "guard-journals").iterdir()) == []
    else:
        module.export_guard_journals(source, results)
        index = json.loads((results / "guard-journals/index.json").read_bytes())
        assert index["files"] == [
            {
                "path": "0000.jsonl",
                "bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
                "kind": "denial",
            }
        ]
        assert (results / "guard-journals/0000.jsonl").read_bytes() == data
        assert journal.read_bytes() == data


@pytest.mark.parametrize("outcome", ["pass", "cap", "nonzero", "stall"])
def test_gate_console_admits_before_growth_and_reaps_owned_child(tmp_path, outcome):
    import os
    import subprocess

    spec = importlib.util.spec_from_file_location(
        "bounded_ci_gate", SOURCE.with_name("run_gates.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    pid = tmp_path / "child-pid"
    script = (
        "import os,sys,time; from pathlib import Path; "
        "Path('child-pid').write_text(str(os.getpid())); "
        + {
            "pass": "os.write(1,b'x'*64)",
            "cap": "os.write(1,b'x'*65); time.sleep(5)",
            "nonzero": "os.write(1,b'x'*3); sys.exit(7)",
            "stall": "time.sleep(5)",
        }[outcome]
    )
    log = tmp_path / "console"
    with log.open("xb") as output:
        if outcome == "pass":
            assert (
                module.run(
                    [sys.executable, "-c", script],
                    cwd=tmp_path,
                    output=output,
                    output_cap=64,
                    timeout=2,
                ).returncode
                == 0
            )
        else:
            expected = {
                "cap": RuntimeError,
                "nonzero": subprocess.CalledProcessError,
                "stall": subprocess.TimeoutExpired,
            }[outcome]
            with pytest.raises(expected) as error:
                module.run(
                    [sys.executable, "-c", script],
                    cwd=tmp_path,
                    output=output,
                    output_cap=64,
                    timeout=0.5,
                )
            if outcome == "nonzero":
                assert error.value.returncode == 7
    assert log.stat().st_size <= 64
    if outcome == "pass":
        assert log.read_bytes() == b"x" * 64
    elif outcome == "cap":
        assert log.read_bytes() == b"x" * log.stat().st_size
    with pytest.raises(ProcessLookupError):
        os.kill(int(pid.read_text()), 0)


@pytest.mark.parametrize("profile", ["gic-pr15-ci", "gic-pr15-clean-ci"])
def test_profile_selection_binds_all_private_management_sockets(tmp_path, monkeypatch, profile):
    for name in ("home", "colima", "colima/_lima", "docker", "cache", "tmp"):
        (tmp_path / name).mkdir(mode=0o700, parents=True, exist_ok=True)
    monkeypatch.setattr(ci.os, "fsencode", lambda _: b"short-test-socket")
    env = ci.colima_environment(tmp_path, tmp_path / "tools", profile=profile)
    assert env["DOCKER_HOST"] == "unix://" + str(tmp_path / "colima" / profile / "docker.sock")
    assert ci.colima_argv(Path("/protected/colima"), "ssh", profile=profile)[1:3] == [
        "--profile",
        profile,
    ]
    rules = [*ci.lima_isolation_override()["portForwards"]]
    for guest, name in (
        ("/var/run/docker.sock", "docker.sock"),
        ("/var/run/containerd/containerd.sock", "containerd.sock"),
    ):
        rules.append(
            {"guestSocket": guest, "hostSocket": str(tmp_path / "colima" / profile / name)}
        )
    value = {
        "ssh": {"loadDotSSHPubKeys": False, "forwardAgent": False},
        "mounts": [],
        "portForwards": rules,
    }
    ci.validate_lima_isolation(value, tmp_path, profile=profile)
    rules[1]["hostSocket"] = str(tmp_path / "colima/unselected/docker.sock")
    with pytest.raises(ci.LocalCIError, match="management socket"):
        ci.validate_lima_isolation(value, tmp_path, profile=profile)
    with pytest.raises(ci.LocalCIError):
        ci.colima_environment(tmp_path, tmp_path / "tools", profile="unapproved")
    with pytest.raises(ci.LocalCIError):
        ci.colima_argv(Path("/protected/colima"), "ssh", profile="unapproved")
