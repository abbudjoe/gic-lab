"""Active offline container boundary checks; no experimental effects."""

import json
import os
import resource
import shutil
import socket
import subprocess
import sys
from pathlib import Path


def main():
    assert os.geteuid() == 10001 and os.getegid() == 10001
    assert resource.getrlimit(resource.RLIMIT_CORE) == (0, 0)
    assert not any(
        name in os.environ
        for name in ("DOCKER_HOST", "DOCKER_CONTEXT", "SSH_AUTH_SOCK", "OPENAI_API_KEY", "GH_TOKEN")
    )
    assert not any(Path(p).exists() for p in ("/var/run/docker.sock", "/run/docker.sock"))
    assert shutil.which("docker") is None and shutil.which("sudo") is None
    status = Path("/proc/self/status").read_text()
    assert "NoNewPrivs:\t1" in status and "CapEff:\t0000000000000000" in status
    for parent in (Path("/input"), Path("/usr")):
        try:
            (parent / "gic-denied-write").write_bytes(b"denied")
        except OSError as error:
            assert error.errno in (13, 30)
        else:
            raise AssertionError("container input/root is writable")
    assert not Path("/Users").exists() and not Path("/Volumes").exists()
    Path("/work/tmp").mkdir(mode=0o700)
    journal = Path("/results/guard")
    journal.mkdir(mode=0o700)
    os.environ["GICLAB_CI_GUARD_JOURNAL"] = str(journal)
    sys.path.insert(0, "/opt/local-ci")
    import offline_guard

    offline_guard.install()
    for executable in ("docker", "sudo"):
        with offline_guard.expected_denial(
            "container-smoke-" + executable, "process:" + executable
        ):
            try:
                subprocess.run([executable, "info"], timeout=1, check=False)
            except offline_guard.EffectDenied:
                pass
            else:
                raise AssertionError("environmental command escaped")
    with (
        socket.socket() as connection,
        offline_guard.expected_denial("container-smoke-network", "socket.connect"),
    ):
        try:
            connection.connect(("192.0.2.1", 443))
        except offline_guard.EffectDenied:
            pass
        else:
            raise AssertionError("external connection escaped")
    left, right = socket.socketpair()
    with left, right:
        left.sendall(b"gic-private-ipc")
        assert right.recv(32) == b"gic-private-ipc"
    child = subprocess.run(
        [sys.executable, "-c", "import sys; print('sitecustomize' in sys.modules)"],
        env={"PATH": os.defpath},
        capture_output=True,
        text=True,
        timeout=5,
        check=True,
    )
    assert child.stdout.strip() == "True"
    denials = [
        json.loads(line) for p in journal.glob("*.jsonl") for line in p.read_text().splitlines()
    ]
    assert len(denials) == 3 and all(row["expected_by"] for row in denials)
    result = {
        "classification": "offline-CI-containment-smoke-not-experimental-evidence",
        "effective_nonroot": True,
        "input_and_root_readonly": True,
        "capabilities_empty": True,
        "no_new_privileges": True,
        "daemon_endpoint_and_cli_absent": True,
        "private_ipc_and_guarded_child": True,
        "expected_denials": len(denials),
        "unexpected_denials": 0,
        "hosted_ci": "not-run-by-owner-instruction",
    }
    (Path("/results") / "smoke.json").write_text(json.dumps(result, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
