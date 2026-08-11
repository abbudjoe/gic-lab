"""Future one-shot Lambda/Jupyter bootstrap for the T07 bounded smoke.

Importing this file is inert.  The executable path requires a fresh, separately
authorized binding, a fresh remote root, and a secret file supplied outside the
bundle.  It never performs a Lambda mutation; the user remains responsible for the
manual console lifecycle in the bound runbook.
"""

from __future__ import annotations

import argparse
import hashlib
import http.client
import importlib.util
import json
import os
import re
import selectors
import shutil
import stat
import subprocess
import sys
import tarfile
import time
import urllib.parse
import zipfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from typing import Final, cast

MAX_PLAN_BYTES: Final = 1_048_576
MAX_AUTHORIZATION_BYTES: Final = 65_536
MAX_COMMAND_OUTPUT_BYTES: Final = 33_554_432
MAX_DOWNLOAD_BYTES: Final = 2_147_483_648
MAX_EVIDENCE_BYTES: Final = 268_435_456
MAX_EVIDENCE_FILES: Final = 4_096
MIN_REMOTE_FREE_BYTES: Final = 34_359_738_368
HARD_PROVIDER_WALL_SECONDS: Final = 3_600
TERMINATION_HEADROOM_SECONDS: Final = 300
_HEX40 = re.compile(r"^[a-f0-9]{40}$")
_HEX64 = re.compile(r"^[a-f0-9]{64}$")
_IMAGE_ID = re.compile(r"^sha256:[a-f0-9]{64}$")
_AUTHORIZATION = re.compile(r"^AUTH-T07-BOUNDED-SIRA-SMOKE-V1-[A-Z0-9._-]{3,80}$")


class BootstrapError(RuntimeError):
    """The one-shot bounded bootstrap failed closed."""


@dataclass(frozen=True, slots=True)
class CommandResult:
    argv: tuple[str, ...]
    returncode: int
    stdout: bytes
    stderr: bytes
    elapsed_seconds: float


class CommandRunner:
    """Shell-free subprocess runner with one monotonic deadline and output cap."""

    def __init__(
        self,
        *,
        deadline: float,
        output_cap: int = MAX_COMMAND_OUTPUT_BYTES,
        max_calls: int = 128,
    ) -> None:
        self.deadline = deadline
        self.output_cap = output_cap
        self.max_calls = max_calls
        self.call_count = 0
        self.output_bytes = 0

    def remaining(self) -> float:
        value = self.deadline - time.monotonic()
        if value <= 0:
            raise BootstrapError("bootstrap deadline is exhausted")
        return value

    def run(
        self,
        argv: Sequence[str],
        *,
        cwd: Path,
        timeout: float | None = None,
        check: bool = True,
    ) -> CommandResult:
        command = tuple(argv)
        if not command or any(not isinstance(item, str) or not item for item in command):
            raise BootstrapError("command array is invalid")
        if self.call_count >= self.max_calls:
            raise BootstrapError("bounded command call cap is exhausted")
        self.call_count += 1
        allowed = self.remaining()
        if timeout is not None:
            if not isinstance(timeout, (int, float)) or timeout <= 0:
                raise BootstrapError("command timeout is outside the remaining deadline")
            allowed = min(float(timeout), allowed)
        environment = {
            "HOME": str(cwd),
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
            "PYTHONDONTWRITEBYTECODE": "1",
        }
        started = time.monotonic()
        try:
            process = subprocess.Popen(
                command,
                cwd=cwd,
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=False,
            )
        except OSError:
            raise BootstrapError("bounded command could not start") from None
        selector = selectors.DefaultSelector()
        if process.stdout is None or process.stderr is None:
            process.kill()
            process.wait()
            selector.close()
            raise BootstrapError("bounded command pipes are unavailable")
        selector.register(process.stdout, selectors.EVENT_READ, "stdout")
        selector.register(process.stderr, selectors.EVENT_READ, "stderr")
        output = {"stdout": bytearray(), "stderr": bytearray()}
        try:
            while selector.get_map():
                elapsed = time.monotonic() - started
                if elapsed >= allowed:
                    process.kill()
                    raise BootstrapError("bounded command exceeded its wall limit")
                for key, _ in selector.select(min(0.1, allowed - elapsed)):
                    chunk = os.read(key.fd, 65_536)
                    if not chunk:
                        selector.unregister(key.fileobj)
                        continue
                    output[key.data].extend(chunk)
                    self.output_bytes += len(chunk)
                    if self.output_bytes > self.output_cap:
                        process.kill()
                        raise BootstrapError("bounded command output exceeded its aggregate cap")
            returncode = process.wait(timeout=max(0.1, allowed - (time.monotonic() - started)))
        except BootstrapError:
            process.kill()
            process.wait()
            raise
        except (OSError, subprocess.SubprocessError):
            process.kill()
            process.wait()
            raise BootstrapError("bounded command supervision failed") from None
        finally:
            selector.close()
        result = CommandResult(
            command,
            returncode,
            bytes(output["stdout"]),
            bytes(output["stderr"]),
            time.monotonic() - started,
        )
        if check and result.returncode != 0:
            raise BootstrapError("bounded command returned failure")
        return result


def _load_contract(path: Path) -> ModuleType:
    resolved = path.resolve(strict=True)
    if resolved.is_symlink() or not resolved.is_file():
        raise BootstrapError("bounded contract module is unsafe")
    specification = importlib.util.spec_from_file_location("t07_bounded_contract", resolved)
    if specification is None or specification.loader is None:
        raise BootstrapError("bounded contract module cannot be loaded")
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


