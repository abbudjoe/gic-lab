"""Deterministic conformance for the retained remote-execution bridge.

The full controller transaction and the remote transport probe are deliberately
separate processes.  The controller receipt proves lifecycle ownership; the relay
probe proves that the retained host bridge and runtime admission client can carry
the same authoritative observer protocol without an in-process shortcut.
"""

from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
import os
import select
import signal
import socket
import struct
import subprocess
import sys
import tarfile
import tempfile
import time
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from typing import BinaryIO, Final, cast

from jsonschema import Draft202012Validator

from giclab.control.category3 import repository_identity
from giclab.control.effects import EFFECT_PROTOCOL_VERSION
from giclab.control.live_conformance import (
    PRODUCTION_ASSEMBLY_ENTRY_POINT,
    SHARED_CONTROLLER_ENTRY_POINT,
    run_live_effect_conformance,
)
from giclab.control.production import _AccountingObserver, _ValidatedRuntimeClock
from giclab.control.remote_bridge import (
    BRIDGE_PROTOCOL_VERSION,
    ConditionBridgeFrame,
    ConditionSessionBinding,
    ConditionSessionSupervisor,
    FramedDuplexEndpoint,
    RemoteBridgeDisconnected,
    RemoteBridgeError,
    RemoteBridgeReplay,
    canonical_bytes,
    expected_condition_bridge_evidence,
    semantic_sha256,
    validate_condition_bridge_evidence,
)
from giclab.control.target import resolve_selected_runtime_target
from giclab.harness.sira_gate_a import (
    SIRA_MODEL_REVISION,
    SIRA_SERVICE_TIER,
    ImmutableModelRouting,
    ModelRole,
    ProviderBudgetBoundary,
    ProviderBudgetCaps,
    ProviderFailureDisposition,
    ProviderRequest,
    ProviderResponseReceiptError,
    ProviderResponseUsage,
    aggregate_caps,
    condition_caps,
)
from giclab.harness.t09_provider_contracts import T09ProviderContract
from giclab.harness.t09_remote_host_phases import RemoteHostBinding
from giclab.harness.t09_runtime_admission import DuplexSupervisorPort
from giclab.registry import load_json

REMOTE_EXECUTION_CONFORMANCE_SCHEMA_VERSION: Final = "1.0.0"
REMOTE_RUNNER_PATH: Final = "containers/sira-smoke/pragmatic/t09_remote_runner.py"
RUNTIME_ADMISSION_ENTRY_POINT: Final = (
    "giclab.harness.sira_gate_a_runtime._install_locked_llm_factory"
)
REMOTE_EXECUTION_CONFORMANCE_SCHEMA: Final = (
    "schemas/t09-remote-execution-bridge-conformance.schema.json"
)
RUNNER_CHILD_MAX_RESULT_BYTES: Final = 65_536
RUNNER_CHILD_TIMEOUT_SECONDS: Final = 30.0


class _ClockSource:
    def monotonic(self) -> float:
        return time.monotonic()

    def wall_time(self) -> float:
        return time.time()

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_sha256(value: object) -> str:
    encoded = json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _write_private(path: Path, value: object | bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    encoded = value if isinstance(value, bytes) else canonical_bytes(value)
    descriptor = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC,
        0o600,
    )
    try:
        offset = 0
        while offset < len(encoded):
            written = os.write(descriptor, encoded[offset:])
            if written <= 0:
                raise OSError("private conformance write made no progress")
            offset += written
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    return path.resolve(strict=True)


def _bound(path: Path) -> dict[str, object]:
    return {
        "path": path.resolve(strict=True).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": _file_sha256(path),
    }


def _tar(path: Path, members: Mapping[str, bytes]) -> tuple[Path, list[dict[str, object]]]:
    with tarfile.open(path, "x", format=tarfile.USTAR_FORMAT) as archive:
        for name, content in sorted(members.items()):
            info = tarfile.TarInfo(name)
            info.size = len(content)
            info.mtime = 0
            info.mode = 0o600
            info.uid = 0
            info.gid = 0
            info.uname = ""
            info.gname = ""
            archive.addfile(info, io.BytesIO(content))
    path.chmod(0o600)
    return path.resolve(strict=True), [
        {
            "path": name,
            "bytes": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
        }
        for name, content in sorted(members.items())
    ]


def _phase_request(
    *,
    phase: str,
    binding: RemoteHostBinding,
    inputs: Mapping[str, Path],
    previous: Path | None = None,
    expected_projection: Mapping[str, object] | None = None,
) -> dict[str, object]:
    projection = {
        **dict(expected_projection or {}),
        "test_completed_wall_time": 101.0,
        "test_completed_monotonic": 51.0,
    }
    return {
        "schema_version": "1.0.0",
        "phase": phase,
        "execution_mode": "deterministic-no-network",
        "binding": binding.to_document(),
        "previous_phase_receipt_path": previous.as_posix() if previous is not None else None,
        "previous_phase_receipt_sha256": (_file_sha256(previous) if previous is not None else None),
        "requested_wall_time": 100.0,
        "requested_monotonic": 50.0,
        "deadline_monotonic": 1000.0,
        "inputs": {name: _bound(path) for name, path in sorted(inputs.items())},
        "output_paths": {},
        "expected_projection": projection,
        "deterministic_fixture": True,
    }


def _runner_environment(repository: Path) -> dict[str, str]:
    return {
        "PATH": os.defpath,
        "PYTHONPATH": str(repository / "src"),
        "PYTHONDONTWRITEBYTECODE": "1",
        "LANG": "C",
        "LC_ALL": "C",
    }


def _write_runner_child_result(descriptor: int, document: Mapping[str, object]) -> None:
    encoded = canonical_bytes(document)
    if len(encoded) > RUNNER_CHILD_MAX_RESULT_BYTES:
        encoded = canonical_bytes(
            {
                "returncode": 1,
                "error_type": "RunnerChildResultTooLarge",
                "error": "retained runner child result exceeded its fixed cap",
                "stdout": "",
                "stderr": "",
            }
        )
    offset = 0
    while offset < len(encoded):
        written = os.write(descriptor, encoded[offset:])
        if written <= 0:
            return
        offset += written


