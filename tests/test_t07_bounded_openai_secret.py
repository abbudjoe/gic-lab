from __future__ import annotations

import hashlib
import importlib.util
import inspect
import json
import shutil
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

from giclab.harness import t07_bounded_smoke as contract
from giclab.harness import t07_bounded_supervisor as supervisor
from giclab.validation import ROOT, validate_instance

OPENAI_DUMMY = b"PUBLIC-DUMMY-" + b"OPENAI-KEY-0123456789"
LAMBDA_DUMMY = b"PUBLIC-DUMMY-" + b"LAMBDA-KEY-9876543210"
AUTHORIZATION_REFERENCE = "AUTH-T07-BOUNDED-SIRA-SMOKE-V3-TEST-SECRET"


def _dotenv(tmp_path: Path, encoded: bytes, *, mode: int = 0o600) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    path = tmp_path / ".env"
    path.write_bytes(encoded)
    path.chmod(mode)
    return path


def _load_entrypoint() -> ModuleType:
    path = ROOT / "containers/sira-smoke/container_entrypoint.py"
    spec = importlib.util.spec_from_file_location("test_t07_v3_entrypoint", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _read_dummy(path: Path) -> bytes:
    destination = path.with_name("filtered-openai-runtime-key")
    identity = supervisor.materialize_runtime_secret(path, destination)
    value = destination.read_bytes()
    supervisor.destroy_runtime_secret(
        destination,
        expected_device=int(identity["runtime_file_device"]),
        expected_inode=int(identity["runtime_file_inode"]),
    )
    assert not destination.exists()
    return value


def _high_level_secret_fixture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    source: Path,
) -> dict[str, object]:
    binding = supervisor.openai_dotenv_path_binding(source)
    monkeypatch.setattr(supervisor, "OPENAI_DOTENV_PATH_BINDING_SHA256", binding)
    monkeypatch.setattr(contract, "OPENAI_DOTENV_PATH_BINDING_SHA256", binding)
    monkeypatch.setattr(supervisor, "verify_repository_identity", lambda *_: None)
    monkeypatch.setattr(
        supervisor,
        "_validate_authority_inputs",
        lambda *args, **kwargs: ({"authorization_reference": AUTHORIZATION_REFERENCE}, {}),
    )
    monkeypatch.setattr(
        supervisor,
        "_validate_openai_secret_contract",
        lambda *args, **kwargs: {"source_path_binding_sha256": binding},
    )
    monkeypatch.setattr(
        supervisor,
        "_validate_cleanup_plan_contract",
        lambda *args, **kwargs: {"source_path_binding_sha256": binding},
    )
    monkeypatch.setattr(
        supervisor,
        "_load_state",
        lambda *_: {"status": "post_launch_passed", "next_phase": "termination"},
    )
    (tmp_path / supervisor.RUN_ROOT_RELATIVE).mkdir(parents=True)
    (tmp_path / supervisor.UPLOAD_ROOT_RELATIVE).mkdir(parents=True)
    authorization_path = tmp_path / supervisor.AUTHORIZATION_RELATIVE
    authorization_path.write_bytes(
        supervisor.canonical_json_bytes({"authorization_reference": AUTHORIZATION_REFERENCE})
    )
    private_binding_path = tmp_path / supervisor.PRIVATE_BINDING_RELATIVE
    private_binding_path.write_text("{}\n", encoding="utf-8")
    return {
        "plan": {},
        "plan_sha256": "1" * 64,
        "expected_commit": "2" * 40,
        "authorization_path": authorization_path,
        "authorization_sha256": "3" * 64,
        "private_binding_path": private_binding_path,
        "private_binding_sha256": "4" * 64,
    }


def test_exact_existing_plain_unquoted_syntax_fixture(tmp_path: Path) -> None:
    # Public dummy fixture for the exact qualified file syntax: one unquoted,
    # single-line NAME=value assignment per channel.
    path = _dotenv(
        tmp_path,
        b"LAMBDA_API_KEY=" + LAMBDA_DUMMY + b"\nOPENAI_API_KEY=" + OPENAI_DUMMY + b"\n",
    )
    assert _read_dummy(path) == OPENAI_DUMMY


def test_in_process_lease_is_redacted_and_zeroed_on_close(tmp_path: Path) -> None:
    path = _dotenv(tmp_path, b"OPENAI_API_KEY=" + OPENAI_DUMMY + b"\n")
    lease = supervisor.load_openai_secret(path)
    assert repr(lease) == "OpenAISecretLease(<redacted>)"
    lease.close()
    assert lease.closed is True
    assert not lease._value


