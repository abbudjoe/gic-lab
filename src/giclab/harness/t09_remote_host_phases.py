"""Exact, phase-specific host bridge validation for the retained T09 runner.

These functions validate private, external request files and retained host outputs.
They do not select a target, mint authority, launch a provider, or run a condition.
The remote runner supplies the environmental primitives; this module makes their
phase boundaries and predecessor chain explicit.
"""

from __future__ import annotations

import builtins
import hashlib
import io
import json
import math
import os
import stat
import tarfile
from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path, PurePosixPath
from typing import Final, cast

from jsonschema import Draft202012Validator

from giclab.control.adapters import AdapterFailure
from giclab.control.remote_bridge import (
    semantic_sha256,
    strict_json_object,
    validate_full_dynamic_frozen_manifest,
    validate_postfreeze_receipt,
)
from giclab.harness.t09_provider_contracts import T09ProviderContract
from giclab.registry import load_json, local_schema_registry

HOST_PHASE_PROTOCOL_VERSION: Final = "1.0.0"
HOST_PHASE_REQUEST_SCHEMA: Final = "schemas/t09-host-phase-request.schema.json"
HOST_PHASE_RECEIPT_SCHEMA: Final = "schemas/t09-host-phase-receipt.schema.json"
MAX_HOST_PHASE_REQUEST_BYTES: Final = 1_048_576
MAX_HOST_PHASE_RECEIPT_BYTES: Final = 4_194_304
MAX_HOST_PHASE_DURATION_SECONDS: Final = 14_400.0
MAX_TRANSFER_ARCHIVE_BYTES: Final = 536_870_912
MAX_TRANSFER_MEMBERS: Final = 4_096
MAX_TRANSFER_MEMBER_BYTES: Final = 67_108_864
_HEX64: Final = frozenset("0123456789abcdef")


class HostPhaseError(RuntimeError):
    """A private phase request or retained phase output failed closed."""


def _is_sha256(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and set(value) <= _HEX64


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(value, allow_nan=False, separators=(",", ":"), sort_keys=True) + "\n"
    ).encode()


def _private_regular(path: Path, *, maximum_bytes: int, label: str) -> tuple[Path, bytes]:
    try:
        metadata = path.stat(follow_symlinks=False)
    except OSError as exc:
        raise HostPhaseError(f"{label} is unavailable") from exc
    if (
        path.is_symlink()
        or not stat.S_ISREG(metadata.st_mode)
        or metadata.st_nlink != 1
        or metadata.st_uid != os.getuid()
        or stat.S_IMODE(metadata.st_mode) != 0o600
        or not 0 <= metadata.st_size <= maximum_bytes
    ):
        raise HostPhaseError(f"{label} is unsafe or oversized")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        held_metadata = os.fstat(descriptor)
        if (
            held_metadata.st_dev != metadata.st_dev
            or held_metadata.st_ino != metadata.st_ino
            or held_metadata.st_size != metadata.st_size
        ):
            raise HostPhaseError(f"{label} changed while being held")
        with os.fdopen(os.dup(descriptor), "rb") as handle:
            encoded = handle.read(maximum_bytes + 1)
        if len(encoded) != metadata.st_size:
            raise HostPhaseError(f"{label} changed while being read")
        return path.resolve(strict=True), encoded
    finally:
        os.close(descriptor)


@dataclass(frozen=True, slots=True)
class PhaseFile:
    path: Path
    bytes: int
    sha256: str

    @classmethod
    def from_document(cls, value: object, *, label: str) -> PhaseFile:
        if not isinstance(value, dict) or set(value) != {"path", "bytes", "sha256"}:
            raise HostPhaseError(f"{label} file binding is malformed")
        path = value.get("path")
        size = value.get("bytes")
        sha = value.get("sha256")
        if (
            not isinstance(path, str)
            or not path.startswith("/")
            or type(size) is not int
            or size < 0
            or not _is_sha256(sha)
        ):
            raise HostPhaseError(f"{label} file identity is malformed")
        return cls(Path(path), size, cast(str, sha))

    def read(self, *, maximum_bytes: int, label: str) -> builtins.bytes:
        _resolved, encoded = _private_regular(self.path, maximum_bytes=maximum_bytes, label=label)
        if len(encoded) != self.bytes or hashlib.sha256(encoded).hexdigest() != self.sha256:
            raise HostPhaseError(f"{label} changed from its request binding")
        return encoded


