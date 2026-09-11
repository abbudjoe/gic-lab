"""Exact-owned outer local CI launcher. No experimental Docker operation is allowed.

Dry-run is the default. Preflight is deliberately separate from preparation/run.
Never consult Docker credential stores or change the user's global context.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import platform
import plistlib
import re
import selectors
import shutil
import signal
import stat
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from giclab.harness.sira_storage import (
    _assert_no_symlink_components,
    diskutil_info_argv,
    retained_free_floor,
)

GIB = 1024**3
HOST_FLOOR = 8 * GIB
GIC_PROFILE = "gic-pr15-ci"
NO_AUTO_UPDATES = (
    "systemctl mask --now apt-daily.timer apt-daily-upgrade.timer "
    "apt-daily.service apt-daily-upgrade.service"
)


class LocalCIError(RuntimeError):
    pass


@dataclass(frozen=True)
class Limits:
    cpus: int = 4
    memory_bytes: int = 8 * GIB
    pids: int = 512
    gate_seconds: int = 21600
    preparation_seconds: int = 5400
    console_bytes: int = 256 * 1024**2
    result_bytes: int = GIB
    workspace_bytes: int = 4 * GIB
    preparation_disk_bytes: int = 4 * GIB

    def __post_init__(self):
        ceilings = (4, 8 * GIB, 512, 21600, 5400, 256 * 1024**2, GIB, 4 * GIB, 4 * GIB)
        if any(
            type(value) is not int or not 0 < value <= cap
            for value, cap in zip(asdict(self).values(), ceilings, strict=True)
        ):
            raise LocalCIError("CI limits cannot exceed the declared ceilings")


DEFAULT_LIMITS = Limits()


def colima_argv(binary: Path, operation: str, arguments=(), *, profile=GIC_PROFILE):
    """Use Colima's global selector for every GIC operation, including SSH.

    Positional names are not profile selectors for all Colima subcommands.
    No caller may supply another selector or silently use the default profile.
    """
    if (
        profile not in {GIC_PROFILE, "gic-pr15-clean-ci"}
        or not binary.is_absolute()
        or operation not in {"start", "stop", "status", "ssh"}
        or any(a in {"--profile", "-p"} or a.startswith("--profile=") for a in arguments)
    ):
        raise LocalCIError("explicit GIC profile operation required")
    return [str(binary), "--profile", profile, operation, *arguments]


def colima_configuration():
    """Supported Colima settings for the separate owner-authorized GIC VM.

    No filesystem creation, credential generation, or runtime contact on import.
    The caller must bind and verify the encrypted backing before applying these.
    """
    return {
        "cpu": 2,
        "memory": 6,
        "disk": 32,
        "rootDisk": 20,
        "arch": "aarch64",
        "vmType": "vz",
        "runtime": "docker",
        # Colima 0.10.3: null disables mounts; [] selects the home-directory
        # default (Config.MountsOrDefault / lima.newConfig). Never normalize it.
        "mounts": None,
        "autoActivate": False,
        "sshConfig": False,
        "forwardAgent": False,
        "portForwarder": "none",
        "binfmt": False,
        "rosetta": False,
        "nestedVirtualization": False,
        "kubernetes": {"enabled": False},
        "network": {
            "address": False,
            "mode": "shared",
            "preferredRoute": False,
            "hostAddresses": False,
        },
        "provision": [{"mode": "system", "script": NO_AUTO_UPDATES}],
    }


def validate_colima_configuration(value):
    """Check the effective supported config, including bootstrap update timers."""
    for name, expected in colima_configuration().items():
        if name not in value:
            raise LocalCIError(f"GIC Colima configuration missing: {name}")
        actual = value.get(name)
        if isinstance(expected, dict):
            if not isinstance(actual, dict) or any(
                type(actual.get(key)) is not type(item) or actual.get(key) != item
                for key, item in expected.items()
            ):
                raise LocalCIError(f"GIC Colima configuration differs: {name}")
        elif type(actual) is not type(expected) or actual != expected:
            raise LocalCIError(f"GIC Colima configuration differs: {name}")
    if value.get("forceDiskImage") not in (None, False):
        raise LocalCIError("unverified bootstrap override forbidden")


def lima_isolation_override():
    """Explicit GIC-only Lima override; no inherited template or default profile.

    Lima 2.2 derives a missing guestIPMustBeZero as true for 0.0.0.0.
    Colima 0.10.3 omits that field in its 'none' rule, leaving loopback exposed.
    The documented override is prepended to instance rules by Lima itself.
    """
    return {
        "portForwards": [
            {
                "guestIP": "0.0.0.0",
                "guestIPMustBeZero": False,
                "guestPortRange": [1, 65535],
                "proto": "any",
                "ignore": True,
            }
        ]
    }


def validate_lima_isolation(value, protected_root: Path, *, profile=GIC_PROFILE):
    """Inspect Lima's effective config, not just Colima's requested 'none'."""
    if value.get("mounts") or value.get("ssh", {}).get("loadDotSSHPubKeys") is not False:
        raise LocalCIError("Lima host mount or personal-key loading is forbidden")
    if value.get("ssh", {}).get("forwardAgent") is not False:
        raise LocalCIError("Lima agent forwarding is forbidden")
    if profile not in {GIC_PROFILE, "gic-pr15-clean-ci"}:
        raise LocalCIError("unapproved GIC profile")
    expected = lima_isolation_override()["portForwards"][0]
    blocked = False
    sockets = set()
    allowed = {
        "/var/run/docker.sock": protected_root / "colima" / profile / "docker.sock",
        "/var/run/containerd/containerd.sock": protected_root
        / "colima"
        / profile
        / "containerd.sock",
    }
    for rule in value.get("portForwards", []):
        guest_socket = rule.get("guestSocket")
        if guest_socket:
            if (
                guest_socket not in allowed
                or rule.get("hostSocket") != str(allowed[guest_socket])
                or rule.get("reverse")
            ):
                raise LocalCIError("Lima management socket binding differs")
            sockets.add(guest_socket)
        elif all(type(rule.get(k)) is type(v) and rule.get(k) == v for k, v in expected.items()):
            blocked = True
        elif not blocked:
            raise LocalCIError("Lima lacks explicit all-interface forwarding denial")
    if not blocked or sockets != set(allowed):
        raise LocalCIError("Lima forwarding policy or management sockets incomplete")


def colima_environment(protected_root: Path, tools: Path, *, profile=GIC_PROFILE):
    """Explicit private homes; never inherit the owner's Docker/SSH environment."""
    if profile not in {GIC_PROFILE, "gic-pr15-clean-ci"}:
        raise LocalCIError("unapproved GIC profile")
    _assert_no_symlink_components(protected_root, allow_missing_leaf=False)
    for relative in ("home", "colima", "colima/_lima", "docker", "cache", "tmp"):
        path = protected_root / relative
        _assert_no_symlink_components(path, allow_missing_leaf=False)
        meta = path.stat()
        if (
            not stat.S_ISDIR(meta.st_mode)
            or meta.st_uid != os.getuid()
            or stat.S_IMODE(meta.st_mode) != 0o700
            or meta.st_dev != protected_root.stat().st_dev
        ):
            raise LocalCIError("GIC runtime requires private protected homes")
    socket_path = protected_root / "colima" / profile / "docker.sock"
    if len(os.fsencode(socket_path)) >= 104:
        raise LocalCIError("GIC runtime Unix endpoint exceeds supported length")
    return {
        "HOME": str(protected_root / "home"),
        "PATH": str(tools / "bin")
        + os.pathsep
        + str(tools / "lima/bin")
        + ":/usr/bin:/bin:/usr/sbin:/sbin",
        "COLIMA_HOME": str(protected_root / "colima"),
        "LIMA_HOME": str(protected_root / "colima/_lima"),
        "COLIMA_CACHE_HOME": str(protected_root / "cache/colima"),
        "DOCKER_CONFIG": str(protected_root / "docker"),
        "DOCKER_HOST": "unix://" + str(socket_path),
        "XDG_CACHE_HOME": str(protected_root / "cache"),
        "TMPDIR": str(protected_root / "tmp"),
        "TMP": str(protected_root / "tmp"),
        "TEMP": str(protected_root / "tmp"),
        "LANG": "en_US.UTF-8",
    }


