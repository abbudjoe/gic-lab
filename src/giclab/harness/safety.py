"""Credential-safe command construction helpers."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from pathlib import Path

_ENVIRONMENT_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_SECRET_NAME = re.compile(
    r"(?:^|_)(?:API_?KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIALS?|PRIVATE_?KEY)(?:_|$)",
    re.IGNORECASE,
)
_SECRET_OPTION = re.compile(
    r"^--?(?:[^=]*(?:api[-_]?key|token|secret|password|passwd|credential|private[-_]?key))"
    r"(?:=|$)",
    re.IGNORECASE,
)
_SECRET_VALUE_PATTERNS = (
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{12,}\b"),
)
_REDACTION_MARKER = b"[REDACTED]"


class CredentialExposureError(ValueError):
    """Raised without echoing private material when retained evidence would expose it."""


class ExactCredentialScrubber:
    """One run's exact-value refusal and output-redaction contract."""

    __slots__ = ("_private_bytes", "_replacement")

    def __setattr__(self, name: str, value: object) -> None:
        if name in self.__slots__ and hasattr(self, name):
            raise AttributeError(f"credential scrubber state is write-owned: {name}")
        object.__setattr__(self, name, value)

    def __init__(self, private_values: Iterable[str]) -> None:
        encoded: set[bytes] = set()
        for private_value in private_values:
            if not private_value:
                raise ValueError("secret environment values must not be empty")
            encoded.add(private_value.encode("utf-8"))
        self._private_bytes = tuple(sorted(encoded, key=len, reverse=True))
        self._replacement = (
            b""
            if any(private_value in _REDACTION_MARKER for private_value in self._private_bytes)
            else _REDACTION_MARKER
        )

    @property
    def private_bytes(self) -> tuple[bytes, ...]:
        return self._private_bytes

    @property
    def replacement(self) -> bytes:
        return self._replacement

    def assert_json(self, value: object, *, label: str) -> None:
        """Refuse exact private values in JSON keys, values, or encoded scalars."""

        for text_value in self._text_values(value):
            self.assert_bytes(text_value.encode("utf-8"), label=label)
        encoded = json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        self.assert_bytes(encoded, label=label)

    def assert_file(self, path: Path, *, label: str, chunk_size: int = 1024 * 1024) -> None:
        """Scan a retained file without loading it all into memory."""

        if chunk_size <= 0:
            raise ValueError("credential scan chunk_size must be > 0")
        if not self._private_bytes:
            return
        retained = max(len(private_value) for private_value in self._private_bytes) - 1
        overlap = b""
        with path.open("rb") as handle:
            while chunk := handle.read(chunk_size):
                combined = overlap + chunk
                self.assert_bytes(combined, label=label)
                overlap = combined[-retained:] if retained else b""

    def assert_bytes(self, value: bytes, *, label: str) -> None:
        if any(private_value in value for private_value in self._private_bytes):
            raise CredentialExposureError(f"{label} contains an exact injected credential value")

    @classmethod
    def _text_values(cls, value: object) -> Iterable[str]:
        if isinstance(value, str):
            yield value
        elif isinstance(value, Mapping):
            for key, item in value.items():
                if isinstance(key, str):
                    yield key
                yield from cls._text_values(item)
        elif isinstance(value, list | tuple):
            for item in value:
                yield from cls._text_values(item)


def validate_environment_name(name: str) -> None:
    """Reject environment names that cannot be passed portably."""

    if _ENVIRONMENT_NAME.fullmatch(name) is None:
        raise ValueError(f"invalid environment variable name: {name!r}")


def looks_secret_name(name: str) -> bool:
    """Return whether a name denotes credential material."""

    return _SECRET_NAME.search(name) is not None


def contains_recognizable_secret(value: str) -> bool:
    """Recognize credential formats that must never be serialized."""

    return any(pattern.search(value) is not None for pattern in _SECRET_VALUE_PATTERNS)


def assert_no_secret_literals(
    argv: Iterable[str],
    environment: Iterable[tuple[str, str]],
) -> None:
    """Refuse secret-like command arguments and literal environment values.

    Credentials must be supplied by name through ``secret_environment``. This keeps
    command rendering and event payloads free of credential values.
    """

    arguments = tuple(argv)
    for index, argument in enumerate(arguments):
        if contains_recognizable_secret(argument):
            raise ValueError(f"command argument {index} contains a recognizable secret value")
        if _SECRET_OPTION.search(argument) is not None:
            raise ValueError(f"command argument {index} is secret-bearing; use secret_environment")
    for name, value in environment:
        if looks_secret_name(name):
            raise ValueError(
                f"literal environment variable {name!r} is secret-bearing; use secret_environment"
            )
        if contains_recognizable_secret(value):
            raise ValueError(f"literal environment variable {name!r} contains a secret value")