@pytest.mark.parametrize(
    ("encoded", "code"),
    [
        (b"LAMBDA_API_KEY=" + LAMBDA_DUMMY + b"\n", "openai_assignment_missing"),
        (b"OPENAI_API_KEY=\n", "openai_assignment_empty"),
        (
            b"OPENAI_API_KEY=" + OPENAI_DUMMY + b"\nOPENAI_API_KEY=PUBLIC-DUMMY-TWO\n",
            "openai_assignment_duplicate",
        ),
        (b"OPENAI_API_KEY='PUBLIC-DUMMY'\n", "dotenv_syntax_unsupported"),
        (b"OPENAI_API_KEY=$(printf PUBLIC-DUMMY)\n", "dotenv_syntax_unsupported"),
        (b"OPENAI_API_KEY=${PUBLIC_DUMMY}\n", "dotenv_syntax_unsupported"),
        (b"OPENAI_API_KEY=PUBLIC-DUMMY\\\nINJECTED=VALUE\n", "dotenv_syntax_unsupported"),
        (b"export OPENAI_API_KEY=PUBLIC-DUMMY\n", "dotenv_syntax_unsupported"),
        (b"OPENAI_API_KEY=PUBLIC\x00DUMMY\n", "dotenv_syntax_unsupported"),
        (b"OPENAI_API_KEY=PUBLIC\rDUMMY\n", "dotenv_syntax_unsupported"),
    ],
)
def test_strict_parser_rejects_unsafe_or_missing_source(
    tmp_path: Path,
    encoded: bytes,
    code: str,
) -> None:
    path = _dotenv(tmp_path, encoded)
    with pytest.raises(supervisor.OpenAISecretSourceError, match=f"^{code}$"):
        supervisor.load_openai_secret(path)


def test_source_rejects_writable_mode_and_symlink(tmp_path: Path) -> None:
    path = _dotenv(tmp_path, b"OPENAI_API_KEY=" + OPENAI_DUMMY + b"\n", mode=0o622)
    with pytest.raises(supervisor.OpenAISecretSourceError, match="dotenv_metadata_unsafe"):
        supervisor.load_openai_secret(path)
    path.chmod(0o600)
    link = tmp_path / "linked.env"
    link.symlink_to(path)
    with pytest.raises(supervisor.OpenAISecretSourceError):
        supervisor.load_openai_secret(link)


def test_parser_has_no_shell_or_subprocess_path() -> None:
    source = inspect.getsource(supervisor.load_openai_secret)
    parser_source = inspect.getsource(supervisor._parse_openai_assignment)
    combined = source + parser_source
    for forbidden in ("subprocess", "shell=True", "source ", "dotenv run", "set -a"):
        assert forbidden not in combined


def test_lambda_and_openai_channels_cannot_cross(tmp_path: Path) -> None:
    path = _dotenv(
        tmp_path,
        b"OPENAI_API_KEY=" + OPENAI_DUMMY + b"\nLAMBDA_API_KEY=" + LAMBDA_DUMMY + b"\n",
    )
    assert _read_dummy(path) == OPENAI_DUMMY
    assert LAMBDA_DUMMY not in _read_dummy(path)
    lambda_environment = {"LAMBDA_API_KEY": LAMBDA_DUMMY.decode(), "PATH": "/usr/bin"}
    supervisor.validate_operation_secret_environment("observe", lambda_environment)
    provider = supervisor.OneShotEnvironmentCredential(lambda_environment)
    assert provider() == LAMBDA_DUMMY.decode()
    assert "LAMBDA_API_KEY" not in lambda_environment
    with pytest.raises(supervisor.BoundedSupervisorError, match="reused"):
        provider()
    for contaminated in (
        {"LAMBDA_API_KEY": "dummy", "OPENAI_API_KEY": "wrong-channel"},
        {"LAMBDA_API_KEY": "dummy", "SIRA_API_KEY": "wrong-channel"},
    ):
        with pytest.raises(supervisor.BoundedSupervisorError, match="contaminated"):
            supervisor.validate_operation_secret_environment("observe", contaminated)
    for operation in ("materialize-openai-secret", "prepare-bundle"):
        with pytest.raises(supervisor.BoundedSupervisorError, match="inherited"):
            supervisor.validate_operation_secret_environment(
                operation, {"LAMBDA_API_KEY": "wrong-channel"}
            )
        with pytest.raises(supervisor.BoundedSupervisorError, match="inherited"):
            supervisor.validate_operation_secret_environment(
                operation, {"OPENAI_API_KEY": "ambient-forbidden"}
            )
    cleanup_environment = {
        "LAMBDA_API_KEY": "dummy-lambda",
        "OPENAI_API_KEY": "dummy-openai",
        "SIRA_API_KEY": "dummy-sira",
        "PATH": "/usr/bin",
    }
    supervisor.validate_operation_secret_environment("abort-openai-secret", cleanup_environment)
    assert cleanup_environment == {"PATH": "/usr/bin"}