def observe_volume(mount: Path) -> dict:
    result = bounded_command(
        list(diskutil_info_argv(mount)), environment={"PATH": os.defpath}, timeout=15
    )
    if result["exit_code"]:
        raise LocalCIError("bound volume observation failed; no internal fallback")
    return plistlib.loads(result["output"].encode())


def startup_device():
    return Path("/System/Volumes/Data" if sys.platform == "darwin" else "/").stat().st_dev


@dataclass(frozen=True)
class ProjectStorage:
    """One locally pinned nonsecret storage destination, never runtime authority."""

    mount: Path
    root: Path
    volume_uuid: str
    container_reference: str
    mount_device: int
    mount_inode: int
    root_inode: int
    ownership_enabled: bool
    external_retained_floor_bytes: int

    @classmethod
    def load(cls, path: Path):
        _assert_no_symlink_components(path.parent, allow_missing_leaf=False)
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            meta = os.fstat(fd)
            if not stat.S_ISREG(meta.st_mode) or not 0 < meta.st_size <= 16384:
                raise LocalCIError("bounded local storage configuration required")
            value = json.loads(os.read(fd, 16385))
        finally:
            os.close(fd)
        if value.get("schema_version") != 1:
            raise LocalCIError("unsupported local storage configuration")
        selected = cls(
            **{
                name: Path(value[name]) if name in {"mount", "root"} else value[name]
                for name in cls.__dataclass_fields__
            }
        )
        selected.recheck()
        return selected

    def recheck(self):
        _assert_no_symlink_components(self.root, allow_missing_leaf=False)
        mount, root = self.mount.stat(), self.root.stat()
        if (
            self.root != self.mount / "GIC-Lab"
            or not os.path.ismount(self.mount)
            or mount.st_dev == startup_device()
            or (mount.st_dev, mount.st_ino, root.st_dev, root.st_ino)
            != (self.mount_device, self.mount_inode, self.mount_device, self.root_inode)
        ):
            raise LocalCIError("project mount identity changed; no internal fallback")
        value = observe_volume(self.mount)
        if (
            value.get("MountPoint") != str(self.mount)
            or value.get("VolumeUUID") != self.volume_uuid
            or value.get("APFSContainerReference") != self.container_reference
            or value.get("FilesystemType") != "apfs"
            or value.get("Internal") is not False
            or value.get("Locked") is not False
            or value.get("Writable") is not True
            or value.get("WritableVolume") is not True
            or value.get("GlobalPermissionsEnabled") != self.ownership_enabled
        ):
            raise LocalCIError("project volume binding differs; no internal fallback")
        capacity, free = value.get("APFSContainerSize"), value.get("APFSContainerFree")
        if type(capacity) is not int or type(free) is not int or not 0 <= free <= capacity:
            raise LocalCIError("allocatable APFS container capacity is unknown")
        if self.external_retained_floor_bytes != retained_free_floor(capacity):
            raise LocalCIError("external retained headroom differs from storage policy")
        available = os.statvfs(self.root)
        allocatable = min(free, available.f_bavail * available.f_frsize)
        if allocatable < self.external_retained_floor_bytes:
            raise LocalCIError("external retained storage headroom unavailable")
        return allocatable

    def destination(self, path: Path, *, missing_leaf=False):
        self.recheck()
        if not path.is_absolute() or not path.is_relative_to(self.root) or ".." in path.parts:
            raise LocalCIError("bulk destination lies outside the bound project volume")
        _assert_no_symlink_components(
            path.parent if missing_leaf else path, allow_missing_leaf=False
        )
        if path.exists() and path.is_symlink():
            raise LocalCIError("symlink bulk destination rejected")
        return path

    def fresh(self, role: str, name: str):
        if role not in {"tmp", "workspaces", "ci/inputs", "ci/results", "evidence/pr15"}:
            raise LocalCIError("unknown project storage role")
        if re.fullmatch(r"[a-zA-Z0-9-]{1,48}", name) is None:
            raise LocalCIError("invalid fresh storage name")
        parent = self.destination(self.root / role)
        fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            if os.fstat(fd).st_dev != self.mount_device:
                raise LocalCIError("storage parent changed before creation")
            os.mkdir(name, mode=0o700, dir_fd=fd)
        finally:
            os.close(fd)
        return self.destination(parent / name)

    def environment(self, run: Path):
        self.destination(run)
        values = {
            "TMPDIR": run / "tmp",
            "TMP": run / "tmp",
            "TEMP": run / "tmp",
            "UV_CACHE_DIR": self.root / "cache/uv",
            "UV_PYTHON_INSTALL_DIR": self.root / "cache/python",
            "PIP_CACHE_DIR": self.root / "cache/pip",
            "XDG_CACHE_HOME": self.root / "cache/xdg",
            "DENO_DIR": self.root / "cache/deno",
            "RUFF_CACHE_DIR": self.root / "cache/ruff",
            "MYPY_CACHE_DIR": self.root / "cache/mypy",
        }
        for path in set(values.values()):
            self.destination(path, missing_leaf=True)
            if not path.exists():
                parent = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
                try:
                    if os.fstat(parent).st_dev != self.mount_device:
                        raise LocalCIError("cache parent changed before creation")
                    os.mkdir(path.name, mode=0o700, dir_fd=parent)
                finally:
                    os.close(parent)
            self.destination(path)
        return {
            **{key: str(value) for key, value in values.items()},
            "PYTHONDONTWRITEBYTECODE": "1",
            "UV_PYTHON_DOWNLOADS": "never",
            "UV_OFFLINE": "1",
            "UV_PROJECT_ENVIRONMENT": str(run / "venv"),
            "GICLAB_CI_BULK_ROOT": str(self.root),
            "GICLAB_CI_BULK_DEVICE": str(self.mount_device),
            "GICLAB_CI_BULK_INODE": str(self.root_inode),
        }