def _execute_runner_in_inherited_contract_child(
    repository: Path,
    command: list[str],
    result_descriptor: int,
) -> None:
    """Execute the tracked runner in an isolated child with the selected registry.

    Receipt conformance must also work for an untracked synthetic successor. A fresh
    interpreter cannot truthfully resolve that deliberately in-memory registry
    entry. Forking preserves the already validated exact contract while still
    exercising the tracked remote-runner entry point across an OS process boundary.
    No serialized contract override or default-version selector exists.
    """

    stdout = io.StringIO()
    stderr = io.StringIO()
    result: dict[str, object]
    try:
        os.chdir(repository)
        os.environ.clear()
        os.environ.update(_runner_environment(repository))
        source_root = str(repository / "src")
        if source_root not in sys.path:
            sys.path.insert(0, source_root)
        runner_path = (repository / REMOTE_RUNNER_PATH).resolve(strict=True)
        runner_path.relative_to(repository)
        if not runner_path.is_file():
            raise ValueError("retained remote runner is not a regular file")
        sys.argv = [str(runner_path), *command]
        specification = importlib.util.spec_from_file_location(
            "_giclab_retained_remote_runner_conformance_child",
            runner_path,
        )
        if specification is None or specification.loader is None:
            raise ImportError("retained remote runner could not be loaded")
        module = importlib.util.module_from_spec(specification)
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            specification.loader.exec_module(module)
            entry_point = getattr(module, "main", None)
            if not callable(entry_point):
                raise TypeError("retained remote runner main entry point is missing")
            returncode = entry_point()
        if not isinstance(returncode, int) or isinstance(returncode, bool):
            raise TypeError("retained remote runner returned a non-integer status")
        result = {
            "returncode": returncode,
            "error_type": None,
            "error": None,
            "stdout": stdout.getvalue()[-4096:],
            "stderr": stderr.getvalue()[-4096:],
        }
    except BaseException as exc:  # child must always return one bounded status frame
        result = {
            "returncode": 1,
            "error_type": type(exc).__name__,
            "error": str(exc)[-4096:],
            "stdout": stdout.getvalue()[-4096:],
            "stderr": stderr.getvalue()[-4096:],
        }
    try:
        _write_runner_child_result(result_descriptor, result)
    finally:
        os.close(result_descriptor)


def _run_inherited_contract_child(repository: Path, command: list[str]) -> dict[str, object]:
    read_descriptor, write_descriptor = os.pipe()
    try:
        process_id = os.fork()
    except BaseException:
        os.close(read_descriptor)
        os.close(write_descriptor)
        raise
    if process_id == 0:
        os.close(read_descriptor)
        try:
            _execute_runner_in_inherited_contract_child(repository, command, write_descriptor)
        finally:
            os._exit(0)
    os.close(write_descriptor)
    encoded = bytearray()
    timed_out = False
    deadline = time.monotonic() + RUNNER_CHILD_TIMEOUT_SECONDS
    try:
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                timed_out = True
                break
            readable, _, _ = select.select([read_descriptor], [], [], remaining)
            if not readable:
                timed_out = True
                break
            chunk = os.read(read_descriptor, 8192)
            if not chunk:
                break
            encoded.extend(chunk)
            if len(encoded) > RUNNER_CHILD_MAX_RESULT_BYTES:
                raise ValueError("retained runner child result exceeded its fixed cap")
    finally:
        os.close(read_descriptor)
        if timed_out:
            with contextlib.suppress(ProcessLookupError):
                os.kill(process_id, signal.SIGKILL)
        _waited_process_id, wait_status = os.waitpid(process_id, 0)
    if timed_out:
        raise TimeoutError("retained runner conformance child exceeded its deadline")
    if not os.WIFEXITED(wait_status) or os.WEXITSTATUS(wait_status) != 0:
        raise ValueError("retained runner conformance child exited abnormally")
    try:
        result: object = json.loads(bytes(encoded))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("retained runner conformance child returned malformed status") from exc
    if not isinstance(result, dict) or not all(isinstance(key, str) for key in result):
        raise ValueError("retained runner conformance child status is not an object")
    if set(result) != {"returncode", "error_type", "error", "stdout", "stderr"}:
        raise ValueError("retained runner conformance child status has unexpected fields")
    if (
        not isinstance(result.get("returncode"), int)
        or isinstance(result.get("returncode"), bool)
        or not all(
            value is None or isinstance(value, str)
            for value in (result.get("error_type"), result.get("error"))
        )
        or not all(isinstance(result.get(name), str) for name in ("stdout", "stderr"))
    ):
        raise ValueError("retained runner conformance child status has invalid field types")
    return cast(dict[str, object], result)


def _run_runner_phase(
    repository: Path,
    root: Path,
    *,
    operation: str,
    request: Path,
    receipt: Path,
    commit: str,
    contract: T09ProviderContract,
) -> dict[str, object]:
    command = [
        "--provider-contract",
        contract.version,
        "--repository",
        str(repository),
        "--artifact-root",
        str(root),
        "--package-commit",
        commit,
        operation,
        "--phase-request",
        str(request),
        "--phase-receipt",
        str(receipt),
    ]
    completed = _run_inherited_contract_child(repository, command)
    if completed.get("returncode") != 0:
        raise ValueError(
            f"retained runner {operation} conformance failed: "
            + str(completed.get("error") or completed.get("stderr") or "unknown child error")
        )
    if completed.get("stdout") or completed.get("stderr"):
        raise ValueError(f"retained runner {operation} emitted unexpected output")
    document = load_json(receipt)
    if (
        document.get("phase") != operation
        or document.get("complete") is not True
        or document.get("model_request_count") != 0
        or document.get("browser_action_count") != 0
        or document.get("condition_entry_count") != 0
        or document.get("network_effects_performed") != 0
    ):
        raise ValueError(f"retained runner {operation} crossed its deterministic phase")
    return document


def _full_manifest_projection(contract: T09ProviderContract) -> dict[str, object]:
    return {
        "manifest_id": contract.frozen_run_manifest_id,
        "plan_id": contract.plan_id,
        "host_run_id": contract.host_run_id,
        "qualification_id": contract.active_image_qualification_id,
        "attempt_order": list(contract.run_ids),
        "empirical_entry_crossed": False,
        "post_entry_code_science_image_freeze": True,
    }


def _full_manifest(
    projection: Mapping[str, object], contract: T09ProviderContract
) -> dict[str, object]:
    hashes = {
        name: hashlib.sha256(f"remote-bridge-conformance:{name}".encode()).hexdigest()
        for name in (
            "source_contract_sha256",
            "plan_sha256",
            "execution_contract_sha256",
            "runtime_contract_sha256",
            "command_manifests_sha256",
            "provider_entry_receipt_sha256",
            "owned_instance_identity_sha256",
            "python_interpreter_sha256",
            "runtime_preflight_sha256",
            "offline_preflight_sha256",
            "core_suppression_preflight_sha256",
            "sealing_primitives_preflight_sha256",
            "browser_preflight_sha256",
            "evaluator_materialization_sha256",
            "final_image_file_hashes_sha256",
            "model_metadata_receipt_sha256",
            "model_metadata_credential_scan_sha256",
            "local_finalizer_qualification_sha256",
            "local_finalizer_interpreter_sha256",
            "local_finalizer_interpreter_dependency_manifest_sha256",
            "local_finalizer_interpreter_dependency_tree_sha256",
            "local_finalizer_evaluator_dependency_tree_sha256",
        )
    }
    return {
        **dict(projection),
        **hashes,
        "schema_version": "0.1.0",
        "qualification_count": 1,
        "build_count": 1,
        "image_materialization_policy": "deterministic-retained-image-qualification",
        "clean_package_commit": "c" * 40,
        "provider_preflight_started_at_epoch": 100.0,
        "owned_lambda_started_at_epoch": 100.25,
        "first_pair_started_at_epoch": 100.5,
        "launch_slot": 1,
        "launch_count": 1,
        "replacement_image_id": "sha256:" + "d" * 64,
        "python_interpreter_path": "/opt/sira/.venv/bin/python",
        "model_metadata_request_count": 1,
        "model_task_request_count": 0,
        "task_browser_action_count": 0,
        "actual_credential_exposure_detected": False,
        "credential_safety_stop_detected": False,
        "core_safety_stop_detected": False,
        "command_argv_sha256s": [
            hashlib.sha256(run_id.encode()).hexdigest() for run_id in contract.run_ids
        ],
        "pair_diffs": [
            {"pair": "task-a", "valid": True},
            {"pair": "task-b", "valid": True},
        ],
        "source_receipts": {
            f"source-{index}": hashlib.sha256(f"source-{index}".encode()).hexdigest()
            for index in range(8)
        },
    }


