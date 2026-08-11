#!/usr/bin/env python3
"""Bounded, shell-free Docker observation helpers for the future L2M bundle."""

from __future__ import annotations

import hashlib
import json
import os
import selectors
import stat
import subprocess
import time
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path

DOCKER = Path("/usr/bin/docker")
MAX_CALL_OUTPUT = 1_048_576
_PROCESS_HEADER_VARIANTS = {
    ("PID", "PPID", "SID", "STAT", "COMMAND"),
    ("PID", "PPID", "SID", "STAT", "COMM"),
}


class DockerInspectionError(RuntimeError):
    pass


@dataclass
class CommandBudget:
    docker_config_dir: Path
    max_calls: int = 32
    max_output_bytes: int = 8_388_608
    cleanup_reserved_calls: int = 10
    cleanup_reserved_output_bytes: int = 1_048_576
    max_work_wall_seconds: int = 270
    max_total_wall_seconds: int = 300
    calls: int = 0
    work_output_bytes: int = 0
    cleanup_output_bytes: int = 0
    started_monotonic: float = field(default_factory=time.monotonic)

    def __post_init__(self) -> None:
        if (
            self.max_calls < 1
            or not 0 <= self.cleanup_reserved_calls < self.max_calls
            or self.max_output_bytes < 2
            or not 1 <= self.cleanup_reserved_output_bytes < self.max_output_bytes
        ):
            raise DockerInspectionError("Docker budget contract is invalid")
        try:
            config_identity = self.docker_config_dir.lstat()
        except OSError:
            raise DockerInspectionError("Docker config root is unavailable") from None
        if (
            not self.docker_config_dir.is_absolute()
            or not stat.S_ISDIR(config_identity.st_mode)
            or config_identity.st_uid != os.getuid()
            or stat.S_IMODE(config_identity.st_mode) != 0o700
            or any(self.docker_config_dir.iterdir())
        ):
            raise DockerInspectionError("Docker config root is not fresh, private, and empty")

    def _validate_config_root(self) -> None:
        identity = self.docker_config_dir.lstat()
        if (
            not stat.S_ISDIR(identity.st_mode)
            or identity.st_uid != os.getuid()
            or stat.S_IMODE(identity.st_mode) != 0o700
            or any(self.docker_config_dir.iterdir())
        ):
            raise DockerInspectionError("Docker config root gained unapproved account state")

    @property
    def output_bytes(self) -> int:
        return self.work_output_bytes + self.cleanup_output_bytes

    def _execute(
        self,
        arguments: list[str],
        *,
        timeout_seconds: float,
        cleanup: bool = False,
        absolute_deadline_monotonic: float | None = None,
    ) -> tuple[int, bytes]:
        if not arguments or arguments[0] != str(DOCKER):
            raise DockerInspectionError("only the exact Docker executable is allowed")
        self._validate_config_root()
        if self.calls + 1 > self.max_calls:
            raise DockerInspectionError("Docker call cap exceeded")
        if not cleanup and self.calls + 1 > self.max_calls - self.cleanup_reserved_calls:
            raise DockerInspectionError("Docker cleanup-call reserve would be consumed")
        work_output_limit = self.max_output_bytes - self.cleanup_reserved_output_bytes
        if cleanup:
            if self.output_bytes >= self.max_output_bytes:
                raise DockerInspectionError("Docker aggregate output cap is exhausted")
        elif self.work_output_bytes >= work_output_limit:
            raise DockerInspectionError("Docker cleanup-output reserve would be consumed")
        wall_cap = self.max_total_wall_seconds if cleanup else self.max_work_wall_seconds
        now = time.monotonic()
        remaining = wall_cap - (now - self.started_monotonic)
        if absolute_deadline_monotonic is not None:
            remaining = min(remaining, absolute_deadline_monotonic - now)
        if remaining <= 0:
            raise DockerInspectionError("Docker wall-time cap exceeded")
        bounded_timeout = min(timeout_seconds, remaining)
        self.calls += 1
        try:
            process = subprocess.Popen(
                arguments,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                shell=False,
                bufsize=0,
                env={
                    "PATH": "/usr/bin:/bin",
                    "HOME": str(self.docker_config_dir),
                    "DOCKER_CONFIG": str(self.docker_config_dir),
                    "DOCKER_HOST": "unix:///var/run/docker.sock",
                    "LANG": "C.UTF-8",
                    "LC_ALL": "C.UTF-8",
                },
            )
        except OSError:
            raise DockerInspectionError("bounded Docker process could not start") from None
        if process.stdout is None:  # pragma: no cover - PIPE guarantees the handle
            process.kill()
            process.wait()
            raise DockerInspectionError("Docker output pipe is unavailable")
        deadline = time.monotonic() + bounded_timeout
        chunks: list[bytes] = []
        call_bytes = 0
        eof = False
        selector: selectors.BaseSelector | None = None
        try:
            selector = selectors.DefaultSelector()
            selector.register(process.stdout, selectors.EVENT_READ)
            while not eof:
                wait_seconds = deadline - time.monotonic()
                if wait_seconds <= 0:
                    process.kill()
                    process.wait()
                    raise DockerInspectionError("bounded Docker call timed out")
                events = selector.select(wait_seconds)
                if not events:
                    process.kill()
                    process.wait()
                    raise DockerInspectionError("bounded Docker call timed out")
                for key, _ in events:
                    remaining_call = MAX_CALL_OUTPUT - call_bytes
                    remaining_aggregate = (
                        self.max_output_bytes - self.output_bytes
                        if cleanup
                        else work_output_limit - self.work_output_bytes
                    )
                    if remaining_call <= 0 or remaining_aggregate <= 0:
                        process.kill()
                        process.wait()
                        raise DockerInspectionError("Docker output cap exceeded")
                    read_size = min(65_536, remaining_call, remaining_aggregate)
                    chunk = os.read(key.fd, read_size)
                    if not chunk:
                        eof = True
                        break
                    call_bytes += len(chunk)
                    if cleanup:
                        self.cleanup_output_bytes += len(chunk)
                    else:
                        self.work_output_bytes += len(chunk)
                    if (
                        call_bytes >= MAX_CALL_OUTPUT
                        or self.output_bytes > self.max_output_bytes
                        or (not cleanup and self.work_output_bytes >= work_output_limit)
                    ):
                        process.kill()
                        process.wait()
                        raise DockerInspectionError("Docker output cap exceeded")
                    chunks.append(chunk)
            return_code = process.wait(timeout=max(0.001, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            raise DockerInspectionError("bounded Docker call timed out") from None
        except BaseException as error:
            if process.poll() is None:
                with suppress(OSError):
                    process.kill()
                with suppress(OSError, subprocess.SubprocessError):
                    process.wait()
            if isinstance(error, (DockerInspectionError, KeyboardInterrupt, SystemExit)):
                raise
            raise DockerInspectionError("bounded Docker observation failed") from None
        finally:
            if selector is not None:
                selector.close()
            process.stdout.close()
        output = b"".join(chunks)
        self._validate_config_root()
        if time.monotonic() - self.started_monotonic > wall_cap:
            raise DockerInspectionError("Docker wall-time cap exceeded")
        return return_code, output

    def run(
        self,
        arguments: list[str],
        *,
        timeout_seconds: float,
        cleanup: bool = False,
        absolute_deadline_monotonic: float | None = None,
    ) -> bytes:
        return_code, output = self._execute(
            arguments,
            timeout_seconds=timeout_seconds,
            cleanup=cleanup,
            absolute_deadline_monotonic=absolute_deadline_monotonic,
        )
        if return_code != 0:
            raise DockerInspectionError("bounded Docker call failed")
        return output

    def probe(
        self,
        arguments: list[str],
        *,
        timeout_seconds: float,
        absolute_deadline_monotonic: float | None = None,
    ) -> tuple[int, bytes]:
        return self._execute(
            arguments,
            timeout_seconds=timeout_seconds,
            absolute_deadline_monotonic=absolute_deadline_monotonic,
        )


def _strict_json(encoded: bytes) -> object:
    try:
        return json.loads(encoded)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise DockerInspectionError("Docker JSON output is invalid") from None


def _required_runtime_version(value: object, *, component: str) -> str:
    if not isinstance(value, str) or not 1 <= len(value) <= 128:
        raise DockerInspectionError(f"required {component} identity is unavailable")
    return value


def _optional_runtime_version(value: object, *, component: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not 1 <= len(value) <= 128:
        raise DockerInspectionError(f"optional {component} identity is invalid")
    return value


def initial_runtime_observation(
    budget: CommandBudget,
    *,
    absolute_deadline_monotonic: float | None = None,
) -> tuple[dict[str, object], dict[str, object]]:
    endpoint_raw = budget.run(
        [str(DOCKER), "context", "inspect", "--format", "{{json .Endpoints.docker.Host}}"],
        timeout_seconds=15,
        absolute_deadline_monotonic=absolute_deadline_monotonic,
    )
    endpoint = _strict_json(endpoint_raw)
    if endpoint != "unix:///var/run/docker.sock":
        raise DockerInspectionError("Docker daemon endpoint is not the reviewed local socket")
    version_raw = budget.run(
        [str(DOCKER), "version", "--format", "{{json .}}"],
        timeout_seconds=15,
        absolute_deadline_monotonic=absolute_deadline_monotonic,
    )
    version = _strict_json(version_raw)
    if not isinstance(version, dict):
        raise DockerInspectionError("Docker version output is not an object")
    client = version.get("Client")
    server = version.get("Server")
    if not isinstance(client, dict) or not isinstance(server, dict):
        raise DockerInspectionError("Docker client/server identity is incomplete")
    components = server.get("Components")
    if not isinstance(components, list):
        raise DockerInspectionError("Docker component identities are unavailable")
    component_versions: dict[str, list[object]] = {}
    for item in components:
        if isinstance(item, dict) and isinstance(item.get("Name"), str):
            component_versions.setdefault(item["Name"], []).append(item.get("Version"))
    required_components: dict[str, str] = {}
    for name in ("containerd", "runc"):
        matches = component_versions.get(name, [])
        if len(matches) != 1:
            raise DockerInspectionError(f"required {name} identity is unavailable")
        required_components[name] = _required_runtime_version(matches[0], component=name)
    client_version = _required_runtime_version(client.get("Version"), component="Docker client")
    server_version = _required_runtime_version(server.get("Version"), component="Docker server")
    buildkit_matches = component_versions.get("buildkit", [])
    if len(buildkit_matches) > 1:
        raise DockerInspectionError("optional buildkit identity is ambiguous")
    buildkit_version = _optional_runtime_version(
        buildkit_matches[0] if buildkit_matches else None,
        component="buildkit",
    )
    container_ids = budget.run(
        [str(DOCKER), "ps", "-aq", "--no-trunc"],
        timeout_seconds=15,
        absolute_deadline_monotonic=absolute_deadline_monotonic,
    ).splitlines()
    image_ids = budget.run(
        [str(DOCKER), "image", "ls", "-q", "--no-trunc"],
        timeout_seconds=15,
        absolute_deadline_monotonic=absolute_deadline_monotonic,
    ).splitlines()
    buildx_status, buildx_raw = budget.probe(
        [str(DOCKER), "buildx", "version"],
        timeout_seconds=15,
        absolute_deadline_monotonic=absolute_deadline_monotonic,
    )
    initial_canonical = json.dumps(
        {
            "container_ids": sorted(line.decode("ascii", "strict") for line in container_ids),
            "image_ids": sorted(line.decode("ascii", "strict") for line in image_ids),
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    buildx_version = _optional_runtime_version(
        buildx_raw.decode("utf-8", "strict").strip() if buildx_status == 0 else None,
        component="buildx",
    )
    public: dict[str, object] = {
        "docker_client_version": client_version,
        "docker_server_version": server_version,
        "containerd_version": required_components["containerd"],
        "runc_version": required_components["runc"],
        "buildx_version": buildx_version,
        "buildkit_version": buildkit_version,
        "docker_service_active": True,
        "docker_endpoint_kind": "local-unix-socket",
        "initial_container_count": len(container_ids),
        "initial_image_count": len(set(image_ids)),
        "initial_state_sha256": hashlib.sha256(initial_canonical).hexdigest(),
    }
    private: dict[str, object] = {
        "version": version,
        "endpoint_sha256": hashlib.sha256(str(endpoint).encode()).hexdigest(),
        "initial_state_sha256": hashlib.sha256(initial_canonical).hexdigest(),
    }
    return public, private


def inspect_container(
    budget: CommandBudget,
    container_id: str,
    *,
    cleanup: bool = False,
    absolute_deadline_monotonic: float | None = None,
) -> dict[str, object]:
    raw = budget.run(
        [str(DOCKER), "inspect", "--type", "container", container_id],
        timeout_seconds=15,
        cleanup=cleanup,
        absolute_deadline_monotonic=absolute_deadline_monotonic,
    )
    value = _strict_json(raw)
    if not isinstance(value, list) or len(value) != 1 or not isinstance(value[0], dict):
        raise DockerInspectionError("container inspect result is invalid")
    return value[0]


def sanitize_image_inspect(
    encoded: bytes,
    *,
    expected_reference: str,
    expected_config_digest: str,
) -> dict[str, object]:
    """Retain only immutable, nonsecret image identity fields."""

    value = _strict_json(encoded)
    if not isinstance(value, list) or len(value) != 1 or not isinstance(value[0], dict):
        raise DockerInspectionError("Docker image inspect result is invalid")
    row = value[0]
    repo_digests = row.get("RepoDigests")
    if (
        row.get("Id") != expected_config_digest
        or row.get("Os") != "linux"
        or row.get("Architecture") != "amd64"
        or not isinstance(repo_digests, list)
        or not 1 <= len(repo_digests) <= 16
        or any(not isinstance(item, str) or len(item) > 512 for item in repo_digests)
        or expected_reference not in repo_digests
    ):
        raise DockerInspectionError("pulled image identity drifted")
    return {
        "id": expected_config_digest,
        "repo_digests": sorted(set(repo_digests)),
        "os": "linux",
        "architecture": "amd64",
    }


def process_structure_report(encoded: bytes) -> dict[str, object]:
    """Reduce `docker top` to bounded structural evidence without raw process values."""

    try:
        lines = encoded.decode("utf-8", "strict").splitlines()
    except UnicodeDecodeError:
        raise DockerInspectionError("Docker process evidence is not UTF-8") from None
    if not lines or tuple(lines[0].split()) not in _PROCESS_HEADER_VARIANTS:
        raise DockerInspectionError("Docker process evidence header drifted")
    if not 4 <= len(lines) <= 65:
        raise DockerInspectionError("Docker process evidence count is outside the PID cap")
    rows: list[tuple[int, int, int, str, str]] = []
    for line in lines[1:]:
        parts = line.split()
        if len(parts) != 5:
            raise DockerInspectionError("Docker process evidence row drifted")
        try:
            pid, ppid, sid = (int(value) for value in parts[:3])
        except ValueError:
            raise DockerInspectionError("Docker process identity is invalid") from None
        if pid <= 0 or ppid < 0 or sid <= 0 or not parts[3] or not parts[4]:
            raise DockerInspectionError("Docker process evidence value is invalid")
        rows.append((pid, ppid, sid, parts[3], parts[4]))
    pids = {row[0] for row in rows}
    if len(pids) != len(rows):
        raise DockerInspectionError("Docker process evidence contains a duplicate PID")

    def parent_depth(pid: int) -> int:
        by_pid = {row[0]: row for row in rows}
        seen: set[int] = set()
        depth = 0
        current = pid
        while current in by_pid:
            if current in seen:
                raise DockerInspectionError("Docker process evidence contains a parent cycle")
            seen.add(current)
            parent = by_pid[current][1]
            if parent not in by_pid:
                break
            depth += 1
            current = parent
        return depth

    roots = [row for row in rows if row[1] not in pids]
    if len(roots) != 1:
        raise DockerInspectionError("Docker process evidence lacks one namespace root")
    root_pid = roots[0][0]
    normalized = [
        {"pid": pid, "ppid": ppid, "sid": sid, "stat": status, "comm": command}
        for pid, ppid, sid, status, command in sorted(rows)
    ]
    return {
        "process_count": len(rows),
        "max_parent_depth": max(parent_depth(pid) for pid in pids),
        "distinct_sid_count": len({row[2] for row in rows}),
        "reparented_session_leader_count": sum(
            1 for pid, ppid, sid, _, _ in rows if ppid == root_pid and pid == sid
        ),
        "structural_sha256": hashlib.sha256(
            json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
    }


def fixture_marker_report(encoded: bytes) -> dict[str, object]:
    """Reduce bounded fixture logs to exact nonsecret proof markers."""

    try:
        lines = encoded.decode("utf-8", "strict").splitlines()
    except UnicodeDecodeError:
        raise DockerInspectionError("fixture log is not UTF-8") from None
    applets_verified = any(line == "T07_APPLETS_VERIFIED=sh,setsid,sleep,ps,kill" for line in lines)
    pid_limit_markers = {
        line
        for line in lines
        if line
        in {
            "T07_PID_LIMIT_OBSERVED=grandchild-spawner",
            "T07_PID_LIMIT_OBSERVED=root-spawner",
        }
    }
    if not applets_verified or not pid_limit_markers:
        raise DockerInspectionError("fixture did not prove applets and PID-limit pressure")
    return {
        "applets_verified": True,
        "pid_limit_observed": True,
        "pid_limit_marker_count": len(pid_limit_markers),
        "log_sha256": hashlib.sha256(encoded).hexdigest(),
    }


def validate_containment_inspect(
    document: dict[str, object],
    *,
    fixture: Path,
    run_id: str,
    marker_alias: str,
    expected_image_id: str,
) -> None:
    host = document.get("HostConfig")
    config = document.get("Config")
    mounts = document.get("Mounts")
    if not isinstance(host, dict) or not isinstance(config, dict) or not isinstance(mounts, list):
        raise DockerInspectionError("container inspect sections are incomplete")
    restart = host.get("RestartPolicy")
    labels = config.get("Labels")
    tmpfs = host.get("Tmpfs")
    log_config = host.get("LogConfig")
    if (
        not isinstance(restart, dict)
        or not isinstance(labels, dict)
        or not isinstance(tmpfs, dict)
        or not isinstance(log_config, dict)
    ):
        raise DockerInspectionError("container policy sections are incomplete")
    expected = {
        "NetworkMode": "none",
        "IpcMode": "private",
        "CgroupnsMode": "private",
        "Privileged": False,
        "ReadonlyRootfs": True,
        "PidsLimit": 64,
        "NanoCpus": 1_000_000_000,
        "Memory": 536_870_912,
        "MemorySwap": 536_870_912,
        "ShmSize": 16_777_216,
        "Init": True,
    }
    if document.get("Image") != expected_image_id:
        raise DockerInspectionError("container immutable image ID drifted")
    if any(host.get(key) != value for key, value in expected.items()):
        raise DockerInspectionError("container resource or namespace policy drifted")
    if host.get("PidMode") not in {"", None} or restart.get("Name") != "no":
        raise DockerInspectionError("container PID or restart policy drifted")
    if set(host.get("CapDrop") or []) != {"ALL"}:
        raise DockerInspectionError("container capabilities were not fully dropped")
    if "no-new-privileges=true" not in set(host.get("SecurityOpt") or []):
        raise DockerInspectionError("container no-new-privileges policy drifted")
    expected_tmpfs_options = {"rw", "noexec", "nosuid", "nodev", "size=16777216"}
    if set(tmpfs) != {"/tmp", "/run"} or any(
        set(str(value).split(",")) != expected_tmpfs_options for value in tmpfs.values()
    ):
        raise DockerInspectionError("container tmpfs policy drifted")
    if log_config != {
        "Type": "local",
        "Config": {"max-file": "1", "max-size": "1m"},
    }:
        raise DockerInspectionError("container log quota drifted")
    if labels.get("giclab.t07.run") != run_id or labels.get("giclab.t07.marker") != marker_alias:
        raise DockerInspectionError("container ownership labels drifted")
    if len(mounts) != 1 or not isinstance(mounts[0], dict):
        raise DockerInspectionError("container mount count drifted")
    mount = mounts[0]
    if (
        mount.get("Type") != "bind"
        or mount.get("Source") != str(fixture)
        or mount.get("Destination") != "/opt/t07/adversarial-containment.sh"
        or mount.get("RW") is not False
    ):
        raise DockerInspectionError("container fixture mount drifted")
    if any("docker.sock" in str(value) or "podman.sock" in str(value) for value in mount.values()):
        raise DockerInspectionError("runtime socket mount is prohibited")
