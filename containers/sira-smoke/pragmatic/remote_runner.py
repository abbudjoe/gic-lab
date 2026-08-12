"""Pragmatic one-pair Lambda runner for the T07 SiRA smoke.

This program runs on the short-lived Lambda host. It builds the pinned image,
performs local browser/model preflights, freezes exact container argv, executes each
condition at most once, packages nonsecret evidence, and removes owned runtime state.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import subprocess
import tarfile
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Final

SIRA_COMMIT: Final = "93fb8d72de71f9a4a13419670adeb34d93cf7acd"
SIRA_TREE: Final = "6a6d9068b94d7632d3533a3d6f013d4de6ff76e8"
MODEL: Final = "gpt-4o-2024-11-20"
QUERY: Final = "go to google flights"
IMAGE_TAG: Final = f"giclab/t07-pragmatic:{SIRA_COMMIT[:12]}"
UV_URL: Final = (
    "https://files.pythonhosted.org/packages/83/eb/4e1557daf6693cb446ed28185664ad6682fd98c6dbac9e433cbc35df450a/"
    "uv-0.11.7-py3-none-manylinux_2_17_x86_64.manylinux2014_x86_64.whl"
)
UV_SHA256: Final = "4e4d5e31bea86e1b6e0f5a0f95e14e80018e6f6c0129256d2915a4b3d793644d"
ADAPTATION_SHA256: Final = "c461dce20fea9e743135cad98b664213a393e46f35d1c1a8434212b2f0367dbb"
ROUTING_PATCH_SHA256: Final = "4d7e2a25f4313fc754db0fa17aeda51cc5cd75a5653adaf13b01ce87a71cb8ed"
BASE_IMAGE: Final = (
    "mcr.microsoft.com/playwright/python:v1.39.0-jammy@sha256:"
    "96955ff5cc37e13f5f1b21f5171afb9fed7e028025aa9d81c690501cd7fa0c6c"
)
REMOTE_REPOSITORY: Final = Path("/home/ubuntu/t07-pragmatic-repository")
REMOTE_SECRET: Final = Path("/home/ubuntu/.config/giclab/t07-pragmatic-openai-provider-key")
CONTAINER_PREFIX: Final = "giclab-t07-pragmatic-"
CONDITION_TIMEOUT_SECONDS: Final = 150
MAX_EVIDENCE_BYTES: Final = 268_435_456


class PragmaticRunError(RuntimeError):
    """A bounded infrastructure or execution contract failed."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")  # noqa: UP017


def canonical_json(document: object) -> bytes:
    return json.dumps(document, allow_nan=False, indent=2, sort_keys=True).encode() + b"\n"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1_048_576):
            digest.update(chunk)
    return digest.hexdigest()


def write_exclusive(path: Path, document: object) -> None:
    encoded = canonical_json(document)
    descriptor = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        offset = 0
        while offset < len(encoded):
            written = os.write(descriptor, encoded[offset:])
            if written <= 0:
                raise PragmaticRunError("evidence write made no progress")
            offset += written
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def safe_environment() -> dict[str, str]:
    environment = dict(os.environ)
    for name in ("LAMBDA_API_KEY", "OPENAI_API_KEY", "SIRA_API_KEY"):
        environment.pop(name, None)
    environment.update({"PYTHONNOUSERSITE": "1", "GIT_TERMINAL_PROMPT": "0"})
    return environment


def run_root(launch_ordinal: int) -> Path:
    if launch_ordinal not in {1, 2}:
        raise PragmaticRunError("launch ordinal must be one or two")
    return Path(f"/home/ubuntu/t07-pragmatic-run-launch-{launch_ordinal:04d}")