def _strict_json(encoded: bytes, *, context: str) -> dict[str, object]:
    def pairs(items: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in items:
            if key in result:
                raise BootstrapError(f"{context} contains a duplicate key")
            result[key] = value
        return result

    try:
        value = json.loads(encoded, object_pairs_hook=pairs)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise BootstrapError(f"{context} is not strict JSON") from None
    if not isinstance(value, dict):
        raise BootstrapError(f"{context} must be an object")
    return value


def _read_regular(path: Path, *, max_bytes: int) -> bytes:
    try:
        linked = path.lstat()
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except OSError:
        raise BootstrapError("required bootstrap input is unavailable") from None
    try:
        opened = os.fstat(descriptor)
        if (
            not stat.S_ISREG(linked.st_mode)
            or stat.S_ISLNK(linked.st_mode)
            or linked.st_nlink != 1
            or (linked.st_dev, linked.st_ino) != (opened.st_dev, opened.st_ino)
            or opened.st_size > max_bytes
        ):
            raise BootstrapError("required bootstrap input identity is unsafe")
        output = bytearray()
        while True:
            chunk = os.read(descriptor, min(65_536, max_bytes + 1 - len(output)))
            if not chunk:
                break
            output.extend(chunk)
            if len(output) > max_bytes:
                raise BootstrapError("required bootstrap input exceeds its cap")
        if len(output) != opened.st_size:
            raise BootstrapError("required bootstrap input changed while held")
        return bytes(output)
    finally:
        os.close(descriptor)


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _parse_utc(value: object, *, context: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise BootstrapError(f"{context} is not an exact UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        raise BootstrapError(f"{context} is malformed") from None
    return parsed


def validate_authorization(
    encoded: bytes,
    *,
    expected_sha256: str,
    plan_sha256: str,
    contract: ModuleType,
) -> dict[str, object]:
    if _HEX64.fullmatch(expected_sha256) is None or _sha256(encoded) != expected_sha256:
        raise BootstrapError("authorization file hash differs from the supplied binding")
    document = _strict_json(encoded, context="authorization")
    expected_keys = {
        "schema_version",
        "authorized",
        "authorization_reference",
        "execution_commit",
        "plan_id",
        "plan_sha256",
        "host_run_id",
        "expires_at_utc",
        "provider_launch_at_utc",
        "pricing",
        "user_present",
        "manual_termination_path_confirmed",
    }
    reference = document.get("authorization_reference")
    pricing = document.get("pricing")
    if (
        set(document) != expected_keys
        or document.get("schema_version") != "0.1.0"
        or document.get("authorized") is not True
        or not isinstance(reference, str)
        or _AUTHORIZATION.fullmatch(reference) is None
        or reference.endswith("-PENDING")
        or document.get("plan_id") != contract.PLAN_ID
        or document.get("host_run_id") != contract.HOST_RUN_ID
        or document.get("plan_sha256") != plan_sha256
        or not isinstance(document.get("execution_commit"), str)
        or _HEX40.fullmatch(str(document["execution_commit"])) is None
        or document.get("user_present") is not True
        or document.get("manual_termination_path_confirmed") is not True
        or pricing
        != {
            "model": contract.MODEL,
            "service_tier": "standard",
            "input_usd_per_million": 2.5,
            "cached_input_usd_per_million": 1.25,
            "output_usd_per_million": 10.0,
            "lambda_cents_per_hour": 129,
        }
    ):
        raise BootstrapError("authorization contract is incomplete or drifted")
    now = datetime.now(UTC)
    launch = _parse_utc(document.get("provider_launch_at_utc"), context="provider launch time")
    expiry = _parse_utc(document.get("expires_at_utc"), context="authorization expiry")
    elapsed = (now - launch).total_seconds()
    if not 0 <= elapsed < HARD_PROVIDER_WALL_SECONDS or now >= expiry:
        raise BootstrapError("authorization or provider wall is expired")
    if HARD_PROVIDER_WALL_SECONDS - elapsed <= TERMINATION_HEADROOM_SECONDS:
        raise BootstrapError("provider termination headroom is exhausted")
    return document


def _validate_secret_file(path: Path, *, forbidden_roots: Sequence[Path]) -> None:
    try:
        linked = path.lstat()
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except OSError:
        raise BootstrapError("SIRA secret file is unavailable") from None
    try:
        opened = os.fstat(descriptor)
        resolved = path.resolve(strict=True)
        if (
            not stat.S_ISREG(linked.st_mode)
            or stat.S_ISLNK(linked.st_mode)
            or linked.st_nlink != 1
            or (linked.st_dev, linked.st_ino) != (opened.st_dev, opened.st_ino)
            or not 0 < opened.st_size <= 16_384
            or stat.S_IMODE(opened.st_mode) & 0o077
            or any(root == resolved or root in resolved.parents for root in forbidden_roots)
        ):
            raise BootstrapError("SIRA secret file contract failed")
    finally:
        os.close(descriptor)


def _download_exact(url: str, destination: Path, *, size: int, sha256: str) -> None:
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.query or parsed.fragment:
        raise BootstrapError("download URL is outside the HTTPS artifact contract")
    connection = http.client.HTTPSConnection(parsed.hostname, timeout=60)
    try:
        target = urllib.parse.urlunsplit(("", "", parsed.path, "", ""))
        connection.request(
            "GET",
            target,
            headers={"Accept": "application/octet-stream", "User-Agent": "gic-lab-t07/1"},
        )
        response = connection.getresponse()
        if response.status != 200 or response.getheader("Location") is not None:
            raise BootstrapError("artifact download did not return an exact 200 response")
        digest = hashlib.sha256()
        written = 0
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(destination, flags, 0o400)
        try:
            while chunk := response.read(65_536):
                written += len(chunk)
                if written > size or written > MAX_DOWNLOAD_BYTES:
                    raise BootstrapError("artifact download exceeded its exact byte contract")
                digest.update(chunk)
                os.write(descriptor, chunk)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    finally:
        connection.close()
    if written != size or digest.hexdigest() != sha256:
        raise BootstrapError("artifact download identity drifted")


def _copy_exact(source: Path, destination: Path, *, sha256: str) -> None:
    encoded = _read_regular(source, max_bytes=4_194_304)
    if _sha256(encoded) != sha256:
        raise BootstrapError("bundle input hash drifted")
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(destination, flags, 0o400)
    try:
        os.write(descriptor, encoded)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _extract_git_archive(archive: Path, destination: Path) -> None:
    destination.mkdir(mode=0o700, exist_ok=False)
    with tarfile.open(archive, "r:") as source:
        members = source.getmembers()
        for member in members:
            candidate = (destination / member.name).resolve(strict=False)
            if (
                destination.resolve() not in candidate.parents
                or member.issym()
                or member.islnk()
                or member.isdev()
                or member.isfifo()
            ):
                raise BootstrapError("SiRA archive contains an unsafe member")
        source.extractall(destination)


def _write_json(path: Path, value: object) -> None:
    encoded = json.dumps(value, allow_nan=False, indent=2, sort_keys=True).encode() + b"\n"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o600)
    try:
        os.write(descriptor, encoded)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_bytes(path: Path, encoded: bytes, *, cap: int = MAX_COMMAND_OUTPUT_BYTES) -> None:
    if len(encoded) > cap:
        raise BootstrapError("bounded evidence output exceeds its file cap")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o600)
    try:
        os.write(descriptor, encoded)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _assert_remote_capacity(root: Path) -> None:
    free = shutil.disk_usage(root.parent).free
    if free < MIN_REMOTE_FREE_BYTES:
        raise BootstrapError("remote root has insufficient free space")


def _artifact_map(plan: Mapping[str, object]) -> dict[str, tuple[int, str]]:
    implementation = plan.get("implementation")
    if not isinstance(implementation, Mapping):
        raise BootstrapError("plan implementation binding is unavailable")
    artifacts = implementation.get("artifacts")
    if not isinstance(artifacts, list):
        raise BootstrapError("plan implementation artifacts are unavailable")
    output: dict[str, tuple[int, str]] = {}
    for raw in artifacts:
        if not isinstance(raw, Mapping):
            raise BootstrapError("plan implementation artifact is invalid")
        path, size, digest = raw.get("path"), raw.get("bytes"), raw.get("sha256")
        if (
            not isinstance(path, str)
            or not isinstance(size, int)
            or not isinstance(digest, str)
            or _HEX64.fullmatch(digest) is None
        ):
            raise BootstrapError("plan implementation artifact identity is invalid")
        output[path] = (size, digest)
    return output


def prepare_build_context(
    *,
    bundle_root: Path,
    work_root: Path,
    plan: Mapping[str, object],
    contract: ModuleType,
    runner: CommandRunner,
) -> Path:
    source_checkout = work_root / "source-checkout"
    runner.run(
        (
            "/usr/bin/git",
            "clone",
            "--no-checkout",
            "https://github.com/sailing-lab/sira.git",
            str(source_checkout),
        ),
        cwd=work_root,
        timeout=min(600, runner.remaining()),
    )
    runner.run(
        (
            "/usr/bin/git",
            "-C",
            str(source_checkout),
            "checkout",
            "--detach",
            contract.UPSTREAM_COMMIT,
        ),
        cwd=work_root,
        timeout=min(120, runner.remaining()),
    )
    head = (
        runner.run(
            ("/usr/bin/git", "-C", str(source_checkout), "rev-parse", "HEAD"),
            cwd=work_root,
            timeout=min(30, runner.remaining()),
        )
        .stdout.decode()
        .strip()
    )
    tree = (
        runner.run(
            ("/usr/bin/git", "-C", str(source_checkout), "rev-parse", "HEAD^{tree}"),
            cwd=work_root,
            timeout=min(30, runner.remaining()),
        )
        .stdout.decode()
        .strip()
    )
    status = runner.run(
        (
            "/usr/bin/git",
            "-C",
            str(source_checkout),
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
        ),
        cwd=work_root,
        timeout=min(30, runner.remaining()),
    ).stdout
    if head != contract.UPSTREAM_COMMIT or tree != contract.UPSTREAM_TREE or status:
        raise BootstrapError("cloned SiRA identity is dirty or drifted")

    context = work_root / "build-context"
    context.mkdir(mode=0o700, exist_ok=False)
    archive = work_root / "upstream.tar"
    runner.run(
        (
            "/usr/bin/git",
            "-C",
            str(source_checkout),
            "archive",
            "--format=tar",
            f"--output={archive}",
            contract.UPSTREAM_COMMIT,
        ),
        cwd=work_root,
        timeout=min(120, runner.remaining()),
    )
    _extract_git_archive(archive, context / "upstream")

    bindings = _artifact_map(plan)
    copies = {
        "containers/sira-smoke/bounded/Containerfile.amd64": "Containerfile.amd64",
        "containers/sira-smoke/bounded/.dockerignore": ".dockerignore",
        "containers/sira-smoke/sira-immutable-model-routing.patch": (
            "sira-immutable-model-routing.patch"
        ),
        "containers/sira-smoke/container_entrypoint.py": "container_entrypoint.py",
        "containers/sira-smoke/bounded/model_preflight.py": "model_preflight.py",
        "containers/sira-smoke/bounded/browser_preflight.py": "browser_preflight.py",
        "containers/sira-smoke/fixtures/static.html": "static.html",
        "src/giclab/__init__.py": "giclab/__init__.py",
        "src/giclab/registry.py": "giclab/registry.py",
        "containers/sira-smoke/bounded/harness_init.py": "giclab/harness/__init__.py",
        "src/giclab/harness/sira_gate_a.py": "giclab/harness/sira_gate_a.py",
        "src/giclab/harness/sira_gate_a_runtime.py": ("giclab/harness/sira_gate_a_runtime.py"),
    }
    for source_relative, destination_relative in copies.items():
        binding = bindings.get(source_relative)
        if binding is None:
            raise BootstrapError("build input is absent from plan bindings")
        source = bundle_root / source_relative
        if source.stat().st_size != binding[0]:
            raise BootstrapError("build input byte identity drifted")
        _copy_exact(source, context / destination_relative, sha256=binding[1])
    vendor = context / "vendor"
    vendor.mkdir(mode=0o700)
    _download_exact(
        contract.UV_WHEEL_URL,
        vendor / contract.UV_WHEEL,
        size=contract.UV_WHEEL_BYTES,
        sha256=contract.UV_WHEEL_SHA256,
    )
    return context


def build_image(
    *,
    context: Path,
    execution_commit: str,
    authorization_reference: str,
    runner: CommandRunner,
    contract: ModuleType,
    evidence_root: Path,
) -> str:
    runner.run(
        (
            "/usr/bin/docker",
            "image",
            "pull",
            "--platform",
            "linux/amd64",
            contract.BASE_IMAGE_INDEX,
        ),
        cwd=context,
        timeout=min(600, runner.remaining()),
    )
    base = runner.run(
        (
            "/usr/bin/docker",
            "image",
            "inspect",
            "--format",
            "{{.Id}}",
            contract.BASE_IMAGE_INDEX,
        ),
        cwd=context,
        timeout=min(30, runner.remaining()),
    )
    if base.stdout.decode("utf-8", "strict").strip() != contract.BASE_IMAGE_AMD64_CONFIG:
        raise BootstrapError("pulled base image config differs from the pinned amd64 identity")
    tag = "giclab/sira-smoke:t07-bounded-v1"
    runner.run(
        (
            "/usr/bin/docker",
            "build",
            "--pull=false",
            "--no-cache",
            "--network=default",
            "--platform",
            "linux/amd64",
            "--file",
            str(context / "Containerfile.amd64"),
            "--tag",
            tag,
            "--label",
            f"org.giclab.t07.repository-commit={execution_commit}",
            "--label",
            f"org.giclab.t07.source-commit={contract.UPSTREAM_COMMIT}",
            "--label",
            f"org.giclab.t07.authorization={authorization_reference}",
            str(context),
        ),
        cwd=context,
        timeout=min(1_800, runner.remaining()),
    )
    result = runner.run(
        ("/usr/bin/docker", "image", "inspect", "--format", "{{.Id}}", tag),
        cwd=context,
        timeout=min(30, runner.remaining()),
    )
    image_id = result.stdout.decode("utf-8", "strict").strip()
    if _IMAGE_ID.fullmatch(image_id) is None:
        raise BootstrapError("built image ID is not immutable")
    inspect = runner.run(
        ("/usr/bin/docker", "image", "inspect", image_id),
        cwd=context,
        timeout=min(30, runner.remaining()),
    )
    _write_bytes(evidence_root / "image-inspect.json", inspect.stdout)
    return image_id


def _capture_json_output(path: Path, result: CommandResult) -> None:
    _write_json(
        path,
        {
            "argv_sha256": _sha256(json.dumps(list(result.argv), separators=(",", ":")).encode()),
            "returncode": result.returncode,
            "stdout_bytes": len(result.stdout),
            "stderr_bytes": len(result.stderr),
            "elapsed_seconds": result.elapsed_seconds,
        },
    )


def _render_lifecycle(
    plan: Mapping[str, object],
    contract: ModuleType,
    action: str,
    substitutions: Mapping[str, str],
) -> tuple[str, ...]:
    lifecycle = plan.get("container_lifecycle")
    if not isinstance(lifecycle, Mapping):
        raise BootstrapError("container lifecycle plan is unavailable")
    template = lifecycle.get(action)
    if not isinstance(template, list) or any(not isinstance(item, str) for item in template):
        raise BootstrapError("container lifecycle command is invalid")
    needed = {
        match.group(0) for item in template for match in re.finditer(r"\$\{[A-Z][A-Z0-9_]*\}", item)
    }
    selected = {key: value for key, value in substitutions.items() if key in needed}
    return cast(tuple[str, ...], contract.materialize_argv(template, selected))


def _line_count(encoded: bytes) -> int:
    return len([line for line in encoded.splitlines() if line.strip()])


def _cleanup_container(
    *,
    container_id: str,
    run_id: str,
    condition: str,
    plan: Mapping[str, object],
    contract: ModuleType,
    cleanup_runner: CommandRunner,
    evidence_root: Path,
) -> None:
    substitutions = {"${CONTAINER_ID}": container_id, "${RUN_ID}": run_id}
    stop = cleanup_runner.run(
        _render_lifecycle(plan, contract, "stop", substitutions),
        cwd=evidence_root,
        timeout=min(15, cleanup_runner.remaining()),
        check=False,
    )
    _capture_json_output(evidence_root / "container-stop.json", stop)
    kill = cleanup_runner.run(
        _render_lifecycle(plan, contract, "kill", substitutions),
        cwd=evidence_root,
        timeout=min(15, cleanup_runner.remaining()),
        check=False,
    )
    _capture_json_output(evidence_root / "container-kill.json", kill)
    terminal = cleanup_runner.run(
        _render_lifecycle(plan, contract, "inspect", substitutions),
        cwd=evidence_root,
        timeout=min(15, cleanup_runner.remaining()),
        check=False,
    )
    _write_bytes(evidence_root / "container-terminal-inspect.json", terminal.stdout)
    terminal_state_observed = False
    if terminal.returncode == 0:
        try:
            inspected = json.loads(terminal.stdout)
            state = inspected[0]["State"]
            terminal_state_observed = state.get("Running") is False and state.get("Status") in {
                "created",
                "exited",
                "dead",
            }
        except (IndexError, KeyError, TypeError, json.JSONDecodeError):
            terminal_state_observed = False
    removed = cleanup_runner.run(
        _render_lifecycle(plan, contract, "remove", substitutions),
        cwd=evidence_root,
        timeout=min(30, cleanup_runner.remaining()),
        check=False,
    )
    _capture_json_output(evidence_root / "container-remove.json", removed)
    removal_probe = cleanup_runner.run(
        _render_lifecycle(plan, contract, "inspect", substitutions),
        cwd=evidence_root,
        timeout=min(15, cleanup_runner.remaining()),
        check=False,
    )
    _capture_json_output(evidence_root / "container-removal-proof.json", removal_probe)
    residue: dict[str, int] = {}
    for kind, action in (
        ("owned_container_residue_count", "container_residue"),
        ("owned_network_residue_count", "network_residue"),
        ("owned_volume_residue_count", "volume_residue"),
    ):
        observed = cleanup_runner.run(
            _render_lifecycle(plan, contract, action, substitutions),
            cwd=evidence_root,
            timeout=min(30, cleanup_runner.remaining()),
        )
        residue[kind] = _line_count(observed.stdout)
    record = {
        "schema_version": contract.SCHEMA_VERSION,
        "condition": condition,
        "container_id_sha256": _sha256(container_id.encode()),
        "terminal_state_observed": terminal_state_observed,
        "removed": removed.returncode == 0 and removal_probe.returncode != 0,
        **residue,
        "browser_process_residue_count": residue["owned_container_residue_count"],
        "evidence_captured_before_removal": (
            (evidence_root / "container-inspect-before-stop.json").is_file()
            and (evidence_root / "container-processes-before-stop.txt").is_file()
        ),
    }
    _write_json(evidence_root / "container-cleanup.json", record)
    contract.validate_container_cleanup(record)


def run_owned_container(
    *,
    condition: str,
    run_id: str,
    create_template: Sequence[str],
    substitutions: Mapping[str, str],
    plan: Mapping[str, object],
    contract: ModuleType,
    work_runner: CommandRunner,
    cleanup_runner: CommandRunner,
    evidence_root: Path,
    attached: bool,
    wall_seconds: int,
    readiness_path: Path | None = None,
) -> CommandResult:
    argv = contract.materialize_argv(create_template, substitutions)
    created = work_runner.run(
        argv,
        cwd=evidence_root,
        timeout=min(60, work_runner.remaining()),
    )
    container_id = created.stdout.decode("utf-8", "strict").strip()
    if re.fullmatch(r"[a-f0-9]{64}", container_id) is None:
        raise BootstrapError("Docker create did not return an immutable container ID")
    _write_bytes(evidence_root / "container-id.txt", container_id.encode() + b"\n", cap=128)
    lifecycle_substitutions = {"${CONTAINER_ID}": container_id, "${RUN_ID}": run_id}
    primary_error: Exception | None = None
    result: CommandResult | None = None
    try:
        action = "start_attached" if attached else "start_detached"
        result = work_runner.run(
            _render_lifecycle(plan, contract, action, lifecycle_substitutions),
            cwd=evidence_root,
            timeout=min(wall_seconds, work_runner.remaining()),
            check=False,
        )
        if readiness_path is not None:
            readiness_deadline = min(time.monotonic() + 45, work_runner.deadline)
            while not readiness_path.is_file():
                if time.monotonic() >= readiness_deadline:
                    raise BootstrapError("container readiness evidence was not produced")
                time.sleep(0.1)
        inspect = work_runner.run(
            _render_lifecycle(plan, contract, "inspect", lifecycle_substitutions),
            cwd=evidence_root,
            timeout=min(30, work_runner.remaining()),
        )
        _write_bytes(evidence_root / "container-inspect-before-stop.json", inspect.stdout)
        top = work_runner.run(
            _render_lifecycle(plan, contract, "top", lifecycle_substitutions),
            cwd=evidence_root,
            timeout=min(30, work_runner.remaining()),
            check=False,
        )
        _write_bytes(evidence_root / "container-processes-before-stop.txt", top.stdout)
        _capture_json_output(evidence_root / "container-start.json", result)
        _write_bytes(evidence_root / "stdout.log", result.stdout)
        _write_bytes(evidence_root / "stderr.log", result.stderr)
        if attached and result.returncode != 0:
            raise BootstrapError("owned container workload returned failure")
    except Exception as exc:
        primary_error = exc
    cleanup_error: Exception | None = None
    try:
        _cleanup_container(
            container_id=container_id,
            run_id=run_id,
            condition=condition,
            plan=plan,
            contract=contract,
            cleanup_runner=cleanup_runner,
            evidence_root=evidence_root,
        )
    except Exception as exc:
        cleanup_error = exc
    if primary_error is not None:
        raise primary_error
    if cleanup_error is not None:
        raise cleanup_error
    if result is None:
        raise BootstrapError("owned container produced no command result")
    return result


def run_condition(
    *,
    condition: str,
    plan: Mapping[str, object],
    contract: ModuleType,
    work_runner: CommandRunner,
    cleanup_runner: CommandRunner,
    image_id: str,
    evidence_root: Path,
    secret_file: Path,
    authorization: Mapping[str, object],
) -> None:
    index = list(contract.CONDITION_ORDER).index(condition)
    conditions = plan.get("conditions")
    if not isinstance(conditions, list) or not isinstance(conditions[index], Mapping):
        raise BootstrapError("condition plan is unavailable")
    template = conditions[index].get("container_create_argv_template")
    if not isinstance(template, list) or any(not isinstance(item, str) for item in template):
        raise BootstrapError("condition command template is invalid")
    condition_root = evidence_root / contract.MODE_VALUES[condition]
    condition_root.mkdir(mode=0o700, exist_ok=False)
    substitutions = {
        "${HOST_ATTEMPT_ROOT}": str(condition_root),
        "${SIRA_SECRET_FILE}": str(secret_file),
        "${EXECUTION_COMMIT}": str(authorization["execution_commit"]),
        "${AUTHORIZATION_REFERENCE}": str(authorization["authorization_reference"]),
        "${IMAGE_ID}": image_id,
    }
    run_owned_container(
        condition=condition,
        run_id=contract.RUN_IDS[condition],
        create_template=template,
        substitutions=substitutions,
        plan=plan,
        contract=contract,
        work_runner=work_runner,
        cleanup_runner=cleanup_runner,
        evidence_root=condition_root,
        attached=True,
        wall_seconds=120,
    )


def package_evidence(evidence_root: Path, contract: ModuleType) -> Path:
    manifest = contract.build_evidence_manifest(
        evidence_root,
        max_total_bytes=MAX_EVIDENCE_BYTES,
        max_files=MAX_EVIDENCE_FILES,
    )
    manifest_path = evidence_root / "EVIDENCE_MANIFEST.json"
    _write_json(manifest_path, manifest)
    archive = evidence_root.parent / "t07-bounded-evidence.zip"
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_STORED) as output:
        for path in sorted(evidence_root.rglob("*")):
            if path.is_file() and not path.is_symlink():
                output.write(path, path.relative_to(evidence_root).as_posix())
    if archive.stat().st_size > MAX_EVIDENCE_BYTES:
        raise BootstrapError("sealed evidence archive exceeds its cap")
    archive_descriptor = os.open(archive, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        os.fsync(archive_descriptor)
    finally:
        os.close(archive_descriptor)
    archive_digest = hashlib.sha256()
    with archive.open("rb") as source:
        while chunk := source.read(1_048_576):
            archive_digest.update(chunk)
    _write_json(
        evidence_root.parent / "ARCHIVE_IDENTITY.json",
        {
            "archive": archive.name,
            "bytes": archive.stat().st_size,
            "sha256": archive_digest.hexdigest(),
            "source_retained": True,
        },
    )
    return archive


def validate_pair_evidence(evidence_root: Path, contract: ModuleType) -> None:
    usages: list[object] = []
    records: list[dict[str, object]] = []
    for condition in contract.CONDITION_ORDER:
        mode = contract.MODE_VALUES[condition]
        root = evidence_root / mode
        budget = _strict_json(
            _read_regular(root / "provider-budget.json", max_bytes=65_536),
            context=f"{mode} provider budget",
        )
        runtime = _strict_json(
            _read_regular(root / "runtime-environment.json", max_bytes=65_536),
            context=f"{mode} runtime environment",
        )
        cleanup = _strict_json(
            _read_regular(root / "runtime-cleanup.json", max_bytes=65_536),
            context=f"{mode} runtime cleanup",
        )
        command = _strict_json(
            _read_regular(root / "container-start.json", max_bytes=65_536),
            context=f"{mode} command result",
        )
        if (
            budget.get("model_revision") != contract.MODEL
            or budget.get("unreconciled_provider_attempts") != 0
            or runtime.get("routing_sha256") != contract.ROUTING_SHA256
            or cleanup.get("all_environment_closes_succeeded") is not True
        ):
            raise BootstrapError("condition accounting, routing, or browser cleanup drifted")
        output_bytes = sum(
            path.stat().st_size
            for path in root.rglob("*")
            if path.is_file() and not path.is_symlink()
        )
        usage = contract.BudgetUsage(
            condition=condition,
            cost_usd=budget.get("cost_usd"),
            input_tokens=budget.get("input_tokens"),
            cached_input_tokens=budget.get("cached_input_tokens"),
            output_tokens=budget.get("output_tokens"),
            model_call_attempts=budget.get("model_call_attempts"),
            browser_actions=budget.get("browser_actions"),
            wall_seconds=command.get("elapsed_seconds"),
            output_bytes=output_bytes,
        )
        usages.append(usage)
        records.append(
            {
                "condition": condition,
                "run_id": contract.RUN_IDS[condition],
                "cost_usd": usage.cost_usd,
                "model_tokens": usage.total_tokens,
                "model_call_attempts": usage.model_call_attempts,
                "browser_actions": usage.browser_actions,
                "wall_seconds": usage.wall_seconds,
                "output_bytes": usage.output_bytes,
            }
        )
    contract.validate_pair_budget(usages)
    _write_json(
        evidence_root / "pair-budget.json",
        {
            "schema_version": contract.SCHEMA_VERSION,
            "plan_id": contract.PLAN_ID,
            "host_run_id": contract.HOST_RUN_ID,
            "condition_order": list(contract.CONDITION_ORDER),
            "conditions": records,
            "within_all_caps": True,
        },
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--plan-sha256", required=True)
    parser.add_argument("--contract-file", type=Path, required=True)
    parser.add_argument("--contract-sha256", required=True)
    parser.add_argument("--authorization", type=Path, required=True)
    parser.add_argument("--authorization-sha256", required=True)
    parser.add_argument("--bundle-root", type=Path, required=True)
    parser.add_argument("--secret-file", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if "OPENAI_API_KEY" in os.environ or "SIRA_API_KEY" in os.environ:
        raise BootstrapError("credentials must not be inherited by the bootstrap")
    contract_bytes = _read_regular(args.contract_file, max_bytes=1_048_576)
    if (
        _HEX64.fullmatch(args.contract_sha256) is None
        or _sha256(contract_bytes) != args.contract_sha256
    ):
        raise BootstrapError("bounded contract module hash drifted")
    contract = _load_contract(args.contract_file)
    plan_bytes = _read_regular(args.plan, max_bytes=MAX_PLAN_BYTES)
    if _HEX64.fullmatch(args.plan_sha256) is None or _sha256(plan_bytes) != args.plan_sha256:
        raise BootstrapError("bounded plan hash drifted")
    plan = _strict_json(plan_bytes, context="bounded plan")
    contract.validate_plan(plan, repository_root=args.bundle_root)
    authorization = validate_authorization(
        _read_regular(args.authorization, max_bytes=MAX_AUTHORIZATION_BYTES),
        expected_sha256=args.authorization_sha256,
        plan_sha256=args.plan_sha256,
        contract=contract,
    )
    output_root = args.output_root.absolute()
    bundle_root = args.bundle_root.resolve(strict=True)
    if output_root.exists() or output_root.resolve(strict=False) != output_root:
        raise BootstrapError("remote output root is not fresh and canonical")
    _assert_remote_capacity(output_root)
    _validate_secret_file(args.secret_file, forbidden_roots=(bundle_root, output_root))
    output_root.mkdir(mode=0o700, parents=True, exist_ok=False)
    evidence_root = output_root / "evidence"
    evidence_root.mkdir(mode=0o700)
    incident = output_root / "TERMINATE_REQUIRED.json"
    launch = _parse_utc(authorization["provider_launch_at_utc"], context="provider launch time")
    remaining = HARD_PROVIDER_WALL_SECONDS - (datetime.now(UTC) - launch).total_seconds()
    now_monotonic = time.monotonic()
    cleanup_reserve = int(contract.LIMITS["container_cleanup_reserve_seconds"])
    work_runner = CommandRunner(
        deadline=now_monotonic + remaining - TERMINATION_HEADROOM_SECONDS - cleanup_reserve,
        max_calls=int(contract.LIMITS["docker_lifecycle_calls"]),
    )
    cleanup_runner = CommandRunner(
        deadline=now_monotonic + remaining - TERMINATION_HEADROOM_SECONDS,
        max_calls=int(contract.LIMITS["docker_lifecycle_calls"]),
    )
    try:
        context = prepare_build_context(
            bundle_root=bundle_root,
            work_root=output_root,
            plan=plan,
            contract=contract,
            runner=work_runner,
        )
        image_id = build_image(
            context=context,
            execution_commit=str(authorization["execution_commit"]),
            authorization_reference=str(authorization["authorization_reference"]),
            runner=work_runner,
            contract=contract,
            evidence_root=evidence_root,
        )
        preflights = plan.get("preflights")
        if not isinstance(preflights, Mapping):
            raise BootstrapError("preflight plan is unavailable")
        browser_plan = preflights.get("browser")
        model_plan = preflights.get("model")
        if not isinstance(browser_plan, Mapping) or not isinstance(model_plan, Mapping):
            raise BootstrapError("preflight command binding is unavailable")
        browser_template = browser_plan.get("container_create_argv_template")
        model_template = model_plan.get("container_create_argv_template")
        if not isinstance(browser_template, list) or not isinstance(model_template, list):
            raise BootstrapError("preflight command template is unavailable")
        browser_root = evidence_root / "browser-preflight"
        browser_root.mkdir(mode=0o700)
        run_owned_container(
            condition="BROWSER-PREFLIGHT",
            run_id=contract.BROWSER_PREFLIGHT_RUN_ID,
            create_template=browser_template,
            substitutions={
                "${HOST_ATTEMPT_ROOT}": str(browser_root),
                "${EXECUTION_COMMIT}": str(authorization["execution_commit"]),
                "${AUTHORIZATION_REFERENCE}": str(authorization["authorization_reference"]),
                "${IMAGE_ID}": image_id,
            },
            plan=plan,
            contract=contract,
            work_runner=work_runner,
            cleanup_runner=cleanup_runner,
            evidence_root=browser_root,
            attached=False,
            wall_seconds=60,
            readiness_path=browser_root / "browser-preflight.json",
        )
        browser_record = _strict_json(
            _read_regular(browser_root / "browser-preflight.json", max_bytes=65_536),
            context="browser preflight",
        )
        if (
            browser_record.get("network_mode") != "none"
            or browser_record.get("browser_actions") != 1
            or browser_record.get("browser_running_before_container_stop") is not True
            or browser_record.get("browser_closed_by_fixture") is not False
            or browser_record.get("playwright_version") != contract.PLAYWRIGHT_VERSION
            or browser_record.get("chromium_revision") != contract.CHROMIUM_REVISION
            or b"chrom"
            not in (browser_root / "container-processes-before-stop.txt").read_bytes().lower()
        ):
            raise BootstrapError("browser preflight identity or cleanup drifted")
        _write_json(
            evidence_root / "image-provenance.json",
            {
                "schema_version": contract.SCHEMA_VERSION,
                "base_image": contract.BASE_IMAGE_INDEX,
                "base_image_index_digest": contract.BASE_IMAGE_INDEX_DIGEST,
                "base_image_amd64_manifest": contract.BASE_IMAGE_AMD64_MANIFEST,
                "base_image_amd64_config": contract.BASE_IMAGE_AMD64_CONFIG,
                "source_commit": contract.UPSTREAM_COMMIT,
                "source_tree": contract.UPSTREAM_TREE,
                "uv_lock_sha256": contract.UPSTREAM_LOCK_SHA256,
                "routing_patch_sha256": contract.ROUTING_PATCH_SHA256,
                "runtime_adaptation_sha256": contract.RUNTIME_ADAPTATION_SHA256,
                "playwright_version": browser_record["playwright_version"],
                "chromium_revision": browser_record["chromium_revision"],
                "chromium_version": browser_record["chromium_browser_version"],
                "chromium_executable_sha256": browser_record["chromium_executable_sha256"],
                "installed_package_manifest_sha256": browser_record[
                    "installed_package_manifest_sha256"
                ],
                "image_id": image_id,
                "platform": "linux/amd64",
            },
        )
        model_root = evidence_root / "model-preflight"
        model_root.mkdir(mode=0o700)
        run_owned_container(
            condition="MODEL-PREFLIGHT",
            run_id=contract.MODEL_PREFLIGHT_RUN_ID,
            create_template=model_template,
            substitutions={
                "${HOST_ATTEMPT_ROOT}": str(model_root),
                "${SIRA_SECRET_FILE}": str(args.secret_file.resolve(strict=True)),
                "${EXECUTION_COMMIT}": str(authorization["execution_commit"]),
                "${AUTHORIZATION_REFERENCE}": str(authorization["authorization_reference"]),
                "${IMAGE_ID}": image_id,
            },
            plan=plan,
            contract=contract,
            work_runner=work_runner,
            cleanup_runner=cleanup_runner,
            evidence_root=model_root,
            attached=True,
            wall_seconds=60,
        )
        model_record = _strict_json(
            _read_regular(model_root / "model-availability.json", max_bytes=65_536),
            context="model availability",
        )
        if model_record != {
            "schema_version": contract.SCHEMA_VERSION,
            "method": "GET",
            "scheme": "https",
            "host": "api.openai.com",
            "path": f"/v1/models/{contract.MODEL}",
            "http_status": 200,
            "response_bytes": model_record.get("response_bytes"),
            "model": contract.MODEL,
            "available": True,
            "retry_count": 0,
            "redirect_follow_count": 0,
        } or not isinstance(model_record.get("response_bytes"), int):
            raise BootstrapError("model availability evidence drifted")
        run_condition(
            condition="SIRA-REACTIVE",
            plan=plan,
            contract=contract,
            work_runner=work_runner,
            cleanup_runner=cleanup_runner,
            image_id=image_id,
            evidence_root=evidence_root,
            secret_file=args.secret_file.resolve(strict=True),
            authorization=authorization,
        )
        run_condition(
            condition="SIRA-SIMULATIVE",
            plan=plan,
            contract=contract,
            work_runner=work_runner,
            cleanup_runner=cleanup_runner,
            image_id=image_id,
            evidence_root=evidence_root,
            secret_file=args.secret_file.resolve(strict=True),
            authorization=authorization,
        )
        validate_pair_evidence(evidence_root, contract)
        package_evidence(evidence_root, contract)
    except Exception as exc:
        _write_json(
            incident,
            {
                "schema_version": "0.1.0",
                "provider_termination_required": True,
                "failure_class": type(exc).__name__,
                "message_retained": False,
            },
        )
        raise
    _write_json(
        incident,
        {
            "schema_version": "0.1.0",
            "provider_termination_required": True,
            "bootstrap_complete": True,
            "message_retained": False,
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