@dataclass(frozen=True, slots=True)
class RemoteHostBinding:
    provider_contract_version: str
    plan_id: str
    host_run_id: str
    provider_handle_identity: str
    provider_launch_ordinal: int
    provider_entry_receipt_sha256: str
    local_assembly_receipt_sha256: str
    source_commit: str
    source_tree: str
    remote_root: str
    host_transfer_receipt_sha256: str | None

    @classmethod
    def from_document(
        cls,
        value: object,
        *,
        contract: T09ProviderContract,
    ) -> RemoteHostBinding:
        if not isinstance(value, dict):
            raise HostPhaseError("host phase binding is malformed")
        try:
            result = cls(**value)
        except TypeError as exc:
            raise HostPhaseError("host phase binding fields are incomplete") from exc
        if (
            result.provider_contract_version != contract.version
            or result.plan_id != contract.plan_id
            or result.host_run_id != contract.host_run_id
            or not _is_sha256(result.provider_handle_identity)
            or type(result.provider_launch_ordinal) is not int
            or not 1 <= result.provider_launch_ordinal <= contract.max_launch_count
            or not all(
                _is_sha256(candidate)
                for candidate in (
                    result.provider_entry_receipt_sha256,
                    result.local_assembly_receipt_sha256,
                )
            )
            or (
                result.host_transfer_receipt_sha256 is not None
                and not _is_sha256(result.host_transfer_receipt_sha256)
            )
            or len(result.source_commit) != 40
            or len(result.source_tree) != 40
            or not result.remote_root.startswith("/")
            or ".." in PurePosixPath(result.remote_root).parts
        ):
            raise HostPhaseError("host phase binding contradicts the selected contract")
        return result

    def to_document(self) -> dict[str, object]:
        return {
            "provider_contract_version": self.provider_contract_version,
            "plan_id": self.plan_id,
            "host_run_id": self.host_run_id,
            "provider_handle_identity": self.provider_handle_identity,
            "provider_launch_ordinal": self.provider_launch_ordinal,
            "provider_entry_receipt_sha256": self.provider_entry_receipt_sha256,
            "local_assembly_receipt_sha256": self.local_assembly_receipt_sha256,
            "source_commit": self.source_commit,
            "source_tree": self.source_tree,
            "remote_root": self.remote_root,
            "host_transfer_receipt_sha256": self.host_transfer_receipt_sha256,
        }


@dataclass(frozen=True, slots=True)
class RemoteHostPhaseRequest:
    phase: str
    execution_mode: str
    binding: RemoteHostBinding
    previous_phase_receipt_path: Path | None
    previous_phase_receipt_sha256: str | None
    requested_wall_time: float
    requested_monotonic: float
    deadline_monotonic: float
    inputs: Mapping[str, PhaseFile]
    output_paths: Mapping[str, Path]
    expected_projection: Mapping[str, object]
    deterministic_fixture: bool
    request_semantic_sha256: str


def load_host_phase_request(
    repository: Path,
    path: Path,
    *,
    expected_phase: str,
    contract: T09ProviderContract,
) -> RemoteHostPhaseRequest:
    _resolved, encoded = _private_regular(
        path, maximum_bytes=MAX_HOST_PHASE_REQUEST_BYTES, label="host phase request"
    )
    try:
        document = strict_json_object(encoded, label="host phase request")
        schema = load_json(repository / HOST_PHASE_REQUEST_SCHEMA)
        Draft202012Validator(
            schema,
            registry=local_schema_registry(repository / "schemas"),
        ).validate(document)
    except Exception as exc:
        raise HostPhaseError("host phase request failed its exact schema") from exc
    if document.get("phase") != expected_phase:
        raise HostPhaseError("host phase request was replayed at another phase")
    execution_mode = document.get("execution_mode")
    deterministic = document.get("deterministic_fixture")
    if (execution_mode == "external-live" and deterministic is not False) or (
        execution_mode == "deterministic-no-network" and deterministic is not True
    ):
        raise HostPhaseError("host phase execution mode and channel are confused")
    binding = RemoteHostBinding.from_document(document.get("binding"), contract=contract)
    requested_wall = float(cast(float, document["requested_wall_time"]))
    requested_monotonic = float(cast(float, document["requested_monotonic"]))
    deadline_monotonic = float(cast(float, document["deadline_monotonic"]))
    if (
        not all(
            math.isfinite(value)
            for value in (requested_wall, requested_monotonic, deadline_monotonic)
        )
        or requested_wall < 0
        or requested_monotonic < 0
        or not 0 < deadline_monotonic - requested_monotonic <= MAX_HOST_PHASE_DURATION_SECONDS
    ):
        raise HostPhaseError("host phase timing envelope is invalid")
    prior_path_raw = document.get("previous_phase_receipt_path")
    prior_sha = document.get("previous_phase_receipt_sha256")
    prior_path = Path(prior_path_raw) if isinstance(prior_path_raw, str) else None
    if (prior_path is None) != (prior_sha is None):
        raise HostPhaseError("host phase predecessor path/hash binding is incomplete")
    inputs_raw = document.get("inputs")
    output_paths_raw = document.get("output_paths")
    expected_projection = document.get("expected_projection")
    if (
        not isinstance(inputs_raw, dict)
        or not isinstance(output_paths_raw, dict)
        or not isinstance(expected_projection, dict)
    ):
        raise HostPhaseError(
            "host phase inputs, output targets, or expected projection are malformed"
        )
    remote_root = PurePosixPath(binding.remote_root)
    output_paths: dict[str, Path] = {}
    seen_output_paths: set[str] = set()
    for name, value in output_paths_raw.items():
        if not isinstance(name, str) or not isinstance(value, str):
            raise HostPhaseError("host phase output target is malformed")
        candidate = PurePosixPath(value)
        try:
            candidate.relative_to(remote_root)
        except ValueError as exc:
            raise HostPhaseError("host phase output target escaped the remote root") from exc
        if not candidate.is_absolute() or ".." in candidate.parts or value in seen_output_paths:
            raise HostPhaseError("host phase output target is unsafe or duplicated")
        seen_output_paths.add(value)
        output_paths[name] = Path(value)
    return RemoteHostPhaseRequest(
        phase=expected_phase,
        execution_mode=cast(str, execution_mode),
        binding=binding,
        previous_phase_receipt_path=prior_path,
        previous_phase_receipt_sha256=cast(str | None, prior_sha),
        requested_wall_time=requested_wall,
        requested_monotonic=requested_monotonic,
        deadline_monotonic=deadline_monotonic,
        inputs={
            name: PhaseFile.from_document(value, label=name) for name, value in inputs_raw.items()
        },
        output_paths=output_paths,
        expected_projection=cast(dict[str, object], expected_projection),
        deterministic_fixture=cast(bool, deterministic),
        request_semantic_sha256=semantic_sha256(document),
    )