def _host_phase_entrypoint_probe(
    repository: Path,
    root: Path,
    contract: T09ProviderContract,
) -> tuple[dict[str, object], str]:
    commit, tree = repository_identity(repository)
    provider_identity = hashlib.sha256(b"retained-no-network-provider-handle").hexdigest()
    provider_entry = _write_private(
        root / "provider-entry.json",
        {
            "host_run_id": contract.host_run_id,
            "owned_instance_identity_sha256": provider_identity,
        },
    )
    archive, members = _tar(
        root / "tracked-package.tar",
        {
            "package/command.json": b'{"command":"deterministic"}\n',
            "package/plan.yaml": b"plan: retained\n",
        },
    )
    assembly_identity = hashlib.sha256(b"deterministic-local-assembly").hexdigest()
    assembly = _write_private(
        root / "local-package-assembly.json",
        {
            "receipt_sha256": assembly_identity,
            "archive_bytes": archive.stat().st_size,
            "archive_sha256": _file_sha256(archive),
            "members": members,
        },
    )
    member_manifest = _write_private(root / "remote-members.json", {"members": members})
    cleanup = _write_private(root / "cleanup-state.json", {"initialized": True})
    binding = RemoteHostBinding(
        provider_contract_version=contract.version,
        plan_id=contract.plan_id,
        host_run_id=contract.host_run_id,
        provider_handle_identity=provider_identity,
        provider_launch_ordinal=1,
        provider_entry_receipt_sha256=_file_sha256(provider_entry),
        local_assembly_receipt_sha256=assembly_identity,
        source_commit=commit,
        source_tree=tree,
        remote_root=root.as_posix(),
        host_transfer_receipt_sha256=None,
    )
    member_sha = semantic_sha256(members)
    acknowledgement = _write_private(
        root / "host-transfer-acknowledgement.json",
        {
            "schema_version": "1.0.0",
            "provider_contract_version": binding.provider_contract_version,
            "plan_id": binding.plan_id,
            "host_run_id": binding.host_run_id,
            "provider_handle_identity": binding.provider_handle_identity,
            "provider_launch_ordinal": binding.provider_launch_ordinal,
            "provider_entry_receipt_sha256": binding.provider_entry_receipt_sha256,
            "local_assembly_receipt_sha256": binding.local_assembly_receipt_sha256,
            "source_commit": commit,
            "source_tree": tree,
            "remote_root": root.as_posix(),
            "remote_archive_bytes": archive.stat().st_size,
            "remote_archive_sha256": _file_sha256(archive),
            "remote_member_manifest_sha256": member_sha,
            "transfer_complete": True,
        },
    )
    transfer_request = _write_private(
        root / "host-transfer-request.json",
        _phase_request(
            phase="host-transfer-verify",
            binding=binding,
            inputs={
                "local_assembly_receipt": assembly,
                "provider_entry_receipt": provider_entry,
                "remote_archive": archive,
                "remote_member_manifest": member_manifest,
                "host_acknowledgement": acknowledgement,
                "cleanup_state": cleanup,
            },
        ),
    )
    receipts: list[dict[str, object]] = []
    transfer_receipt = root / "host-transfer-receipt.json"
    receipts.append(
        _run_runner_phase(
            repository,
            root,
            operation="host-transfer-verify",
            request=transfer_request,
            receipt=transfer_receipt,
            commit=commit,
            contract=contract,
        )
    )
    binding = replace(
        binding,
        host_transfer_receipt_sha256=cast(str, receipts[-1]["receipt_sha256"]),
    )
    path_qualification = _write_private(
        root / "remote-path-qualification.json",
        {
            "schema_version": "1.0.0",
            "provider_contract_version": binding.provider_contract_version,
            "plan_id": binding.plan_id,
            "host_run_id": binding.host_run_id,
            "provider_handle_identity": binding.provider_handle_identity,
            "remote_root": binding.remote_root,
            "source_commit": binding.source_commit,
            "source_tree": binding.source_tree,
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
        },
    )
    preflight_request = _write_private(
        root / "host-preflight-request.json",
        _phase_request(
            phase="host-preflight",
            binding=binding,
            inputs={
                "remote_path_qualification": path_qualification,
                "cleanup_state": cleanup,
            },
            previous=transfer_receipt,
        ),
    )
    preflight_receipt = root / "host-preflight-receipt.json"
    receipts.append(
        _run_runner_phase(
            repository,
            root,
            operation="host-preflight",
            request=preflight_request,
            receipt=preflight_receipt,
            commit=commit,
            contract=contract,
        )
    )
    qualification_hashes = {
        name: hashlib.sha256(f"qualification:{name}".encode()).hexdigest()
        for name in (
            "image_materialization_receipt_sha256",
            "python_interpreter_sha256",
            "dependency_manifest_sha256",
            "dependency_tree_sha256",
            "browser_qualification_sha256",
            "evaluator_qualification_sha256",
            "finalizer_sources_sha256",
            "cleanup_readiness_sha256",
        )
    }
    qualification = _write_private(
        root / "host-qualification.json",
        {
            "schema_version": "1.0.0",
            "provider_contract_version": binding.provider_contract_version,
            "plan_id": binding.plan_id,
            "host_run_id": binding.host_run_id,
            "provider_handle_identity": binding.provider_handle_identity,
            **qualification_hashes,
            "image_digest": "sha256:" + "3" * 64,
            "python_version": "3.11.14",
            "dynamic_manifest_published": False,
            "condition_entry_performed": False,
            "model_request_count": 0,
            "browser_action_count": 0,
        },
    )
    qualify_request = _write_private(
        root / "host-qualify-request.json",
        _phase_request(
            phase="host-qualify",
            binding=binding,
            inputs={"qualification": qualification, "cleanup_state": cleanup},
            previous=preflight_receipt,
        ),
    )
    qualify_receipt = root / "host-qualify-receipt.json"
    receipts.append(
        _run_runner_phase(
            repository,
            root,
            operation="host-qualify",
            request=qualify_request,
            receipt=qualify_receipt,
            commit=commit,
            contract=contract,
        )
    )
    projection = {
        **_full_manifest_projection(contract),
        "test_completed_wall_time": 101.0,
        "test_completed_monotonic": 51.0,
    }
    frozen_manifest = _write_private(
        root / "frozen-run-manifest.json",
        _full_manifest(projection, contract),
    )
    postfreeze = _write_private(
        root / "postfreeze-validation.json",
        {
            "schema_version": "0.1.0",
            "plan_id": binding.plan_id,
            "host_run_id": binding.host_run_id,
            "frozen_run_manifest_sha256": _file_sha256(frozen_manifest),
            "frozen_manifest_published_before_empirical_clock": True,
            "model_task_request_count": 0,
            "task_browser_action_count": 0,
        },
    )
    freeze_request = _write_private(
        root / "host-freeze-request.json",
        _phase_request(
            phase="host-freeze",
            binding=binding,
            inputs={
                "full_frozen_manifest": frozen_manifest,
                "postfreeze_validation": postfreeze,
                "cleanup_state": cleanup,
            },
            previous=qualify_receipt,
            expected_projection=projection,
        ),
    )
    freeze_receipt = root / "host-freeze-receipt.json"
    receipts.append(
        _run_runner_phase(
            repository,
            root,
            operation="host-freeze",
            request=freeze_request,
            receipt=freeze_receipt,
            commit=commit,
            contract=contract,
        )
    )
    cleanup_terminal = _write_private(
        root / "host-cleanup-terminal.json",
        {
            "provider_contract_version": binding.provider_contract_version,
            "plan_id": binding.plan_id,
            "host_run_id": binding.host_run_id,
            "provider_handle_identity": binding.provider_handle_identity,
            "owned_roots_only": True,
            "private_ipc_removed": True,
            "temporary_credentials_removed": True,
            "terminal_or_honestly_unresolved": True,
        },
    )
    cleanup_request = _write_private(
        root / "host-cleanup-request.json",
        _phase_request(
            phase="host-cleanup",
            binding=binding,
            inputs={"cleanup_terminal": cleanup_terminal, "cleanup_state": cleanup},
            previous=freeze_receipt,
        ),
    )
    cleanup_receipt = root / "host-cleanup-receipt.json"
    receipts.append(
        _run_runner_phase(
            repository,
            root,
            operation="host-cleanup",
            request=cleanup_request,
            receipt=cleanup_receipt,
            commit=commit,
            contract=contract,
        )
    )
    phases = [cast(str, receipt["phase"]) for receipt in receipts]
    if phases != [
        "host-transfer-verify",
        "host-preflight",
        "host-qualify",
        "host-freeze",
        "host-cleanup",
    ]:
        raise ValueError("retained runner phase order drifted")
    freeze_outputs = cast(dict[str, object], receipts[3]["phase_outputs"])
    transfer_outputs = cast(dict[str, object], receipts[0]["phase_outputs"])
    receipt_projection_sha256s = [
        semantic_sha256(
            {
                "phase": item["phase"],
                "phase_output_names": sorted(cast(dict[str, object], item["phase_outputs"])),
                "model_request_count": item["model_request_count"],
                "browser_action_count": item["browser_action_count"],
                "condition_entry_count": item["condition_entry_count"],
                "network_effects_performed": item["network_effects_performed"],
                "complete": item["complete"],
            }
        )
        for item in receipts
    ]
    return (
        {
            "operations": phases,
            "receipt_validation_projection_sha256s": receipt_projection_sha256s,
            "ordered": True,
            "provider_entry_precedes_transfer": True,
            "transfer_rehashed": transfer_outputs.get("remote_archive_sha256")
            == _file_sha256(archive),
            "full_manifest_validated": freeze_outputs.get("full_manifest_sha256")
            == _file_sha256(frozen_manifest),
            "condition_entries": sum(cast(int, item["condition_entry_count"]) for item in receipts),
            "model_requests": sum(cast(int, item["model_request_count"]) for item in receipts),
            "browser_actions": sum(cast(int, item["browser_action_count"]) for item in receipts),
            "network_effects": sum(
                cast(int, item["network_effects_performed"]) for item in receipts
            ),
            "subprocess_count": len(receipts),
            "process_model": "forked-selected-contract-child",
            "tracked_runner_loaded": True,
            "serialized_contract_override": False,
        },
        _file_sha256(frozen_manifest),
    )