def test_exact_private_dotenv_path_binding_rejects_another_safe_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    approved = _dotenv(tmp_path / "approved", b"OPENAI_API_KEY=" + OPENAI_DUMMY + b"\n")
    other = _dotenv(tmp_path / "other", b"OPENAI_API_KEY=" + OPENAI_DUMMY + b"\n")
    common = _high_level_secret_fixture(tmp_path, monkeypatch, approved)
    with pytest.raises(supervisor.OpenAISecretSourceError, match="dotenv_path_identity_mismatch"):
        supervisor.materialize_openai_runtime_secret(
            tmp_path,
            openai_dotenv_path=other,
            **common,
        )
    assert not (tmp_path / supervisor.OPENAI_SECRET_ATTEMPT_RELATIVE).exists()


def test_partial_high_level_materialization_has_durable_cleaned_failure_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _dotenv(tmp_path / "approved", b"OPENAI_API_KEY=" + OPENAI_DUMMY + b"\n")
    common = _high_level_secret_fixture(tmp_path, monkeypatch, source)

    def fail_after_partial_write(lease: supervisor.OpenAISecretLease, descriptor: int) -> None:
        supervisor.os.write(descriptor, lease._value[:7])
        raise supervisor.OpenAISecretSourceError("runtime_secret_write_failed")

    monkeypatch.setattr(supervisor.OpenAISecretLease, "write_to", fail_after_partial_write)
    with pytest.raises(supervisor.OpenAISecretSourceError) as captured:
        supervisor.materialize_openai_runtime_secret(
            tmp_path,
            openai_dotenv_path=source,
            **common,
        )
    assert captured.value.credential_rotation_required is False
    state = supervisor._verify_local_openai_secret_cleanup(
        tmp_path,
        disposition="failed",
        authorization_reference=AUTHORIZATION_REFERENCE,
    )
    assert state["state"] == "materialization_failed_cleaned"
    assert state["state"] != "not_materialized"
    assert state["credential_access_may_have_occurred"] is True
    assert state["cleanup_verified"] is True
    assert state["credential_rotation_required"] is False
    assert (tmp_path / supervisor.OPENAI_SECRET_ATTEMPT_RELATIVE).is_file()
    assert (tmp_path / supervisor.OPENAI_SECRET_FAILURE_RELATIVE).is_file()


def test_cleanup_rejects_replaced_path_identity_and_requires_rotation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _dotenv(tmp_path / "approved", b"OPENAI_API_KEY=" + OPENAI_DUMMY + b"\n")
    common = _high_level_secret_fixture(tmp_path, monkeypatch, source)
    supervisor.materialize_openai_runtime_secret(
        tmp_path,
        openai_dotenv_path=source,
        **common,
    )
    destination = tmp_path / supervisor.UPLOAD_ROOT_RELATIVE / supervisor.UPLOAD_OPENAI_SECRET_NAME
    displaced = destination.with_name("displaced-dummy-secret")
    destination.rename(displaced)
    destination.write_bytes(b"PUBLIC-DUMMY-REPLACEMENT")
    destination.chmod(0o600)
    with pytest.raises(supervisor.OpenAISecretSourceError) as captured:
        supervisor.cleanup_openai_runtime_secret(
            tmp_path,
            remote_upload_attestation=(
                "confirmed-exact-filtered-file-uploaded-and-permissions-qualified"
            ),
            **common,
        )
    assert captured.value.credential_rotation_required is True
    assert destination.is_file()
    assert displaced.is_file()
    receipt = json.loads((tmp_path / supervisor.OPENAI_SECRET_CLEANUP_RELATIVE).read_text())
    assert receipt["cleanup_verified"] is False
    assert receipt["credential_rotation_required"] is True


def test_cleanup_receipt_failure_preserves_rotation_requirement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _dotenv(tmp_path / "approved", b"OPENAI_API_KEY=" + OPENAI_DUMMY + b"\n")
    common = _high_level_secret_fixture(tmp_path, monkeypatch, source)
    supervisor.materialize_openai_runtime_secret(
        tmp_path,
        openai_dotenv_path=source,
        **common,
    )

    def fail_cleanup(*args: object, **kwargs: object) -> dict[str, object]:
        raise supervisor.OpenAISecretSourceError(
            "runtime_secret_cleanup_failed",
            credential_rotation_required=True,
        )

    original_write = supervisor._write_exclusive

    def fail_cleanup_receipt(path: Path, *args: object, **kwargs: object) -> None:
        if path == tmp_path / supervisor.OPENAI_SECRET_CLEANUP_RELATIVE:
            raise OSError
        original_write(path, *args, **kwargs)

    monkeypatch.setattr(supervisor, "destroy_runtime_secret", fail_cleanup)
    monkeypatch.setattr(supervisor, "_write_exclusive", fail_cleanup_receipt)
    with pytest.raises(supervisor.OpenAISecretSourceError) as captured:
        supervisor.cleanup_openai_runtime_secret(
            tmp_path,
            remote_upload_attestation=(
                "confirmed-exact-filtered-file-uploaded-and-permissions-qualified"
            ),
            **common,
        )
    assert captured.value.code == "runtime_secret_cleanup_receipt_unavailable"
    assert captured.value.credential_rotation_required is True