def _json_input(
    request: RemoteHostPhaseRequest,
    name: str,
    *,
    maximum_bytes: int = MAX_HOST_PHASE_RECEIPT_BYTES,
) -> tuple[dict[str, object], str]:
    try:
        bound = request.inputs[name]
    except KeyError as exc:
        raise HostPhaseError(f"host phase omitted required input: {name}") from exc
    encoded = bound.read(maximum_bytes=maximum_bytes, label=name)
    try:
        return strict_json_object(encoded, label=name), hashlib.sha256(encoded).hexdigest()
    except ValueError as exc:
        raise HostPhaseError(f"{name} is not strict JSON") from exc


def bind_generated_host_phase_outputs(
    request: RemoteHostPhaseRequest,
    generated: Mapping[str, Path],
) -> RemoteHostPhaseRequest:
    """Hold exact external-live outputs without rewriting the original request identity."""

    if request.deterministic_fixture or request.execution_mode != "external-live":
        raise HostPhaseError("generated host outputs are forbidden in deterministic mode")
    if set(generated) != set(request.output_paths):
        raise HostPhaseError("generated host outputs differ from their declared targets")
    bound = dict(request.inputs)
    for name, path in generated.items():
        declared = request.output_paths[name]
        if path != declared or name in bound:
            raise HostPhaseError("generated host output replaced an input or changed path")
        _resolved, encoded = _private_regular(
            path,
            maximum_bytes=MAX_HOST_PHASE_RECEIPT_BYTES,
            label=f"generated {name}",
        )
        bound[name] = PhaseFile(
            path=path,
            bytes=len(encoded),
            sha256=hashlib.sha256(encoded).hexdigest(),
        )
    return replace(request, inputs=bound)


def begin_external_host_phase(
    request: RemoteHostPhaseRequest,
    *,
    started_wall_time: float,
    started_monotonic: float,
) -> RemoteHostPhaseRequest:
    """Translate the supervisor duration cap into the remote host clock domain."""

    if request.deterministic_fixture or request.execution_mode != "external-live":
        raise HostPhaseError("external host clock admission received a deterministic request")
    if (
        not math.isfinite(started_wall_time)
        or not math.isfinite(started_monotonic)
        or started_wall_time < request.requested_wall_time
        or started_monotonic < 0
    ):
        raise HostPhaseError("external host clock admission is malformed")
    duration = request.deadline_monotonic - request.requested_monotonic
    return replace(
        request,
        requested_wall_time=started_wall_time,
        requested_monotonic=started_monotonic,
        deadline_monotonic=started_monotonic + duration,
    )


def _load_previous(
    repository: Path,
    request: RemoteHostPhaseRequest,
    *,
    expected_phase: str,
) -> dict[str, object]:
    if request.previous_phase_receipt_path is None or request.previous_phase_receipt_sha256 is None:
        raise HostPhaseError("host phase lacks its exact predecessor receipt")
    _resolved, encoded = _private_regular(
        request.previous_phase_receipt_path,
        maximum_bytes=MAX_HOST_PHASE_RECEIPT_BYTES,
        label="previous host phase receipt",
    )
    if hashlib.sha256(encoded).hexdigest() != request.previous_phase_receipt_sha256:
        raise HostPhaseError("host phase predecessor file hash drifted")
    try:
        document = strict_json_object(encoded, label="previous host phase receipt")
        _validate_receipt_schema(repository, document)
    except Exception as exc:
        raise HostPhaseError("host phase predecessor receipt is invalid") from exc
    projected = dict(document)
    observed = projected.pop("receipt_sha256", None)
    if observed != semantic_sha256(projected):
        raise HostPhaseError("host phase predecessor semantic hash drifted")
    expected_binding = request.binding.to_document()
    if expected_phase == "host-transfer-verify":
        expected_binding["host_transfer_receipt_sha256"] = None
    if document.get("phase") != expected_phase or document.get("binding") != expected_binding:
        raise HostPhaseError("host phase predecessor belongs to another phase or host")
    return document