def local_endpoint(path: Path) -> str:
    if any(
        key in os.environ
        for key in (
            "DOCKER_HOST",
            "DOCKER_CONTEXT",
            "DOCKER_TLS_VERIFY",
            "DOCKER_CERT_PATH",
        )
    ):
        raise LocalCIError("inherited Docker endpoint/context override must be removed")
    if not path.is_absolute() or not stat.S_ISSOCK(path.stat().st_mode):
        raise LocalCIError("explicit existing local Unix socket required")
    return "unix://" + str(path.resolve(strict=True))


def plan(endpoint: str, task_root: Path, limits: Limits = DEFAULT_LIMITS, *, storage=None) -> dict:
    if not endpoint.startswith("unix:///") or any(c in endpoint for c in "\n\r,"):
        raise LocalCIError("remote or malformed endpoint is forbidden")
    free = shutil.disk_usage(Path(__file__).resolve().parents[2]).free
    external = None if storage is None else storage.recheck()
    if storage is not None:
        storage.destination(task_root, missing_leaf=True)
    budget_free = free if storage is None else external
    budget_floor = HOST_FLOOR if storage is None else storage.external_retained_floor_bytes
    return {
        "classification": "outer-local-ci-infrastructure-only",
        "endpoint": endpoint,
        "docker_config": str(task_root / "docker-config"),
        "input_root": str(task_root / "input"),
        "results_root": str(task_root / "results"),
        "limits": asdict(limits),
        "host_free_bytes": free,
        "host_retained_floor_bytes": HOST_FLOOR,
        "host_headroom_available": free >= HOST_FLOOR,
        "external_available_bytes": external,
        "external_retained_floor_bytes": (
            None if storage is None else storage.external_retained_floor_bytes
        ),
        "runtime_backing_external_verified": False,
        "preparation_budget_filesystem": "unbound" if storage is None else "bound-external",
        "preparation_budget_headroom_available": budget_free
        >= budget_floor + limits.preparation_disk_bytes,
        "preparation_budget_required_free_bytes": budget_floor + limits.preparation_disk_bytes,
        "preparation_budget_deficit_bytes": max(
            0, budget_floor + limits.preparation_disk_bytes - budget_free
        ),
        # A declared 4-GiB ceiling is not an observation of unpacked layers,
        # dependency/build peaks, or available storage in the Linux VM.
        "preparation_storage_admitted": False,
        "preparation_storage_status": "unqualified-image-peak-and-backing-filesystem",
        "platform": "linux/arm64" if platform.machine() == "arm64" else "linux/amd64",
        "operations": [
            "version",
            "pull-pinned-ci-image",
            "build-ci-dependencies",
            "create",
            "start",
            "wait",
            "inspect-owned",
            "stop-owned",
            "kill-owned-if-still-running",
            "remove-owned",
        ],
        "metadata_command": ["version", "--format", "{{json .Server}}"],
        "cleanup_targets": "only immutable IDs returned to this exact launcher",
        "experimental_effects_authorized": False,
        "hosted_ci": "not-run-by-owner-instruction",
    }


