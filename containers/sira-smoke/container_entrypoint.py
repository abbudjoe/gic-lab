"""One-child credential entrypoint for an authorized provider process.

The mounted bytes originate from the filtered OPENAI_API_KEY assignment.  The model
metadata child receives the provider-native name and each pinned SiRA condition child
receives only its required ephemeral SIRA_API_KEY alias.
"""

from __future__ import annotations

import argparse
import os
import stat
import time
from collections.abc import Sequence
from pathlib import Path

CHANNEL_PATH = Path("/run/secrets/sira_api_key")
SIRA_CHANNEL_NAME = "SIRA_API_KEY"
SOURCE_ASSIGNMENT_NAME = "OPENAI_API_KEY"
ALLOWED_CHILD_ASSIGNMENTS = frozenset({SOURCE_ASSIGNMENT_NAME, SIRA_CHANNEL_NAME})
MAX_CHANNEL_BYTES = 16_384
SECRET_VALUE_BYTES = frozenset(b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._-")
SECRET_VALUE_CONTRACT = "single-nonempty-ascii-token-[A-Za-z0-9._-]-no-line-terminator-v1"
ATTEMPT_ROOT = Path("/giclab/attempt")
READY_PATH = ATTEMPT_ROOT / ".giclab-entrypoint-ready"
RELEASE_PATH = ATTEMPT_ROOT / ".giclab-release"
RELEASE_WAIT_SECONDS = 30


def _write_all(descriptor: int, encoded: bytes) -> None:
    offset = 0
    while offset < len(encoded):
        written = os.write(descriptor, encoded[offset:])
        if written <= 0:
            raise RuntimeError("supervisor marker write made no progress")
        offset += written


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--supervised-release", action="store_true")
    parser.add_argument(
        "--runtime-assignment",
        choices=tuple(sorted(ALLOWED_CHILD_ASSIGNMENTS)),
        default=SIRA_CHANNEL_NAME,
    )
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
    if (
        not raw
        or len(raw) > MAX_CHANNEL_BYTES
        or any(byte not in SECRET_VALUE_BYTES for byte in raw)
    ):
        raise RuntimeError("the SiRA secret file is empty or malformed")
    try:
        return raw.decode("ascii")
    except UnicodeDecodeError as exc:  # defensive parity with the closed byte set
        raise RuntimeError("the SiRA secret file is malformed") from exc


def child_environment(
    secret: str,
    ambient: dict[str, str] | None = None,
    *,
    runtime_assignment: str = SIRA_CHANNEL_NAME,
) -> dict[str, str]:
    if runtime_assignment not in ALLOWED_CHILD_ASSIGNMENTS:
        raise RuntimeError("the provider child assignment is not allowlisted")
    environment = dict(os.environ if ambient is None else ambient)
    environment.pop("LAMBDA_API_KEY", None)
    environment.pop(SOURCE_ASSIGNMENT_NAME, None)
    environment.pop(SIRA_CHANNEL_NAME, None)
    environment[runtime_assignment] = secret
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
        _write_all(descriptor, b"ready\n")
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
    environment = child_environment(
        channel_value,
        runtime_assignment=args.runtime_assignment,
    )
    os.execvpe(command[0], command, environment)
    raise AssertionError("exec returned unexpectedly")


if __name__ == "__main__":
    raise SystemExit(run())