def validate_host_phase_predecessor(
    repository: Path,
    request: RemoteHostPhaseRequest,
    *,
    expected_phase: str,
) -> Mapping[str, object]:
    """Validate one predecessor before a later environmental phase can start."""

    return _load_previous(repository, request, expected_phase=expected_phase)


def _validate_receipt_schema(repository: Path, document: object) -> None:
    schema = load_json(repository / HOST_PHASE_RECEIPT_SCHEMA)
    Draft202012Validator(
        schema,
        registry=local_schema_registry(repository / "schemas"),
    ).validate(document)


def _phase_receipt(
    repository: Path,
    request: RemoteHostPhaseRequest,
    *,
    completed_wall_time: float,
    completed_monotonic: float,
    outputs: Mapping[str, object],
    output_sha256s: tuple[str, ...],
    cleanup_state_sha256: str,
    network_effects_performed: int,
) -> dict[str, object]:
    if (
        completed_wall_time < request.requested_wall_time
        or completed_monotonic < request.requested_monotonic
        or completed_monotonic > request.deadline_monotonic
        or not output_sha256s
        or len(set(output_sha256s)) != len(output_sha256s)
        or not all(_is_sha256(value) for value in output_sha256s)
        or not _is_sha256(cleanup_state_sha256)
        or type(network_effects_performed) is not int
        or network_effects_performed < 0
    ):
        raise HostPhaseError("host phase timing or output identity is malformed")
    values: dict[str, object] = {
        "schema_version": HOST_PHASE_PROTOCOL_VERSION,
        "phase": request.phase,
        "binding": request.binding.to_document(),
        "previous_phase_receipt_sha256": request.previous_phase_receipt_sha256,
        "request_semantic_sha256": request.request_semantic_sha256,
        "started_wall_time": request.requested_wall_time,
        "completed_wall_time": completed_wall_time,
        "started_monotonic": request.requested_monotonic,
        "completed_monotonic": completed_monotonic,
        "phase_outputs": dict(outputs),
        "phase_output_sha256s": list(output_sha256s),
        "cleanup_state_sha256": cleanup_state_sha256,
        "model_request_count": 0,
        "browser_action_count": 0,
        "condition_entry_count": 0,
        "network_effects_performed": network_effects_performed,
        "complete": True,
    }
    values["receipt_sha256"] = semantic_sha256(values)
    _validate_receipt_schema(repository, values)
    return values


def _tracked_members(document: Mapping[str, object], *, label: str) -> list[dict[str, object]]:
    raw = document.get("members")
    if not isinstance(raw, list) or not raw or len(raw) > MAX_TRANSFER_MEMBERS:
        raise HostPhaseError(f"{label} member manifest is empty or oversized")
    members: list[dict[str, object]] = []
    names: set[str] = set()
    for value in raw:
        if not isinstance(value, dict) or set(value) != {"path", "bytes", "sha256"}:
            raise HostPhaseError(f"{label} member identity is malformed")
        name, size, sha = value.get("path"), value.get("bytes"), value.get("sha256")
        if (
            not isinstance(name, str)
            or PurePosixPath(name).is_absolute()
            or ".." in PurePosixPath(name).parts
            or name in names
            or type(size) is not int
            or not 0 <= size <= MAX_TRANSFER_MEMBER_BYTES
            or not _is_sha256(sha)
        ):
            raise HostPhaseError(f"{label} contains an unsafe member")
        names.add(name)
        members.append(dict(value))
    return members


def _rehash_archive(encoded: bytes) -> list[dict[str, object]]:
    members: list[dict[str, object]] = []
    names: set[str] = set()
    try:
        with tarfile.open(fileobj=io.BytesIO(encoded), mode="r:*") as archive:
            for member in archive:
                if not member.isfile() or member.issym() or member.islnk():
                    raise HostPhaseError("transferred archive contains a non-regular member")
                relative = PurePosixPath(member.name)
                if (
                    relative.is_absolute()
                    or ".." in relative.parts
                    or member.name in names
                    or member.size > MAX_TRANSFER_MEMBER_BYTES
                ):
                    raise HostPhaseError("transferred archive member is unsafe")
                source = archive.extractfile(member)
                if source is None:
                    raise HostPhaseError("transferred archive member cannot be read")
                data = source.read(MAX_TRANSFER_MEMBER_BYTES + 1)
                if len(data) != member.size:
                    raise HostPhaseError("transferred archive member size drifted")
                names.add(member.name)
                members.append(
                    {
                        "path": member.name,
                        "bytes": len(data),
                        "sha256": hashlib.sha256(data).hexdigest(),
                    }
                )
    except (tarfile.TarError, OSError) as exc:
        raise HostPhaseError("transferred package archive is invalid") from exc
    return sorted(members, key=lambda value: cast(str, value["path"]))