_RUNTIME_CHILD = r"""from __future__ import annotations
import hashlib
import importlib.util
import json
import os
import socket
import sys
import time
import types
from pathlib import Path

from giclab.control.remote_bridge import ConditionSessionBinding, canonical_bytes, semantic_sha256
from giclab.harness.sira_gate_a import SIRA_MODEL_REVISION
from giclab.harness.sira_gate_a_runtime import _install_locked_llm_factory
from giclab.harness.t09_remote_host_phases import RemoteHostBinding, RemoteHostPhaseRequest
from giclab.harness.t09_runtime_admission import build_private_socket_supervisor_port

repository = Path(sys.argv[1]).resolve(strict=True)
attempt_root = Path(sys.argv[2]).resolve(strict=True)
raw_root = Path(sys.argv[3]).resolve(strict=True)
status_path = Path(sys.argv[4])
run_id = sys.argv[5]
evaluator_run_id = sys.argv[6]
session_id = sys.argv[7]
frozen_sha = sys.argv[8]
transaction_identity = sys.argv[9]
provider_contract_version = sys.argv[10]
plan_id = sys.argv[11]
host_run_id = sys.argv[12]
roles = sys.argv[13].split(',')
deadline = time.monotonic() + 25.0

spec = importlib.util.spec_from_file_location(
    'giclab_t09_remote_runner_conformance',
    repository / 'containers/sira-smoke/pragmatic/t09_remote_runner.py',
)
if spec is None or spec.loader is None:
    raise RuntimeError('retained runner cannot be loaded')
runner_module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = runner_module
spec.loader.exec_module(runner_module)

binding = ConditionSessionBinding(
    session_id=session_id,
    provider_contract_version=provider_contract_version,
    plan_id=plan_id,
    host_run_id=host_run_id,
    condition_run_id=run_id,
    evaluator_run_id=evaluator_run_id,
    frozen_manifest_sha256=frozen_sha,
)
host_binding = RemoteHostBinding(
    provider_contract_version='V16',
    plan_id=binding.plan_id,
    host_run_id=binding.host_run_id,
    provider_handle_identity='a' * 64,
    provider_launch_ordinal=1,
    provider_entry_receipt_sha256='b' * 64,
    local_assembly_receipt_sha256='c' * 64,
    source_commit='d' * 40,
    source_tree='e' * 40,
    remote_root=attempt_root.parent.as_posix(),
    host_transfer_receipt_sha256='f' * 64,
)
request = RemoteHostPhaseRequest(
    phase='condition-session',
    execution_mode='deterministic-no-network',
    binding=host_binding,
    previous_phase_receipt_path=None,
    previous_phase_receipt_sha256=None,
    requested_wall_time=100.0,
    requested_monotonic=50.0,
    deadline_monotonic=deadline,
    inputs={},
    output_paths={},
    expected_projection={},
    deterministic_fixture=True,
    request_semantic_sha256=hashlib.sha256(run_id.encode()).hexdigest(),
)
bridge = runner_module._ConditionSessionBridge(
    request=request,
    binding=binding,
    transaction_root_identity=transaction_identity,
)
bridge.prepare(raw_root)

llm_module = types.ModuleType('sira.web.utils.llm')
class FakeLLM:
    def __init__(self, *, model, **kwargs):
        del kwargs
        self.model_name = model
        self.max_output_tokens = 64
        self._completion = self._send
    def get_token_count(self, messages):
        return max(1, len(messages) * 7)
    def _send(self, *args, **kwargs):
        del args, kwargs
        FakeLLM.send_count += 1
        return {
            'id': f'fake-response-{FakeLLM.send_count}',
            'content': f'no-network-response-{FakeLLM.send_count}',
            'service_tier': 'default',
            'usage': {
                'prompt_tokens': 7,
                'completion_tokens': 5,
                'prompt_tokens_details': {'cached_tokens': 1},
            },
        }
FakeLLM.send_count = 0
llm_module.LLM = FakeLLM
sys.modules['sira.web.utils.llm'] = llm_module
fake_runner = types.SimpleNamespace()
port = build_private_socket_supervisor_port(
    manifest_path=bridge.listener.manifest_path,
    attempt_root=raw_root,
    expected_binding=binding,
    expected_transaction_root_identity=transaction_identity,
)
_install_locked_llm_factory(
    fake_runner,
    admission_port=port,
    llm_timeout_seconds=30,
    ledger_path=raw_root / 'unused-historical-ledger.json',
)
role_llms = fake_runner.make_llm(SIRA_MODEL_REVISION, 'runtime-created-dummy-fragment')
answers = []
actions = []
try:
    for role in roles:
        response = role_llms[role]._completion(
            messages=[{'role': 'user', 'content': f'no-network-{role}'}],
            max_completion_tokens=16,
            n=1,
        )
        answers.append(response['content'])
    for index in range(2):
        action_id = f'ACTION-{run_id}-{index:02d}'
        port.browser_action(
            action_id=action_id,
            perform=lambda value=action_id: actions.append(value),
        )
    port.output_bytes(total_bytes=256)
    detached = port.detach_runtime()
    (raw_root / 'duplex-runtime-detached.json').write_bytes(canonical_bytes(detached))
    (raw_root / 'duplex-runtime-detached.json').chmod(0o600)
    raw_manifest = attempt_root / 'raw-attempt-manifest.json'
    raw_receipt = attempt_root / 'raw-attempt-complete.json'
    raw_manifest.write_bytes(canonical_bytes({'run_id': run_id, 'files': ['answer.json']}))
    raw_manifest.chmod(0o600)
    raw_receipt.write_bytes(canonical_bytes({'run_id': run_id, 'complete': True}))
    raw_receipt.chmod(0o600)
    bridge.finish(
        attempt_root=attempt_root,
        exit_code=0,
        completed=True,
        answer=';'.join(answers),
        error='',
        manifest_path=raw_manifest,
        receipt_path=raw_receipt,
    )
    status = {
        'run_id': run_id,
        'roles': roles,
        'model_calls': FakeLLM.send_count,
        'browser_actions': len(actions),
        'remote_authoritative_boundary': False,
        'runtime_admission_integration': '_install_locked_llm_factory',
        'private_socket_removed': not (
            raw_root / '.giclab-supervisor/condition-admission.sock'
        ).exists(),
        'private_binding_removed': not (
            raw_root / '.giclab-supervisor/condition-admission-binding.json'
        ).exists(),
    }
    status_path.write_bytes(canonical_bytes(status))
    status_path.chmod(0o600)
finally:
    port.close()
    bridge.close()
"""


