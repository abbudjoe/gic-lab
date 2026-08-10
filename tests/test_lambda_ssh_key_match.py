from __future__ import annotations

import base64
import hashlib
import json
import os
import stat
from pathlib import Path
from unittest.mock import patch

import pytest

from giclab.harness.lambda_ssh_key_fingerprint import (
    FINGERPRINT_SCHEMA_RELATIVE_PATH,
    MATCH_SCHEMA_RELATIVE_PATH,
    RUN_ROOT_RELATIVE_PATH,
    AccountKeyProjection,
    SSHKeyFingerprintError,
    project_account_ssh_keys,
    validate_document_against_schema,
)
from giclab.harness.lambda_ssh_key_match import (
    MatchState,
    discover_local_public_keys,
    invalid_evidence_report,
    match_account_to_local_keys,
    validate_sanitized_report,
    write_local_evidence_bundle,
)
from giclab.validation import ROOT

ACCOUNT_NAMES = (
    "aic-codex-lambda",
    "codex-fawx-20260527",
    "fractal-lambda-codex",
)


def _ssh_string(value: bytes) -> bytes:
    return len(value).to_bytes(4, "big") + value


def _public_key(seed: int) -> str:
    key = bytes((seed + index) % 256 for index in range(32))
    wire = _ssh_string(b"ssh-ed25519") + _ssh_string(key)
    return f"ssh-ed25519 {base64.b64encode(wire).decode()} fixture-{seed}"


def _projection(keys: tuple[str, str, str]) -> AccountKeyProjection:
    document = {
        "data": [
            {"id": f"private-raw-id-{index}", "name": name, "public_key": key}
            for index, (name, key) in enumerate(zip(ACCOUNT_NAMES, keys, strict=True), start=1)
        ]
    }
    return project_account_ssh_keys(
        json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    )


def _write_public(ssh_root: Path, name: str, value: str, *, private: bool = True) -> None:
    (ssh_root / f"{name}.pub").write_text(value, encoding="utf-8")
    if private:
        (ssh_root / name).write_text("PRIVATE-BYTES-MUST-NOT-BE-OPENED", encoding="utf-8")
        (ssh_root / name).chmod(0o600)


def test_unique_match_requires_user_approval_and_hides_sensitive_values(tmp_path: Path) -> None:
    ssh_root = tmp_path / ".ssh"
    ssh_root.mkdir(mode=0o700)
    keys = (_public_key(1), _public_key(2), _public_key(3))
    _write_public(ssh_root, "selected", keys[0])
    local = discover_local_public_keys(ssh_root)
    result = match_account_to_local_keys(_projection(keys), local)
    rows = result.sanitized_report["account_key_matches"]
    assert isinstance(rows, list)
    assert rows[0]["match_status"] == MatchState.UNIQUE_MATCH
    assert result.sanitized_report["recommended_account_key_name"] == ACCOUNT_NAMES[0]
    assert result.sanitized_report["selection_authorized"] is False
    public = json.dumps(result.sanitized_report, sort_keys=True)
    assert "private-raw-id" not in public
    assert "SHA256:" not in public
    assert str(tmp_path) not in public
    assert keys[0] not in public
    validate_sanitized_report(result.sanitized_report, repository_root=ROOT)


def test_no_match_is_blocked(tmp_path: Path) -> None:
    ssh_root = tmp_path / ".ssh"
    ssh_root.mkdir()
    _write_public(ssh_root, "different", _public_key(99))
    keys = (_public_key(1), _public_key(2), _public_key(3))
    result = match_account_to_local_keys(
        _projection(keys),
        discover_local_public_keys(ssh_root),
    )
    rows = result.sanitized_report["account_key_matches"]
    assert isinstance(rows, list)
    assert {row["match_status"] for row in rows} == {MatchState.NO_MATCH}
    assert result.sanitized_report["recommended_account_key_name"] is None
    assert result.sanitized_report["selection_state"] == "blocked"


def test_duplicate_local_public_key_is_ambiguous(tmp_path: Path) -> None:
    ssh_root = tmp_path / ".ssh"
    ssh_root.mkdir()
    keys = (_public_key(1), _public_key(2), _public_key(3))
    _write_public(ssh_root, "one", keys[0])
    _write_public(ssh_root, "two", keys[0])
    result = match_account_to_local_keys(
        _projection(keys),
        discover_local_public_keys(ssh_root),
    )
    rows = result.sanitized_report["account_key_matches"]
    assert isinstance(rows, list)
    assert rows[0]["match_status"] == MatchState.AMBIGUOUS_MATCH
    assert rows[0]["local_key_alias"] is None
    assert result.sanitized_report["recommended_account_key_name"] is None