def verify_host_transfer_phase(
    repository: Path,
    request: RemoteHostPhaseRequest,
    *,
    completed_wall_time: float,
    completed_monotonic: float,
) -> dict[str, object]:
    if (
        request.phase != "host-transfer-verify"
        or request.previous_phase_receipt_path is not None
        or request.output_paths
    ):
        raise HostPhaseError("host transfer has an invalid phase predecessor")
    required = {
        "local_assembly_receipt",
        "provider_entry_receipt",
        "remote_archive",
        "remote_member_manifest",
        "host_acknowledgement",
        "cleanup_state",
    }
    if set(request.inputs) != required:
        raise HostPhaseError("host transfer inputs are incomplete or unbound")
    assembly, _assembly_file_sha = _json_input(request, "local_assembly_receipt")
    entry, entry_file_sha = _json_input(request, "provider_entry_receipt")
    manifest, manifest_file_sha = _json_input(request, "remote_member_manifest")
    acknowledgement, acknowledgement_file_sha = _json_input(request, "host_acknowledgement")
    _cleanup, cleanup_sha = _json_input(request, "cleanup_state")
    if (
        assembly.get("receipt_sha256") != request.binding.local_assembly_receipt_sha256
        or entry_file_sha != request.binding.provider_entry_receipt_sha256
        or entry.get("host_run_id") != request.binding.host_run_id
        or entry.get("owned_instance_identity_sha256") != request.binding.provider_handle_identity
    ):
        raise HostPhaseError("host transfer source or provider-entry binding drifted")
    archive_binding = request.inputs["remote_archive"]
    archive_bytes = archive_binding.read(
        maximum_bytes=MAX_TRANSFER_ARCHIVE_BYTES, label="remote archive"
    )
    archive_sha = hashlib.sha256(archive_bytes).hexdigest()
    if (
        assembly.get("archive_bytes") != len(archive_bytes)
        or assembly.get("archive_sha256") != archive_sha
    ):
        raise HostPhaseError("host archive differs from the immutable local assembly")
    expected_members = _tracked_members(assembly, label="local assembly")
    declared_members = _tracked_members(manifest, label="remote")
    observed_members = _rehash_archive(archive_bytes)
    if expected_members != declared_members or declared_members != observed_members:
        raise HostPhaseError("host archive member rehash differs from the local assembly")
    member_semantic_sha = semantic_sha256(declared_members)
    expected_ack = {
        "schema_version": HOST_PHASE_PROTOCOL_VERSION,
        "provider_contract_version": request.binding.provider_contract_version,
        "plan_id": request.binding.plan_id,
        "host_run_id": request.binding.host_run_id,
        "provider_handle_identity": request.binding.provider_handle_identity,
        "provider_launch_ordinal": request.binding.provider_launch_ordinal,
        "provider_entry_receipt_sha256": request.binding.provider_entry_receipt_sha256,
        "local_assembly_receipt_sha256": request.binding.local_assembly_receipt_sha256,
        "source_commit": request.binding.source_commit,
        "source_tree": request.binding.source_tree,
        "remote_root": request.binding.remote_root,
        "remote_archive_bytes": len(archive_bytes),
        "remote_archive_sha256": archive_sha,
        "remote_member_manifest_sha256": member_semantic_sha,
        "transfer_complete": True,
    }
    if acknowledgement != expected_ack:
        raise HostPhaseError("host transfer acknowledgement is incomplete or cross-host")
    outputs = {
        "remote_package_path": archive_binding.path.as_posix(),
        "remote_manifest_path": request.inputs["remote_member_manifest"].path.as_posix(),
        "remote_archive_bytes": len(archive_bytes),
        "remote_archive_sha256": archive_sha,
        "remote_member_manifest_sha256": member_semantic_sha,
        "host_acknowledgement_sha256": acknowledgement_file_sha,
        "member_count": len(observed_members),
    }
    return _phase_receipt(
        repository,
        request,
        completed_wall_time=completed_wall_time,
        completed_monotonic=completed_monotonic,
        outputs=outputs,
        output_sha256s=(
            archive_sha,
            manifest_file_sha,
            member_semantic_sha,
            acknowledgement_file_sha,
        ),
        cleanup_state_sha256=cleanup_sha,
        network_effects_performed=0 if request.deterministic_fixture else 1,
    )