def _observer_for(
    binding: ConditionSessionBinding,
) -> tuple[ProviderBudgetBoundary, _AccountingObserver]:
    condition = "simulative" if "SIMULATIVE" in binding.condition_run_id else "reactive"
    caps = replace(
        condition_caps(condition),
        max_model_call_attempts=16,
        max_browser_actions=16,
    )
    aggregate: ProviderBudgetCaps = replace(
        aggregate_caps(),
        max_model_call_attempts=64,
        max_browser_actions=64,
    )
    boundary = ProviderBudgetBoundary(
        routing=ImmutableModelRouting.locked(),
        aggregate_caps=aggregate,
        condition_caps=caps,
    )
    observer = _AccountingObserver(
        run_id=binding.condition_run_id,
        model_revision=SIRA_MODEL_REVISION,
        service_tier=SIRA_SERVICE_TIER,
        boundary=boundary,
        prior_call_ids=frozenset(),
        prior_logical_call_ids=frozenset(),
        clock=_ValidatedRuntimeClock(_ClockSource()),
        campaign_deadline_monotonic=time.monotonic() + 30.0,
    )
    return boundary, observer


def _roles_for_run(run_id: str) -> tuple[str, ...]:
    if "SIMULATIVE" in run_id:
        return ("world_model", "critic")
    return ("default", "actor")


def _admission_order_valid(endpoint: FramedDuplexEndpoint) -> bool:
    events = [entry.frame.event_type for entry in endpoint.entries]
    model_reserves = [index for index, value in enumerate(events) if value == "model-call-reserve"]
    browser_reserves = [
        index for index, value in enumerate(events) if value == "browser-action-reserve"
    ]
    for reserve in model_reserves:
        admitted = events.index("model-call-admitted", reserve + 1)
        sent = events.index("model-send-start", admitted + 1)
        if not reserve < admitted < sent:
            return False
    for reserve in browser_reserves:
        admitted = events.index("browser-action-admitted", reserve + 1)
        completed = events.index("browser-action-complete", admitted + 1)
        if not reserve < admitted < completed:
            return False
    return bool(model_reserves and browser_reserves)