def test_successful_destroy_with_cleanup_receipt_failure_stays_conservative(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _dotenv(tmp_path / "approved", b"OPENAI_API_KEY=" + OPENAI_DUMMY + b"\n")
    common = _high_level_secret_fixture(tmp_path, monkeypatch, source)
    supervisor.materialize_openai_runtime_secret(
        tmp_path,
        openai_dotenv_path=source,
        **common,
    )
    original_write = supervisor._write_exclusive

    def fail_cleanup_receipt(path: Path, *args: object, **kwargs: object) -> None:
        if path == tmp_path / supervisor.OPENAI_SECRET_CLEANUP_RELATIVE:
            raise OSError
        original_write(path, *args, **kwargs)

    monkeypatch.setattr(supervisor, "_write_exclusive", fail_cleanup_receipt)
    with pytest.raises(supervisor.OpenAISecretSourceError) as captured:
        supervisor.cleanup_openai_runtime_secret(
            tmp_path,
            remote_upload_attestation=(
                "confirmed-exact-filtered-file-uploaded-and-permissions-qualified"
            ),
            **common,
        )
    assert captured.value.code == "runtime_secret_cleanup_receipt_unavailable"
    assert captured.value.credential_rotation_required is True
    assert not (
        tmp_path / supervisor.UPLOAD_ROOT_RELATIVE / supervisor.UPLOAD_OPENAI_SECRET_NAME
    ).exists()
    state = supervisor._verify_local_openai_secret_cleanup(
        tmp_path,
        disposition="failed",
        authorization_reference=AUTHORIZATION_REFERENCE,
    )
    assert state["state"] == "remote_uploaded_local_cleanup_unverified"
    assert state["remote_upload_confirmed"] is True
    assert state["cleanup_verified"] is False
    assert state["credential_rotation_required"] is True


def test_remote_upload_receipt_failure_burns_unknown_lifecycle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _dotenv(tmp_path / "approved", b"OPENAI_API_KEY=" + OPENAI_DUMMY + b"\n")
    common = _high_level_secret_fixture(tmp_path, monkeypatch, source)
    supervisor.materialize_openai_runtime_secret(
        tmp_path,
        openai_dotenv_path=source,
        **common,
    )
    original_write = supervisor._write_exclusive

    def fail_remote_receipt(path: Path, *args: object, **kwargs: object) -> None:
        if path == tmp_path / supervisor.OPENAI_SECRET_UPLOAD_OUTCOME_RELATIVE:
            raise OSError
        original_write(path, *args, **kwargs)

    monkeypatch.setattr(supervisor, "_write_exclusive", fail_remote_receipt)
    with pytest.raises(supervisor.OpenAISecretSourceError) as captured:
        supervisor.cleanup_openai_runtime_secret(
            tmp_path,
            remote_upload_attestation=(
                "confirmed-exact-filtered-file-uploaded-and-permissions-qualified"
            ),
            **common,
        )
    assert captured.value.code == "runtime_secret_remote_upload_receipt_unavailable"
    assert captured.value.credential_rotation_required is True
    state = supervisor._verify_local_openai_secret_cleanup(
        tmp_path,
        disposition="failed",
        authorization_reference=AUTHORIZATION_REFERENCE,
    )
    assert state["state"] == "remote_upload_outcome_unknown_cleanup_unverified"
    assert state["remote_upload_confirmed"] is False
    assert state["remote_upload_outcome_unknown"] is True
    assert state["credential_rotation_required"] is True


@pytest.mark.parametrize(
    ("outcome", "expected_state", "unknown", "rotation"),
    (
        (
            "definitely-not-uploaded",
            "aborted_not_uploaded_cleaned",
            False,
            False,
        ),
        (
            "unknown-or-permissions-unqualified",
            "aborted_unknown_cleaned",
            True,
            True,
        ),
    ),
)
def test_upload_abort_has_typed_local_cleanup_and_blocks_release(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    outcome: str,
    expected_state: str,
    unknown: bool,
    rotation: bool,
) -> None:
    source = _dotenv(tmp_path / "approved", b"OPENAI_API_KEY=" + OPENAI_DUMMY + b"\n")
    common = _high_level_secret_fixture(tmp_path, monkeypatch, source)
    supervisor.materialize_openai_runtime_secret(
        tmp_path,
        openai_dotenv_path=source,
        **common,
    )
    result = supervisor.abort_openai_runtime_secret(
        tmp_path,
        remote_upload_outcome=outcome,
        **common,
    )
    assert result["cleanup_verified"] is True
    assert result["credential_rotation_required"] is rotation
    assert not (
        tmp_path / supervisor.UPLOAD_ROOT_RELATIVE / supervisor.UPLOAD_OPENAI_SECRET_NAME
    ).exists()
    state = supervisor._verify_local_openai_secret_cleanup(
        tmp_path,
        disposition="failed",
        authorization_reference=AUTHORIZATION_REFERENCE,
    )
    assert state["state"] == expected_state
    assert state["remote_upload_confirmed"] is False
    assert state["remote_upload_outcome_unknown"] is unknown
    assert state["cleanup_verified"] is True
    assert state["credential_rotation_required"] is rotation
    upload = json.loads(
        (tmp_path / supervisor.OPENAI_SECRET_UPLOAD_OUTCOME_RELATIVE).read_text(encoding="utf-8")
    )
    assert upload["required_remote_parent_mode"] == "0700"
    assert upload["required_remote_file_mode"] == "0600"
    if unknown:
        assert upload["observed_remote_parent_mode"] is None
        assert upload["observed_remote_file_mode"] is None
        assert upload["observed_remote_current_user_owned"] is None
        assert upload["remote_permissions_qualified"] is False
    with pytest.raises(supervisor.BoundedSupervisorError):
        supervisor.issue_bootstrap_release(
            tmp_path,
            provider_image_attestation="confirmed-in-provider-console",
            **common,
        )


def test_abort_cleanup_survives_repository_hard_stop_after_materialization(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _dotenv(tmp_path / "approved", b"OPENAI_API_KEY=" + OPENAI_DUMMY + b"\n")
    common = _high_level_secret_fixture(tmp_path, monkeypatch, source)
    supervisor.materialize_openai_runtime_secret(
        tmp_path,
        openai_dotenv_path=source,
        **common,
    )

    def repository_drift(*args: object, **kwargs: object) -> None:
        raise supervisor.BoundedSupervisorError("synthetic repository drift")

    monkeypatch.setattr(supervisor, "verify_repository_identity", repository_drift)
    result = supervisor.abort_openai_runtime_secret(
        tmp_path,
        remote_upload_outcome="definitely-not-uploaded",
        **common,
    )
    assert result["cleanup_verified"] is True
    assert not (
        tmp_path / supervisor.UPLOAD_ROOT_RELATIVE / supervisor.UPLOAD_OPENAI_SECRET_NAME
    ).exists()


def test_hash_first_bootstrap_skips_clean_tree_only_for_cleanup_capabilities() -> None:
    path = ROOT / "containers/sira-smoke/bounded/local_supervisor_bootstrap.py"
    spec = importlib.util.spec_from_file_location("test_t07_v3_local_bootstrap_cleanup", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    assert module._operation(["abort-openai-secret"]) == "abort-openai-secret"
    assert module._operation(["cleanup-openai-secret"]) == "cleanup-openai-secret"
    assert module._operation(["observe"]) == ""


def test_main_abort_cleanup_survives_plan_bound_artifact_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _dotenv(tmp_path / "approved", b"OPENAI_API_KEY=" + OPENAI_DUMMY + b"\n")
    binding = supervisor.openai_dotenv_path_binding(source)
    monkeypatch.setattr(supervisor, "OPENAI_DOTENV_PATH_BINDING_SHA256", binding)
    monkeypatch.setattr(contract, "OPENAI_DOTENV_PATH_BINDING_SHA256", binding)
    monkeypatch.setattr(supervisor, "verify_repository_identity", lambda *_: None)
    monkeypatch.setattr(
        supervisor,
        "_validate_authority_inputs",
        lambda *args, **kwargs: ({"authorization_reference": AUTHORIZATION_REFERENCE}, {}),
    )
    monkeypatch.setattr(
        supervisor,
        "_load_state",
        lambda *_: {"status": "post_launch_passed", "next_phase": "termination"},
    )
    for name in ("LAMBDA_API_KEY", "OPENAI_API_KEY", "SIRA_API_KEY"):
        monkeypatch.delenv(name, raising=False)

    current_plan = json.loads((ROOT / supervisor.BOUNDED_PLAN_RELATIVE).read_text(encoding="utf-8"))
    provider = current_plan["secrets"]["openai_provider"]
    assert isinstance(provider, dict)
    provider["source_path_binding_sha256"] = binding
    for record in current_plan["implementation"]["artifacts"]:
        assert isinstance(record, dict) and isinstance(record.get("path"), str)
        relative = Path(record["path"])
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, destination)
    for relative in contract.SCIENTIFIC_HASHES:
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, destination)
    secret_schema = tmp_path / supervisor.OPENAI_SECRET_SCHEMA_RELATIVE
    secret_schema.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / supervisor.OPENAI_SECRET_SCHEMA_RELATIVE, secret_schema)
    plan_path = tmp_path / supervisor.BOUNDED_PLAN_RELATIVE
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_encoded = supervisor.canonical_json_bytes(current_plan)
    plan_path.write_bytes(plan_encoded)
    plan_sha256 = hashlib.sha256(plan_encoded).hexdigest()

    run_root = tmp_path / supervisor.RUN_ROOT_RELATIVE
    upload_root = tmp_path / supervisor.UPLOAD_ROOT_RELATIVE
    run_root.mkdir(parents=True)
    upload_root.mkdir(parents=True)
    authorization_path = tmp_path / supervisor.AUTHORIZATION_RELATIVE
    authorization_path.write_bytes(
        supervisor.canonical_json_bytes({"authorization_reference": AUTHORIZATION_REFERENCE})
    )
    private_binding_path = tmp_path / supervisor.PRIVATE_BINDING_RELATIVE
    private_binding_path.write_text("{}\n", encoding="utf-8")
    expected_commit = "2" * 40
    authorization_sha256 = "3" * 64
    private_binding_sha256 = "4" * 64
    supervisor.materialize_openai_runtime_secret(
        tmp_path,
        plan=current_plan,
        plan_sha256=plan_sha256,
        expected_commit=expected_commit,
        authorization_path=authorization_path,
        authorization_sha256=authorization_sha256,
        private_binding_path=private_binding_path,
        private_binding_sha256=private_binding_sha256,
        openai_dotenv_path=source,
    )

    drifted = tmp_path / "docs/PROJECT_STATE.yaml"
    drifted.write_bytes(drifted.read_bytes() + b"# synthetic post-materialization drift\n")
    common_argv = [
        "--repository-root",
        str(tmp_path),
        "--plan",
        str(plan_path),
        "--plan-sha256",
        plan_sha256,
        "--contract-file",
        str(tmp_path / "src/giclab/harness/t07_bounded_smoke.py"),
        "--contract-sha256",
        "5" * 64,
        "--expected-commit",
        expected_commit,
    ]
    authority_argv = [
        "--authorization",
        str(authorization_path),
        "--authorization-sha256",
        authorization_sha256,
        "--private-binding",
        str(private_binding_path),
        "--private-binding-sha256",
        private_binding_sha256,
    ]
    assert (
        supervisor.main(
            [
                *common_argv,
                "abort-openai-secret",
                *authority_argv,
                "--remote-upload-outcome",
                "definitely-not-uploaded",
            ],
            contract=contract,
        )
        == 0
    )
    assert not (upload_root / supervisor.UPLOAD_OPENAI_SECRET_NAME).exists()
    with pytest.raises(contract.BoundedSmokeContractError, match="artifact identity drifted"):
        supervisor.main(
            [
                *common_argv,
                "release-bootstrap",
                *authority_argv,
                "--provider-image-attestation",
                "confirmed-in-provider-console",
            ],
            contract=contract,
        )