def validate_host_preflight_phase(
    repository: Path,
    request: RemoteHostPhaseRequest,
    *,
    completed_wall_time: float,
    completed_monotonic: float,
) -> dict[str, object]:
    previous = _load_previous(repository, request, expected_phase="host-transfer-verify")
    required = {"remote_path_qualification", "cleanup_state"}
    if (
        request.phase != "host-preflight"
        or set(request.inputs) != required
        or (request.deterministic_fixture and request.output_paths)
    ):
        raise HostPhaseError("host preflight inputs are incomplete or unbound")
    path_receipt, path_sha = _json_input(request, "remote_path_qualification")
    _cleanup, cleanup_sha = _json_input(request, "cleanup_state")
    if previous.get(
        "receipt_sha256"
    ) != request.binding.host_transfer_receipt_sha256 or path_receipt != {
        "schema_version": HOST_PHASE_PROTOCOL_VERSION,
        "provider_contract_version": request.binding.provider_contract_version,
        "plan_id": request.binding.plan_id,
        "host_run_id": request.binding.host_run_id,
        "provider_handle_identity": request.binding.provider_handle_identity,
        "remote_root": request.binding.remote_root,
        "source_commit": request.binding.source_commit,
        "source_tree": request.binding.source_tree,
        "package_verified": True,
        "filesystem_admitted": True,
        "secret_channel_structure_valid": True,
        "core_suppression_ready": True,
        "container_control_ready": True,
        "cleanup_initialized": True,
        "empirical_state_absent": True,
        "image_qualification_performed": False,
        "scientific_freeze_performed": False,
        "condition_entry_performed": False,
        "authenticated_metadata_requests": 0,
    }:
        raise HostPhaseError("host preflight crossed a later phase or drifted")
    return _phase_receipt(
        repository,
        request,
        completed_wall_time=completed_wall_time,
        completed_monotonic=completed_monotonic,
        outputs={"remote_path_qualification_sha256": path_sha},
        output_sha256s=(path_sha,),
        cleanup_state_sha256=cleanup_sha,
        network_effects_performed=0,
    )


_QUALIFICATION_REQUIRED: Final = frozenset(
    {
        "schema_version",
        "provider_contract_version",
        "plan_id",
        "host_run_id",
        "provider_handle_identity",
        "image_materialization_receipt_sha256",
        "image_digest",
        "python_version",
        "python_interpreter_sha256",
        "dependency_manifest_sha256",
        "dependency_tree_sha256",
        "browser_qualification_sha256",
        "evaluator_qualification_sha256",
        "finalizer_sources_sha256",
        "cleanup_readiness_sha256",
        "dynamic_manifest_published",
        "condition_entry_performed",
        "model_request_count",
        "browser_action_count",
    }
)


def validate_host_qualification_phase(
    repository: Path,
    request: RemoteHostPhaseRequest,
    *,
    completed_wall_time: float,
    completed_monotonic: float,
) -> dict[str, object]:
    _load_previous(repository, request, expected_phase="host-preflight")
    required = {"qualification", "cleanup_state"}
    if not request.deterministic_fixture:
        required.add("qualification_context")
    if (
        request.phase != "host-qualify"
        or set(request.inputs) != required
        or (request.deterministic_fixture and request.output_paths)
    ):
        raise HostPhaseError("host qualification inputs are incomplete or unbound")
    qualification, qualification_sha = _json_input(request, "qualification")
    _cleanup, cleanup_sha = _json_input(request, "cleanup_state")
    context_sha: str | None = None
    if not request.deterministic_fixture:
        context, context_sha = _json_input(request, "qualification_context")
        if (
            context.get("schema_version") != HOST_PHASE_PROTOCOL_VERSION
            or context.get("provider_contract_version") != request.binding.provider_contract_version
            or context.get("plan_id") != request.binding.plan_id
            or context.get("host_run_id") != request.binding.host_run_id
            or context.get("provider_handle_identity") != request.binding.provider_handle_identity
            or context.get("model_request_count") != 0
            or context.get("task_browser_action_count") != 0
            or context.get("dynamic_manifest_published") is not False
            or context.get("condition_entry_performed") is not False
        ):
            raise HostPhaseError("host qualification context crossed a later phase")
    if set(qualification) != _QUALIFICATION_REQUIRED:
        raise HostPhaseError("host qualification evidence is incomplete")
    exact = {
        "schema_version": HOST_PHASE_PROTOCOL_VERSION,
        "provider_contract_version": request.binding.provider_contract_version,
        "plan_id": request.binding.plan_id,
        "host_run_id": request.binding.host_run_id,
        "provider_handle_identity": request.binding.provider_handle_identity,
    }
    if (
        any(qualification.get(key) != value for key, value in exact.items())
        or qualification.get("python_version") != "3.11.14"
        or qualification.get("dynamic_manifest_published") is not False
        or qualification.get("condition_entry_performed") is not False
        or qualification.get("model_request_count") != 0
        or qualification.get("browser_action_count") != 0
        or not all(
            _is_sha256(qualification.get(key))
            for key in _QUALIFICATION_REQUIRED
            if key.endswith("_sha256")
        )
        or not isinstance(qualification.get("image_digest"), str)
        or not cast(str, qualification["image_digest"]).startswith("sha256:")
        or not _is_sha256(cast(str, qualification["image_digest"])[7:])
    ):
        raise HostPhaseError("host qualification evidence drifted or crossed freeze")
    return _phase_receipt(
        repository,
        request,
        completed_wall_time=completed_wall_time,
        completed_monotonic=completed_monotonic,
        outputs={
            "qualification_sha256": qualification_sha,
            **({"qualification_context_sha256": context_sha} if context_sha is not None else {}),
            "image_digest": qualification["image_digest"],
            "python_version": qualification["python_version"],
        },
        output_sha256s=(
            (qualification_sha, context_sha) if context_sha is not None else (qualification_sha,)
        ),
        cleanup_state_sha256=cleanup_sha,
        network_effects_performed=0,
    )