def run_capture(
    argv: list[str],
    *,
    stdout_path: Path,
    stderr_path: Path,
    cwd: Path | None = None,
    timeout: int | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[bytes]:
    stdout_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with stdout_path.open("xb") as stdout, stderr_path.open("xb") as stderr:
        try:
            result = subprocess.run(
                argv,
                cwd=cwd,
                env=safe_environment(),
                stdin=subprocess.DEVNULL,
                stdout=stdout,
                stderr=stderr,
                check=False,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise PragmaticRunError(f"command timed out: {argv[0]}") from exc
    if check and result.returncode != 0:
        raise PragmaticRunError(f"command failed ({result.returncode}): {argv[0]}")
    return result


def output(argv: list[str], *, timeout: int = 30) -> str:
    result = subprocess.run(
        argv,
        env=safe_environment(),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
        timeout=timeout,
    )
    if result.returncode != 0:
        raise PragmaticRunError(f"command failed ({result.returncode}): {argv[0]}")
    return result.stdout.decode("utf-8", errors="strict").strip()


def docker_prefix(root: Path, *, discover: bool = False) -> list[str]:
    record = root / "docker-prefix.json"
    if record.exists():
        parsed = json.loads(record.read_text())
        prefix = parsed.get("argv_prefix")
        if prefix in (["docker"], ["sudo", "-n", "docker"]):
            return list(prefix)
        raise PragmaticRunError("Docker prefix evidence is invalid")
    if not discover:
        raise PragmaticRunError("Docker prefix has not been established")
    candidates = (["docker"], ["sudo", "-n", "docker"])
    for candidate in candidates:
        result = subprocess.run(
            [*candidate, "info"],
            env=safe_environment(),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=30,
        )
        if result.returncode == 0:
            write_exclusive(record, {"schema_version": "0.1.0", "argv_prefix": candidate})
            return list(candidate)
    raise PragmaticRunError("Docker is unavailable to the remote user")


def validate_secret_metadata() -> None:
    descriptor = os.open(REMOTE_SECRET, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_uid != os.getuid()
            or metadata.st_nlink != 1
            or stat.S_IMODE(metadata.st_mode) != 0o600
            or not 0 < metadata.st_size <= 16_384
        ):
            raise PragmaticRunError("remote provider credential metadata is unsafe")
    finally:
        os.close(descriptor)


def prepare_build_context(root: Path, setup_dir: Path) -> Path:
    context = Path(tempfile.mkdtemp(prefix="build-context-", dir=root))
    shutil.copy2(
        REMOTE_REPOSITORY / "containers/sira-smoke/pragmatic/Containerfile.amd64",
        context / "Containerfile",
    )
    shutil.copy2(
        REMOTE_REPOSITORY / "containers/sira-smoke/sira-immutable-model-routing.patch",
        context / "sira-immutable-model-routing.patch",
    )
    shutil.copy2(
        REMOTE_REPOSITORY / "containers/sira-smoke/container_entrypoint.py",
        context / "container_entrypoint.py",
    )
    shutil.copy2(
        REMOTE_REPOSITORY / "containers/sira-smoke/bounded/model_preflight.py",
        context / "model_preflight.py",
    )
    shutil.copy2(
        REMOTE_REPOSITORY / "containers/sira-smoke/bounded/browser_preflight.py",
        context / "browser_preflight.py",
    )
    shutil.copy2(
        REMOTE_REPOSITORY / "containers/sira-smoke/fixtures/static.html", context / "static.html"
    )
    shutil.copytree(REMOTE_REPOSITORY / "src/giclab", context / "giclab")
    (context / "vendor").mkdir(mode=0o700)
    upstream = context / "upstream"
    git_log = setup_dir / "source-fetch.stdout"
    git_err = setup_dir / "source-fetch.stderr"
    run_capture(["git", "init", str(upstream)], stdout_path=git_log, stderr_path=git_err)
    run_capture(
        [
            "git",
            "-C",
            str(upstream),
            "remote",
            "add",
            "origin",
            "https://github.com/sailing-lab/sira.git",
        ],
        stdout_path=setup_dir / "source-remote.stdout",
        stderr_path=setup_dir / "source-remote.stderr",
    )
    run_capture(
        ["git", "-C", str(upstream), "fetch", "--depth", "1", "origin", SIRA_COMMIT],
        stdout_path=setup_dir / "source-fetch-commit.stdout",
        stderr_path=setup_dir / "source-fetch-commit.stderr",
        timeout=300,
    )
    run_capture(
        ["git", "-C", str(upstream), "checkout", "--detach", "FETCH_HEAD"],
        stdout_path=setup_dir / "source-checkout.stdout",
        stderr_path=setup_dir / "source-checkout.stderr",
    )
    if output(["git", "-C", str(upstream), "rev-parse", "HEAD"]) != SIRA_COMMIT:
        raise PragmaticRunError("pinned SiRA commit did not materialize")
    if output(["git", "-C", str(upstream), "rev-parse", "HEAD^{tree}"]) != SIRA_TREE:
        raise PragmaticRunError("pinned SiRA tree did not materialize")
    wheel = context / "vendor" / "uv-0.11.7-py3-none-manylinux_2_17_x86_64.manylinux2014_x86_64.whl"
    run_capture(
        [
            "curl",
            "--fail",
            "--location",
            "--silent",
            "--show-error",
            "--retry",
            "0",
            "--max-time",
            "300",
            "--output",
            str(wheel),
            UV_URL,
        ],
        stdout_path=setup_dir / "uv-download.stdout",
        stderr_path=setup_dir / "uv-download.stderr",
        timeout=330,
    )
    if sha256_file(wheel) != UV_SHA256:
        raise PragmaticRunError("uv wheel digest mismatch")
    if sha256_file(context / "sira-immutable-model-routing.patch") != ROUTING_PATCH_SHA256:
        raise PragmaticRunError("routing patch digest mismatch")
    if sha256_file(context / "giclab/harness/sira_gate_a_runtime.py") != ADAPTATION_SHA256:
        raise PragmaticRunError("runtime adaptation digest mismatch")
    return context


def docker_common(*, name: str, attempt: Path, network: str, image_id: str) -> list[str]:
    return [
        "create",
        "--name",
        name,
        "--platform",
        "linux/amd64",
        "--network",
        network,
        "--ipc",
        "private",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges=true",
        "--read-only",
        "--init",
        "--restart",
        "no",
        "--cpus",
        "2.0",
        "--memory",
        "4g",
        "--memory-swap",
        "4g",
        "--pids-limit",
        "512",
        "--shm-size",
        "1g",
        "--tmpfs",
        "/tmp:rw,noexec,nosuid,nodev,size=134217728,uid=1000,gid=1000,mode=0700",
        "--user",
        "1000:1000",
        "--mount",
        f"type=bind,src={attempt},dst=/giclab/attempt",
        "--entrypoint",
        "/usr/bin/python3",
        image_id,
    ]


def remove_container(prefix: list[str], name: str) -> None:
    subprocess.run(
        [*prefix, "rm", "--force", name],
        env=safe_environment(),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
        timeout=30,
    )


def browser_preflight(
    root: Path, setup_dir: Path, prefix: list[str], image_id: str, launch_ordinal: int
) -> None:
    attempt = setup_dir / "browser-preflight"
    attempt.mkdir(mode=0o700)
    name = f"{CONTAINER_PREFIX}browser-{launch_ordinal:04d}"
    create = [
        *prefix,
        *docker_common(name=name, attempt=attempt, network="none", image_id=image_id),
        "/opt/giclab/browser_preflight.py",
    ]
    run_capture(
        create,
        stdout_path=setup_dir / "browser-create.stdout",
        stderr_path=setup_dir / "browser-create.stderr",
    )
    try:
        run_capture(
            [*prefix, "start", name],
            stdout_path=setup_dir / "browser-start.stdout",
            stderr_path=setup_dir / "browser-start.stderr",
        )
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            if (attempt / "browser-preflight.json").is_file():
                break
            time.sleep(1)
        else:
            raise PragmaticRunError("local-static-page Chromium preflight did not complete")
        run_capture(
            [*prefix, "stop", "--time", "10", name],
            stdout_path=setup_dir / "browser-stop.stdout",
            stderr_path=setup_dir / "browser-stop.stderr",
            check=False,
            timeout=30,
        )
        run_capture(
            [*prefix, "inspect", name],
            stdout_path=setup_dir / "browser-inspect.json",
            stderr_path=setup_dir / "browser-inspect.stderr",
        )
        run_capture(
            [*prefix, "logs", name],
            stdout_path=setup_dir / "browser-logs.stdout",
            stderr_path=setup_dir / "browser-logs.stderr",
            check=False,
        )
    finally:
        remove_container(prefix, name)


def model_preflight(setup_dir: Path, prefix: list[str], image_id: str, launch_ordinal: int) -> None:
    validate_secret_metadata()
    attempt = setup_dir / "model-preflight"
    attempt.mkdir(mode=0o700)
    name = f"{CONTAINER_PREFIX}model-{launch_ordinal:04d}"
    create = [
        *prefix,
        *docker_common(name=name, attempt=attempt, network="bridge", image_id=image_id),
    ]
    secret_index = create.index("--entrypoint")
    create[secret_index:secret_index] = [
        "--mount",
        f"type=bind,src={REMOTE_SECRET},dst=/run/secrets/sira_api_key,readonly",
    ]
    create.extend(
        [
            "/opt/giclab/container_entrypoint.py",
            "--runtime-assignment",
            "OPENAI_API_KEY",
            "--",
            "/usr/bin/python3",
            "/opt/giclab/model_preflight.py",
        ]
    )
    run_capture(
        create,
        stdout_path=setup_dir / "model-create.stdout",
        stderr_path=setup_dir / "model-create.stderr",
    )
    try:
        run_capture(
            [*prefix, "start", "--attach", name],
            stdout_path=setup_dir / "model.stdout",
            stderr_path=setup_dir / "model.stderr",
            timeout=60,
        )
        run_capture(
            [*prefix, "inspect", name],
            stdout_path=setup_dir / "model-inspect.json",
            stderr_path=setup_dir / "model-inspect.stderr",
        )
    finally:
        remove_container(prefix, name)
    availability = json.loads((attempt / "model-availability.json").read_text())
    if availability.get("model") != MODEL or availability.get("available") is not True:
        raise PragmaticRunError("immutable model preflight did not validate")


def setup(launch_ordinal: int) -> None:
    root = run_root(launch_ordinal)
    root.mkdir(mode=0o700, exist_ok=True)
    if (root / "run-manifest.json").exists():
        raise PragmaticRunError("setup cannot change after the run manifest is frozen")
    if (root / "setup-complete.json").exists():
        raise PragmaticRunError("setup is already complete")
    validate_secret_metadata()
    ordinal = 1 + len(list(root.glob("setup-attempt-*.json")))
    setup_dir = root / f"setup-attempt-{ordinal:02d}"
    setup_dir.mkdir(mode=0o700)
    write_exclusive(
        root / f"setup-attempt-{ordinal:02d}.json",
        {"schema_version": "0.1.0", "ordinal": ordinal, "started_at_utc": utc_now()},
    )
    prefix = docker_prefix(root, discover=True)
    context = prepare_build_context(root, setup_dir)
    run_capture(
        [
            *prefix,
            "build",
            "--pull=false",
            "--progress=plain",
            "--tag",
            IMAGE_TAG,
            "--file",
            str(context / "Containerfile"),
            str(context),
        ],
        stdout_path=setup_dir / "docker-build.stdout",
        stderr_path=setup_dir / "docker-build.stderr",
        timeout=3600,
    )
    image_id = output([*prefix, "image", "inspect", "--format", "{{.Id}}", IMAGE_TAG])
    if not image_id.startswith("sha256:"):
        raise PragmaticRunError("built image identity is unavailable")
    run_capture(
        [*prefix, "image", "inspect", image_id],
        stdout_path=setup_dir / "image-inspect.json",
        stderr_path=setup_dir / "image-inspect.stderr",
    )
    browser_preflight(root, setup_dir, prefix, image_id, launch_ordinal)
    model_preflight(setup_dir, prefix, image_id, launch_ordinal)
    write_exclusive(
        root / "setup-complete.json",
        {
            "schema_version": "0.1.0",
            "completed_at_utc": utc_now(),
            "launch_ordinal": launch_ordinal,
            "sira_commit": SIRA_COMMIT,
            "sira_tree": SIRA_TREE,
            "model": MODEL,
            "base_image": BASE_IMAGE,
            "image_id": image_id,
            "image_tag": IMAGE_TAG,
            "docker_argv_prefix": prefix,
            "runtime_adaptation_sha256": ADAPTATION_SHA256,
            "routing_patch_sha256": ROUTING_PATCH_SHA256,
            "browser_preflight": "passed",
            "model_preflight": "passed",
            "setup_attempt": ordinal,
        },
    )


def condition_container_argv(root: Path, mode: str, prefix: list[str], image_id: str) -> list[str]:
    if mode not in {"reactive", "simulative"}:
        raise PragmaticRunError("condition mode is invalid")
    attempt = root / "evidence" / mode
    name = f"{CONTAINER_PREFIX}{mode}-{root.name.rsplit('-', 1)[-1]}"
    command = [
        *prefix,
        *docker_common(name=name, attempt=attempt, network="bridge", image_id=image_id),
    ]
    insert = command.index("--entrypoint")
    command[insert:insert] = [
        "--mount",
        f"type=bind,src={REMOTE_SECRET},dst=/run/secrets/sira_api_key,readonly",
        "--label",
        "org.giclab.t07.profile=pragmatic-smoke-v1",
        "--label",
        f"org.giclab.t07.condition=SIRA-{mode.upper()}",
    ]
    command.extend(
        [
            "/opt/giclab/container_entrypoint.py",
            "--runtime-assignment",
            "SIRA_API_KEY",
            "--",
            "/opt/sira/.venv/bin/python",
            "/opt/giclab-src/giclab/harness/sira_gate_a_runtime.py",
            "--gate-upstream-runner",
            "/opt/sira/scripts/run_web_agent.py",
            "--gate-attempt-root",
            "/giclab/attempt",
            "--gate-mode",
            mode,
            "--gate-adaptation-sha256",
            ADAPTATION_SHA256,
            "--",
            f"EXP-0001-SMOKE-{mode.upper()}",
            "--query",
            QUERY,
            "--mode",
            mode,
            "--agent",
            "sira",
            "--model",
            MODEL,
            "--max_steps",
            "1",
            "--timeout",
            "30",
            "--max_retry",
            "0",
            "--output_dir",
            "/giclab/attempt/sira-output",
            "--seed",
            "42",
        ]
    )
    return command


def render_manifest(
    launch_ordinal: int,
    execution_commit: str,
    instance_id: str,
    region: str,
    image_id_provider: str,
) -> None:
    root = run_root(launch_ordinal)
    setup_doc = json.loads((root / "setup-complete.json").read_text())
    prefix = docker_prefix(root)
    image_id = setup_doc.get("image_id")
    if not isinstance(image_id, str):
        raise PragmaticRunError("built image identity is unavailable")
    if len(execution_commit) != 40 or any(c not in "0123456789abcdef" for c in execution_commit):
        raise PragmaticRunError("execution commit is invalid")
    conditions = {}
    for mode, order, calls in (("reactive", 1, 16), ("simulative", 2, 61)):
        conditions[mode] = {
            "condition": f"SIRA-{mode.upper()}",
            "order": order,
            "attempts": 1,
            "retries": 0,
            "browser_steps": 1,
            "model_call_attempt_cap": calls,
            "model_token_cap": 200_000,
            "adapter_cost_cap_usd": 2.0,
            "wall_seconds": 120,
            "docker_argv": condition_container_argv(root, mode, prefix, image_id),
        }
    write_exclusive(
        root / "run-manifest.json",
        {
            "schema_version": "0.1.0",
            "manifest_id": "T07-PRAGMATIC-SMOKE-RUN-0001",
            "frozen_at_utc": utc_now(),
            "git_commit": execution_commit,
            "sira_commit": SIRA_COMMIT,
            "sira_tree": SIRA_TREE,
            "model_snapshot": MODEL,
            "task": {"kind": "open-ended-query", "query": QUERY, "seed": 42, "max_steps": 1},
            "condition_order": ["SIRA-REACTIVE", "SIRA-SIMULATIVE"],
            "permitted_condition_differences": [
                "condition",
                "mode",
                "job_name",
                "attempt_root",
                "output_dir",
                "source-declared planner policy",
            ],
            "conditions": conditions,
            "budgets": {
                "authorized_openai_aggregate_usd": 10.0,
                "effective_adapter_openai_aggregate_usd": 4.0,
                "authorized_lambda_aggregate_usd": 5.0,
                "lambda_wall_seconds_per_launch": 7200,
                "maximum_lambda_launches": 2,
                "persistent_filesystems": 0,
            },
            "provider": {
                "instance_id": instance_id,
                "instance_type": "gpu_1x_a10",
                "region": region,
                "provider_image_id": image_id_provider,
                "persistent_filesystems": 0,
            },
            "runtime": {
                "built_image_id": image_id,
                "base_image": BASE_IMAGE,
                "runtime_adaptation_sha256": ADAPTATION_SHA256,
                "routing_patch_sha256": ROUTING_PATCH_SHA256,
                "runner_sha256": sha256_file(Path(__file__).resolve(strict=True)),
            },
            "interpretation_allowed": False,
        },
    )


def execute_condition(launch_ordinal: int, mode: str) -> int:
    root = run_root(launch_ordinal)
    manifest = json.loads((root / "run-manifest.json").read_text())
    if manifest.get("condition_order") != ["SIRA-REACTIVE", "SIRA-SIMULATIVE"]:
        raise PragmaticRunError("condition order drifted")
    if mode == "simulative" and not (root / "evidence/reactive/condition-status.json").is_file():
        raise PragmaticRunError("simulative cannot start before reactive is terminal")
    if mode == "reactive" and (root / "evidence/simulative/condition-started.json").exists():
        raise PragmaticRunError("reactive cannot start after simulative")
    attempt = root / "evidence" / mode
    attempt.mkdir(parents=True, mode=0o700, exist_ok=False)
    started = utc_now()
    write_exclusive(
        attempt / "condition-started.json",
        {
            "schema_version": "0.1.0",
            "condition": f"SIRA-{mode.upper()}",
            "started_at_utc": started,
            "attempt": 1,
        },
    )
    validate_secret_metadata()
    record = manifest.get("conditions", {}).get(mode, {})
    argv = record.get("docker_argv")
    expected = condition_container_argv(
        root, mode, docker_prefix(root), manifest["runtime"]["built_image_id"]
    )
    if argv != expected:
        raise PragmaticRunError("frozen condition argv drifted")
    name = argv[argv.index("--name") + 1]
    prefix = docker_prefix(root)
    create_argv = list(argv)
    run_capture(
        create_argv,
        stdout_path=attempt / "container-create.stdout",
        stderr_path=attempt / "container-create.stderr",
    )
    before = time.monotonic()
    returncode = 125
    timeout_observed = False
    try:
        result = run_capture(
            [*prefix, "start", "--attach", name],
            stdout_path=attempt / "condition.stdout",
            stderr_path=attempt / "condition.stderr",
            timeout=CONDITION_TIMEOUT_SECONDS,
            check=False,
        )
        returncode = result.returncode
    except PragmaticRunError as exc:
        if "timed out" not in str(exc):
            raise
        returncode = 124
        timeout_observed = True
    finally:
        run_capture(
            [*prefix, "inspect", name],
            stdout_path=attempt / "container-inspect.json",
            stderr_path=attempt / "container-inspect.stderr",
            check=False,
        )
        run_capture(
            [*prefix, "logs", name],
            stdout_path=attempt / "container-logs.stdout",
            stderr_path=attempt / "container-logs.stderr",
            check=False,
        )
        remove_container(prefix, name)
    wall = time.monotonic() - before
    write_exclusive(
        attempt / "condition-status.json",
        {
            "schema_version": "0.1.0",
            "condition": f"SIRA-{mode.upper()}",
            "attempt": 1,
            "started_at_utc": started,
            "finished_at_utc": utc_now(),
            "returncode": returncode,
            "timeout_observed": timeout_observed,
            "wall_seconds": wall,
            "terminal_state": "executed" if returncode == 0 else "execution_failed",
            "container_removed": True,
        },
    )
    return returncode


def scan_for_secret(root: Path) -> list[str]:
    validate_secret_metadata()
    descriptor = os.open(REMOTE_SECRET, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        credential = os.read(descriptor, 16_385)
    finally:
        os.close(descriptor)
    if not credential or len(credential) > 16_384:
        raise PragmaticRunError("remote provider credential is malformed")
    hits: list[str] = []
    for path in sorted(root.rglob("*")):
        if "build-context-" in str(path):
            continue
        if path.is_file() and not path.is_symlink() and path.stat().st_size <= MAX_EVIDENCE_BYTES:
            with path.open("rb") as handle:
                if credential in handle.read():
                    hits.append(str(path.relative_to(root)))
    credential = b""
    return hits


def package_evidence(launch_ordinal: int) -> None:
    root = run_root(launch_ordinal)
    hits = scan_for_secret(root)
    write_exclusive(
        root / "secret-scan.json",
        {"schema_version": "0.1.0", "passed": not hits, "matching_paths": hits},
    )
    if hits:
        raise PragmaticRunError("credential material was detected in retained evidence")
    files: list[dict[str, Any]] = []
    total = 0
    for path in sorted(root.rglob("*")):
        if (
            not path.is_file()
            or path.is_symlink()
            or path.name in {"evidence-manifest.json", "t07-pragmatic-evidence.tar.gz"}
            or "build-context-" in str(path)
        ):
            continue
        size = path.stat().st_size
        total += size
        if total > MAX_EVIDENCE_BYTES:
            raise PragmaticRunError("retained evidence exceeds its cap")
        files.append(
            {"path": str(path.relative_to(root)), "bytes": size, "sha256": sha256_file(path)}
        )
    write_exclusive(
        root / "evidence-manifest.json",
        {
            "schema_version": "0.1.0",
            "generated_at_utc": utc_now(),
            "files": files,
            "total_bytes": total,
        },
    )
    archive = root / "t07-pragmatic-evidence.tar.gz"
    with tarfile.open(archive, "x:gz") as handle:
        for entry in files:
            handle.add(root / entry["path"], arcname=entry["path"], recursive=False)
        handle.add(
            root / "evidence-manifest.json", arcname="evidence-manifest.json", recursive=False
        )
    write_exclusive(
        root / "archive-identity.json",
        {
            "schema_version": "0.1.0",
            "path": archive.name,
            "bytes": archive.stat().st_size,
            "sha256": sha256_file(archive),
        },
    )


def destroy_secret() -> bool:
    try:
        descriptor = os.open(REMOTE_SECRET, os.O_RDWR | getattr(os, "O_NOFOLLOW", 0))
    except FileNotFoundError:
        return True
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
            return False
        remaining = metadata.st_size
        os.lseek(descriptor, 0, os.SEEK_SET)
        zero = b"\0" * min(65_536, max(remaining, 1))
        while remaining:
            written = os.write(descriptor, zero[: min(remaining, len(zero))])
            if written <= 0:
                return False
            remaining -= written
        os.ftruncate(descriptor, 0)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    REMOTE_SECRET.unlink()
    return not REMOTE_SECRET.exists()


def cleanup(launch_ordinal: int) -> None:
    root = run_root(launch_ordinal)
    prefix = docker_prefix(root)
    raw = output([*prefix, "ps", "--all", "--format", "{{.ID}}\t{{.Names}}"])
    removed: list[str] = []
    for line in raw.splitlines():
        identifier, _, name = line.partition("\t")
        if identifier and name.startswith(CONTAINER_PREFIX):
            remove_container(prefix, identifier)
            removed.append(name)
    secret_removed = destroy_secret()
    write_exclusive(
        root / "cleanup.json",
        {
            "schema_version": "0.1.0",
            "completed_at_utc": utc_now(),
            "owned_containers_removed": removed,
            "remote_secret_removed": secret_removed,
        },
    )
    if not secret_removed:
        raise PragmaticRunError("remote secret destruction could not be verified")


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser()
    result.add_argument("--launch-ordinal", type=int, required=True)
    sub = result.add_subparsers(dest="operation", required=True)
    sub.add_parser("setup")
    manifest = sub.add_parser("render-manifest")
    manifest.add_argument("--execution-commit", required=True)
    manifest.add_argument("--instance-id", required=True)
    manifest.add_argument("--region", required=True)
    manifest.add_argument("--provider-image-id", required=True)
    condition = sub.add_parser("condition")
    condition.add_argument("--mode", choices=("reactive", "simulative"), required=True)
    sub.add_parser("package")
    sub.add_parser("cleanup")
    return result


def main() -> int:
    args = parser().parse_args()
    if args.operation == "setup":
        setup(args.launch_ordinal)
        return 0
    if args.operation == "render-manifest":
        render_manifest(
            args.launch_ordinal,
            args.execution_commit,
            args.instance_id,
            args.region,
            args.provider_image_id,
        )
        return 0
    if args.operation == "condition":
        return execute_condition(args.launch_ordinal, args.mode)
    if args.operation == "package":
        package_evidence(args.launch_ordinal)
        return 0
    if args.operation == "cleanup":
        cleanup(args.launch_ordinal)
        return 0
    raise AssertionError("unreachable")


if __name__ == "__main__":
    raise SystemExit(main())