def bounded_command(argv, *, environment, timeout, cap=65536):
    """Bound console bytes and descendants without a blocking communicate escape."""
    start = time.monotonic()
    output = bytearray()
    process = subprocess.Popen(
        argv,
        env=environment,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    assert process.stdout is not None
    try:
        os.set_blocking(process.stdout.fileno(), False)
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            while selector.get_map():
                if time.monotonic() - start >= timeout:
                    raise LocalCIError("outer CI command deadline exceeded")
                for key, _ in selector.select(min(0.1, timeout)):
                    try:
                        data = os.read(key.fd, min(65536, cap + 1 - len(output)))
                    except (BlockingIOError, InterruptedError):
                        continue
                    if not data:
                        selector.unregister(key.fileobj)
                    output.extend(data)
                    if len(output) > cap:
                        raise LocalCIError("outer CI console cap exceeded")
        code = process.wait(timeout=max(0.01, timeout - (time.monotonic() - start)))
        return {
            "exit_code": code,
            "output": output.decode(errors="replace"),
            "elapsed_seconds": time.monotonic() - start,
            "bytes": len(output),
        }
    finally:
        # A client may exit while descendants still hold the output pipe open.
        # The dedicated session is ours even after its leader exits.
        with contextlib.suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGTERM)
        if process.poll() is None:
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=2)
        process.stdout.close()