def test_plan_selects_existing_openai_source_without_user_sira_file() -> None:
    secrets = contract.secrets_contract()
    source = secrets["openai_provider"]
    assert isinstance(source, dict)
    assert source["source_assignment"] == "OPENAI_API_KEY"
    assert source["user_created_sira_api_key_file_required"] is False
    assert source["complete_env_upload_permitted"] is False
    assert source["fallbacks"] == []
    assert source["provider_credential_fallback"] == "none"
    assert source["metadata_runtime_name"] == "OPENAI_API_KEY"
    assert source["runtime_mapping"] == "provider-native-metadata-and-ephemeral-sira-child-alias"


def test_entrypoint_alias_is_single_child_and_does_not_mutate_parent() -> None:
    entrypoint = _load_entrypoint()
    ambient = {
        "PATH": "/usr/bin",
        "LAMBDA_API_KEY": "wrong-lambda-value",
        "OPENAI_API_KEY": "wrong-openai-value",
        "SIRA_API_KEY": "wrong-sira-value",
    }
    child = entrypoint.child_environment(OPENAI_DUMMY.decode(), ambient)
    assert child["SIRA_API_KEY"] == OPENAI_DUMMY.decode()
    assert "OPENAI_API_KEY" not in child
    assert "LAMBDA_API_KEY" not in child
    assert ambient["OPENAI_API_KEY"] == "wrong-openai-value"
    assert ambient["SIRA_API_KEY"] == "wrong-sira-value"
    metadata_child = entrypoint.child_environment(
        OPENAI_DUMMY.decode(),
        ambient,
        runtime_assignment="OPENAI_API_KEY",
    )
    assert metadata_child["OPENAI_API_KEY"] == OPENAI_DUMMY.decode()
    assert "SIRA_API_KEY" not in metadata_child
    assert "LAMBDA_API_KEY" not in metadata_child


