"""Adversarial process tree used only by a later authorized Gate B2 probe."""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path


def _ignore_term() -> None:
    signal.signal(signal.SIGTERM, signal.SIG_IGN)


def _sleeper() -> None:
    _ignore_term()
    while True:
        time.sleep(10)


def _reparented_spawner(output: Path) -> None:
    _ignore_term()
    child = os.fork()
    if child > 0:
        os._exit(0)
    os.setsid()
    spawned = 0
    while True:
        try:
            subprocess.Popen(
                (sys.executable, str(Path(__file__).resolve()), "--role", "sleeper"),
                close_fds=True,
            )
            spawned += 1
        except OSError as exc:
            output.write_text(
                json.dumps(
                    {
                        "schema_version": "0.1.0",
                        "role": "reparented-session-spawner",
                        "pid": os.getpid(),
                        "ppid": os.getppid(),
                        "sid": os.getsid(0),
                        "runtime_uid": os.getuid(),
                        "runtime_gid": os.getgid(),
                        "term_ignored": True,
                        "spawned_before_limit": spawned,
                        "bounded_error": type(exc).__name__,
                    },
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            break
    while True:
        time.sleep(10)


def _root(output: Path) -> None:
    _ignore_term()
    subprocess.Popen(
        (
            sys.executable,
            str(Path(__file__).resolve()),
            "--role",
            "reparented-spawner",
            "--output",
            str(output),
        ),
        start_new_session=True,
        close_fds=True,
    )
    (output.parent / "adversarial-root-ready.json").write_text(
        json.dumps(
            {
                "schema_version": "0.1.0",
                "pid": os.getpid(),
                "ppid": os.getppid(),
                "pgid": os.getpgid(0),
                "sid": os.getsid(0),
                "runtime_uid": os.getuid(),
                "runtime_gid": os.getgid(),
                "term_ignored": True,
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    while True:
        time.sleep(10)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--role", choices=("root", "reparented-spawner", "sleeper"), default="root")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("/giclab/attempt/adversarial-reparented.json"),
    )
    args = parser.parse_args()
    if args.role == "sleeper":
        _sleeper()
    elif args.role == "reparented-spawner":
        _reparented_spawner(args.output)
    else:
        _root(args.output)


if __name__ == "__main__":
    main()