@dataclass(frozen=True)
class GuestVolumes:
    """Names bound to one recorded GIC volume-creation intent, never host paths.

    This validates rendering only; creation/inspection and exact-owned cleanup
    must still establish that these are the volumes returned to this launcher.
    """

    transaction: str

    def __post_init__(self):
        if not re.fullmatch(r"gic-pr15-ci-[0-9a-f]{16}", self.transaction):
            raise LocalCIError("explicit GIC guest-volume transaction required")

    def name(self, role: str):
        if role not in {"input", "work", "results"}:
            raise LocalCIError("unknown GIC guest-volume role")
        return self.transaction + "-" + role


def container_argv(image_id: str, volumes: GuestVolumes, limits=DEFAULT_LIMITS):
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", image_id):
        raise LocalCIError("execution requires an immutable local CI image ID")
    if not isinstance(volumes, GuestVolumes):
        raise LocalCIError("CI input/work/results must be exact-owned guest volumes")
    return [
        "create",
        "--network=none",
        "--user=10001:10001",
        "--read-only",
        "--init",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges:true",
        "--ipc=private",
        "--restart=no",
        "--pids-limit=" + str(limits.pids),
        "--cpus=" + str(limits.cpus),
        "--memory=" + str(limits.memory_bytes),
        "--memory-swap=" + str(limits.memory_bytes),
        "--ulimit=core=0:0",
        "--log-driver=local",
        "--log-opt=max-size=64m",
        "--log-opt=max-file=4",
        "--mount",
        f"type=volume,src={volumes.name('input')},dst=/input,readonly,volume-nocopy",
        "--mount",
        f"type=volume,src={volumes.name('results')},dst=/results,volume-nocopy",
        "--mount",
        f"type=volume,src={volumes.name('work')},dst=/work,volume-nocopy",
        "--tmpfs",
        "/tmp:rw,nosuid,nodev,size=67108864,uid=10001,gid=10001",
        "--env=HOME=/work/home",
        "--env=UV_OFFLINE=1",
        "--env=UV_PYTHON_DOWNLOADS=never",
        "--env=UV_CACHE_DIR=/work/uv-cache",
        "--env=TMPDIR=/work/tmp",
        image_id,
    ]


