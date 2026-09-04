from __future__ import annotations

import hashlib
import io
import json
import tarfile
from dataclasses import replace
from pathlib import Path
from typing import cast

import pytest

from giclab.control.category3 import repository_identity
from giclab.harness.t09_provider_contracts import V16_PROVIDER_CONTRACT
from giclab.harness.t09_remote_host_phases import (
    HostPhaseError,
    RemoteHostBinding,
    RemoteHostPhaseRequest,
    load_host_phase_request,
    validate_condition_session_request,
    validate_host_freeze_phase,
    validate_host_preflight_phase,
    validate_host_qualification_phase,
    verify_host_transfer_phase,
    write_phase_receipt,
)

ROOT = Path(__file__).resolve().parents[2]


def _encoded(value: object) -> bytes:
    return (
        json.dumps(value, allow_nan=False, separators=(",", ":"), sort_keys=True) + "\n"
    ).encode()


def _write(path: Path, value: object | bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.write_bytes(value if isinstance(value, bytes) else _encoded(value))
    path.chmod(0o600)
    return path.resolve(strict=True)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _bound(path: Path) -> dict[str, object]:
    return {"path": path.as_posix(), "bytes": path.stat().st_size, "sha256": _sha(path)}


def _tar(path: Path, members: dict[str, bytes]) -> tuple[Path, list[dict[str, object]]]:
    with tarfile.open(path, "w") as archive:
        for name, content in sorted(members.items()):
            info = tarfile.TarInfo(name)
            info.size = len(content)
            info.mtime = 0
            info.mode = 0o600
            archive.addfile(info, io.BytesIO(content))
    path.chmod(0o600)
    return path.resolve(strict=True), [
        {"path": name, "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()}
        for name, content in sorted(members.items())
    ]


def _request_document(
    *,
    phase: str,
    binding: RemoteHostBinding,
    inputs: dict[str, Path],
    previous: Path | None = None,
    expected_projection: dict[str, object] | None = None,
    deterministic: bool = True,
) -> dict[str, object]:
    return {
        "schema_version": "1.0.0",
        "phase": phase,
        "execution_mode": ("deterministic-no-network" if deterministic else "external-live"),
        "binding": binding.to_document(),
        "previous_phase_receipt_path": previous.as_posix() if previous else None,
        "previous_phase_receipt_sha256": _sha(previous) if previous else None,
        "requested_wall_time": 100.0,
        "requested_monotonic": 50.0,
        "deadline_monotonic": 1000.0,
        "inputs": {name: _bound(path) for name, path in inputs.items()},
        "output_paths": {},
        "expected_projection": expected_projection or {},
        "deterministic_fixture": deterministic,
    }


def _load(path: Path, phase: str) -> RemoteHostPhaseRequest:
    return load_host_phase_request(
        ROOT,
        path,
        expected_phase=phase,
        contract=V16_PROVIDER_CONTRACT,
    )


def _transfer_fixture(tmp_path: Path) -> tuple[RemoteHostBinding, Path, dict[str, Path]]:
    commit, tree = repository_identity(ROOT)
    provider_entry = _write(
        tmp_path / "provider-entry.json",
        {
            "host_run_id": V16_PROVIDER_CONTRACT.host_run_id,
            "owned_instance_identity_sha256": "a" * 64,
        },
    )
    archive, members = _tar(
        tmp_path / "package.tar",
        {"package/a.txt": b"alpha\n", "package/b.json": b'{"beta":2}\n'},
    )
    assembly_identity = "1" * 64
    assembly = _write(
        tmp_path / "local-assembly.json",
        {
            "receipt_sha256": assembly_identity,
            "archive_bytes": archive.stat().st_size,
            "archive_sha256": _sha(archive),
            "members": members,
        },
    )
    manifest = _write(tmp_path / "remote-members.json", {"members": members})
    cleanup = _write(tmp_path / "cleanup.json", {"initialized": True})
    binding = RemoteHostBinding(
        provider_contract_version=V16_PROVIDER_CONTRACT.version,
        plan_id=V16_PROVIDER_CONTRACT.plan_id,
        host_run_id=V16_PROVIDER_CONTRACT.host_run_id,
        provider_handle_identity="a" * 64,
        provider_launch_ordinal=1,
        provider_entry_receipt_sha256=_sha(provider_entry),
        local_assembly_receipt_sha256=assembly_identity,
        source_commit=commit,
        source_tree=tree,
        remote_root="/opt/giclab/t09",
        host_transfer_receipt_sha256=None,
    )
    acknowledgement = _write(
        tmp_path / "host-ack.json",
        {
            "schema_version": "1.0.0",
            "provider_contract_version": binding.provider_contract_version,
            "plan_id": binding.plan_id,
            "host_run_id": binding.host_run_id,
            "provider_handle_identity": binding.provider_handle_identity,
            "provider_launch_ordinal": 1,
            "provider_entry_receipt_sha256": binding.provider_entry_receipt_sha256,
            "local_assembly_receipt_sha256": binding.local_assembly_receipt_sha256,
            "source_commit": commit,
            "source_tree": tree,
            "remote_root": binding.remote_root,
            "remote_archive_bytes": archive.stat().st_size,
            "remote_archive_sha256": _sha(archive),
            "remote_member_manifest_sha256": hashlib.sha256(_encoded(members)).hexdigest(),
            "transfer_complete": True,
        },
    )
    return (
        binding,
        provider_entry,
        {
            "local_assembly_receipt": assembly,
            "provider_entry_receipt": provider_entry,
            "remote_archive": archive,
            "remote_member_manifest": manifest,
            "host_acknowledgement": acknowledgement,
            "cleanup_state": cleanup,
        },
    )


def _complete_transfer(tmp_path: Path) -> tuple[RemoteHostBinding, Path, Path]:
    binding, _entry, inputs = _transfer_fixture(tmp_path)
    request_path = _write(
        tmp_path / "transfer-request.json",
        _request_document(phase="host-transfer-verify", binding=binding, inputs=inputs),
    )
    receipt = verify_host_transfer_phase(
        ROOT,
        _load(request_path, "host-transfer-verify"),
        completed_wall_time=101.0,
        completed_monotonic=51.0,
    )
    receipt_path = tmp_path / "transfer-receipt.json"
    write_phase_receipt(receipt_path, receipt)
    return (
        replace(
            binding,
            host_transfer_receipt_sha256=cast(str, receipt["receipt_sha256"]),
        ),
        receipt_path.resolve(strict=True),
        inputs["cleanup_state"],
    )


def _path_qualification(binding: RemoteHostBinding, path: Path) -> Path:
    return _write(
        path,
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


def _complete_preflight(tmp_path: Path) -> tuple[RemoteHostBinding, Path, Path]:
    binding, transfer_receipt, cleanup = _complete_transfer(tmp_path)
    request_path = _write(
        tmp_path / "preflight-request.json",
        _request_document(
            phase="host-preflight",
            binding=binding,
            inputs={
                "remote_path_qualification": _path_qualification(
                    binding, tmp_path / "path-qualification.json"
                ),
                "cleanup_state": cleanup,
            },
            previous=transfer_receipt,
        ),
    )
    receipt = validate_host_preflight_phase(
        ROOT,
        _load(request_path, "host-preflight"),
        completed_wall_time=102.0,
        completed_monotonic=52.0,
    )
    receipt_path = tmp_path / "preflight-receipt.json"
    write_phase_receipt(receipt_path, receipt)
    return binding, receipt_path.resolve(strict=True), cleanup


def _qualification(binding: RemoteHostBinding, path: Path) -> Path:
    return _write(
        path,
        {
            "schema_version": "1.0.0",
            "provider_contract_version": binding.provider_contract_version,
            "plan_id": binding.plan_id,
            "host_run_id": binding.host_run_id,
            "provider_handle_identity": binding.provider_handle_identity,
            "image_materialization_receipt_sha256": "2" * 64,
            "image_digest": "sha256:" + "3" * 64,
            "python_version": "3.11.14",
            "python_interpreter_sha256": "4" * 64,
            "dependency_manifest_sha256": "5" * 64,
            "dependency_tree_sha256": "6" * 64,
            "browser_qualification_sha256": "7" * 64,
            "evaluator_qualification_sha256": "8" * 64,
            "finalizer_sources_sha256": "9" * 64,
            "cleanup_readiness_sha256": "a" * 64,
            "dynamic_manifest_published": False,
            "condition_entry_performed": False,
            "model_request_count": 0,
            "browser_action_count": 0,
        },
    )


def _complete_qualification(tmp_path: Path) -> tuple[RemoteHostBinding, Path, Path]:
    binding, preflight_receipt, cleanup = _complete_preflight(tmp_path)
    request_path = _write(
        tmp_path / "qualification-request.json",
        _request_document(
            phase="host-qualify",
            binding=binding,
            inputs={
                "qualification": _qualification(binding, tmp_path / "qualification.json"),
                "cleanup_state": cleanup,
            },
            previous=preflight_receipt,
        ),
    )
    receipt = validate_host_qualification_phase(
        ROOT,
        _load(request_path, "host-qualify"),
        completed_wall_time=103.0,
        completed_monotonic=53.0,
    )
    receipt_path = tmp_path / "qualification-receipt.json"
    write_phase_receipt(receipt_path, receipt)
    return binding, receipt_path.resolve(strict=True), cleanup


def _full_manifest() -> tuple[dict[str, object], dict[str, object]]:
    contract = V16_PROVIDER_CONTRACT
    projection: dict[str, object] = {
        "manifest_id": contract.frozen_run_manifest_id,
        "plan_id": contract.plan_id,
        "host_run_id": contract.host_run_id,
        "qualification_id": contract.active_image_qualification_id,
        "attempt_order": list(contract.run_ids),
        "empirical_entry_crossed": False,
        "post_entry_code_science_image_freeze": True,
    }
    sha_fields = {
        name: "b" * 64
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
    document: dict[str, object] = {
        **projection,
        **sha_fields,
        "schema_version": "0.1.0",
        "qualification_count": 1,
        "build_count": 1,
        "image_materialization_policy": "exact-source-bound-image",
        "clean_package_commit": "c" * 40,
        "provider_preflight_started_at_epoch": 100.0,
        "owned_lambda_started_at_epoch": 101.0,
        "first_pair_started_at_epoch": 102.0,
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
        "command_argv_sha256s": ["e" * 64 for _ in contract.run_ids],
        "pair_diffs": [{"pair": "task-a", "valid": True}],
        "source_receipts": {f"source-{index}": "f" * 64 for index in range(8)},
    }
    return document, projection


def _complete_freeze(
    tmp_path: Path,
) -> tuple[RemoteHostBinding, Path, Path, Path, dict[str, object]]:
    binding, qualification_receipt, cleanup = _complete_qualification(tmp_path)
    document, projection = _full_manifest()
    manifest = _write(tmp_path / "frozen-run-manifest.json", document)
    postfreeze = _write(
        tmp_path / "postfreeze-validation.json",
        {
            "schema_version": "0.1.0",
            "plan_id": binding.plan_id,
            "host_run_id": binding.host_run_id,
            "frozen_run_manifest_sha256": _sha(manifest),
            "frozen_manifest_published_before_empirical_clock": True,
            "model_task_request_count": 0,
            "task_browser_action_count": 0,
        },
    )
    request_path = _write(
        tmp_path / "freeze-request.json",
        _request_document(
            phase="host-freeze",
            binding=binding,
            inputs={
                "full_frozen_manifest": manifest,
                "postfreeze_validation": postfreeze,
                "cleanup_state": cleanup,
            },
            previous=qualification_receipt,
            expected_projection=projection,
        ),
    )
    receipt = validate_host_freeze_phase(
        ROOT,
        _load(request_path, "host-freeze"),
        contract=V16_PROVIDER_CONTRACT,
        completed_wall_time=104.0,
        completed_monotonic=54.0,
    )
    receipt_path = tmp_path / "freeze-receipt.json"
    write_phase_receipt(receipt_path, receipt)
    return binding, receipt_path.resolve(strict=True), manifest, cleanup, projection


def test_transfer_rehashes_exact_archive_after_provider_entry(tmp_path: Path) -> None:
    binding, _entry, inputs = _transfer_fixture(tmp_path)
    request_path = _write(
        tmp_path / "request.json",
        _request_document(phase="host-transfer-verify", binding=binding, inputs=inputs),
    )
    receipt = verify_host_transfer_phase(
        ROOT,
        _load(request_path, "host-transfer-verify"),
        completed_wall_time=101.0,
        completed_monotonic=51.0,
    )
    assert receipt["phase"] == "host-transfer-verify"
    assert receipt["model_request_count"] == 0
    assert receipt["browser_action_count"] == 0
    assert receipt["condition_entry_count"] == 0
    outputs = cast(dict[str, object], receipt["phase_outputs"])
    assert outputs["remote_archive_sha256"] == _sha(inputs["remote_archive"])
    assert outputs["member_count"] == 2


@pytest.mark.parametrize(
    "mutation",
    ["missing-entry", "wrong-host", "archive", "member-manifest", "acknowledgement"],
)
def test_transfer_rejects_missing_or_mutated_source_binding(
    tmp_path: Path,
    mutation: str,
) -> None:
    binding, _entry, inputs = _transfer_fixture(tmp_path)
    if mutation == "missing-entry":
        inputs.pop("provider_entry_receipt")
    elif mutation == "wrong-host":
        binding = replace(binding, provider_handle_identity="b" * 64)
    elif mutation == "archive":
        inputs["remote_archive"].write_bytes(inputs["remote_archive"].read_bytes() + b"x")
    elif mutation == "member-manifest":
        _write(inputs["remote_member_manifest"], {"members": []})
    else:
        _write(inputs["host_acknowledgement"], {"transfer_complete": True})
    request_path = _write(
        tmp_path / "request.json",
        _request_document(phase="host-transfer-verify", binding=binding, inputs=inputs),
    )
    with pytest.raises(HostPhaseError):
        verify_host_transfer_phase(
            ROOT,
            _load(request_path, "host-transfer-verify"),
            completed_wall_time=101.0,
            completed_monotonic=51.0,
        )


def test_preflight_is_phase_specific_and_cannot_qualify_or_freeze(tmp_path: Path) -> None:
    binding, transfer_receipt, cleanup = _complete_transfer(tmp_path)
    path_qualification = _path_qualification(binding, tmp_path / "path-qualification.json")
    request_path = _write(
        tmp_path / "preflight-request.json",
        _request_document(
            phase="host-preflight",
            binding=binding,
            inputs={
                "remote_path_qualification": path_qualification,
                "cleanup_state": cleanup,
            },
            previous=transfer_receipt,
        ),
    )
    receipt = validate_host_preflight_phase(
        ROOT,
        _load(request_path, "host-preflight"),
        completed_wall_time=102.0,
        completed_monotonic=52.0,
    )
    assert receipt["phase"] == "host-preflight"
    assert receipt["network_effects_performed"] == 0


def test_qualification_requires_preflight_and_cannot_freeze(tmp_path: Path) -> None:
    binding, transfer_receipt, cleanup = _complete_transfer(tmp_path)
    # A transfer receipt cannot be replayed as the qualification predecessor.
    qualification = _write(
        tmp_path / "qualification.json",
        {
            "schema_version": "1.0.0",
            "provider_contract_version": binding.provider_contract_version,
            "plan_id": binding.plan_id,
            "host_run_id": binding.host_run_id,
            "provider_handle_identity": binding.provider_handle_identity,
            "image_materialization_receipt_sha256": "2" * 64,
            "image_digest": "sha256:" + "3" * 64,
            "python_version": "3.11.14",
            "python_interpreter_sha256": "4" * 64,
            "dependency_manifest_sha256": "5" * 64,
            "dependency_tree_sha256": "6" * 64,
            "browser_qualification_sha256": "7" * 64,
            "evaluator_qualification_sha256": "8" * 64,
            "finalizer_sources_sha256": "9" * 64,
            "cleanup_readiness_sha256": "a" * 64,
            "dynamic_manifest_published": False,
            "condition_entry_performed": False,
            "model_request_count": 0,
            "browser_action_count": 0,
        },
    )
    request_path = _write(
        tmp_path / "qualification-request.json",
        _request_document(
            phase="host-qualify",
            binding=binding,
            inputs={"qualification": qualification, "cleanup_state": cleanup},
            previous=transfer_receipt,
        ),
    )
    with pytest.raises(HostPhaseError, match="predecessor"):
        validate_host_qualification_phase(
            ROOT,
            _load(request_path, "host-qualify"),
            completed_wall_time=103.0,
            completed_monotonic=53.0,
        )


def test_external_live_rejects_deterministic_phase_channel(tmp_path: Path) -> None:
    binding, _entry, inputs = _transfer_fixture(tmp_path)
    request = _request_document(
        phase="host-transfer-verify",
        binding=binding,
        inputs=inputs,
        deterministic=True,
    )
    request["execution_mode"] = "external-live"
    path = _write(tmp_path / "request.json", request)
    with pytest.raises(HostPhaseError, match="confused"):
        _load(path, "host-transfer-verify")


def test_qualification_is_independent_and_cannot_publish_freeze(tmp_path: Path) -> None:
    _binding, receipt_path, _cleanup = _complete_qualification(tmp_path)
    receipt = json.loads(receipt_path.read_bytes())
    assert receipt["phase"] == "host-qualify"
    assert receipt["model_request_count"] == 0
    assert receipt["browser_action_count"] == 0
    assert "full_manifest_sha256" not in receipt["phase_outputs"]


def test_full_retained_manifest_and_postfreeze_chain_pass(tmp_path: Path) -> None:
    _binding, receipt_path, manifest, _cleanup, _projection = _complete_freeze(tmp_path)
    receipt = json.loads(receipt_path.read_bytes())
    assert receipt["phase"] == "host-freeze"
    assert receipt["phase_outputs"]["full_manifest_sha256"] == _sha(manifest)
    assert receipt["phase_outputs"]["full_manifest_field_count"] >= 50
    assert receipt["model_request_count"] == 0
    assert receipt["condition_entry_count"] == 0


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("minimal", "schema"),
        ("field", "manifest"),
        ("schema", "schema"),
        ("postfreeze", "post-freeze"),
    ],
)
def test_freeze_rejects_minimal_or_mutated_full_manifest(
    tmp_path: Path,
    mutation: str,
    message: str,
) -> None:
    binding, qualification_receipt, cleanup = _complete_qualification(tmp_path)
    document, projection = _full_manifest()
    if mutation == "minimal":
        document = {
            "schema_version": "0.1.0",
            "manifest_id": V16_PROVIDER_CONTRACT.frozen_run_manifest_id,
            "plan_id": binding.plan_id,
        }
    elif mutation == "field":
        document["host_run_id"] = "RUN-CROSS-HOST"
    elif mutation == "schema":
        document["schema_version"] = "9.9.9"
    manifest = _write(tmp_path / "frozen-run-manifest.json", document)
    postfreeze_document = {
        "schema_version": "0.1.0",
        "plan_id": binding.plan_id,
        "host_run_id": binding.host_run_id,
        "frozen_run_manifest_sha256": _sha(manifest),
        "frozen_manifest_published_before_empirical_clock": True,
        "model_task_request_count": 0,
        "task_browser_action_count": 0,
    }
    if mutation == "postfreeze":
        postfreeze_document["frozen_run_manifest_sha256"] = "0" * 64
    postfreeze = _write(tmp_path / "postfreeze-validation.json", postfreeze_document)
    request_path = _write(
        tmp_path / "freeze-request.json",
        _request_document(
            phase="host-freeze",
            binding=binding,
            inputs={
                "full_frozen_manifest": manifest,
                "postfreeze_validation": postfreeze,
                "cleanup_state": cleanup,
            },
            previous=qualification_receipt,
            expected_projection=projection,
        ),
    )
    with pytest.raises((HostPhaseError, ValueError), match=message):
        validate_host_freeze_phase(
            ROOT,
            _load(request_path, "host-freeze"),
            contract=V16_PROVIDER_CONTRACT,
            completed_wall_time=104.0,
            completed_monotonic=54.0,
        )


def test_cross_host_phase_receipt_cannot_be_replayed(tmp_path: Path) -> None:
    binding, preflight_receipt, cleanup = _complete_preflight(tmp_path)
    cross_host = replace(binding, provider_handle_identity="b" * 64)
    request_path = _write(
        tmp_path / "cross-host-qualification-request.json",
        _request_document(
            phase="host-qualify",
            binding=cross_host,
            inputs={
                "qualification": _qualification(
                    cross_host, tmp_path / "cross-host-qualification.json"
                ),
                "cleanup_state": cleanup,
            },
            previous=preflight_receipt,
        ),
    )
    with pytest.raises(HostPhaseError, match="another phase or host"):
        validate_host_qualification_phase(
            ROOT,
            _load(request_path, "host-qualify"),
            completed_wall_time=103.0,
            completed_monotonic=53.0,
        )


def test_condition_requires_exact_full_freeze_and_package_hashes(tmp_path: Path) -> None:
    binding, freeze_receipt, manifest, _cleanup, _projection = _complete_freeze(tmp_path)
    command = _write(tmp_path / "commands.json", {"commands": "bound"})
    condition = _write(tmp_path / "condition.yaml", b"condition: bound\n")
    expected = {
        "condition_run_id": V16_PROVIDER_CONTRACT.run_ids[0],
        "evaluator_run_id": V16_PROVIDER_CONTRACT.evaluator_run_ids[0],
        "frozen_manifest_sha256": _sha(manifest),
        "command_package_sha256": _sha(command),
        "command_argv_sha256": "1" * 64,
        "condition_plan_sha256": _sha(condition),
        "zero_retry": True,
        "shared_accounting_owner": "ConditionEventObserver",
        "remote_authoritative_boundary": False,
    }
    request_path = _write(
        tmp_path / "condition-request.json",
        _request_document(
            phase="condition-session",
            binding=binding,
            inputs={
                "full_frozen_manifest": manifest,
                "command_manifest": command,
                "condition_plan": condition,
            },
            previous=freeze_receipt,
            expected_projection=expected,
        ),
    )
    validate_condition_session_request(
        ROOT,
        _load(request_path, "condition-session"),
        contract=V16_PROVIDER_CONTRACT,
        condition_run_id=V16_PROVIDER_CONTRACT.run_ids[0],
        evaluator_run_id=V16_PROVIDER_CONTRACT.evaluator_run_ids[0],
        frozen_manifest_sha256=_sha(manifest),
        command_package_sha256=_sha(command),
        command_argv_sha256="1" * 64,
        condition_plan_sha256=_sha(condition),
    )
    expected["command_argv_sha256"] = "2" * 64
    mutated_path = _write(
        tmp_path / "condition-request-mutated.json",
        _request_document(
            phase="condition-session",
            binding=binding,
            inputs={
                "full_frozen_manifest": manifest,
                "command_manifest": command,
                "condition_plan": condition,
            },
            previous=freeze_receipt,
            expected_projection=expected,
        ),
    )
    with pytest.raises(HostPhaseError, match="identity"):
        validate_condition_session_request(
            ROOT,
            _load(mutated_path, "condition-session"),
            contract=V16_PROVIDER_CONTRACT,
            condition_run_id=V16_PROVIDER_CONTRACT.run_ids[0],
            evaluator_run_id=V16_PROVIDER_CONTRACT.evaluator_run_ids[0],
            frozen_manifest_sha256=_sha(manifest),
            command_package_sha256=_sha(command),
            command_argv_sha256="1" * 64,
            condition_plan_sha256=_sha(condition),
        )