@pytest.mark.parametrize(
    "unsafe_value",
    [
        b"OPENAI_API_KEY=PUBLIC-DUMMY\nLAMBDA_API_KEY=PUBLIC-DUMMY-LAMBDA",
        b"PUBLIC-DUMMY\n",
        b"PUBLIC-DUMMY\r",
        b"PUBLIC DUMMY",
    ],
)
def test_entrypoint_rejects_swapped_or_multiline_secret_before_child(
    tmp_path: Path, unsafe_value: bytes
) -> None:
    entrypoint = _load_entrypoint()
    bootstrap_path = ROOT / "containers/sira-smoke/bounded/bootstrap.py"
    spec = importlib.util.spec_from_file_location(
        "test_t07_v3_bootstrap_value_contract", bootstrap_path
    )
    assert spec is not None and spec.loader is not None
    bootstrap = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = bootstrap
    spec.loader.exec_module(bootstrap)
    assert entrypoint.SECRET_VALUE_CONTRACT == bootstrap.REMOTE_SECRET_VALUE_CONTRACT

    secret_path = tmp_path / "swapped-provider-secret"
    secret_path.write_bytes(unsafe_value)
    secret_path.chmod(0o600)
    with pytest.raises(RuntimeError, match="empty or malformed"):
        entrypoint.read_secret_file(secret_path)


