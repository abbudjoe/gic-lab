"""Prove the future SiRA secret mount is readable without reading its value."""

from __future__ import annotations

import argparse
import json
import os
import stat
from pathlib import Path


class SecretPreflightError(RuntimeError):
    """The mounted secret channel is not the exact T09 channel."""


def inspect_without_reading(path: Path) -> dict[str, object]:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
            raise SecretPreflightError("secret mount is not one regular file")
        if not 16 <= metadata.st_size <= 16_384:
            raise SecretPreflightError("secret mount size is outside the channel contract")
        return {
            "schema_version": "0.1.0",
            "opened_read_only_without_value_read": True,
            "regular_file": True,
            "link_count": metadata.st_nlink,
            "size_bytes": metadata.st_size,
            "container_effective_uid": os.geteuid(),
            "container_effective_gid": os.getegid(),
            "secret_bytes_read": 0,
            "secret_value_or_hash_retained": False,
        }
    finally:
        os.close(descriptor)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--secret", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    receipt = inspect_without_reading(args.secret)
    descriptor = os.open(
        args.output,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        encoded = (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode()
        if os.write(descriptor, encoded) != len(encoded):
            raise SecretPreflightError("secret-channel receipt write was incomplete")
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
