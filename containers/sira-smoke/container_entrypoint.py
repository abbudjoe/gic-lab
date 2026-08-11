"""Secret-file entrypoint for a future authorized SiRA process."""

from __future__ import annotations

import argparse
import os
import stat
import time
from collections.abc import Sequence
from pathlib import Path

CHANNEL_PATH = Path("/run/secrets/sira_api_key")
SIRA_CHANNEL_NAME = "SIRA_API_KEY"
MAX_CHANNEL_BYTES = 16_384
ATTEMPT_ROOT = Path("/giclab/attempt")
READY_PATH = ATTEMPT_ROOT / ".giclab-entrypoint-ready"
RELEASE_PATH = ATTEMPT_ROOT / ".giclab-release"
RELEASE_WAIT_SECONDS = 30


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--supervised-release", action="store_true")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    return parser


def read_secret_file(path: Path = CHANNEL_PATH) -> str:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise RuntimeError("the SiRA secret mount must be a regular file")
        raw = os.read(descriptor, MAX_CHANNEL_BYTES + 1)
    finally:
        os.close(descriptor)
    if not raw or len(raw) > MAX_CHANNEL_BYTES or b"\x00" in raw:
        raise RuntimeError("the SiRA secret file is empty or malformed")
    try:
        value = raw.rstrip(b"\r\n").decode("utf-8")
    except UnicodeDecodeError as exc:
        raise RuntimeError("the SiRA secret file must be UTF-8") from exc
    if not value:
        raise RuntimeError("the SiRA secret file is empty")
    return value


def child_environment(secret: str, ambient: dict[str, str] | None = None) -> dict[str, str]:
    environment = dict(os.environ if ambient is None else ambient)
    environment.pop("OPENAI_API_KEY", None)
    environment.pop(SIRA_CHANNEL_NAME, None)
    environment[SIRA_CHANNEL_NAME] = secret
    return environment


def wait_for_supervisor_release() -> None:
    if not ATTEMPT_ROOT.is_dir() or ATTEMPT_ROOT.is_symlink():
        raise RuntimeError("the attempt root is unavailable")
    descriptor = os.open(
        READY_PATH,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        os.write(descriptor, b"ready\n")
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    deadline = time.monotonic() + RELEASE_WAIT_SECONDS
    while time.monotonic() < deadline:
        if RELEASE_PATH.is_file() and not RELEASE_PATH.is_symlink():
            return
        time.sleep(0.05)
    raise RuntimeError("the container supervisor release was not received")


def run(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    command = tuple(args.command)
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        raise RuntimeError("a SiRA child argument array is required")
    if args.supervised_release:
        wait_for_supervisor_release()
    channel_value = read_secret_file()
    environment = child_environment(channel_value)
    os.execvpe(command[0], command, environment)
    raise AssertionError("exec returned unexpectedly")


if __name__ == "__main__":
    raise SystemExit(run())