def _duplex_subprocess_session(
    repository: Path,
    transaction_root: Path,
    *,
    contract: T09ProviderContract,
    run_id: str,
    frozen_manifest_sha256: str,
) -> dict[str, object]:
    run_index = contract.run_ids.index(run_id)
    evaluator_run_id = contract.evaluator_run_ids[run_index]
    session_id = f"SESSION-{run_id}"
    binding = ConditionSessionBinding(
        session_id=session_id,
        provider_contract_version=contract.version,
        plan_id=contract.plan_id,
        host_run_id=contract.host_run_id,
        condition_run_id=run_id,
        evaluator_run_id=evaluator_run_id,
        frozen_manifest_sha256=frozen_manifest_sha256,
    )
    attempt_root = transaction_root / "a" / str(run_index + 1)
    raw_root = attempt_root / "raw"
    raw_root.mkdir(parents=True, mode=0o700)
    supervisor_root = raw_root / ".giclab-supervisor"
    supervisor_root.mkdir(mode=0o700)
    status_path = transaction_root / "child-status" / f"{run_id}.json"
    status_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    transaction_identity = hashlib.sha256(
        f"remote-bridge-transaction:{run_id}".encode()
    ).hexdigest()
    command = [
        sys.executable,
        "-c",
        _RUNTIME_CHILD,
        str(repository),
        str(attempt_root),
        str(raw_root),
        str(status_path),
        run_id,
        evaluator_run_id,
        session_id,
        frozen_manifest_sha256,
        transaction_identity,
        contract.version,
        contract.plan_id,
        contract.host_run_id,
        ",".join(_roles_for_run(run_id)),
    ]
    process = subprocess.Popen(
        command,
        cwd=repository,
        env=_runner_environment(repository),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if process.stdin is None or process.stdout is None or process.stderr is None:
        process.kill()
        raise ValueError("local SSH stand-in lacks a complete duplex stream")
    boundary, observer = _observer_for(binding)
    deadline = time.monotonic() + 25.0
    endpoint = FramedDuplexEndpoint(
        reader=cast(BinaryIO, process.stdout),
        writer=cast(BinaryIO, process.stdin),
        binding=binding,
        deadline_monotonic=deadline,
    )
    supervisor = ConditionSessionSupervisor(
        endpoint,
        observer,
        accounting_document=boundary.accounting_document,
    )
    try:
        try:
            terminal = supervisor.serve()
        except BaseException as exc:
            with contextlib.suppress(subprocess.TimeoutExpired):
                process.wait(timeout=2)
            stderr = process.stderr.read().decode("utf-8", errors="replace")
            raise ValueError("remote relay supervisor failed: " + stderr[-2000:]) from exc
        process.stdin.close()
        exit_code = process.wait(timeout=10)
        stderr = process.stderr.read().decode("utf-8", errors="replace")
        if exit_code != 0:
            raise ValueError("remote relay subprocess failed: " + stderr[-2000:])
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
        with contextlib.suppress(OSError):
            process.stdout.close()
        with contextlib.suppress(OSError):
            process.stderr.close()
        with contextlib.suppress(OSError):
            process.stdin.close()
    status = load_json(status_path)
    evidence = expected_condition_bridge_evidence(
        transaction_root=transaction_root,
        raw_root=raw_root,
        run_id=run_id,
    )
    evidence.shared_transcript_path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    _write_private(
        evidence.shared_transcript_path,
        endpoint.transcript_document(side="shared-authoritative"),
    )
    _write_private(evidence.shared_terminal_receipt_path, terminal.to_document())
    raw_manifest = attempt_root / "raw-attempt-manifest.json"
    raw_receipt = attempt_root / "raw-attempt-complete.json"
    validated = validate_condition_bridge_evidence(
        repository,
        evidence,
        expected_binding=binding,
        raw_manifest_sha256=_file_sha256(raw_manifest),
        raw_receipt_sha256=_file_sha256(raw_receipt),
        shared_accounting=boundary.accounting_document(),
    )
    mutated_rejected = False
    relay_document = load_json(evidence.relay_transcript_path)
    relay_frames = cast(list[dict[str, object]], relay_document["frames"])
    first_frame = cast(dict[str, object], relay_frames[0]["frame"])
    payload = cast(dict[str, object], first_frame["payload"])
    payload["remote_authoritative_boundary"] = True
    mutated_bytes = canonical_bytes(relay_document)

    def mutated_reader(path: Path) -> bytes:
        if path == evidence.relay_transcript_path:
            return mutated_bytes
        return path.read_bytes()

    try:
        validate_condition_bridge_evidence(
            repository,
            evidence,
            expected_binding=binding,
            raw_manifest_sha256=_file_sha256(raw_manifest),
            raw_receipt_sha256=_file_sha256(raw_receipt),
            shared_accounting=boundary.accounting_document(),
            reader=mutated_reader,
        )
    except RemoteBridgeError:
        mutated_rejected = True
    if (
        status.get("remote_authoritative_boundary") is not False
        or status.get("runtime_admission_integration") != "_install_locked_llm_factory"
        or status.get("private_socket_removed") is not True
        or status.get("private_binding_removed") is not True
        or boundary.condition_usage.model_call_attempts != len(_roles_for_run(run_id))
        or boundary.condition_usage.browser_actions != 2
        or not _admission_order_valid(endpoint)
        or not mutated_rejected
    ):
        raise ValueError("duplex subprocess conformance did not preserve shared admission")
    return {
        "run_id": run_id,
        "roles": list(cast(list[str], status["roles"])),
        "model_calls": cast(int, status["model_calls"]),
        "browser_actions": cast(int, status["browser_actions"]),
        "shared_transcript_sha256": terminal.transcript_sha256,
        "evidence_binding_sha256": validated.evidence_binding_sha256,
        "terminal_acknowledged": terminal.terminal_acknowledged,
        "remote_boundary_authoritative": False,
        "admission_order_valid": True,
        "process_reaped": process.poll() is not None,
        "private_endpoints_removed": True,
        "transcript_mutation_rejected": mutated_rejected,
    }


def _coupling_probe(contract: T09ProviderContract) -> bool:
    """Disable the shared observer and prove the remote cannot cross admission."""

    binding = ConditionSessionBinding(
        session_id="SESSION-COUPLING-PROBE",
        provider_contract_version=contract.version,
        plan_id=contract.plan_id,
        host_run_id=contract.host_run_id,
        condition_run_id=contract.run_ids[0],
        evaluator_run_id=contract.evaluator_run_ids[0],
        frozen_manifest_sha256="a" * 64,
    )
    left, right = socket.socketpair()
    reader = cast(BinaryIO, right.makefile("rb", buffering=0))
    writer = cast(BinaryIO, right.makefile("wb", buffering=0))
    left.close()
    try:
        endpoint = FramedDuplexEndpoint(
            reader=reader,
            writer=writer,
            binding=binding,
            deadline_monotonic=time.monotonic() + 1.0,
        )
        try:
            DuplexSupervisorPort(
                endpoint,
                remote_journal_path=Path(tempfile.gettempdir())
                / f"t09-coupling-{os.getpid()}.json",
            )
        except RemoteBridgeDisconnected:
            return True
        return False
    finally:
        reader.close()
        writer.close()
        right.close()
        with contextlib.suppress(FileNotFoundError):
            (Path(tempfile.gettempdir()) / f"t09-coupling-{os.getpid()}.json").unlink()


def _replay_probe(contract: T09ProviderContract) -> bool:
    binding = ConditionSessionBinding(
        session_id="SESSION-REPLAY-PROBE",
        provider_contract_version=contract.version,
        plan_id=contract.plan_id,
        host_run_id=contract.host_run_id,
        condition_run_id=contract.run_ids[0],
        evaluator_run_id=contract.evaluator_run_ids[0],
        frozen_manifest_sha256="b" * 64,
    )
    frame = ConditionBridgeFrame.create(
        binding,
        sequence_number=1,
        previous_frame_sha256="0" * 64,
        event_id="REPLAY-EVENT",
        event_type="condition-session-hello",
        payload={"probe": True},
    )
    encoded = canonical_bytes(frame.to_document())
    packet = struct.pack("!I", len(encoded)) + encoded
    with tempfile.TemporaryFile() as reader, tempfile.TemporaryFile() as writer:
        reader.write(packet + packet)
        reader.seek(0)
        endpoint = FramedDuplexEndpoint(
            reader=cast(BinaryIO, reader),
            writer=cast(BinaryIO, writer),
            binding=binding,
            deadline_monotonic=1.0,
            monotonic=lambda: 0.0,
        )
        endpoint.read_event()
        try:
            endpoint.read_event()
        except RemoteBridgeReplay:
            return True
    return False


def _accounting_incomplete_probe(root: Path, contract: T09ProviderContract) -> bool:
    binding = ConditionSessionBinding(
        session_id="SESSION-ACCOUNTING-INCOMPLETE",
        provider_contract_version=contract.version,
        plan_id=contract.plan_id,
        host_run_id=contract.host_run_id,
        condition_run_id=contract.run_ids[0],
        evaluator_run_id=contract.evaluator_run_ids[0],
        frozen_manifest_sha256="c" * 64,
    )
    left, right = socket.socketpair()
    streams = (
        cast(BinaryIO, left.makefile("rb", buffering=0)),
        cast(BinaryIO, left.makefile("wb", buffering=0)),
        cast(BinaryIO, right.makefile("rb", buffering=0)),
        cast(BinaryIO, right.makefile("wb", buffering=0)),
    )
    boundary, observer = _observer_for(binding)
    deadline = time.monotonic() + 10
    server = FramedDuplexEndpoint(
        reader=streams[0], writer=streams[1], binding=binding, deadline_monotonic=deadline
    )
    client = FramedDuplexEndpoint(
        reader=streams[2], writer=streams[3], binding=binding, deadline_monotonic=deadline
    )
    import concurrent.futures

    pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    future = pool.submit(
        ConditionSessionSupervisor(
            server, observer, accounting_document=boundary.accounting_document
        ).serve
    )
    port = DuplexSupervisorPort(
        client,
        remote_journal_path=root / "accounting-incomplete-journal.json",
    )
    incomplete = False
    try:
        request = ProviderRequest(
            role=ModelRole.DEFAULT,
            model=SIRA_MODEL_REVISION,
            input_tokens=7,
            max_output_tokens=5,
            service_tier=SIRA_SERVICE_TIER,
            implicit_transport_retries=0,
        )
        try:
            port.model_call(
                request,
                lambda _request: (
                    "known-response",
                    cast(ProviderResponseUsage, object()),
                ),
                before_send=None,
                call_id="CALL-INCOMPLETE-PROBE",
                logical_call_id="LOGICAL-INCOMPLETE-PROBE",
                classify_failure=lambda _exc: ProviderFailureDisposition.OUTCOME_UNKNOWN,
            )
        except ProviderResponseReceiptError:
            incomplete = boundary.unknown_outcomes == 1
        port.process_exit(exit_code=1)
        port.completion(completed=False, answer=None, error="accounting-incomplete")
        port.raw_published(manifest_sha256="d" * 64, receipt_sha256="e" * 64)
        port.terminalize()
        future.result(timeout=5)
        return incomplete
    finally:
        port.close()
        for channel in (left, right):
            with contextlib.suppress(OSError):
                channel.shutdown(socket.SHUT_RDWR)
        for stream in streams:
            stream.close()
        left.close()
        right.close()
        pool.shutdown(wait=True, cancel_futures=True)


def _ambiguous_send_probe(root: Path, contract: T09ProviderContract) -> bool:
    """Lose the environmental send acknowledgement after shared admission."""

    binding = ConditionSessionBinding(
        session_id="SESSION-AMBIGUOUS-SEND",
        provider_contract_version=contract.version,
        plan_id=contract.plan_id,
        host_run_id=contract.host_run_id,
        condition_run_id=contract.run_ids[0],
        evaluator_run_id=contract.evaluator_run_ids[0],
        frozen_manifest_sha256="f" * 64,
    )
    left, right = socket.socketpair()
    streams = (
        cast(BinaryIO, left.makefile("rb", buffering=0)),
        cast(BinaryIO, left.makefile("wb", buffering=0)),
        cast(BinaryIO, right.makefile("rb", buffering=0)),
        cast(BinaryIO, right.makefile("wb", buffering=0)),
    )
    boundary, observer = _observer_for(binding)
    deadline = time.monotonic() + 10
    server = FramedDuplexEndpoint(
        reader=streams[0], writer=streams[1], binding=binding, deadline_monotonic=deadline
    )
    client = FramedDuplexEndpoint(
        reader=streams[2], writer=streams[3], binding=binding, deadline_monotonic=deadline
    )
    import concurrent.futures

    pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    future = pool.submit(
        ConditionSessionSupervisor(
            server, observer, accounting_document=boundary.accounting_document
        ).serve
    )
    port = DuplexSupervisorPort(
        client,
        remote_journal_path=root / "ambiguous-send-journal.json",
    )
    ambiguous = False
    try:
        request = ProviderRequest(
            role=ModelRole.POLICY,
            model=SIRA_MODEL_REVISION,
            input_tokens=7,
            max_output_tokens=5,
            service_tier=SIRA_SERVICE_TIER,
            implicit_transport_retries=0,
        )

        def disconnected(_request: ProviderRequest) -> tuple[str, ProviderResponseUsage]:
            raise RemoteBridgeDisconnected("send acknowledgement was lost")

        try:
            port.model_call(
                request,
                disconnected,
                before_send=None,
                call_id="CALL-AMBIGUOUS-PROBE",
                logical_call_id="LOGICAL-AMBIGUOUS-PROBE",
                classify_failure=lambda _exc: ProviderFailureDisposition.OUTCOME_UNKNOWN,
            )
        except RemoteBridgeDisconnected:
            ambiguous = boundary.unknown_outcomes == 1
        port.process_exit(exit_code=1)
        port.completion(completed=False, answer=None, error="ambiguous-send")
        port.raw_published(manifest_sha256="1" * 64, receipt_sha256="2" * 64)
        port.terminalize()
        future.result(timeout=5)
        return ambiguous
    finally:
        port.close()
        for channel in (left, right):
            with contextlib.suppress(OSError):
                channel.shutdown(socket.SHUT_RDWR)
        for stream in streams:
            stream.close()
        left.close()
        right.close()
        pool.shutdown(wait=True, cancel_futures=True)


def _controller_projection(receipt: Mapping[str, object]) -> dict[str, object]:
    package = receipt.get("temporary_package")
    if not isinstance(package, dict):
        raise ValueError("live conformance package projection is missing")
    traces = package.get("condition_traces")
    checkpoint = package.get("first_pair_checkpoint")
    raw_chain = package.get("raw_finalizer_evaluator_chain")
    cleanup = package.get("cleanup")
    if (
        receipt.get("complete") is not True
        or package.get("controller_terminal_state") != "category3-live-complete-clean"
        or not isinstance(traces, dict)
        or len(traces) != 4
        or not isinstance(checkpoint, dict)
        or checkpoint.get("retained_first_pair_decision_invoked") is not True
        or not isinstance(raw_chain, dict)
        or raw_chain.get("finalizer_consumed_raw_manifests") is not True
        or raw_chain.get("evaluator_consumed_finalized_sessions") is not True
        or cleanup
        != {
            "state": "complete",
            "resumed": False,
            "provider_resources_zero": True,
            "security_restored": True,
            "privacy_clean": True,
        }
    ):
        raise ValueError("shared controller conformance is not complete")
    return {
        "receipt_semantic_sha256": receipt["semantic_sha256"],
        "terminal_state": package["controller_terminal_state"],
        "condition_session_count": len(traces),
        "first_pair_checkpoint_retained": True,
        "raw_finalizer_evaluator_chain": True,
        "cleanup_to_zero": True,
        "shared_controller_used": receipt.get("shared_controller_entry_point")
        == SHARED_CONTROLLER_ENTRY_POINT,
        "shared_production_assembly_used": receipt.get("production_assembly_entry_point")
        == PRODUCTION_ASSEMBLY_ENTRY_POINT,
    }


def run_remote_execution_bridge_conformance(
    repository: Path,
    *,
    live_effect_conformance_receipt: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Run the complete local-only bridge probe and return its public receipt."""

    root = repository.resolve(strict=True)
    commit, tree = repository_identity(root)
    contract = resolve_selected_runtime_target(root).selected_contract
    live_receipt = (
        dict(live_effect_conformance_receipt)
        if live_effect_conformance_receipt is not None
        else run_live_effect_conformance(root)
    )
    controller = _controller_projection(live_receipt)
    # Darwin limits filesystem-backed AF_UNIX names.  Keep the isolated private
    # root short while preserving the held attempt-relative socket policy.
    with tempfile.TemporaryDirectory(prefix="t09-rb-", dir="/tmp") as directory:
        private_root = Path(directory)
        host_root = private_root / "remote-host"
        host_root.mkdir(mode=0o700)
        host_phases, frozen_sha = _host_phase_entrypoint_probe(root, host_root, contract)
        transaction_root = private_root / "t"
        transaction_root.mkdir(mode=0o700)
        sessions = [
            _duplex_subprocess_session(
                root,
                transaction_root,
                contract=contract,
                run_id=run_id,
                frozen_manifest_sha256=frozen_sha,
            )
            for run_id in contract.run_ids
        ]
        coupling = _coupling_probe(contract)
        replay = _replay_probe(contract)
        accounting_incomplete = _accounting_incomplete_probe(private_root, contract)
        ambiguous_send = _ambiguous_send_probe(private_root, contract)
    roles = sorted({role for session in sessions for role in cast(list[str], session["roles"])})
    duplex = {
        "run_ids": [cast(str, session["run_id"]) for session in sessions],
        "session_count": len(sessions),
        "model_call_count": sum(cast(int, session["model_calls"]) for session in sessions),
        "model_roles": roles,
        "browser_action_count": sum(cast(int, session["browser_actions"]) for session in sessions),
        "local_subprocess_count": len(sessions),
        "private_ipc_count": len(sessions),
        "shared_transcript_sha256s": [
            cast(str, session["shared_transcript_sha256"]) for session in sessions
        ],
        "evidence_binding_sha256s": [
            cast(str, session["evidence_binding_sha256"]) for session in sessions
        ],
        "all_terminal_acknowledged": all(
            session["terminal_acknowledged"] is True for session in sessions
        ),
        "all_remote_boundaries_nonauthoritative": all(
            session["remote_boundary_authoritative"] is False for session in sessions
        ),
        "all_effects_admitted_before_execution": all(
            session["admission_order_valid"] is True for session in sessions
        ),
        "all_processes_reaped": all(session["process_reaped"] is True for session in sessions),
        "all_private_endpoints_removed": all(
            session["private_endpoints_removed"] is True for session in sessions
        ),
    }
    temporary_package = cast(dict[str, object], live_receipt["temporary_package"])
    failure_receipts = cast(
        dict[str, object], temporary_package.get("review_failure_subreceipts", {})
    )
    ambiguous_failure = failure_receipts.get("ambiguous-send-essential-failure")
    cleanup_after_failure = (
        isinstance(ambiguous_failure, dict) and ambiguous_failure.get("cleanup_complete") is True
    )
    document: dict[str, object] = {
        "schema_version": REMOTE_EXECUTION_CONFORMANCE_SCHEMA_VERSION,
        "control_implementation_commit": commit,
        "control_implementation_tree": tree,
        "provider_contract_version": contract.version,
        "effect_protocol_version": EFFECT_PROTOCOL_VERSION,
        "bridge_protocol_version": BRIDGE_PROTOCOL_VERSION,
        "shared_controller_entry_point": SHARED_CONTROLLER_ENTRY_POINT,
        "production_assembly_entry_point": PRODUCTION_ASSEMBLY_ENTRY_POINT,
        "remote_runner_entry_point": REMOTE_RUNNER_PATH,
        "runtime_admission_entry_point": RUNTIME_ADMISSION_ENTRY_POINT,
        "controller_conformance": controller,
        "host_phase_entrypoints": host_phases,
        "duplex_condition_sessions": duplex,
        "sole_accountant": {
            "owner": "ConditionEventObserver",
            "remote_boundary_authoritative": False,
            "independent_remote_budget_boundary": False,
            "coupling_probe_passed": coupling,
        },
        "evidence": {
            "shared_authoritative_transcript": True,
            "remote_mirrored_journal": True,
            "host_relay_transcript": True,
            "terminal_hash_chain": True,
            "raw_and_essential_binding": True,
        },
        "failure_probes": {
            "disconnect_before_send": coupling,
            "disconnect_after_send": ambiguous_send,
            "replay_rejected": replay,
            "response_accounting_incomplete": accounting_incomplete,
            "transcript_mutation_rejected": all(
                session["transcript_mutation_rejected"] is True for session in sessions
            ),
            "cleanup_after_bridge_failure": cleanup_after_failure,
        },
        "zero_real_effects": {
            "secret_reads": 0,
            "authenticated_metadata_requests": 0,
            "provider_requests": 0,
            "cloud_mutations": 0,
            "live_ssh": 0,
            "docker": 0,
            "browser": 0,
            "scientific_actions": 0,
            "condition_reservations": 0,
            "new_cost_usd": "0.00",
        },
        "actual_v17_artifacts_created": False,
        "live_authority_created": False,
        "scientific_interpretation_allowed": False,
        "projected_real_cost_usd": "0.00",
        "complete": True,
    }
    document["semantic_sha256"] = _canonical_sha256(document)
    schema = load_json(root / REMOTE_EXECUTION_CONFORMANCE_SCHEMA)
    Draft202012Validator(schema).validate(document)
    return document


__all__ = [
    "REMOTE_EXECUTION_CONFORMANCE_SCHEMA_VERSION",
    "run_remote_execution_bridge_conformance",
]