def validate_host_freeze_phase(
    repository: Path,
    request: RemoteHostPhaseRequest,
    *,
    contract: T09ProviderContract,
    completed_wall_time: float,
    completed_monotonic: float,
) -> dict[str, object]:
    previous = _load_previous(repository, request, expected_phase="host-qualify")
    required = {"full_frozen_manifest", "postfreeze_validation", "cleanup_state"}
    if not request.deterministic_fixture:
        required.update(
            {
                "provider_entry_receipt",
                "qualification_context",
                "model_metadata_receipt",
                "compatibility_preflight_receipt",
            }
        )
    if (
        request.phase != "host-freeze"
        or set(request.inputs) != required
        or (request.deterministic_fixture and request.output_paths)
    ):
        raise HostPhaseError("host freeze inputs are incomplete or unbound")
    full_manifest = request.inputs["full_frozen_manifest"]
    full_manifest.read(maximum_bytes=MAX_HOST_PHASE_RECEIPT_BYTES, label="full frozen manifest")
    try:
        validated = validate_full_dynamic_frozen_manifest(
            repository,
            full_manifest.path,
            contract=contract,
            expected_projection=request.expected_projection,
        )
    except AdapterFailure as exc:
        raise HostPhaseError(f"full frozen manifest validation failed: {exc}") from exc
    postfreeze = request.inputs["postfreeze_validation"]
    postfreeze.read(maximum_bytes=MAX_HOST_PHASE_RECEIPT_BYTES, label="postfreeze validation")
    try:
        validate_postfreeze_receipt(
            postfreeze.path,
            contract=contract,
            manifest_sha256=validated.file_sha256,
        )
    except AdapterFailure as exc:
        raise HostPhaseError(f"post-freeze validation failed: {exc}") from exc
    _cleanup, cleanup_sha = _json_input(request, "cleanup_state")
    compatibility_sha: str | None = None
    if not request.deterministic_fixture:
        previous_outputs = previous.get("phase_outputs")
        context, context_sha = _json_input(request, "qualification_context")
        entry, entry_sha = _json_input(request, "provider_entry_receipt")
        metadata, _metadata_sha = _json_input(request, "model_metadata_receipt")
        compatibility, compatibility_sha = _json_input(
            request,
            "compatibility_preflight_receipt",
        )
        if (
            not isinstance(previous_outputs, dict)
            or previous_outputs.get("qualification_context_sha256") != context_sha
            or context.get("provider_handle_identity") != request.binding.provider_handle_identity
            or entry_sha != request.binding.provider_entry_receipt_sha256
            or entry.get("owned_instance_identity_sha256")
            != request.binding.provider_handle_identity
            or metadata.get("requested_model_id") != "gpt-4o-2024-11-20"
            or compatibility.get("frozen_run_manifest_sha256") != validated.file_sha256
            or compatibility.get("postfreeze_validation_sha256") != postfreeze.sha256
            or compatibility.get("empirical_entry_crossed") is not False
        ):
            raise HostPhaseError("host freeze source or compatibility chain drifted")
    return _phase_receipt(
        repository,
        request,
        completed_wall_time=completed_wall_time,
        completed_monotonic=completed_monotonic,
        outputs={
            "full_manifest_sha256": validated.file_sha256,
            "full_manifest_schema_version": validated.schema_version,
            "full_manifest_projection_sha256": validated.projection_sha256,
            "full_manifest_field_count": validated.full_field_count,
            "postfreeze_validation_sha256": postfreeze.sha256,
            **(
                {"compatibility_preflight_receipt_sha256": compatibility_sha}
                if compatibility_sha is not None
                else {}
            ),
        },
        output_sha256s=(
            validated.file_sha256,
            validated.projection_sha256,
            postfreeze.sha256,
            *((compatibility_sha,) if compatibility_sha is not None else ()),
        ),
        cleanup_state_sha256=cleanup_sha,
        network_effects_performed=0,
    )


