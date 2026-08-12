"""Materialize only OPENAI_API_KEY from a repository-external dotenv file."""

from __future__ import annotations

import argparse
import os
import stat
from pathlib import Path

MAX_DOTENV_BYTES = 65_536
MAX_SECRET_BYTES = 16_384
ALLOWED_SECRET_BYTES = frozenset(
    b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._-"
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dotenv", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def _read_regular_nofollow(path: Path, *, max_bytes: int) -> bytes:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_uid != os.getuid()
            or metadata.st_nlink != 1
            or stat.S_IMODE(metadata.st_mode) & 0o077
            or metadata.st_size > max_bytes
        ):
            raise RuntimeError("dotenv metadata is unsafe")
        raw = os.read(descriptor, max_bytes + 1)
        if len(raw) != metadata.st_size or len(raw) > max_bytes:
            raise RuntimeError("dotenv size changed while reading")
        return raw
    finally:
        os.close(descriptor)


def parse_openai_api_key(raw: bytes) -> bytes:
    if b"\0" in raw:
        raise RuntimeError("dotenv contains a NUL byte")
    matches: list[bytes] = []
    for raw_line in raw.splitlines():
        line = raw_line.strip()
        if not line or line.startswith(b"#"):
            continue
        if b"=" not in line:
            raise RuntimeError("dotenv contains a malformed assignment")
        name, value = line.split(b"=", 1)
        if name.strip() == b"OPENAI_API_KEY":
            matches.append(value.strip())
    if len(matches) != 1:
        raise RuntimeError("dotenv must contain exactly one OPENAI_API_KEY assignment")
    credential = matches[0]
    if (
        not credential
        or len(credential) > MAX_SECRET_BYTES
        or any(byte not in ALLOWED_SECRET_BYTES for byte in credential)
    ):
        raise RuntimeError("OPENAI_API_KEY does not satisfy the single-token contract")
    return credential


def write_secret_exclusive(path: Path, secret: bytes) -> None:
    if path.parent.is_symlink() or not path.parent.is_dir():
        raise RuntimeError("secret output parent is unsafe")
    descriptor = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        offset = 0
        while offset < len(secret):
            written = os.write(descriptor, secret[offset:])
            if written <= 0:
                raise RuntimeError("secret write made no progress")
            offset += written
        os.fsync(descriptor)
        if stat.S_IMODE(os.fstat(descriptor).st_mode) != 0o600:
            raise RuntimeError("secret output mode drifted")
    finally:
        os.close(descriptor)


def main() -> int:
    args = _parser().parse_args()
    raw = _read_regular_nofollow(args.dotenv.resolve(strict=True), max_bytes=MAX_DOTENV_BYTES)
    credential = parse_openai_api_key(raw)
    write_secret_exclusive(args.output, credential)
    credential = b""
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