def test_one_local_key_matching_multiple_account_names_is_ambiguous(tmp_path: Path) -> None:
    ssh_root = tmp_path / ".ssh"
    ssh_root.mkdir()
    shared = _public_key(5)
    keys = (shared, shared, _public_key(9))
    _write_public(ssh_root, "shared", shared)
    result = match_account_to_local_keys(
        _projection(keys),
        discover_local_public_keys(ssh_root),
    )
    rows = result.sanitized_report["account_key_matches"]
    assert isinstance(rows, list)
    assert [row["match_status"] for row in rows[:2]] == [
        MatchState.AMBIGUOUS_MATCH,
        MatchState.AMBIGUOUS_MATCH,
    ]


def test_same_stem_private_file_is_metadata_only(tmp_path: Path) -> None:
    ssh_root = tmp_path / ".ssh"
    ssh_root.mkdir()
    _write_public(ssh_root, "metadata-only", _public_key(7))
    original_open = os.open
    attempted_private_open = False

    def observed_open(path: object, *args: object, **kwargs: object) -> int:
        nonlocal attempted_private_open
        if path == "metadata-only":
            attempted_private_open = True
            raise AssertionError("private key was opened")
        return original_open(path, *args, **kwargs)  # type: ignore[arg-type]

    with patch("giclab.harness.lambda_ssh_key_match.os.open", side_effect=observed_open):
        records = discover_local_public_keys(ssh_root)
    assert not attempted_private_open
    assert records[0].same_stem.present
    assert records[0].same_stem.regular_file
    assert records[0].private_key_bytes_accessed is False


def test_symlink_nonregular_and_open_swap_are_rejected(tmp_path: Path) -> None:
    ssh_root = tmp_path / ".ssh"
    ssh_root.mkdir()
    outside = tmp_path / "outside.pub"
    outside.write_text(_public_key(1))
    (ssh_root / "symlink.pub").symlink_to(outside)
    with pytest.raises(SSHKeyFingerprintError):
        discover_local_public_keys(ssh_root)
    (ssh_root / "symlink.pub").unlink()
    (ssh_root / "directory.pub").mkdir()
    with pytest.raises(SSHKeyFingerprintError):
        discover_local_public_keys(ssh_root)
    (ssh_root / "directory.pub").rmdir()
    target = ssh_root / "swap.pub"
    target.write_text(_public_key(2))

    def swap(name: str) -> None:
        assert name == "swap.pub"
        target.unlink()
        target.symlink_to(outside)

    with pytest.raises(SSHKeyFingerprintError):
        discover_local_public_keys(ssh_root, pre_open_hook=swap)


def test_private_and_public_documents_validate_and_evidence_writes_exclusively(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repo"
    run_root = repository / RUN_ROOT_RELATIVE_PATH
    run_root.mkdir(parents=True)
    ssh_root = tmp_path / ".ssh"
    ssh_root.mkdir()
    keys = (_public_key(1), _public_key(2), _public_key(3))
    _write_public(ssh_root, "selected", keys[0])
    projection = _projection(keys)
    result = match_account_to_local_keys(
        projection,
        discover_local_public_keys(ssh_root),
    )
    validate_document_against_schema(
        result.private_manifest,
        repository_root=ROOT,
        schema_relative_path=FINGERPRINT_SCHEMA_RELATIVE_PATH,
    )
    validate_document_against_schema(
        result.sanitized_report,
        repository_root=ROOT,
        schema_relative_path=MATCH_SCHEMA_RELATIVE_PATH,
    )
    raw = json.dumps(
        {
            "data": [
                {"id": f"private-raw-id-{index}", "name": name, "public_key": key}
                for index, (name, key) in enumerate(zip(ACCOUNT_NAMES, keys, strict=True), start=1)
            ]
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    bundle = write_local_evidence_bundle(repository, raw_response=raw, result=result)
    assert bundle.raw_response.sha256 == hashlib.sha256(raw).hexdigest()
    for name in (
        "ssh-keys-response.json",
        "private-evidence.json",
        "match-report.json",
        "PRIVATE_EVIDENCE_SEAL.json",
    ):
        assert stat.S_IMODE((run_root / name).stat().st_mode) == 0o400
    with pytest.raises(SSHKeyFingerprintError):
        write_local_evidence_bundle(repository, raw_response=raw, result=result)


def test_invalid_evidence_is_blocked_and_schema_valid() -> None:
    document = invalid_evidence_report(ACCOUNT_NAMES)
    assert document["selection_state"] == "blocked"
    assert document["recommended_account_key_name"] is None
    validate_sanitized_report(document, repository_root=ROOT)


def test_match_module_contains_no_ssh_or_network_execution_primitive() -> None:
    source = (ROOT / "src/giclab/harness/lambda_ssh_key_match.py").read_text()
    for forbidden in (
        "subprocess",
        "socket.",
        "http.client",
        "urllib.request",
        "ssh-keyscan",
        "ssh-agent",
        "ssh-keygen",
    ):
        assert forbidden not in source