def test_remote_bootstrap_rejects_every_ambient_secret_channel() -> None:
    bootstrap_path = ROOT / "containers/sira-smoke/bounded/bootstrap.py"
    spec = importlib.util.spec_from_file_location("test_t07_v3_bootstrap_channels", bootstrap_path)
    assert spec is not None and spec.loader is not None
    bootstrap = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = bootstrap
    spec.loader.exec_module(bootstrap)
    bootstrap.reject_inherited_credentials({"PATH": "/usr/bin"})
    for name in ("LAMBDA_API_KEY", "OPENAI_API_KEY", "SIRA_API_KEY"):
        with pytest.raises(bootstrap.BootstrapError, match="must not be inherited"):
            bootstrap.reject_inherited_credentials({"PATH": "/usr/bin", name: "dummy"})


def test_runtime_file_is_automatic_unarchived_private_and_destroyed(tmp_path: Path) -> None:
    source = _dotenv(
        tmp_path,
        b"LAMBDA_API_KEY=" + LAMBDA_DUMMY + b"\nOPENAI_API_KEY=" + OPENAI_DUMMY + b"\n",
    )
    runtime_root = tmp_path / "runtime"
    runtime_root.mkdir(mode=0o700)
    destination = runtime_root / supervisor.UPLOAD_OPENAI_SECRET_NAME
    record = supervisor.materialize_runtime_secret(source, destination)
    assert destination.read_bytes() == OPENAI_DUMMY
    assert destination.stat().st_mode & 0o777 == 0o600
    retained = json.dumps(record, sort_keys=True).encode()
    assert OPENAI_DUMMY not in retained
    assert hashlib.sha256(OPENAI_DUMMY).hexdigest().encode() not in retained
    assert record["complete_dotenv_uploaded"] is False
    assert record["user_managed_sira_file_required"] is False
    cleanup = supervisor.destroy_runtime_secret(
        destination,
        expected_device=int(record["runtime_file_device"]),
        expected_inode=int(record["runtime_file_inode"]),
    )
    assert not destination.exists()
    assert cleanup["cleanup_verified"] is True
    assert cleanup["credential_rotation_required"] is False


def test_cleanup_failure_requires_credential_rotation(tmp_path: Path) -> None:
    with pytest.raises(supervisor.OpenAISecretSourceError) as captured:
        supervisor.destroy_runtime_secret(
            tmp_path / supervisor.UPLOAD_OPENAI_SECRET_NAME,
            expected_device=0,
            expected_inode=1,
        )
    assert captured.value.credential_rotation_required is True