def checked_container_id(value: str) -> str:
    if not re.fullmatch(r"[0-9a-f]{64}", value):
        raise LocalCIError("missing or ambiguous exact container identity")
    return value


def exact_container_absent(result, container_id: str) -> bool:
    checked_container_id(container_id)
    return (
        result["exit_code"] == 1
        and re.fullmatch(
            r"\s*(?:error: no such object: |error response from daemon: no such container: )"
            + re.escape(container_id)
            + r"\s*",
            result["output"],
            re.IGNORECASE,
        )
        is not None
    )


def validate_container_isolation(
    value, container_id, image_id, volumes, limits, *, preparation=False
):
    """Admission over observed Docker fields, before any container process starts."""
    checked_container_id(container_id)
    host = value["HostConfig"]
    config = value["Config"]
    expected_caps = ["CAP_CHOWN"] if preparation else []
    if (
        value["Id"] != container_id
        or value["Image"] != image_id
        or host["NetworkMode"] != "none"
        or not host["ReadonlyRootfs"]
        or host["Privileged"]
        or host["CapDrop"] != ["ALL"]
        or (host["CapAdd"] or []) != expected_caps
        or config["User"] != ("0:0" if preparation else "10001:10001")
        or host["Memory"] != limits.memory_bytes
        or host["MemorySwap"] != limits.memory_bytes
        or host["NanoCpus"] != limits.cpus * 1_000_000_000
        or host["PidsLimit"] != limits.pids
        or host["SecurityOpt"] != ["no-new-privileges:true"]
        or host["IpcMode"] != "private"
        or host["PidMode"] == "host"
        or not host["Init"]
        or host["Devices"]
    ):
        raise LocalCIError("observed CI container restriction differs")
    mounts = value["Mounts"]
    if len(mounts) != 3 or {m["Destination"] for m in mounts} != {"/input", "/work", "/results"}:
        raise LocalCIError("observed CI volume set differs")
    for mount in mounts:
        role = mount["Destination"].removeprefix("/")
        if (
            mount["Type"] != "volume"
            or mount["Name"] != volumes.name(role)
            or mount["RW"] != (preparation or role != "input")
        ):
            raise LocalCIError("observed CI volume ownership or mode differs")


