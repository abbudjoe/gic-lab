"""Inner offline gate: verified history input, Linux scratch, existing Make gate.

Not yet qualified by a real container run. Fails closed on incomplete inputs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path


def offline_paths(scratch: Path, results: Path) -> dict[str, str]:
    """Writable tool locations inside the isolated, externally backed runtime."""
    return {
        "TMPDIR": str(scratch / "tmp"),
        "TMP": str(scratch / "tmp"),
        "TEMP": str(scratch / "tmp"),
        "UV_CACHE_DIR": str(scratch / "uv-cache"),
        "UV_PYTHON_INSTALL_DIR": str(scratch / "python"),
        "PIP_CACHE_DIR": str(scratch / "pip-cache"),
        "XDG_CACHE_HOME": str(scratch / "cache"),
        "DENO_DIR": str(scratch / "deno-cache"),
        "RUFF_CACHE_DIR": str(scratch / "ruff-cache"),
        "MYPY_CACHE_DIR": str(scratch / "mypy-cache"),
        "QUARTO_LOG": str(results / "quarto.log"),
        "COVERAGE_FILE": str(results / "coverage"),
        "UV_OFFLINE": "1",
        "UV_PYTHON_DOWNLOADS": "never",
        "PYTHONDONTWRITEBYTECODE": "1",
    }


def run(argv, *, cwd, output=None):
    return subprocess.run(
        argv,
        cwd=cwd,
        stdin=subprocess.DEVNULL,
        stdout=output,
        stderr=subprocess.STDOUT,
        check=True,
        timeout=21600,
    )


def execute_checked_gate(argv, *, checkout, results, verify_source, identity):
    """Preserve the gate outcome and check source integrity even after failure."""
    gate_error = None
    source_error = None
    exit_code = None
    try:
        with (results / "gate.log").open("xb") as log:
            run(argv, cwd=checkout, output=log)
        exit_code = 0
    except BaseException as error:
        gate_error = error
        if isinstance(error, subprocess.CalledProcessError):
            exit_code = error.returncode
    try:
        verify_source()
    except BaseException as error:
        source_error = error
    (results / "gate.json").write_text(
        json.dumps(
            {
                **identity,
                "gate": "passed" if gate_error is None and source_error is None else "failed",
                "exit_code": exit_code,
                "gate_error_type": type(gate_error).__name__ if gate_error else None,
                "source_unchanged": source_error is None,
                "source_error_type": type(source_error).__name__ if source_error else None,
                "hosted_ci": "not-run-by-owner-instruction",
                "independent_review": "pending",
            },
            sort_keys=True,
        )
        + "\n"
    )
    if source_error is not None:
        raise source_error from gate_error
    if gate_error is not None:
        raise gate_error


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--focused-node", action="append", default=[])
    args = parser.parse_args()
    if os.geteuid() == 0 or os.environ.get("UV_OFFLINE") != "1":
        raise RuntimeError("offline non-root CI environment required")
    if any(Path(p).exists() for p in ("/var/run/docker.sock", "/run/docker.sock")):
        raise RuntimeError("daemon socket must not be present")
    if any(k.endswith(("API_KEY", "ACCESS_TOKEN", "SECRET_ACCESS_KEY")) for k in os.environ):
        raise RuntimeError("credential variable present")
    status = Path("/proc/self/status").read_text()
    if "NoNewPrivs:\t1" not in status or "CapEff:\t0000000000000000" not in status:
        raise RuntimeError("container privileges do not match the CI contract")
    inputs, scratch, results = Path("/input"), Path("/work"), Path("/results")
    os.environ.update(offline_paths(scratch, results))
    contract = json.loads((inputs / "history.json").read_bytes())
    development = (
        contract.get("classification") == "explicit-dirty-development-candidate-not-reviewed-commit"
    )
    if development != bool(args.focused_node):
        raise RuntimeError(
            "dirty development requires explicit focused nodes; final gate requires a commit"
        )
    bundle = inputs / "history.bundle"
    if hashlib.sha256(bundle.read_bytes()).hexdigest() != contract["bundle_sha256"]:
        raise RuntimeError("source/history input hash drift")
    for name in ("home", "tmp"):
        (scratch / name).mkdir(mode=0o700)
    shutil.copytree("/opt/uv-cache", scratch / "uv-cache")
    checkout = scratch / "checkout"
    run(["git", "clone", "--no-checkout", str(bundle), str(checkout)], cwd=scratch)
    run(["git", "checkout", "--detach", contract["head"]], cwd=checkout)
    for key in ("base", "head"):
        actual = subprocess.check_output(
            ["git", "rev-parse", contract[key] + "^{tree}"], cwd=checkout, text=True
        ).strip()
        if actual != contract[key + "_tree"]:
            raise RuntimeError("materialized Git tree mismatch")
    if development:
        dirty = inputs / "dirty-source.tar"
        if hashlib.sha256(dirty.read_bytes()).hexdigest() != contract["dirty_tar_sha256"]:
            raise RuntimeError("dirty development input archive drift")
        expected = {item["path"]: item for item in contract["dirty_members"]}
        if len(expected) != len(contract["dirty_members"]):
            raise RuntimeError("duplicate dirty source member")
        with tarfile.open(dirty) as archive:
            members = archive.getmembers()
            if len(members) != len(expected) or {m.name for m in members} != set(expected):
                raise RuntimeError("dirty source member closure differs")
            for member in members:
                path = Path(member.name)
                if (
                    path.is_absolute()
                    or ".." in path.parts
                    or not member.isfile()
                    or member.size != expected[member.name]["bytes"]
                    or member.size > 16 * 1024**2
                ):
                    raise RuntimeError("unsafe dirty source member")
                stream = archive.extractfile(member)
                assert stream is not None
                if hashlib.sha256(stream.read()).hexdigest() != expected[member.name]["sha256"]:
                    raise RuntimeError("dirty source bytes differ")
            archive.extractall(checkout, filter="data")
    # The retained local qualifier requires the actual launcher target to be
    # owned by the invoking account. Use stdlib's copied interpreter mode;
    # a default uv symlink would resolve to the image's root-owned executable.
    run(
        [sys.executable, "-m", "venv", "--copies", "--without-pip", str(checkout / ".venv")],
        cwd=checkout,
    )
    # Install before loading test code, still with network disabled and frozen lock.
    run(["make", "sync"], cwd=checkout)
    environment_guard = scratch / "guard-denials"
    environment_guard.mkdir(mode=0o700)
    os.environ["GICLAB_CI_GUARD_JOURNAL"] = str(environment_guard)
    os.environ["PYTHONPATH"] = "/opt/local-ci"
    if development:
        if any(
            not node.startswith("tests/") or ".." in Path(node.split("::")[0]).parts
            for node in args.focused_node
        ):
            raise RuntimeError("explicit repository test node required")
        argv = [
            str(checkout / ".venv/bin/python"),
            "-m",
            "pytest",
            "-p",
            "offline_guard",
            *args.focused_node,
            "--junitxml=" + str(results / "focused.xml"),
            "--basetemp=" + str(scratch / "pytest"),
            "-o",
            "cache_dir=" + str(scratch / "pytest-cache"),
        ]
    else:
        argv = ["make", "ci-check", "BASE_SHA=" + contract["base"], "HEAD_SHA=" + contract["head"]]

    def verify_source():
        if development:
            for path, member in expected.items():
                file = checkout / path
                if (
                    file.is_symlink()
                    or hashlib.sha256(file.read_bytes()).hexdigest() != member["sha256"]
                ):
                    raise RuntimeError("dirty source changed during development gate")
            changed = subprocess.check_output(
                ["git", "diff", "--name-only", contract["head"]], cwd=checkout, text=True
            ).splitlines()
            if set(changed) - set(expected):
                raise RuntimeError("previously unchanged tracked source changed during gate")
        else:
            run(["git", "diff", "--exit-code", contract["head"]], cwd=checkout)

    execute_checked_gate(
        argv,
        checkout=checkout,
        results=results,
        verify_source=verify_source,
        identity={
            "head": contract["head"],
            "base": contract["base"],
            "history_manifest_sha256": hashlib.sha256(
                (inputs / "history.json").read_bytes()
            ).hexdigest(),
            "classification": "focused-dirty-development"
            if development
            else "exact-commit-final-gate",
        },
    )


if __name__ == "__main__":
    main()
