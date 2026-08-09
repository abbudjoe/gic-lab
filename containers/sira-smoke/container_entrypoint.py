"""Secret-file entrypoint for a future authorized SiRA process."""

from __future__ import annotations

import argparse
import os
import stat
from collections.abc import Sequence
from pathlib import Path

CHANNEL_PATH = Path("/run/secrets/sira_api_key")
SIRA_CHANNEL_NAME = "SIRA_API_KEY"
MAX_CHANNEL_BYTES = 16_384


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
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


def run(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    command = tuple(args.command)
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        raise RuntimeError("a SiRA child argument array is required")
    channel_value = read_secret_file()
    environment = child_environment(channel_value)
    os.execvpe(command[0], command, environment)
    raise AssertionError("exec returned unexpectedly")


if __name__ == "__main__":
    raise SystemExit(run())
