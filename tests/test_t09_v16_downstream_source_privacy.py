from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

from giclab.harness.t09_sira_pilot import (
    EvaluatorIdentity,
    evaluate_retained_session,
    file_sha256,
)

ROOT = Path(__file__).resolve().parents[1]
HOST_SOURCE = ROOT / "containers/sira-smoke/pragmatic/t09_remote_runner.py"
PREFLIGHT_SOURCE = ROOT / "containers/sira-smoke/pragmatic/t09_preflight.py"
EVALUATOR_ROOT = ROOT / "tests/fixtures/t09/pinned-evaluator"
DATASET_FIXTURE = ROOT / "tests/fixtures/t09/fanout-two-task-fixture.json"
RAW_FIXTURE = ROOT / "tests/fixtures/t09/finalizer-raw-shape"


def _module(name: str, path: Path) -> ModuleType:
    specification = importlib.util.spec_from_file_location(name, path)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


@pytest.fixture
def host() -> ModuleType:
    return _module("giclab_t09_v16_host_test", HOST_SOURCE)


def _git(repository: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", "-C", repository, *arguments],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _repository_with_source(
    tmp_path: Path,
    host: ModuleType,
    *,
    role: object,
    payload: bytes,
) -> tuple[Path, Path, str, str]:
    repository = tmp_path / "repository"
    repository.mkdir()
    _git(repository, "init", "-q")
    _git(repository, "config", "user.name", "T09 V16 Test")
    _git(repository, "config", "user.email", "t09-v16@example.invalid")
    contract = host.DOWNSTREAM_SOURCE_CONTRACTS[role]
    relative = contract.relative_path
    source = repository / relative
    source.parent.mkdir(parents=True)
    source.write_bytes(payload)
    source.chmod(0o644)
    _git(repository, "add", relative)
    _git(repository, "commit", "-q", "-m", "bind downstream source")
    return repository, source, relative, _git(repository, "rev-parse", "HEAD")


def _validate(
    host: ModuleType,
    repository: Path,
    source: Path,
    relative: str,
    commit: str,
    role: object,
) -> dict[str, object]:
    return host.validate_git_bound_downstream_source(
        repository=repository,
        commit=commit,
        role=role,
        relative=relative,
        source=source,
    )


def test_exact_current_selector_passes_with_content_free_git_binding(
    tmp_path: Path, host: ModuleType
) -> None:
    payload = HOST_SOURCE.read_bytes()
    assert len(payload) > 1_048_576
    repository, source, relative, commit = _repository_with_source(
        tmp_path,
        host,
        role=host.DownstreamSourceRole.SELECTOR,
        payload=payload,
    )
    receipt = _validate(
        host,
        repository,
        source,
        relative,
        commit,
        host.DownstreamSourceRole.SELECTOR,
    )
    assert receipt == {
        "role": "selector",
        "path": host.SELECTOR_RELATIVE_PATH,
        "bytes": len(payload),
        "maximum_bytes": 4_194_304,
        "git_blob": _git(repository, "rev-parse", f"{commit}:{relative}"),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }
    assert payload not in json.dumps(receipt, sort_keys=True).encode()


