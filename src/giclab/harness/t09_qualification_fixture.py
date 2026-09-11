"""Explicit offline qualification input, separate from retained historical evidence.

There is no CLI, environment selection, serialized capability, or historical
fallback. The isolated test bootstrap passes the immutable result directly to the
retained qualification function. Actual archive verification is never replaced.
"""

from __future__ import annotations

import gzip
import hashlib
import io
import json
import os
import tarfile
from dataclasses import dataclass
from pathlib import Path
from typing import Final

FIXTURE_ID: Final = "T09-OFFLINE-QUALIFICATION-FIXTURE-1"
SOURCE_ROOT: Final = "tests/fixtures/t09/finalizer-raw-shape"
GENERATOR_PATH: Final = "src/giclab/harness/t09_qualification_fixture.py"
DATASET_PATH: Final = "tests/fixtures/t09/fanout-two-task-fixture.json"
EVALUATOR_ROOT: Final = "tests/fixtures/t09/pinned-evaluator"
MAX_DECODED_BYTES: Final = 1_048_576
MAX_ARCHIVE_BYTES: Final = 1_048_576
_BINDING_SENTINEL = object()


@dataclass(frozen=True, slots=True)
class FixtureMember:
    path: str
    bytes: int
    sha256: str

    def document(self) -> dict[str, object]:
        return {"path": self.path, "bytes": self.bytes, "sha256": self.sha256}


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _json(value: object) -> bytes:
    return (
        json.dumps(value, allow_nan=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()


def _contents(repository: Path) -> tuple[dict[str, bytes], tuple[FixtureMember, ...]]:
    source = repository / SOURCE_ROOT
    data: dict[str, bytes] = {}
    inputs = []
    for path in sorted(source.rglob("*")):
        if path.is_symlink():
            raise ValueError("qualification source fixture contains a symlink")
        if path.is_file():
            value = path.read_bytes()
            data[path.relative_to(source).as_posix()] = value
            inputs.append(
                FixtureMember(path.relative_to(repository).as_posix(), len(value), _sha(value))
            )
    if len(inputs) != 6:
        raise ValueError("qualification source fixture inventory changed")
    for relative in (
        DATASET_PATH,
        *(
            f"{EVALUATOR_ROOT}/{name}"
            for name in (
                "evaluator.py",
                "run.py",
                "utils/helpers.py",
                "utils/norm.py",
                "utils/models.py",
            )
        ),
    ):
        path = repository / relative
        if path.is_symlink() or path.stat().st_size > MAX_DECODED_BYTES:
            raise ValueError("qualification evaluator fixture source is unsafe")
        value = path.read_bytes()
        inputs.append(FixtureMember(relative, len(value), _sha(value)))
    # These are declared fixture inputs, not measured historical outcomes.
    data.update(
        {
            "attempt-wall.json": _json({"wall_seconds": 1.0, "fixture_id": FIXTURE_ID}),
            "condition.stderr": b"",
            "condition.stdout": b"offline fixture only\n",
            "container-command.json": _json({"fixture_id": FIXTURE_ID, "execution": "not-run"}),
            "container-state.json": _json({"State": {"ExitCode": 0, "OOMKilled": False}}),
            "gpu-accounting.json": _json({"gpu_use_claimed": False}),
            "runtime-cleanup.json": _json(
                {"fixture_id": FIXTURE_ID, "browser_cleanup": "fixture-only"}
            ),
            "attempt-outcome.json": _json(
                {
                    "fixture_id": FIXTURE_ID,
                    "expected_answer": "No relevant answer.",
                    "expected_score": 0.0,
                }
            ),
            "evidence-index.json": _json(
                {"fixture_id": FIXTURE_ID, "classification": "non-scientific-no-network-non-live"}
            ),
        }
    )
    if sum(map(len, data.values())) > MAX_DECODED_BYTES:
        raise ValueError("qualification fixture decoded cap exceeded")
    return data, tuple(inputs)


def _encode(data: dict[str, bytes]) -> bytes:
    output = io.BytesIO()
    with (
        gzip.GzipFile(
            fileobj=output, mode="wb", filename="", mtime=0, compresslevel=9
        ) as compressed,
        tarfile.open(fileobj=compressed, mode="w", format=tarfile.USTAR_FORMAT) as archive,
    ):
        for name, value in sorted(data.items()):
            member = tarfile.TarInfo(name)
            member.size = len(value)
            member.mode = 0o400
            member.uid = member.gid = member.mtime = 0
            member.uname = member.gname = ""
            archive.addfile(member, io.BytesIO(value))
    encoded = output.getvalue()
    if len(encoded) > MAX_ARCHIVE_BYTES:
        raise ValueError("qualification fixture archive cap exceeded")
    return encoded


@dataclass(frozen=True, slots=True)
class DeterministicQualificationArchive:
    """In-process test dependency; cannot be selected by a host request document."""

    fixture_id: str
    archive_path: Path
    bytes: int
    sha256: str
    members: tuple[FixtureMember, ...]
    sources: tuple[FixtureMember, ...]
    generator_sha256: str
    _token: object

    def document(self) -> dict[str, object]:
        return {
            "fixture_id": self.fixture_id,
            "input_kind": "deterministic-test",
            "classification": "non-scientific-no-network-non-live",
            "archive_bytes": self.bytes,
            "archive_sha256": self.sha256,
            "members": [m.document() for m in self.members],
            "sources": [m.document() for m in self.sources],
            "generator_path": GENERATOR_PATH,
            "generator_sha256": self.generator_sha256,
            "expected_behavior": {
                "answer": "No relevant answer.",
                "score": 0.0,
                "historical_replay": False,
            },
        }

    def evaluator_files(self) -> list[dict[str, str]]:
        """The ordered source projection selected by this explicit test input."""
        if self._token is not _BINDING_SENTINEL or self.fixture_id != FIXTURE_ID:
            raise ValueError("qualification fixture binding was not constructed locally")
        return [
            {
                "path": "evaluation/fanout/" + member.path.removeprefix(EVALUATOR_ROOT + "/"),
                "sha256": member.sha256,
            }
            for member in self.sources
            if member.path.startswith(EVALUATOR_ROOT + "/")
        ]

    def validate(self, repository: Path, *, archive_path: Path | None = None) -> None:
        if self._token is not _BINDING_SENTINEL or self.fixture_id != FIXTURE_ID:
            raise ValueError("qualification fixture binding was not constructed locally")
        data, sources = _contents(repository)
        encoded = _encode(data)
        expected = tuple(
            FixtureMember(name, len(value), _sha(value)) for name, value in sorted(data.items())
        )
        if (
            self.sources != sources
            or self.members != expected
            or self.generator_sha256 != _sha((repository / GENERATOR_PATH).read_bytes())
            or self.bytes != len(encoded)
            or self.sha256 != _sha(encoded)
        ):
            raise ValueError("qualification fixture source/member binding drifted")
        path = self.archive_path if archive_path is None else archive_path
        metadata = path.lstat()
        if (
            path.is_symlink()
            or not path.is_file()
            or metadata.st_nlink != 1
            or metadata.st_uid != os.getuid()
        ):
            raise ValueError("qualification fixture archive ownership drifted")
        if metadata.st_size != self.bytes or _sha(path.read_bytes()) != self.sha256:
            raise ValueError("qualification fixture archive bytes drifted")
        with tarfile.open(path, "r:gz") as archive:
            members = archive.getmembers()
            if len(members) != len(expected):
                raise ValueError("qualification fixture member count drifted")
            total = 0
            for member, bound in zip(members, expected, strict=True):
                if not member.isfile() or member.name != bound.path or member.size != bound.bytes:
                    raise ValueError("qualification fixture member identity drifted")
                total += member.size
                if total > MAX_DECODED_BYTES:
                    raise ValueError("qualification fixture decoded cap exceeded")
                stream = archive.extractfile(member)
                if stream is None or _sha(stream.read(bound.bytes + 1)) != bound.sha256:
                    raise ValueError("qualification fixture member content drifted")


def build_deterministic_qualification_archive(
    repository: Path, directory: Path
) -> DeterministicQualificationArchive:
    root = directory.resolve(strict=True)
    if root == repository.resolve() or repository.resolve() in root.parents:
        raise ValueError("qualification fixture archive must remain outside the Git tree")
    data, _sources = _contents(repository)
    encoded = _encode(data)
    path = root / "offline-qualification-fixture.tar.gz"
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())
    return load_deterministic_qualification_archive(repository, path)


def load_deterministic_qualification_archive(
    repository: Path, path: Path
) -> DeterministicQualificationArchive:
    """Reopen one transaction's input without regenerating or repairing its bytes.

    Expectations come from the tracked generator/source fixtures, never from the
    file being reopened. The ordinary historical selector does not call this.
    """
    data, sources = _contents(repository)
    encoded = _encode(data)
    binding = DeterministicQualificationArchive(
        FIXTURE_ID,
        path,
        len(encoded),
        _sha(encoded),
        tuple(FixtureMember(name, len(value), _sha(value)) for name, value in sorted(data.items())),
        sources,
        _sha((repository / GENERATOR_PATH).read_bytes()),
        _BINDING_SENTINEL,
    )
    binding.validate(repository)
    return binding


def validate_fixture_regression_receipt(
    repository: Path,
    binding: DeterministicQualificationArchive,
    receipt: dict[str, object],
) -> None:
    """Validate declared fixture semantics, without accepting historical claims."""
    binding.validate(repository)
    projection = receipt.get("semantic_projection")
    expected = {
        "task_id": "7dcbbbdc7f1120cd",
        "condition": "SIRA-REACTIVE",
        "model_revision": "gpt-4o-2024-11-20",
        "sira_commit": "93fb8d72de71f9a4a13419670adeb34d93cf7acd",
        "task_completed": True,
        "answer_produced": True,
        "evaluator_valid": True,
        "score": 0.0,
        "provider_call_count": 1,
        "browser_action_count": 1,
    }
    if (
        receipt.get("fixture_binding") != binding.document()
        or receipt.get("classification") != "non-scientific-no-network-non-live"
        or receipt.get("historical_replay") is not False
        or receipt.get("live_qualification") is not False
        or receipt.get("source_archive_sha256") != binding.sha256
        or receipt.get("source_archive_bytes") != binding.bytes
        or receipt.get("network_disabled") is not True
        or receipt.get("additional_model_requests") != 0
        or receipt.get("additional_browser_actions") != 0
        or not isinstance(projection, dict)
        or any(projection.get(key) != value for key, value in expected.items())
        or receipt.get("deterministic_repeat_projection") != projection
    ):
        raise ValueError("offline fixture regression semantics or provenance drifted")