def run_owned_container(command, create_argv, *, admit, collect, record):
    """One launch; remove an executed container only after verified export.

    command is the narrow outer client channel, also exercised with deterministic
    fake responses. No experimental path imports this launcher.
    """
    container_id = None
    start_attempted = False
    record.update(
        {"create_attempts": 1, "cleanup": "unresolved", "id": None, "export_verified": False}
    )
    try:
        created = command(create_argv, timeout=30)
        if created["exit_code"] != 0:
            raise LocalCIError("container creation failed or is ambiguous; do not retry")
        container_id = checked_container_id(created["output"].strip())
        record["id"] = container_id
        admit(container_id)
        # A failed acknowledgement does not prove that execution never started.
        start_attempted = True
        started = command(["start", container_id], timeout=30)
        if started["exit_code"] != 0:
            raise LocalCIError("owned CI container failed to start")
        waited = command(["wait", container_id], timeout=DEFAULT_LIMITS.gate_seconds)
        if waited["exit_code"] != 0 or not waited["output"].strip().isdigit():
            raise LocalCIError("owned CI container wait failed")
        record["test_exit_code"] = int(waited["output"].strip())
        collect(container_id)
        record["export_verified"] = True
        if record["test_exit_code"] != 0:
            raise LocalCIError("container gate failed; evidence retained")
    except BaseException as error:
        record["primary_error_type"] = type(error).__name__
        raise
    finally:
        if container_id is not None:

            def state():
                inspected = command(["inspect", "--format", "{{json .}}", container_id], timeout=15)
                if inspected["exit_code"] != 0:
                    raise LocalCIError("owned CI cleanup inspection unavailable")
                value = json.loads(inspected["output"])
                if value.get("Id") != container_id:
                    raise LocalCIError("cleanup container identity drifted")
                return value["State"]

            if state()["Running"]:
                command(["stop", "--time", "10", container_id], timeout=15)
                if state()["Running"]:
                    killed = command(["kill", container_id], timeout=15)
                    if killed["exit_code"] != 0 or state()["Running"]:
                        raise LocalCIError("owned CI container termination unresolved")
            if start_attempted and not record["export_verified"]:
                # Stop effects, retain possible results and the immutable ID.
                # No return here: the original failure must still propagate.
                record["cleanup"] = "exact-id-stopped-export-unresolved"
            else:
                removed = command(["rm", container_id], timeout=15)
                if removed["exit_code"] != 0:
                    raise LocalCIError("owned CI container removal unresolved")
                absent = command(["inspect", "--format", "{{.Id}}", container_id], timeout=15)
                if not exact_container_absent(absent, container_id):
                    raise LocalCIError("owned CI container absence unproven")
                record["cleanup"] = "exact-id-absent"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--endpoint", type=Path, required=True)
    parser.add_argument("--record-root", type=Path, required=True)
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument(
        "--storage-config",
        type=Path,
        default=(Path(__file__).resolve().parents[2] / ".tools/local-ci-storage.json"),
    )
    args = parser.parse_args()
    storage = ProjectStorage.load(args.storage_config)
    endpoint = local_endpoint(args.endpoint)
    record = storage.destination(args.record_root, missing_leaf=True)
    if record.exists():
        raise LocalCIError("record root must be fresh")
    launch_plan = plan(endpoint, record, storage=storage)
    # A plan is always published before any daemon contact.
    if not args.preflight:
        print(json.dumps(launch_plan, indent=2, sort_keys=True))
        return
    storage.destination(record, missing_leaf=True)
    record.mkdir(mode=0o700)
    config = record / "docker-config"
    config.mkdir(mode=0o700)
    (config / "config.json").write_text("{}\n")
    (record / "plan.json").write_text(json.dumps(launch_plan, indent=2, sort_keys=True) + "\n")
    docker = shutil.which("docker")
    if docker is None:
        raise LocalCIError("configured Docker client is unavailable; no installation permitted")
    environment = {"PATH": os.defpath, "HOME": str(record), "DOCKER_CONFIG": str(config)}
    argv = [docker, "--config", str(config), "--host", endpoint, *launch_plan["metadata_command"]]
    result = bounded_command(argv, environment=environment, timeout=15)
    storage.recheck()
    (record / "metadata.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    if result["exit_code"] != 0:
        raise LocalCIError("local runtime metadata unavailable; preserved exact new result")
    server = json.loads(result["output"])
    if server.get("Os") != "linux" or server.get("Arch") not in {"arm64", "aarch64"}:
        raise LocalCIError("runtime is not the selected native Linux arm64 platform")
    if not launch_plan["preparation_storage_admitted"]:
        raise LocalCIError(
            "runtime metadata is usable; preparation storage remains unqualified "
            f"(declared-budget deficit={launch_plan['preparation_budget_deficit_bytes']} bytes)"
        )
    print(
        json.dumps(
            {
                "runtime": "usable",
                "version": server.get("Version"),
                "arch": server.get("Arch"),
                "preparation": "not-run",
            }
        )
    )


if __name__ == "__main__":
    main()