def test_exact_finalizer_validation_path_binds_all_current_source_roles(
    tmp_path: Path, host: ModuleType
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    _git(repository, "init", "-q")
    _git(repository, "config", "user.name", "T09 V16 Test")
    _git(repository, "config", "user.email", "t09-v16@example.invalid")
    for contract in host.DOWNSTREAM_SOURCE_CONTRACTS.values():
        source = repository / contract.relative_path
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes((ROOT / contract.relative_path).read_bytes())
        source.chmod(0o644)
    _git(repository, "add", ".")
    _git(repository, "commit", "-q", "-m", "bind complete downstream closure")
    commit = _git(repository, "rev-parse", "HEAD")
    repository_host = _module(
        "giclab_t09_v16_complete_source_closure",
        repository / host.SELECTOR_RELATIVE_PATH,
    )
    result = repository_host.validate_finalizer_source(
        repository=repository,
        package_commit=commit,
        finalizer_commit=commit,
        source=repository / repository_host.FINALIZER_RELATIVE_PATH,
        projection_source=repository / repository_host.FINALIZER_PROJECTION_RELATIVE_PATH,
    )
    bindings = result[-1]
    assert set(bindings) == {
        "selector",
        "finalizer",
        "finalizer-projection",
        "refinalization-schema",
    }
    assert bindings["selector"]["bytes"] == HOST_SOURCE.stat().st_size
    assert bindings["selector"]["maximum_bytes"] == 4_194_304


@pytest.mark.parametrize("size", [1_048_577, 4_194_304])
def test_selector_accepts_large_and_exact_boundary_blobs(
    tmp_path: Path, host: ModuleType, size: int
) -> None:
    repository, source, relative, commit = _repository_with_source(
        tmp_path,
        host,
        role=host.DownstreamSourceRole.SELECTOR,
        payload=b"s" * size,
    )
    assert (
        _validate(
            host,
            repository,
            source,
            relative,
            commit,
            host.DownstreamSourceRole.SELECTOR,
        )["bytes"]
        == size
    )


def test_selector_rejects_cap_plus_one_before_git_blob_read(
    tmp_path: Path, host: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository, source, relative, commit = _repository_with_source(
        tmp_path,
        host,
        role=host.DownstreamSourceRole.SELECTOR,
        payload=b"s" * (4_194_304 + 1),
    )
    calls = 0

    def forbidden(*_args: object, **_kwargs: object) -> bytes:
        nonlocal calls
        calls += 1
        raise AssertionError("oversized local source must fail before Git output")

    monkeypatch.setattr(host, "_bounded_git_output", forbidden)
    with pytest.raises(host.T09HostError, match="metadata is unsafe"):
        _validate(
            host,
            repository,
            source,
            relative,
            commit,
            host.DownstreamSourceRole.SELECTOR,
        )
    assert calls == 0


@pytest.mark.parametrize(
    "role_name",
    ["FINALIZER", "FINALIZER_PROJECTION", "REFINALIZATION_SCHEMA"],
)
def test_smaller_source_role_caps_remain_independent(
    tmp_path: Path, host: ModuleType, role_name: str
) -> None:
    role = getattr(host.DownstreamSourceRole, role_name)
    repository, source, relative, commit = _repository_with_source(
        tmp_path,
        host,
        role=role,
        payload=b"f" * (1_048_576 + 1),
    )
    with pytest.raises(host.T09HostError, match="metadata is unsafe"):
        _validate(host, repository, source, relative, commit, role)


def test_cross_role_path_and_unbounded_git_output_fail_closed(
    tmp_path: Path, host: ModuleType
) -> None:
    repository, source, relative, commit = _repository_with_source(
        tmp_path,
        host,
        role=host.DownstreamSourceRole.SELECTOR,
        payload=b"selector\n",
    )
    with pytest.raises(host.T09HostError, match="role and path disagree"):
        host.validate_git_bound_downstream_source(
            repository=repository,
            commit=commit,
            role=host.DownstreamSourceRole.FINALIZER,
            relative=relative,
            source=source,
        )
    with pytest.raises(host.T09HostError, match="bounded output cap"):
        host._bounded_git_output(
            [sys.executable, "-c", "import sys; sys.stdout.write('x' * 65)"],
            maximum_bytes=64,
        )


@pytest.mark.parametrize("mutation", ["symlink", "hardlink", "directory", "writable"])
def test_unsafe_local_source_metadata_fails(
    tmp_path: Path, host: ModuleType, mutation: str
) -> None:
    repository, source, relative, commit = _repository_with_source(
        tmp_path,
        host,
        role=host.DownstreamSourceRole.SELECTOR,
        payload=b"selector\n",
    )
    retained = source.read_bytes()
    source.unlink()
    if mutation == "symlink":
        target = tmp_path / "target"
        target.write_bytes(retained)
        source.symlink_to(target)
    elif mutation == "hardlink":
        target = tmp_path / "target"
        target.write_bytes(retained)
        os.link(target, source)
    elif mutation == "directory":
        source.mkdir()
    else:
        source.write_bytes(retained)
        source.chmod(0o666)
    with pytest.raises((host.T09HostError, OSError)):
        _validate(
            host,
            repository,
            source,
            relative,
            commit,
            host.DownstreamSourceRole.SELECTOR,
        )


def test_wrong_owner_truncation_growth_replacement_commit_and_blob_fail(
    tmp_path: Path, host: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    role = host.DownstreamSourceRole.SELECTOR
    repository, source, relative, commit = _repository_with_source(
        tmp_path, host, role=role, payload=b"selector-one\n"
    )
    current_uid = os.getuid()
    monkeypatch.setattr(host.os, "getuid", lambda: current_uid + 1)
    with pytest.raises(host.T09HostError, match="metadata is unsafe"):
        _validate(host, repository, source, relative, commit, role)
    monkeypatch.undo()

    for changed in (b"short\n", b"selector-one-grown\n", b"selector-two\n"):
        source.write_bytes(changed)
        source.chmod(0o644)
        with pytest.raises(host.T09HostError):
            _validate(host, repository, source, relative, commit, role)
    source.write_bytes(b"selector-one\n")
    with pytest.raises(host.T09HostError, match="Git plumbing failed"):
        _validate(host, repository, source, relative, "f" * 40, role)


def test_changed_during_git_comparison_is_rejected(
    tmp_path: Path, host: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    role = host.DownstreamSourceRole.SELECTOR
    repository, source, relative, commit = _repository_with_source(
        tmp_path, host, role=role, payload=b"selector-one\n"
    )
    original = host._bounded_git_output
    calls = 0

    def mutate_after_blob(argv: list[str], **kwargs: object) -> bytes:
        nonlocal calls
        retained = original(argv, **kwargs)
        calls += 1
        if calls == 4:
            replacement = source.with_suffix(".replacement")
            replacement.write_bytes(b"selector-two\n")
            replacement.chmod(0o644)
            replacement.replace(source)
        return retained

    monkeypatch.setattr(host, "_bounded_git_output", mutate_after_blob)
    with pytest.raises(host.T09HostError, match="changed during Git comparison"):
        _validate(host, repository, source, relative, commit, role)


@pytest.mark.parametrize(
    "ordinary",
    [
        "task-b-normalization-edge",
        "risk-scoring",
        "desk-example",
        "prefixsk-constructed-value",
    ],
)
def test_embedded_identifier_is_not_a_credential_pattern(
    tmp_path: Path, host: ModuleType, ordinary: str
) -> None:
    (tmp_path / "fixture.json").write_text(json.dumps({"name": ordinary}), encoding="utf-8")
    assert host.privacy_violations(tmp_path) == []


@pytest.mark.parametrize("separator", ["", " ", "=", ":", '"'])
def test_runtime_constructed_openai_token_boundaries_are_detected(
    tmp_path: Path, host: ModuleType, separator: str
) -> None:
    canary = "".join(("s", "k-", "runtime", "Canary", "0123456789"))
    (tmp_path / "candidate.txt").write_text(separator + canary + "\n", encoding="utf-8")
    assert host.privacy_violations(tmp_path) == ["candidate.txt:credential-pattern"]


def test_runtime_constructed_aws_bearer_and_chunk_spanning_tokens_are_detected(
    tmp_path: Path, host: ModuleType
) -> None:
    aws = "AK" + "IA" + "ABCDEFGHIJKLMNOP"
    bearer = "Bear" + "er " + "runtime.canary/value=0123456789"
    (tmp_path / "aws.txt").write_text(aws, encoding="utf-8")
    (tmp_path / "bearer.txt").write_text(bearer, encoding="utf-8")
    canary = "".join(("s", "k-", "chunkBoundary", "0123456789")).encode()
    (tmp_path / "chunk.txt").write_bytes(
        b"x" * (host.MAX_PRIVACY_SCAN_CHUNK_BYTES - 3) + b" " + canary
    )
    assert host.privacy_violations(tmp_path) == [
        "aws.txt:credential-pattern",
        "bearer.txt:credential-pattern",
        "chunk.txt:credential-pattern",
    ]


def test_path_and_content_scanning_share_boundaries_and_other_privacy_checks_remain(
    tmp_path: Path, host: ModuleType
) -> None:
    (tmp_path / "task-b-normalization-edge.txt").write_text("public\n", encoding="utf-8")
    canary = "".join(("s", "k-", "pathCanary", "0123456789"))
    (tmp_path / canary).write_text("public\n", encoding="utf-8")
    (tmp_path / "sensitive.json").write_text('{"api_key":"redacted"}', encoding="utf-8")
    (tmp_path / "jupyter.txt").write_text(
        "http://localhost:8888/lab?token=public-canary", encoding="utf-8"
    )
    (tmp_path / "network.txt").write_text("10.0.0.1", encoding="utf-8")
    hits = host.privacy_violations(tmp_path)
    assert f"{canary}:credential-pattern-path" in hits
    assert not any(item.startswith("task-b-normalization-edge.txt:") for item in hits)
    assert "sensitive.json:sensitive-json-field" in hits
    assert "jupyter.txt:jupyter-url" in hits
    assert "network.txt:private-network" in hits


def test_exact_secret_scan_remains_independent_and_chunk_safe(
    tmp_path: Path, host: ModuleType
) -> None:
    exact = b"exact-runtime-canary-value"
    (tmp_path / "exact.bin").write_bytes(b"x" * (1_048_576 - 4) + exact)
    assert host.secret_hits(tmp_path, exact) == ["exact.bin"]


def test_production_preflight_receipt_is_structurally_clean(
    tmp_path: Path, host: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    preflight = _module("giclab_t09_v16_preflight_test", PREFLIGHT_SOURCE)
    attempt_root = tmp_path / "offline-runtime-preflight"
    attempt_root.mkdir(mode=0o700)
    execution = tmp_path / "execution.json"
    commands = tmp_path / "commands.json"
    finalizer = ROOT / "containers/sira-smoke/pragmatic/t09_evaluate_attempt.py"
    execution.write_text("{}\n", encoding="utf-8")
    commands.write_text("{}\n", encoding="utf-8")

    class FixtureIdentity:
        def __init__(
            self,
            *,
            root: Path,
            dataset_path: Path,
            task_index: int,
            fixture_subset: bool = False,
        ) -> None:
            assert fixture_subset is False
            self._identity = EvaluatorIdentity(
                root=root,
                dataset_path=dataset_path,
                task_index=task_index,
                fixture_subset=True,
            )
            self.root = root
            self.dataset_path = dataset_path
            self.task_index = task_index
            self.fixture_subset = True

        def verify(self) -> None:
            self._identity.verify()

    fake_contract = SimpleNamespace(
        attempts=[SimpleNamespace(giclab_commit="a" * 40)],
        sha256="b" * 64,
        plan_id="PLAN-EXP0001-PILOT-V16",
    )
    monkeypatch.setattr(
        preflight, "load_execution_contract", lambda *_args, **_kwargs: fake_contract
    )
    monkeypatch.setattr(preflight, "validate_command_manifest_package", lambda **_kwargs: [])
    monkeypatch.setattr(preflight, "EvaluatorIdentity", FixtureIdentity)
    monkeypatch.setattr(
        preflight,
        "evaluate_retained_session",
        lambda identity, sessions: evaluate_retained_session(identity._identity, sessions),
    )
    monkeypatch.setattr(
        preflight,
        "_run_finalizer_raw_fixture",
        lambda **_kwargs: {
            "task_completed": True,
            "answer_produced": True,
            "evaluator_valid": True,
            "score": 0.0,
            "provider_call_count": 1,
            "browser_action_count": 1,
        },
    )
    result = preflight.run(
        SimpleNamespace(
            execution_contract=execution,
            execution_contract_sha256=file_sha256(execution),
            command_manifests=commands,
            command_manifests_sha256=file_sha256(commands),
            runtime_adaptation_sha256="c" * 64,
            pilot_library_sha256="d" * 64,
            attempt_root=attempt_root,
            aggregate_ledger=tmp_path / "aggregate.json",
            pilot_state=tmp_path / "pilot-state.json",
            evaluator_root=EVALUATOR_ROOT,
            dataset=DATASET_FIXTURE,
            finalizer_source=finalizer,
            finalizer_source_sha256=file_sha256(finalizer),
            finalizer_raw_fixture=RAW_FIXTURE,
        )
    )
    assert result["provider_or_model_requests"] == 0
    assert result["secret_reads"] == 0
    receipt = attempt_root / "offline-runtime-preflight.json"
    assert "task-b-normalization-edge" in receipt.read_text(encoding="utf-8")
    assert host.privacy_violations(attempt_root) == []
    canary = "".join(("s", "k-", "nearbyCanary", "0123456789"))
    (attempt_root / "nearby.txt").write_text(canary, encoding="utf-8")
    assert "nearby.txt:credential-pattern" in host.privacy_violations(attempt_root)