def test_partial_materialization_failure_zeroes_and_unlinks_dummy_value(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _dotenv(tmp_path, b"OPENAI_API_KEY=" + OPENAI_DUMMY + b"\n")
    destination = tmp_path / supervisor.UPLOAD_OPENAI_SECRET_NAME

    def fail_after_partial_write(lease: supervisor.OpenAISecretLease, descriptor: int) -> None:
        assert descriptor >= 0
        supervisor.os.write(descriptor, lease._value[:7])
        raise supervisor.OpenAISecretSourceError("synthetic_partial_write")

    monkeypatch.setattr(
        supervisor.OpenAISecretLease,
        "write_to",
        fail_after_partial_write,
    )
    with pytest.raises(supervisor.OpenAISecretSourceError, match="synthetic_partial_write"):
        supervisor.materialize_runtime_secret(source, destination)
    assert not destination.exists()


def test_partial_materialization_cleanup_failure_requires_rotation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _dotenv(tmp_path, b"OPENAI_API_KEY=" + OPENAI_DUMMY + b"\n")
    destination = tmp_path / supervisor.UPLOAD_OPENAI_SECRET_NAME
    original_unlink = supervisor.os.unlink

    def fail_after_partial_write(lease: supervisor.OpenAISecretLease, descriptor: int) -> None:
        supervisor.os.write(descriptor, lease._value[:7])
        raise supervisor.OpenAISecretSourceError("synthetic_partial_write")

    def fail_runtime_unlink(path: object, *args: object, **kwargs: object) -> None:
        if path == destination.name:
            raise OSError
        original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(
        supervisor.OpenAISecretLease,
        "write_to",
        fail_after_partial_write,
    )
    monkeypatch.setattr(supervisor.os, "unlink", fail_runtime_unlink)
    with pytest.raises(supervisor.OpenAISecretSourceError) as captured:
        supervisor.materialize_runtime_secret(source, destination)
    assert captured.value.code == "runtime_secret_materialization_cleanup_failed"
    assert captured.value.credential_rotation_required is True
    assert destination.exists()
    original_unlink(destination)


def test_upload_bundle_contract_excludes_dotenv_and_runtime_secret() -> None:
    source = inspect.getsource(supervisor._plan_upload_rows)
    assert 'part in {".git", ".env", "artifacts", ".secrets"}' in source
    assert supervisor.UPLOAD_OPENAI_SECRET_NAME not in contract.REQUIRED_IMPLEMENTATION_ARTIFACTS
    storage = contract.storage_contract()
    assert all(
        "openai-provider-key" not in item
        for item in storage["external_archive_required_upload_artifacts"]
    )


def test_v2_is_preserved_burned_and_v3_roots_are_fresh() -> None:
    v2 = ROOT / "containers/sira-smoke/bounded/bounded-smoke-plan-v2.json"
    encoded = v2.read_bytes()
    assert len(encoded) == 43_198
    assert hashlib.sha256(encoded).hexdigest() == (
        "f0d635783d719d1c5cb5df5351eaf8f6f54e9049da1f2565e4227e66f48ef511"
    )
    assert contract.PLAN_ID == "PLAN-T07-BOUNDED-SIRA-SMOKE-V3"
    assert contract.HOST_RUN_ID == "RUN-T07-BOUNDED-HOST-0003"
    assert not (ROOT / "artifacts/t07/bounded/RUN-T07-BOUNDED-HOST-0003").exists()
    assert not (ROOT / "artifacts/t07/bounded-upload/RUN-T07-BOUNDED-HOST-0003").exists()


def test_science_model_and_all_v2_limits_are_unchanged() -> None:
    v2 = json.loads((ROOT / "containers/sira-smoke/bounded/bounded-smoke-plan-v2.json").read_text())
    assert v2["limits"] == dict(contract.LIMITS)
    assert v2["scientific_lock"]["model"] == contract.MODEL
    assert v2["scientific_lock"]["condition_order"] == list(contract.CONDITION_ORDER)
    for relative, digest in contract.SCIENTIFIC_HASHES.items():
        assert contract.sha256_file(ROOT / relative) == digest


def test_secret_source_schema_and_v3_plan_are_strict() -> None:
    schema_path = ROOT / "schemas/t07-bounded-openai-secret-source.schema.json"
    assert hashlib.sha256(schema_path.read_bytes()).hexdigest() == (
        contract.OPENAI_SECRET_SOURCE_SCHEMA_SHA256
    )
    assert validate_instance(contract.openai_secret_source_contract(), schema_path) == []
    plan_path = ROOT / "containers/sira-smoke/bounded/bounded-smoke-plan-v3.json"
    if plan_path.exists():
        plan = json.loads(plan_path.read_text())
        assert plan["execution_permissions_now"] == {
            "browser": False,
            "cloud_mutations": 0,
            "containers": False,
            "jupyter": False,
            "lambda_account_requests": 0,
            "openai_account_requests": 0,
            "paid_compute": False,
            "scientific_execution": False,
            "sira": False,
        }


def test_repair_surface_contains_no_live_transport_or_execution_call() -> None:
    # This turn's implementation is local-only. The strict loader itself has no
    # account transport, process launch, container, browser, or SiRA execution path.
    source = inspect.getsource(supervisor.load_openai_secret)
    source += inspect.getsource(supervisor.materialize_runtime_secret)
    for forbidden in (
        "httpsconnection",
        "urlopen",
        "socket.",
        "subprocess",
        "docker",
        "chromium",
        "run_condition",
    ):
        assert forbidden not in source.casefold()


def test_secret_names_and_dummy_value_do_not_enter_public_repository_files() -> None:
    canary = OPENAI_DUMMY
    listed = subprocess.run(
        [
            "/usr/bin/git",
            "-C",
            str(ROOT),
            "ls-files",
            "-z",
            "--cached",
            "--others",
            "--exclude-standard",
        ],
        check=True,
        capture_output=True,
    ).stdout
    for relative in filter(None, listed.decode().split("\0")):
        path = ROOT / relative
        if path.suffix in {".pyc", ".png", ".jpg", ".zip", ".tar"}:
            continue
        assert canary not in path.read_bytes(), path