def validate_host_cleanup_phase(
    repository: Path,
    request: RemoteHostPhaseRequest,
    *,
    completed_wall_time: float,
    completed_monotonic: float,
) -> dict[str, object]:
    _load_previous(repository, request, expected_phase="host-freeze")
    required = {"cleanup_terminal", "cleanup_state"}
    if not request.deterministic_fixture:
        required.add("provider_entry_receipt")
    if (
        request.phase != "host-cleanup"
        or set(request.inputs) != required
        or (request.deterministic_fixture and request.output_paths)
    ):
        raise HostPhaseError("host cleanup inputs are incomplete or unbound")
    terminal, terminal_sha = _json_input(request, "cleanup_terminal")
    _cleanup, cleanup_sha = _json_input(request, "cleanup_state")
    retained_sha = terminal.get("retained_cleanup_sha256")
    journal_sha = terminal.get("cleanup_journal_version_sha256")
    if (
        terminal.get("provider_contract_version") != request.binding.provider_contract_version
        or terminal.get("plan_id") != request.binding.plan_id
        or terminal.get("host_run_id") != request.binding.host_run_id
        or terminal.get("provider_handle_identity") != request.binding.provider_handle_identity
        or terminal.get("owned_roots_only") is not True
        or terminal.get("private_ipc_removed") is not True
        or terminal.get("temporary_credentials_removed") is not True
        or terminal.get("terminal_or_honestly_unresolved") is not True
        or (
            not request.deterministic_fixture
            and (
                not _is_sha256(retained_sha)
                or not _is_sha256(journal_sha)
                or terminal.get("cleanup_journal_disposition") not in {"partial", "complete"}
                or _json_input(request, "provider_entry_receipt")[1]
                != request.binding.provider_entry_receipt_sha256
            )
        )
    ):
        raise HostPhaseError("host cleanup terminal evidence drifted from exact ownership")
    return _phase_receipt(
        repository,
        request,
        completed_wall_time=completed_wall_time,
        completed_monotonic=completed_monotonic,
        outputs={
            "cleanup_terminal_sha256": terminal_sha,
            **(
                {
                    "retained_cleanup_sha256": retained_sha,
                    "cleanup_journal_version_sha256": journal_sha,
                }
                if not request.deterministic_fixture
                else {}
            ),
        },
        output_sha256s=(
            terminal_sha,
            *(
                (cast(str, retained_sha), cast(str, journal_sha))
                if not request.deterministic_fixture
                else ()
            ),
        ),
        cleanup_state_sha256=cleanup_sha,
        network_effects_performed=0,
    )


def validate_condition_session_request(
    repository: Path,
    request: RemoteHostPhaseRequest,
    *,
    contract: T09ProviderContract,
    condition_run_id: str,
    evaluator_run_id: str,
    frozen_manifest_sha256: str,
    command_package_sha256: str,
    command_argv_sha256: str,
    condition_plan_sha256: str,
) -> None:
    """Admit one remote condition relay only after the exact freeze receipt."""

    previous = _load_previous(repository, request, expected_phase="host-freeze")
    required = {"full_frozen_manifest", "command_manifest", "condition_plan"}
    if request.phase != "condition-session" or set(request.inputs) != required:
        raise HostPhaseError("condition session inputs are incomplete or unbound")
    expected = {
        "condition_run_id": condition_run_id,
        "evaluator_run_id": evaluator_run_id,
        "frozen_manifest_sha256": frozen_manifest_sha256,
        "command_package_sha256": command_package_sha256,
        "command_argv_sha256": command_argv_sha256,
        "condition_plan_sha256": condition_plan_sha256,
        "zero_retry": True,
        "shared_accounting_owner": "ConditionEventObserver",
        "remote_authoritative_boundary": False,
    }
    if any(request.expected_projection.get(key) != value for key, value in expected.items()):
        raise HostPhaseError("condition session identity or accounting ownership drifted")
    previous_outputs = previous.get("phase_outputs")
    if (
        not isinstance(previous_outputs, dict)
        or previous_outputs.get("full_manifest_sha256") != frozen_manifest_sha256
        or request.inputs["full_frozen_manifest"].sha256 != frozen_manifest_sha256
        or request.inputs["command_manifest"].sha256 != command_package_sha256
        or request.inputs["condition_plan"].sha256 != condition_plan_sha256
        or condition_run_id not in contract.run_ids
        or evaluator_run_id != contract.evaluator_run_ids[contract.run_ids.index(condition_run_id)]
    ):
        raise HostPhaseError("condition session does not inherit the exact frozen package")
    for name, maximum in (
        ("full_frozen_manifest", MAX_HOST_PHASE_RECEIPT_BYTES),
        ("command_manifest", MAX_HOST_PHASE_RECEIPT_BYTES),
        ("condition_plan", MAX_HOST_PHASE_RECEIPT_BYTES),
    ):
        request.inputs[name].read(maximum_bytes=maximum, label=name)


def write_phase_receipt(path: Path, receipt: Mapping[str, object]) -> None:
    """Publish one private receipt exclusively with mode 0600 and durable bytes."""

    encoded = _canonical_bytes(receipt)
    if len(encoded) > MAX_HOST_PHASE_RECEIPT_BYTES:
        raise HostPhaseError("host phase receipt exceeds its finite cap")
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        os.close(descriptor)


__all__ = [
    "HOST_PHASE_PROTOCOL_VERSION",
    "MAX_HOST_PHASE_DURATION_SECONDS",
    "HostPhaseError",
    "RemoteHostPhaseRequest",
    "begin_external_host_phase",
    "bind_generated_host_phase_outputs",
    "load_host_phase_request",
    "validate_condition_session_request",
    "validate_host_cleanup_phase",
    "validate_host_freeze_phase",
    "validate_host_phase_predecessor",
    "validate_host_preflight_phase",
    "validate_host_qualification_phase",
    "verify_host_transfer_phase",
    "write_phase_receipt",
]
