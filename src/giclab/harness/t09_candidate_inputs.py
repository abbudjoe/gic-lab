"""Sealed source inputs for explicit offline T09 tests, never live authority.

Hash order: source bytes -> member inventory and dirty delta -> binding payload
-> binding digest. The payload does not contain its own digest. Paths in public
documents are relative; private snapshot locations are held only by the caller.
No CLI, environment selector, historical fallback, or provider registry exists
here. A bootstrap must supply the expected binding digest out of band.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import stat
import subprocess
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Final

FIXTURE_ID: Final = "T09-OFFLINE-CANDIDATE-SOURCE-PACKAGE-1"
INVENTORY_PATH: Final = "tests/fixtures/t09/offline-candidate-closure.json"
GENERATOR_PATH: Final = "src/giclab/harness/t09_candidate_inputs.py"
MARKER: Final = ".offline-candidate-source.json"
MAX_MEMBERS: Final = 512
MAX_MEMBER_BYTES: Final = 2_000_000
MAX_SOURCE_BYTES: Final = 16_000_000
MAX_BINDING_BYTES: Final = 1_000_000
CLASSIFICATION: Final = "non-scientific-no-network-non-live"
TEMPLATE_REFERENCE: Final = "a98b4b875ab4d101709d62bc7222b5c90681a893"
TEMPLATE_CONTRACT: Final = "V16"
PACKAGE_PREFIX: Final = "experiments/EXP-0001-sira-simulative-vs-reactive/contracts/proposals/"
RUNTIME_PATH: Final = PACKAGE_PREFIX + "T09_PILOT_RUNTIME_IDENTITY_V16.json"
EXECUTION_PATH: Final = PACKAGE_PREFIX + "T09_PILOT_EXECUTION_CONTRACT_V16.json"
COMMAND_PATH: Final = PACKAGE_PREFIX + "T09_PILOT_COMMAND_MANIFESTS_V16.json"
_TOKEN = object()


class CandidateInputError(ValueError):
    """The explicit offline source input does not match its frozen binding."""


def canonical(value: object) -> bytes:
    return (
        json.dumps(value, allow_nan=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()


def sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in items:
        if key in result:
            raise CandidateInputError("duplicate candidate binding key")
        result[key] = value
    return result


def decode(value: bytes) -> dict[str, Any]:
    if len(value) > MAX_BINDING_BYTES:
        raise CandidateInputError("candidate binding exceeds cap")
    result = json.loads(value, object_pairs_hook=_pairs)
    if not isinstance(result, dict) or canonical(result) != value:
        raise CandidateInputError("candidate binding must be a canonical object")
    return result


def _relative(value: str) -> tuple[str, ...]:
    path = PurePosixPath(value)
    if (
        not value
        or path.is_absolute()
        or path.as_posix() != value
        or any(part in {"", ".", ".."} for part in value.split("/"))
    ):
        raise CandidateInputError("candidate member path is unsafe")
    return path.parts


def read_member(root: Path, relative: str) -> bytes:
    """Descriptor-relative, no-follow read with a stable before/after identity."""
    parts = _relative(relative)
    descriptor = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    directories = [(root, os.fstat(descriptor))]
    try:
        prefix = root
        for part in parts[:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor)
            prefix = prefix / part
            directories.append((prefix, os.fstat(child)))
            os.close(descriptor)
            descriptor = child
        fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=descriptor)
        try:
            before = os.fstat(fd)
            if (
                not stat.S_ISREG(before.st_mode)
                or before.st_nlink != 1
                or before.st_uid != os.getuid()
                or before.st_size > MAX_MEMBER_BYTES
                or before.st_mode & (stat.S_ISUID | stat.S_ISGID | 0o022)
            ):
                raise CandidateInputError("candidate member metadata is unsafe")
            value = bytearray()
            while len(value) <= MAX_MEMBER_BYTES:
                chunk = os.read(fd, min(65536, MAX_MEMBER_BYTES + 1 - len(value)))
                if not chunk:
                    break
                value.extend(chunk)
            after = os.fstat(fd)
            named = os.stat(parts[-1], dir_fd=descriptor, follow_symlinks=False)

            def identity(item: os.stat_result) -> tuple[int, int, int, int, int]:
                return (
                    item.st_dev,
                    item.st_ino,
                    item.st_size,
                    item.st_mtime_ns,
                    item.st_ctime_ns,
                )

            if identity(before) != identity(after) or identity(after) != identity(named):
                raise CandidateInputError("candidate member replaced during read")
            for directory, original in directories:
                current = directory.lstat()
                if (
                    not stat.S_ISDIR(current.st_mode)
                    or current.st_uid != os.getuid()
                    or current.st_mode & 0o022
                    or (current.st_dev, current.st_ino) != (original.st_dev, original.st_ino)
                ):
                    raise CandidateInputError("candidate directory replaced during read")
            if len(value) != before.st_size or len(value) > MAX_MEMBER_BYTES:
                raise CandidateInputError("candidate member byte size changed")
            return bytes(value)
        finally:
            os.close(fd)
    finally:
        os.close(descriptor)


def _git(repository: Path, *args: str, missing: bool = False) -> bytes | None:
    result = subprocess.run(
        ["git", "-C", str(repository), *args],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        timeout=15,
        check=False,
    )
    if result.returncode:
        if missing:
            return None
        raise CandidateInputError("candidate parent Git identity cannot be verified")
    return result.stdout


def _parent(repository: Path, head: str, tree: str) -> None:
    for value in (head, tree):
        if len(value) != 40 or any(c not in "0123456789abcdef" for c in value):
            raise CandidateInputError("candidate parent identity is malformed")
    if _git(repository, "rev-parse", f"{head}^{{tree}}") != (tree + "\n").encode():
        raise CandidateInputError("candidate parent tree differs")


def _inventory(repository: Path) -> list[dict[str, str]]:
    document = json.loads(read_member(repository, INVENTORY_PATH), object_pairs_hook=_pairs)
    if set(document) != {
        "schema_version",
        "scope",
        "classification",
        "template_contract",
        "members",
    }:
        raise CandidateInputError("candidate closure fields changed")
    if (
        document["schema_version"] != "1.0.0"
        or document["template_contract"] != TEMPLATE_CONTRACT
        or document["scope"] != "offline-candidate-source-package"
        or document["classification"] != CLASSIFICATION
    ):
        raise CandidateInputError("candidate closure identity changed")
    members = document["members"]
    if not isinstance(members, list) or not 1 <= len(members) <= MAX_MEMBERS:
        raise CandidateInputError("candidate closure member cap exceeded")
    paths = []
    for member in members:
        if not isinstance(member, dict) or set(member) != {"path", "role"}:
            raise CandidateInputError("candidate closure member is malformed")
        _relative(member["path"])
        if member["role"] not in {
            "retained-entrypoint",
            "import-dependency",
            "import-package",
            "retained-resource",
            "historical-template",
            "qualification-fixture-input",
            "candidate-binding-input",
            "active-validation-input",
            "control-validation-input",
        }:
            raise CandidateInputError("candidate closure role is unsupported")
        paths.append(member["path"])
    if paths != sorted(set(paths)):
        raise CandidateInputError("candidate closure contains duplicate or unordered members")
    validation_inputs = {
        path.relative_to(repository).as_posix()
        for base in ("src/giclab", "containers/sira-smoke/pragmatic")
        for path in (repository / base).rglob("*.py")
    } | {
        path.relative_to(repository).as_posix() for path in (repository / "schemas").glob("*.json")
    }
    if not validation_inputs.issubset(paths):
        raise CandidateInputError("candidate closure omits an active validation input")
    return members


def _record(path: str, role: str, value: bytes) -> dict[str, object]:
    runtime_paths = ["/opt/giclab-project/" + path]
    expected_import = None
    if path.startswith("src/"):
        runtime_paths.extend(
            ["/opt/giclab-src/" + path[4:], "/opt/giclab-accounting-src/" + path[4:]]
        )
        if path.endswith(".py"):
            expected_import = path[4:-3].replace("/", ".").removesuffix(".__init__")
    elif path.startswith("containers/sira-smoke/") and path.endswith(".py"):
        runtime_paths.append("/opt/giclab/" + PurePosixPath(path).name)
    elif path == EXECUTION_PATH:
        runtime_paths.append("/opt/giclab-contracts/execution.json")
    elif path == COMMAND_PATH:
        runtime_paths.append("/opt/giclab-contracts/commands.json")
    return {
        "path": path,
        "role": role,
        "bytes": len(value),
        "sha256": sha(value),
        "runtime_paths": runtime_paths,
        "expected_import": expected_import,
    }


@dataclass(frozen=True, slots=True)
class CandidateSourceSnapshot:
    root: Path
    binding_bytes: bytes
    parent_repository: Path
    _token: object
    _root_identity: tuple[int, int]

    @property
    def digest(self) -> str:
        return sha(self.binding_bytes)

    def document(self) -> dict[str, Any]:
        return decode(self.binding_bytes)

    def source_sha256(self, repository: Path, relative: str) -> str:
        """Enforce one source identity at copied/mounted package boundaries."""
        self.validate()
        selected = next(
            (m for m in self.document()["source_members"] if m["path"] == relative), None
        )
        value = read_member(repository, relative)
        if selected is None or len(value) != selected["bytes"] or sha(value) != selected["sha256"]:
            raise CandidateInputError("candidate source differs across package boundaries")
        return sha(value)

    def package_identity(self, repository: Path) -> tuple[str, str]:
        """Parent Git identity, explicitly distinct from the candidate byte digest."""
        validate_candidate_package(self, repository)
        document = self.document()
        _parent(self.parent_repository, document["parent_head"], document["parent_tree"])
        return document["parent_head"], document["parent_tree"]

    def command_package_sha256(self, repository: Path) -> str:
        validate_candidate_package(self, repository)
        return sha(read_member(repository, COMMAND_PATH))

    def template_repository(self) -> Path:
        """Read-only template metadata; never an executed candidate source root.

        Target selection still names historical V16, not candidate acceptance.
        Every metadata input it may consume must equal the sealed snapshot.
        """
        self.validate()
        for member in self.document()["source_members"]:
            if member["role"] in {
                "historical-template",
                "control-validation-input",
                "retained-resource",
            }:
                value = read_member(self.parent_repository, member["path"])
                if len(value) != member["bytes"] or sha(value) != member["sha256"]:
                    raise CandidateInputError("bound template metadata changed")
        return self.parent_repository

    def validate(self) -> None:
        if self._token is not _TOKEN:
            raise CandidateInputError("candidate input was not explicitly loaded")
        root_metadata = self.root.lstat()
        if (
            not stat.S_ISDIR(root_metadata.st_mode)
            or (root_metadata.st_dev, root_metadata.st_ino) != self._root_identity
        ):
            raise CandidateInputError("candidate source root was replaced")
        document = self.document()
        members = document["source_members"]
        expected = {member["path"] for member in members}
        actual: set[str] = set()
        for directory, dirs, files in os.walk(self.root, followlinks=False):
            for name in (*dirs, *files):
                path = Path(directory) / name
                if path.is_symlink():
                    raise CandidateInputError("candidate snapshot contains a symlink")
            actual.update(
                (Path(directory) / name).relative_to(self.root).as_posix() for name in files
            )
        if actual != expected | {MARKER}:
            raise CandidateInputError("candidate snapshot member set changed")
        for member in members:
            value = read_member(self.root, member["path"])
            if len(value) != member["bytes"] or sha(value) != member["sha256"]:
                raise CandidateInputError("candidate snapshot source bytes changed")
        if read_member(self.root, MARKER) != canonical(
            {"candidate_binding_sha256": self.digest, "classification": CLASSIFICATION}
        ):
            raise CandidateInputError("candidate snapshot binding marker changed")


def reject_candidate_source(repository: Path) -> None:
    """Normal entrypoints call this before credentials or environmental effects."""
    if os.path.lexists(repository / MARKER):
        raise CandidateInputError(
            "offline candidate source cannot enter historical/live invocation"
        )


def build_candidate_source_snapshot(
    repository: Path,
    destination: Path,
    *,
    parent_head: str,
    parent_tree: str,
    qualification_document: dict[str, object],
) -> CandidateSourceSnapshot:
    """Copy only the reviewed explicit closure; never absorb arbitrary files."""
    _parent(repository, parent_head, parent_tree)
    if _git(repository, "rev-parse", "HEAD") != (parent_head + "\n").encode():
        raise CandidateInputError("candidate parent is not the selected source HEAD")
    if destination.is_symlink() or destination.resolve().is_relative_to(repository.resolve()):
        raise CandidateInputError("candidate snapshot must be private and outside the repository")
    # The archive identity is independent of the candidate source identity.
    if (
        qualification_document.get("fixture_id") != "T09-OFFLINE-QUALIFICATION-FIXTURE-1"
        or qualification_document.get("archive_bytes") != 2034
        or qualification_document.get("archive_sha256")
        != "284c3c37b9be5c9cead25499252c8aeec908157da6a99d1d79cc312b83d20acb"
        or qualification_document.get("classification") != CLASSIFICATION
    ):
        raise CandidateInputError("candidate qualification archive identity changed")
    source = {}
    members = []
    delta = []
    locked = []
    for item in _inventory(repository):
        path, role = item["path"], item["role"]
        value = read_member(repository, path)
        source[path] = value
        record = _record(path, role, value)
        members.append(record)
        original = _git(repository, "show", f"{parent_head}:{path}", missing=True)
        if role == "historical-template":
            if (
                original != value
                or _git(repository, "show", f"{TEMPLATE_REFERENCE}:{path}") != value
            ):
                raise CandidateInputError("candidate scientific/policy template changed")
            locked.append(record)
        if original != value:
            delta.append(
                {
                    "path": path,
                    "parent_sha256": None if original is None else sha(original),
                    "candidate_sha256": sha(value),
                }
            )
    if sum(map(len, source.values())) > MAX_SOURCE_BYTES:
        raise CandidateInputError("candidate source closure exceeds byte cap")
    payload = {
        "schema_version": "1.0.0",
        "scope": "offline-candidate-source-package",
        "audience": "isolated-offline-test-bootstrap",
        "fixture_id": FIXTURE_ID,
        "revision": 1,
        "classification": CLASSIFICATION,
        "template_contract": "V16",
        "historical_template_reference": TEMPLATE_REFERENCE,
        "parent_head": parent_head,
        "parent_tree": parent_tree,
        "source_kind": "dirty-snapshot" if delta else "committed-source-closure",
        "dirty_delta": delta,
        "dirty_delta_sha256": sha(canonical(delta)),
        "source_members": members,
        "source_member_manifest_sha256": sha(canonical(members)),
        "unchanged_template_members": locked,
        "scientific_policy_sha256": sha(canonical(locked)),
        "qualification_fixture": qualification_document,
        "qualification_member_manifest_sha256": sha(canonical(qualification_document["members"])),
        "generator_sha256": sha(source[GENERATOR_PATH]),
        "closure_schema_sha256": sha(source[INVENTORY_PATH]),
        "limits": {
            "members": MAX_MEMBERS,
            "member_bytes": MAX_MEMBER_BYTES,
            "source_bytes": MAX_SOURCE_BYTES,
        },
        "historical_replay": "not-run",
        "live_qualification": "not-run",
        "scientific_result": None,
    }
    binding = canonical(payload)
    destination.mkdir(mode=0o700)
    snapshot_root = destination / "source"
    snapshot_root.mkdir(mode=0o700)
    for path, value in source.items():
        target = snapshot_root / path
        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        if read_member(snapshot_root, path) != value or read_member(repository, path) != value:
            raise CandidateInputError("candidate source changed during snapshot copy")
    for metadata_path, value in (
        (destination / "binding.json", binding),
        (
            snapshot_root / MARKER,
            canonical({"candidate_binding_sha256": sha(binding), "classification": CLASSIFICATION}),
        ),
    ):
        fd = os.open(metadata_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400)
        with os.fdopen(fd, "wb") as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
    root_metadata = snapshot_root.lstat()
    result = CandidateSourceSnapshot(
        snapshot_root, binding, repository, _TOKEN, (root_metadata.st_dev, root_metadata.st_ino)
    )
    result.validate()
    return result


def load_candidate_source_snapshot(
    destination: Path,
    *,
    expected_binding_sha256: str,
    parent_repository: Path,
    expected_parent_head: str,
    expected_parent_tree: str,
) -> CandidateSourceSnapshot:
    """Explicit test-bootstrap loader; an expected digest is never read from the input."""
    binding = read_member(destination, "binding.json")
    if sha(binding) != expected_binding_sha256:
        raise CandidateInputError("candidate binding digest differs from explicit selection")
    document = decode(binding)
    required = {
        "schema_version",
        "scope",
        "audience",
        "fixture_id",
        "revision",
        "classification",
        "template_contract",
        "historical_template_reference",
        "parent_head",
        "parent_tree",
        "source_kind",
        "dirty_delta",
        "dirty_delta_sha256",
        "source_members",
        "source_member_manifest_sha256",
        "unchanged_template_members",
        "scientific_policy_sha256",
        "qualification_fixture",
        "qualification_member_manifest_sha256",
        "generator_sha256",
        "closure_schema_sha256",
        "limits",
        "historical_replay",
        "live_qualification",
        "scientific_result",
    }
    if (
        set(document) != required
        or document.get("schema_version") != "1.0.0"
        or document.get("template_contract") != TEMPLATE_CONTRACT
        or document.get("fixture_id") != FIXTURE_ID
        or document.get("revision") != 1
        or document.get("scope") != "offline-candidate-source-package"
        or document.get("classification") != CLASSIFICATION
        or document.get("audience") != "isolated-offline-test-bootstrap"
        or document.get("historical_template_reference") != TEMPLATE_REFERENCE
        or document.get("parent_head") != expected_parent_head
        or document.get("parent_tree") != expected_parent_tree
        or document.get("historical_replay") != "not-run"
        or document.get("live_qualification") != "not-run"
        or document.get("scientific_result") is not None
        or document.get("limits")
        != {
            "members": MAX_MEMBERS,
            "member_bytes": MAX_MEMBER_BYTES,
            "source_bytes": MAX_SOURCE_BYTES,
        }
    ):
        raise CandidateInputError("candidate binding identity differs")
    qualification = document.get("qualification_fixture")
    if (
        not isinstance(qualification, dict)
        or qualification.get("fixture_id") != "T09-OFFLINE-QUALIFICATION-FIXTURE-1"
        or qualification.get("archive_bytes") != 2034
        or qualification.get("archive_sha256")
        != "284c3c37b9be5c9cead25499252c8aeec908157da6a99d1d79cc312b83d20acb"
        or qualification.get("classification") != CLASSIFICATION
        or document.get("qualification_member_manifest_sha256")
        != sha(canonical(qualification.get("members")))
    ):
        raise CandidateInputError("candidate qualification binding differs")
    _parent(parent_repository, expected_parent_head, expected_parent_tree)
    root_metadata = (destination / "source").lstat()
    result = CandidateSourceSnapshot(
        destination / "source",
        binding,
        parent_repository,
        _TOKEN,
        (root_metadata.st_dev, root_metadata.st_ino),
    )
    result.validate()
    inventory = _inventory(result.root)
    members = document["source_members"]
    if [{"path": m["path"], "role": m["role"]} for m in members] != inventory:
        raise CandidateInputError("candidate binding and explicit closure differ")
    delta = []
    locked = []
    for member in members:
        original = _git(
            parent_repository, "show", f"{expected_parent_head}:{member['path']}", missing=True
        )
        value = read_member(result.root, member["path"])
        if member != _record(member["path"], member["role"], value):
            raise CandidateInputError("candidate source member mapping differs")
        if original != value:
            delta.append(
                {
                    "path": member["path"],
                    "parent_sha256": None if original is None else sha(original),
                    "candidate_sha256": sha(value),
                }
            )
        if member["role"] == "historical-template":
            if (
                original != value
                or _git(parent_repository, "show", f"{TEMPLATE_REFERENCE}:{member['path']}")
                != value
            ):
                raise CandidateInputError("candidate scientific/policy template changed")
            locked.append(member)
    if (
        document["dirty_delta"] != delta
        or document["source_kind"] != ("dirty-snapshot" if delta else "committed-source-closure")
        or document["dirty_delta_sha256"] != sha(canonical(delta))
        or document["source_member_manifest_sha256"] != sha(canonical(members))
        or document["unchanged_template_members"] != locked
        or document["scientific_policy_sha256"] != sha(canonical(locked))
        or document["generator_sha256"] != sha(read_member(result.root, GENERATOR_PATH))
        or document["closure_schema_sha256"] != sha(read_member(result.root, INVENTORY_PATH))
    ):
        raise CandidateInputError("candidate source/delta/template digest differs")
    return result


def project_candidate_package(
    snapshot: CandidateSourceSnapshot, destination: Path
) -> dict[str, object]:
    """Derive three input documents; source and scientific template stay sealed.

    Call from the isolated bootstrap after loading all giclab code from this
    snapshot. No provider contract registration or tracked file is modified.
    Historical identifiers in these documents are template selectors only;
    the candidate marker binds the actual source closure used by the test.
    """
    snapshot.validate()
    if destination.resolve().is_relative_to(snapshot.root.resolve()):
        raise CandidateInputError("candidate package must not mutate source snapshot")
    destination.mkdir(mode=0o700)
    for member in snapshot.document()["source_members"]:
        target = destination / member["path"]
        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        value = read_member(snapshot.root, member["path"])
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(value)
    runtime = json.loads(read_member(snapshot.root, RUNTIME_PATH), object_pairs_hook=_pairs)
    source_map = {m["path"]: m for m in snapshot.document()["source_members"]}
    for member in runtime["repository_instrumentation"]["files"]:
        member["sha256"] = source_map[member["path"]]["sha256"]
    (destination / RUNTIME_PATH).write_bytes(canonical(runtime))
    execution = json.loads(read_member(snapshot.root, EXECUTION_PATH), object_pairs_hook=_pairs)
    execution["contract_bindings"]["runtime"]["sha256"] = sha(canonical(runtime))
    (destination / EXECUTION_PATH).write_bytes(canonical(execution))
    generator = destination / "containers/sira-smoke/pragmatic/t09_freeze_commands.py"
    spec = importlib.util.spec_from_file_location("offline_candidate_command_generator", generator)
    if spec is None or spec.loader is None:
        raise CandidateInputError("candidate command generator cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    # Compile the held, inventoried bytes directly. Import machinery may write
    # an unbound __pycache__ member or read stale bytecode from an ambient tree.
    exec(
        compile(
            read_member(destination, generator.relative_to(destination).as_posix()),
            str(generator),
            "exec",
        ),
        module.__dict__,
    )
    commands = module.render(destination, provider_version="V16", source_inputs=snapshot)
    (destination / COMMAND_PATH).write_bytes(module.encode_command_manifest_document(commands))
    derived = []
    for relative in (RUNTIME_PATH, EXECUTION_PATH, COMMAND_PATH):
        old = read_member(snapshot.root, relative)
        new = read_member(destination, relative)
        derived.append(
            {
                "path": relative,
                "template_bytes": len(old),
                "template_sha256": sha(old),
                "bytes": len(new),
                "sha256": sha(new),
                "field_differences": _field_differences(json.loads(old), json.loads(new)),
            }
        )
    marker: dict[str, object] = {
        "candidate_binding_sha256": snapshot.digest,
        "classification": CLASSIFICATION,
        "template_contract": "V16",
        "derived_inputs": derived,
    }
    (destination / MARKER).write_bytes(canonical(marker))
    snapshot.validate()
    return marker


def _field_differences(before: Any, after: Any, path: str = "") -> list[dict[str, Any]]:
    """Index every mechanical projection difference using JSON Pointer paths."""
    if before == after:
        return []
    if isinstance(before, dict) and isinstance(after, dict) and before.keys() == after.keys():
        return [
            difference
            for key in sorted(before)
            for difference in _field_differences(
                before[key], after[key], path + "/" + key.replace("~", "~0").replace("/", "~1")
            )
        ]
    if isinstance(before, list) and isinstance(after, list) and len(before) == len(after):
        return [
            difference
            for index, (old, new) in enumerate(zip(before, after, strict=True))
            for difference in _field_differences(old, new, f"{path}/{index}")
        ]
    return [{"path": path, "template": before, "candidate": after}]


def validate_candidate_package(
    snapshot: CandidateSourceSnapshot, repository: Path
) -> dict[str, Any]:
    """Check exact cross-package equality plus independently limited projection."""
    snapshot.validate()
    marker = decode(read_member(repository, MARKER))
    if (
        set(marker)
        != {"candidate_binding_sha256", "classification", "template_contract", "derived_inputs"}
        or marker.get("template_contract") != TEMPLATE_CONTRACT
        or marker.get("candidate_binding_sha256") != snapshot.digest
        or marker.get("classification") != CLASSIFICATION
    ):
        raise CandidateInputError("candidate package switched source snapshot")
    derived = marker.get("derived_inputs")
    if not isinstance(derived, list) or [m.get("path") for m in derived] != [
        RUNTIME_PATH,
        EXECUTION_PATH,
        COMMAND_PATH,
    ]:
        raise CandidateInputError("candidate derived input set differs")
    source_map = {m["path"]: m for m in snapshot.document()["source_members"]}
    actual_members: set[str] = set()
    for directory, dirs, files in os.walk(repository, followlinks=False):
        for name in (*dirs, *files):
            if (Path(directory) / name).is_symlink():
                raise CandidateInputError("candidate package contains a symlink")
        actual_members.update(
            (Path(directory) / name).relative_to(repository).as_posix() for name in files
        )
    if actual_members != set(source_map) | {MARKER}:
        raise CandidateInputError("candidate package member set differs")
    for relative in source_map:
        if relative not in {RUNTIME_PATH, EXECUTION_PATH, COMMAND_PATH}:
            value = read_member(repository, relative)
            if (
                len(value) != source_map[relative]["bytes"]
                or sha(value) != source_map[relative]["sha256"]
            ):
                raise CandidateInputError("candidate package source member differs")
    for member in derived:
        value = read_member(repository, member["path"])
        original = read_member(snapshot.root, member["path"])
        if (len(value), sha(value), len(original), sha(original)) != (
            member["bytes"],
            member["sha256"],
            member["template_bytes"],
            member["template_sha256"],
        ):
            raise CandidateInputError("candidate derived input bytes differ")
        if member.get("field_differences") != _field_differences(
            json.loads(original), json.loads(value)
        ):
            raise CandidateInputError("candidate derived field inventory differs")
    runtime = json.loads(read_member(repository, RUNTIME_PATH), object_pairs_hook=_pairs)
    template_runtime = json.loads(
        read_member(snapshot.root, RUNTIME_PATH), object_pairs_hook=_pairs
    )
    for original in template_runtime["repository_instrumentation"]["files"]:
        original["sha256"] = source_map[original["path"]]["sha256"]
    if runtime != template_runtime:
        raise CandidateInputError("candidate runtime scientific/policy projection differs")
    execution = json.loads(read_member(repository, EXECUTION_PATH), object_pairs_hook=_pairs)
    template_execution = json.loads(
        read_member(snapshot.root, EXECUTION_PATH), object_pairs_hook=_pairs
    )
    template_execution["contract_bindings"]["runtime"]["sha256"] = sha(
        read_member(repository, RUNTIME_PATH)
    )
    if execution != template_execution:
        raise CandidateInputError("candidate execution scientific/policy projection differs")
    generator = repository / "containers/sira-smoke/pragmatic/t09_freeze_commands.py"
    spec = importlib.util.spec_from_file_location("offline_candidate_command_validation", generator)
    if spec is None or spec.loader is None:
        raise CandidateInputError("candidate command validator cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    exec(
        compile(
            read_member(repository, generator.relative_to(repository).as_posix()),
            str(generator),
            "exec",
        ),
        module.__dict__,
    )
    expected_commands = module.render(repository, provider_version="V16", source_inputs=snapshot)
    actual_commands = json.loads(read_member(repository, COMMAND_PATH), object_pairs_hook=_pairs)
    if actual_commands != expected_commands:
        raise CandidateInputError("candidate command/argv projection differs")
    return marker
