"""Candidate input boundaries; these tests alone close none of R1-R6."""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from giclab.harness.t09_candidate_inputs import (
    COMMAND_PATH,
    EXECUTION_PATH,
    MARKER,
    RUNTIME_PATH,
    CandidateInputError,
    build_candidate_source_snapshot,
    canonical,
    decode,
    load_candidate_source_snapshot,
    project_candidate_package,
    read_member,
    reject_candidate_source,
    sha,
    validate_candidate_package,
)
from giclab.harness.t09_qualification_fixture import build_deterministic_qualification_archive

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def candidate(tmp_path):
    head = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
    tree = subprocess.check_output(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD^{tree}"], text=True
    ).strip()
    archive = build_deterministic_qualification_archive(ROOT, tmp_path)
    snapshot = build_candidate_source_snapshot(
        ROOT,
        tmp_path / "candidate",
        parent_head=head,
        parent_tree=tree,
        qualification_document=archive.document(),
    )
    return snapshot, archive


def test_candidate_snapshot_round_trip_and_deterministic_inputs(candidate, tmp_path):
    first, archive = candidate
    document = first.document()
    second = build_candidate_source_snapshot(
        ROOT,
        tmp_path / "second",
        parent_head=document["parent_head"],
        parent_tree=document["parent_tree"],
        qualification_document=archive.document(),
    )
    assert first.binding_bytes == second.binding_bytes
    loaded = load_candidate_source_snapshot(
        first.root.parent,
        expected_binding_sha256=first.digest,
        parent_repository=ROOT,
        expected_parent_head=document["parent_head"],
        expected_parent_tree=document["parent_tree"],
    )
    assert loaded.digest == first.digest
    assert document["source_kind"] == (
        "dirty-snapshot" if document["dirty_delta"] else "committed-source-closure"
    )
    assert document["historical_replay"] == "not-run"


@pytest.mark.parametrize(
    "mutation", ["one-byte", "same-size", "missing", "unexpected", "symlink", "nonregular"]
)
def test_candidate_source_mutations_fail(candidate, mutation):
    snapshot, _ = candidate
    target = snapshot.root / "src/giclab/harness/sira_gate_a_runtime.py"
    target.chmod(0o600)
    if mutation in {"one-byte", "same-size"}:
        value = target.read_bytes()
        target.write_bytes(
            bytes([value[0] ^ 1]) + value[1:] if mutation == "one-byte" else b"x" * len(value)
        )
    elif mutation == "missing":
        target.unlink()
    elif mutation == "unexpected":
        (snapshot.root / "unexpected.py").write_text("raise AssertionError\n")
    elif mutation == "symlink":
        target.unlink()
        target.symlink_to(ROOT / "src/giclab/harness/sira_gate_a_runtime.py")
    else:
        target.unlink()
        os.mkfifo(target)
    with pytest.raises((CandidateInputError, OSError)):
        snapshot.validate()


def test_normal_entry_rejects_candidate_before_effects(candidate, monkeypatch):
    snapshot, _ = candidate
    monkeypatch.setenv("GICLAB_TEST_FIXTURE", str(snapshot.root))
    with pytest.raises(CandidateInputError, match="historical/live"):
        reject_candidate_source(snapshot.root)
    reject_candidate_source(ROOT)


def test_candidate_evidence_schema_preserves_science_and_rejects_drift(candidate, tmp_path):
    from copy import deepcopy

    from jsonschema import Draft202012Validator

    from giclab.harness.t09_environment_fixture import build_environment_fixture

    snapshot, _ = candidate
    package = tmp_path / "schema-package"
    project_candidate_package(snapshot, package)
    environment = build_environment_fixture(snapshot, package, tmp_path / "schema-environment")
    original = json.loads((package / "schemas/t09-sira-pilot-evidence.schema.json").read_bytes())
    selected = environment.evidence_schema(snapshot, package, original)
    allowed = {
        "installed_package_manifest_sha256",
        "chromium_executable_sha256",
        "patched_upstream_runner_sha256",
    }
    restored = deepcopy(selected)
    for field in allowed:
        old = original["properties"]["runtime"]["properties"][field]
        new = selected["properties"]["runtime"]["properties"][field]
        assert old != new
        assert not list(Draft202012Validator(new).iter_errors(new["const"]))
        assert list(Draft202012Validator(old).iter_errors(new["const"]))
        assert list(Draft202012Validator(new).iter_errors("0" * 64))
        restored["properties"]["runtime"]["properties"][field] = old
    assert restored == original
    altered = deepcopy(original)
    altered["properties"]["runtime"]["properties"]["model_revision"] = {"const": "altered"}
    with pytest.raises(CandidateInputError, match="schema source differs"):
        environment.evidence_schema(snapshot, package, altered)
    # A rehashed/rebound expected value is deliberately not generated after drift.
    member = environment.root / "image-files/opt/giclab/installed-packages.txt"
    member.chmod(0o600)
    content = member.read_bytes()
    member.write_bytes(bytes([content[0] ^ 1]) + content[1:])
    with pytest.raises(CandidateInputError, match="input drifted"):
        environment.evidence_schema(snapshot, package, original)


def test_normal_local_qualifier_rejects_candidate_before_runtime_access(
    candidate, tmp_path, monkeypatch
):
    snapshot, _ = candidate
    package = tmp_path / "qualifier-package"
    project_candidate_package(snapshot, package)
    source = package / "containers/sira-smoke/pragmatic/t09_local_finalizer_qualification.py"
    specification = importlib.util.spec_from_file_location("candidate_normal_qualifier", source)
    assert specification and specification.loader
    qualifier = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(qualifier)
    accesses = []

    def forbidden_interpreter(path):
        accesses.append("interpreter")
        raise RuntimeError("test blocked runtime access")

    monkeypatch.setattr(qualifier, "_interpreter_launcher_identity", forbidden_interpreter)
    args = SimpleNamespace(
        repository=package,
        provider_contract="V16",
        plan_id=None,
        interpreter=tmp_path / "unopened-runtime",
    )
    from giclab.harness.t09_provider_contracts import V16_PROVIDER_CONTRACT

    args.provider_contract = V16_PROVIDER_CONTRACT.version
    try:
        qualifier.qualify(args)
    except (CandidateInputError, RuntimeError):
        pass
    else:
        pytest.fail("normal local qualifier accepted candidate inputs")
    assert accesses == [], "normal candidate rejection occurred after runtime access"


@pytest.mark.parametrize(
    "exercise_preparation",
    [
        False,
        True,
        "transaction",
        "condition-failure-export",
        "condition-failure-cleanup-admission-disconnect",
        "condition-failure-cleanup-descendant-interruption",
        "transaction-no-answer",
        "transaction-attach-output-denial",
        "transaction-export-output-denial",
        "provider-entry-pre-transfer-failure",
        "qualification-start-failure",
        "preflight-start-failure",
        "local-qualification",
        "package-current-commit",
    ],
    ids=[
        "package",
        "preparation",
        "transaction",
        "condition-failure-export",
        "condition-failure-cleanup-admission-disconnect",
        "condition-failure-cleanup-descendant-interruption",
        "transaction-no-answer",
        "transaction-attach-output-denial",
        "transaction-export-output-denial",
        "provider-entry-pre-transfer-failure",
        "qualification-start-failure",
        "preflight-start-failure",
        "local-qualification",
        "package-current-commit",
    ],
)
def test_candidate_actual_package_verifier_in_isolated_source_process(
    candidate, tmp_path, exercise_preparation
):
    snapshot, _ = candidate
    local_qualification = exercise_preparation == "local-qualification"
    current_commit = exercise_preparation == "package-current-commit"
    if local_qualification or current_commit:
        exercise_preparation = False
    document = snapshot.document()
    bootstrap = snapshot.root / "tests/control/candidate_bootstrap.py"
    request = {
        "snapshot": str(snapshot.root.parent),
        "package": str(tmp_path / "package"),
        "parent_repository": str(ROOT),
        "binding_sha256": snapshot.digest,
        "parent_head": document["parent_head"],
        "parent_tree": document["parent_tree"],
        "exercise_preparation": bool(exercise_preparation),
        "exercise_local_qualification": local_qualification,
        "exercise_current_commit": current_commit,
        "exercise_transaction": exercise_preparation
        if isinstance(exercise_preparation, str)
        else False,
    }
    result = subprocess.run(
        [sys.executable, "-B", str(bootstrap)],
        input=json.dumps(request),
        text=True,
        capture_output=True,
        # Whole-transaction watchdog includes all retained phase subprocesses
        # and cleanup. Individual phase/transport deadlines remain unchanged.
        timeout=900
        if exercise_preparation
        in {
            "transaction",
            "condition-failure-export",
            "condition-failure-cleanup-admission-disconnect",
            "condition-failure-cleanup-descendant-interruption",
            "transaction-no-answer",
            "transaction-attach-output-denial",
            "transaction-export-output-denial",
        }
        else 90,
        check=False,
        cwd=snapshot.root,
        env={
            "PATH": os.defpath,
            "PYTHONPATH": str(snapshot.root / "src"),
            "PYTHONDONTWRITEBYTECODE": "1",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": "/dev/null",
        },
    )
    assert result.returncode == 0, result.stderr
    receipt = json.loads(result.stdout)
    if exercise_preparation in {"transaction", "condition-failure-export"}:
        (tmp_path / "candidate-verifier-receipt.json").write_text(result.stdout)
    if current_commit:
        assert receipt["current_commit_checks"] == ["exact-candidate", "wrong-current-rejected"]
    if local_qualification:
        local = receipt["local_qualification"]
        assert local["offline_candidate_inputs"]["candidate_binding_sha256"] == snapshot.digest
        assert (
            local["offline_candidate_inputs"]["qualification_fixture"]
            == document["qualification_fixture"]
        )
        assert local["offline_candidate_inputs"]["historical_replay"] is False
        assert local["offline_candidate_inputs"]["live_qualification"] is False
        assert local["dataset_sha256"] == (
            "5beff220f4d68bcf78d7a9767b5eb09b36e56944a563a8807220168c56f0eea9"
        )
        assert local["model_requests"] == local["browser_actions"] == 0
        assert local["interpreter_dependency_tree"]["entry_count"] > 0
        assert local["dependency_tree"]["entry_count"] > 0
    assert receipt["forbidden_effects"] == []
    assert len(receipt["conditions"]) == 4
    assert "src/giclab/harness/t09_sira_pilot.py" in receipt["imported_sources"]
    assert receipt["marker"]["candidate_binding_sha256"] == snapshot.digest
    assert (
        receipt["archive_staging"]["sha256"]
        == "284c3c37b9be5c9cead25499252c8aeec908157da6a99d1d79cc312b83d20acb"
    )
    assert receipt["archive_regression"]["semantic_projection"]["score"] == 0.0
    assert receipt["archive_regression"]["historical_replay"] is False
    assert receipt["normal_entry_rejections"] == ["verify_package", "retained_cli"] + (
        ["candidate-live-authority-context"] if exercise_preparation else []
    )
    assert set(receipt["downstream_source_bindings"]) == {
        "selector",
        "finalizer",
        "finalizer-projection",
        "refinalization-schema",
    }
    for member in receipt["downstream_source_bindings"].values():
        assert member["candidate_binding_sha256"] == snapshot.digest
        assert member["git_blob"] is None
    if exercise_preparation:
        from giclab.harness.t09_provider_contracts import PROVIDER_CONTRACTS

        preparation = receipt["preparation"]
        assert preparation["candidate_binding_sha256"] == snapshot.digest
        assert preparation["registry_contract_count"] == len(PROVIDER_CONTRACTS)
        transaction = preparation["joined_transaction"]
        if exercise_preparation is True:
            assert transaction == "not-run"
        elif exercise_preparation == "condition-failure-export":
            assert transaction["terminal_state"] == "category3-shadow-stopped-cleanup-verified"
            assert transaction["earliest_stopping_phase"] == "condition-execution"
            assert len(transaction["condition_identities_consumed"]) == 1
            failure = preparation["retained_failure_projection"]
            assert failure["answer"] == "No relevant answer."
            assert failure["process_exit_code"] != 0
            assert failure["unscored"] is True and failure["export_complete"] is True
            assert failure["candidate_binding_sha256"] == snapshot.digest
            assert len(failure["call_ids"]) == len(set(failure["call_ids"])) == 2
            assert failure["call_ids"] == failure["logical_call_ids"]
            assert failure["source_authority"] == "immutable-raw-attempt"
            assert all(item["returncode"] == 0 for item in preparation["retained_phase_events"])
        elif exercise_preparation in {
            "condition-failure-cleanup-admission-disconnect",
            "condition-failure-cleanup-descendant-interruption",
        }:
            assert transaction["terminal_state"] == "category3-shadow-stopped-cleanup-unresolved"
            assert len(transaction["condition_identities_consumed"]) == 1
            assert preparation["retained_provider_closeouts"] == []
        elif exercise_preparation == "transaction-export-output-denial":
            assert transaction["terminal_state"] == "category3-shadow-stopped-cleanup-unresolved"
            assert transaction["earliest_stopping_phase"] == "condition-execution"
            assert len(transaction["condition_identities_consumed"]) == 1
            export_events = [
                item
                for item in preparation["retained_phase_events"]
                if item["phase"] == "retained-attempt-export"
            ]
            assert len(export_events) == 1 and export_events[0]["returncode"] != 0
        elif exercise_preparation == "transaction-attach-output-denial":
            assert transaction["terminal_state"] == "category3-shadow-stopped-cleanup-verified"
            assert transaction["earliest_stopping_phase"] == "condition-execution"
            assert len(transaction["condition_identities_consumed"]) == 1
        elif exercise_preparation == "transaction-no-answer":
            assert transaction["terminal_state"] == "category3-shadow-stopped-cleanup-verified"
            assert len(transaction["condition_identities_consumed"]) == 2
            assert transaction["earliest_stopping_phase"] == "first-pair-checkpoint"
            assert all(item["returncode"] == 0 for item in preparation["retained_phase_events"])
        elif exercise_preparation == "provider-entry-pre-transfer-failure":
            assert transaction["terminal_state"] == "category3-shadow-stopped-cleanup-verified"
            assert transaction["condition_identities_consumed"] == []
            assert preparation["retained_phase_events"] == []
            assert len(preparation["retained_provider_closeouts"]) == 1
        elif exercise_preparation in {"qualification-start-failure", "preflight-start-failure"}:
            assert transaction["terminal_state"] == "category3-shadow-stopped-cleanup-verified"
            assert transaction["earliest_stopping_phase"] == (
                "host-preflight"
                if exercise_preparation == "preflight-start-failure"
                else "image-finalizer-qualification"
            )
            assert transaction["condition_identities_consumed"] == []
            assert [item["phase"] for item in preparation["retained_phase_events"]] == [
                "host-transfer-verify",
                "host-preflight",
                "host-cleanup",
            ]
            assert [item["returncode"] for item in preparation["retained_phase_events"]] == (
                [0, 1, 0] if exercise_preparation == "preflight-start-failure" else [0, 0, 0]
            )
            assert len(preparation["retained_provider_closeouts"]) == 1
        else:
            assert transaction["terminal_state"] == "category3-shadow-complete-clean"
            assert len(transaction["condition_identities_consumed"]) == 4
        assert preparation["controller_local_assembly"]["candidate_source_binding_sha256"] == (
            snapshot.digest
        )
        assert set(preparation["lint_files_scanned"]) == {
            path.relative_to(ROOT).as_posix()
            for base in ("src/giclab", "containers/sira-smoke/pragmatic")
            for path in (ROOT / base).rglob("*.py")
        } | {"Makefile", ".github/workflows/ci.yml"}
    snapshot.validate()


@pytest.mark.parametrize(
    "mutation",
    ["ancestor", "tree", "delta", "fixture-id", "archive-sha", "source-map", "policy-digest"],
)
def test_rehashed_candidate_binding_mutations_still_fail(candidate, mutation):
    snapshot, _ = candidate
    document = snapshot.document()
    original_head, original_tree = document["parent_head"], document["parent_tree"]
    if mutation == "ancestor":
        document["parent_head"] = "0" * 40
    elif mutation == "tree":
        document["parent_tree"] = "0" * 40
    elif mutation == "delta":
        document["dirty_delta"] = []
        document["dirty_delta_sha256"] = sha(canonical([]))
    elif mutation == "fixture-id":
        document["qualification_fixture"]["fixture_id"] = "WRONG-FIXTURE"
    elif mutation == "archive-sha":
        document["qualification_fixture"]["archive_sha256"] = "0" * 64
    elif mutation == "source-map":
        document["source_members"][0]["runtime_paths"] = ["/wrong-mount"]
        document["source_member_manifest_sha256"] = sha(canonical(document["source_members"]))
    else:
        document["scientific_policy_sha256"] = "0" * 64
    value = canonical(document)
    metadata = snapshot.root.parent / "binding.json"
    metadata.chmod(0o600)
    metadata.write_bytes(value)
    marker = snapshot.root / MARKER
    marker.chmod(0o600)
    marker.write_bytes(
        canonical(
            {"candidate_binding_sha256": sha(value), "classification": document["classification"]}
        )
    )
    with pytest.raises(CandidateInputError):
        load_candidate_source_snapshot(
            snapshot.root.parent,
            expected_binding_sha256=sha(value),
            parent_repository=ROOT,
            expected_parent_head=original_head,
            expected_parent_tree=original_tree,
        )


@pytest.mark.parametrize("path", ["../outside", "/absolute", "a/../b", "a//b", "./file"])
def test_candidate_path_escape_is_rejected(tmp_path, path):
    with pytest.raises(CandidateInputError, match="path is unsafe"):
        read_member(tmp_path, path)


def test_candidate_duplicate_json_key_is_rejected():
    with pytest.raises(CandidateInputError, match="duplicate"):
        decode(b'{"fixture_id":"a","fixture_id":"b"}\n')


def test_candidate_replacement_during_read_fails(tmp_path, monkeypatch):
    target = tmp_path / "source.py"
    target.write_bytes(b"original")
    original_read = os.read
    changed = False

    def replace_while_reading(fd, count):
        nonlocal changed
        value = original_read(fd, count)
        if not changed:
            changed = True
            replacement = tmp_path / "replacement"
            replacement.write_bytes(b"replaced")
            replacement.replace(target)
        return value

    monkeypatch.setattr(os, "read", replace_while_reading)
    with pytest.raises(CandidateInputError, match="replaced during read"):
        read_member(tmp_path, "source.py")


def test_same_byte_source_root_replacement_is_rejected(candidate):
    snapshot, _ = candidate
    retained = snapshot.root.with_name("retained-source")
    snapshot.root.rename(retained)
    shutil.copytree(retained, snapshot.root)
    with pytest.raises(CandidateInputError, match="source root was replaced"):
        snapshot.validate()


def test_parent_directory_replacement_during_read_is_rejected(tmp_path, monkeypatch):
    parent = tmp_path / "parent"
    parent.mkdir()
    (parent / "source.py").write_bytes(b"original")
    original_read = os.read
    replaced = False

    def replace_directory(fd, count):
        nonlocal replaced
        value = original_read(fd, count)
        if not replaced:
            replaced = True
            retained = tmp_path / "retained"
            parent.rename(retained)
            shutil.copytree(retained, parent)
        return value

    monkeypatch.setattr(os, "read", replace_directory)
    with pytest.raises(CandidateInputError, match="directory replaced during read"):
        read_member(tmp_path, "parent/source.py")


@pytest.mark.parametrize("member", [RUNTIME_PATH, EXECUTION_PATH, COMMAND_PATH])
def test_rehashed_derived_scientific_change_is_rejected(candidate, tmp_path, member):
    snapshot, _ = candidate
    package = tmp_path / "projection"
    marker = project_candidate_package(snapshot, package)
    value = json.loads((package / member).read_bytes())
    # An attacker may update an outer checksum. The independent template
    # equality check must still reject an added/changed scientific policy.
    value["unauthorized_scientific_policy"] = {"condition_retries": 1}
    encoded = canonical(value)
    (package / member).write_bytes(encoded)
    for derived in marker["derived_inputs"]:
        if derived["path"] == member:
            derived["bytes"] = len(encoded)
            derived["sha256"] = sha(encoded)
            # Even a fully rehashed outer identity and field-difference index
            # cannot approve policy changes against the immutable template.
            derived["field_differences"] = [
                {
                    "path": "",
                    "template": json.loads((snapshot.root / member).read_bytes()),
                    "candidate": value,
                }
            ]
    (package / MARKER).write_bytes(canonical(marker))
    with pytest.raises(CandidateInputError, match="projection differs"):
        validate_candidate_package(snapshot, package)


def test_stale_argv_hash_is_rejected(candidate, tmp_path):
    snapshot, _ = candidate
    package = tmp_path / "projection"
    project_candidate_package(snapshot, package)
    value = json.loads((package / COMMAND_PATH).read_bytes())
    value["manifests"][0]["argv_sha256"] = "0" * 64
    (package / COMMAND_PATH).write_bytes(canonical(value))
    with pytest.raises(CandidateInputError, match="derived input bytes"):
        validate_candidate_package(snapshot, package)


def test_package_cannot_switch_candidate_snapshot(candidate, tmp_path):
    snapshot, archive = candidate
    package = tmp_path / "projection"
    project_candidate_package(snapshot, package)
    second = build_candidate_source_snapshot(
        ROOT,
        tmp_path / "second",
        parent_head=snapshot.document()["parent_head"],
        parent_tree=snapshot.document()["parent_tree"],
        qualification_document=archive.document(),
    )
    # Equivalent snapshots have the same identity and are interchangeable.
    assert second.digest == snapshot.digest
    marker = decode((package / MARKER).read_bytes())
    marker["candidate_binding_sha256"] = "0" * 64
    (package / MARKER).write_bytes(canonical(marker))
    with pytest.raises(CandidateInputError, match="switched source snapshot"):
        validate_candidate_package(second, package)


def _image_fixture_setup(candidate, tmp_path):
    from giclab.harness.t09_environment_fixture import build_environment_fixture

    snapshot, _ = candidate
    package = tmp_path / "image-package"
    project_candidate_package(snapshot, package)
    environment = build_environment_fixture(snapshot, package, tmp_path / "image-environment")
    prior_bytecode = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec = importlib.util.spec_from_file_location(
            "candidate_image_host", package / "containers/sira-smoke/pragmatic/t09_remote_runner.py"
        )
        host = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = host
        spec.loader.exec_module(host)
        spec = importlib.util.spec_from_file_location(
            "candidate_image_channel", snapshot.root / "tests/control/retained_candidate_effects.py"
        )
        channel_module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = channel_module
        spec.loader.exec_module(channel_module)
    finally:
        sys.dont_write_bytecode = prior_bytecode
    return snapshot, package, environment, host, channel_module.ImageCommandChannel


def test_candidate_carrier_consumes_durable_credential_target(candidate, tmp_path):
    from giclab.harness.t09_cleanup_state import EarlyCleanupJournal, EarlyCleanupStateError

    _image_fixture_setup(candidate, tmp_path)
    module = sys.modules["candidate_image_channel"]
    effects = object.__new__(module.RetainedCandidateEffects)
    effects._root = tmp_path / "transaction"
    effects._root.mkdir(mode=0o700)
    campaign = effects._root / "campaign"
    campaign.mkdir(mode=0o700)
    locator = effects._root / "remote" / "test-model-secret"
    journal = EarlyCleanupJournal.initialize(
        campaign / "preflight-cleanup-state",
        plan_id="PLAN-EXP0001-PILOT-V16",
        host_run_id="RUN-T09-PILOT-HOST-AUTONOMOUS-0009",
        package_commit="a" * 40,
        plan_sha256="b" * 64,
        provider_instance_id="fixture-owned-instance",
        provider_instance_identity_sha256="c" * 64,
        provider_started_at_epoch=999.0,
        launch_slot=1,
        replacement_eligibility_sha256=None,
        firewall_baseline_identity_sha256="d" * 64,
        temporary_remote_secret_locator=str(locator),
        clock=lambda: 1000.0,
    )
    entry = campaign / "entry-source" / "provider-entry.json"
    original = journal.latest_version_sha256()
    assert effects._credential_target(entry) == locator
    assert journal.latest_version_sha256() == original
    target = next(t for t in journal.load().targets if t.target_id == "temporary-remote-secret")
    with pytest.raises(EarlyCleanupStateError, match="rebound"):
        journal.register_target(
            target_id=target.target_id,
            kind=target.kind,
            locator=str(effects._root / "other"),
            ownership_sha256=target.ownership_sha256,
            public_alias=target.public_alias,
        )
    # The carrier cannot turn that authority into a write outside its transaction.
    locator.parent.symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(RuntimeError, match="outside its ownership"):
        effects._credential_target(entry)


def test_environment_inputs_deterministic_and_exact(candidate, tmp_path):
    from giclab.harness.t09_environment_fixture import (
        build_environment_fixture,
        load_environment_fixture,
    )

    snapshot, package, first, _, _ = _image_fixture_setup(candidate, tmp_path)
    second = build_environment_fixture(snapshot, package, tmp_path / "second-environment")
    assert first.binding_bytes == second.binding_bytes
    assert first.archive_path.read_bytes() == second.archive_path.read_bytes()
    assert first.document()["archive"]["bytes"] < 1_048_576
    assert first.document()["archive"]["sha256"] != first.image_id.removeprefix("sha256:")
    assert first.document()["qualification_fixture"]["archive_sha256"] == (
        "284c3c37b9be5c9cead25499252c8aeec908157da6a99d1d79cc312b83d20acb"
    )
    loaded = load_environment_fixture(
        first.root, expected_sha256=first.digest, source=snapshot, package=package
    )
    assert loaded.digest == first.digest
    assert first.document()["live_qualification"] is False
    assert first.document()["simulated_daemon_identity"]["observed_real_docker_image"] is False


def test_offline_freeze_inputs_reject_missing_or_mixed_selection(candidate, tmp_path):
    from dataclasses import replace

    snapshot, package, environment, host, _ = _image_fixture_setup(candidate, tmp_path)
    fixture = candidate[1]
    selected = host._offline_freeze_inputs(
        package, source_inputs=snapshot, environment_binding=environment, fixture_binding=fixture
    )
    assert selected["candidate_binding_sha256"] == snapshot.digest
    assert selected["environment_binding_sha256"] == environment.digest
    assert selected["qualification_fixture"] == fixture.document()
    assert selected["historical_replay"] is selected["live_qualification"] is False
    for sources, bound_environment, archive in (
        (None, environment, fixture),
        (snapshot, None, fixture),
        (snapshot, environment, None),
        (None, None, None),
    ):
        with pytest.raises((CandidateInputError, host.T09HostError)):
            host._offline_freeze_inputs(
                package,
                source_inputs=sources,
                environment_binding=bound_environment,
                fixture_binding=archive,
            )
    changed = environment.document()
    changed["candidate_binding_sha256"] = "f" * 64
    with pytest.raises(CandidateInputError):
        host._offline_freeze_inputs(
            package,
            source_inputs=snapshot,
            environment_binding=replace(environment, binding_bytes=canonical(changed)),
            fixture_binding=fixture,
        )


def test_retained_sealing_probe_does_not_publish_container_mutation_authority(
    candidate, tmp_path, monkeypatch
):
    from giclab.harness.t09_provider_contracts import V16_PROVIDER_CONTRACT

    snapshot, package, _environment, host, _ = _image_fixture_setup(candidate, tmp_path)
    contract = V16_PROVIDER_CONTRACT
    root = tmp_path / "sealing-transaction"
    root.mkdir(mode=0o700)
    commands = []

    def run(argv, **kwargs):
        commands.append(argv)
        if argv == ["docker", "info"] and kwargs.get("timeout") == 30:
            return subprocess.CompletedProcess(argv, 0, stdout=b"", stderr=b"")
        raise AssertionError("sealing probe denied an unbound environmental command")

    def denied(*args, **kwargs):
        raise AssertionError("sealing probe denied real subprocess creation")

    monkeypatch.setattr(subprocess, "run", run)
    monkeypatch.setattr(subprocess, "Popen", denied)
    result = host.sealing_primitives_preflight(
        probe_root=host.allocate_sealing_probe_root(root),
        repository=package,
        artifact_root=root,
        command_document=json.loads((package / COMMAND_PATH).read_bytes()),
        package_commit=snapshot.document()["parent_head"],
        execution_contract_sha256=sha((package / EXECUTION_PATH).read_bytes()),
        provider_contract=contract,
        expected_run_ids=contract.run_ids,
    )
    assert result["raw_reconstruction_passed"] is result["essential_reconstruction_passed"] is True
    try:
        intents = host.owned_container_intents(root, repository=package, contract=contract)
    except host.T09HostError as exc:
        pytest.fail(f"retained sealing fixture polluted the real container intent ledger: {exc}")
    assert intents == {}, "a no-container qualification probe must not mint mutation authority"
    assert result["evidence_role"] == "qualification-sealing-probe"
    assert result["mutation_authority"] is False
    probe_parent = root / "qualification-probe-evidence"
    first_probe = next(probe_parent.iterdir())
    host.publish_sealing_probe_selection(
        artifact_root=root, probe_root=first_probe, receipt=result, contract=contract
    )
    selected = root / contract.control_root_name / "sealing-primitives-preflight/receipt.json"
    assert json.loads(selected.read_bytes()) == result
    assert host.owned_container_intents(root, repository=package, contract=contract) == {}
    original = {
        p.relative_to(first_probe): p.read_bytes() for p in first_probe.rglob("*") if p.is_file()
    }
    second = host.allocate_sealing_probe_root(root)
    host.sealing_primitives_preflight(
        probe_root=second,
        repository=package,
        artifact_root=root,
        command_document=json.loads((package / COMMAND_PATH).read_bytes()),
        package_commit=snapshot.document()["parent_head"],
        execution_contract_sha256=sha((package / EXECUTION_PATH).read_bytes()),
        provider_contract=contract,
        expected_run_ids=contract.run_ids,
    )
    assert second != first_probe
    assert json.loads(selected.read_bytes()) == result
    assert host.owned_container_intents(root, repository=package, contract=contract) == {}
    assert original == {
        p.relative_to(first_probe): p.read_bytes() for p in first_probe.rglob("*") if p.is_file()
    }
    # Copying a probe into the authority namespace does not promote its role.
    forged = host._pilot_root(root, contract) / "forged-container-command.json"
    forged.parent.mkdir(parents=True, exist_ok=True)
    forged.write_bytes(next(first_probe.rglob("container-command.json")).read_bytes())
    with pytest.raises(host.T09HostError, match="malformed"):
        host.owned_container_intents(root, repository=package, contract=contract)
    assert forged.exists(), "fail-closed inspection must preserve malformed evidence"
    assert 0 < len(commands) <= 16
    assert all(command == ["docker", "info"] for command in commands)


@pytest.mark.parametrize("failure", [RuntimeError, KeyboardInterrupt])
def test_sealing_probe_failure_preserves_separate_evidence(
    candidate, tmp_path, monkeypatch, failure
):
    from giclab.harness.t09_provider_contracts import V16_PROVIDER_CONTRACT as contract

    snapshot, package, _environment, host, _ = _image_fixture_setup(candidate, tmp_path)
    root = tmp_path / "interrupted-sealing"
    root.mkdir(mode=0o700)
    unrelated = root / "unrelated-evidence"
    unrelated.write_bytes(b"unchanged")
    probe = host.allocate_sealing_probe_root(root)

    def stop(**kwargs):
        raise failure("injected-seal-interruption")

    monkeypatch.setattr(host, "seal_raw_attempt", stop)
    with pytest.raises(failure, match="injected-seal-interruption"):
        host.sealing_primitives_preflight(
            probe_root=probe,
            repository=package,
            artifact_root=root,
            command_document=json.loads((package / COMMAND_PATH).read_bytes()),
            package_commit=snapshot.document()["parent_head"],
            execution_contract_sha256=sha((package / EXECUTION_PATH).read_bytes()),
            provider_contract=contract,
            expected_run_ids=contract.run_ids,
        )
    assert list(probe.rglob("container-command.json")), "partial probe evidence must remain"
    assert host.owned_container_intents(root, repository=package, contract=contract) == {}
    assert unrelated.read_bytes() == b"unchanged"
    with pytest.raises(host.T09HostError, match="fresh"):
        host.sealing_primitives_preflight(
            probe_root=probe,
            repository=package,
            artifact_root=root,
            command_document={},
            package_commit=snapshot.document()["parent_head"],
            execution_contract_sha256="f" * 64,
            provider_contract=contract,
            expected_run_ids=contract.run_ids,
        )


@pytest.mark.parametrize(
    "probe,fault",
    [
        ("core", None),
        ("core", "core-limit"),
        ("browser", None),
        ("browser", "browser-version"),
    ],
)
def test_retained_process_qualification_uses_bound_observations(
    candidate, tmp_path, monkeypatch, probe, fault
):
    from giclab.harness.t09_cleanup_state import EarlyCleanupJournal
    from giclab.harness.t09_provider_contracts import V16_PROVIDER_CONTRACT

    snapshot, package, environment, host, channel_type = _image_fixture_setup(candidate, tmp_path)
    contract = V16_PROVIDER_CONTRACT
    root = tmp_path / "process-qualification"
    root.mkdir(mode=0o700)
    host.initialize_state(
        root,
        sha((package / EXECUTION_PATH).read_bytes()),
        contract=contract,
        lambda_started_at_epoch=999.0,
    )
    journal = EarlyCleanupJournal.initialize(
        root / "preflight-cleanup-state",
        plan_id=contract.plan_id,
        host_run_id=contract.host_run_id,
        package_commit=snapshot.document()["parent_head"],
        plan_sha256="b" * 64,
        provider_instance_id="offline-fixture-instance",
        provider_instance_identity_sha256="c" * 64,
        provider_started_at_epoch=999.0,
        launch_slot=1,
        replacement_eligibility_sha256=None,
        firewall_baseline_identity_sha256="d" * 64,
        clock=lambda: 1000.0,
    )
    channel = channel_type(
        environment,
        tag=contract.replacement_image_tag,
        transaction_root=tmp_path,
        package=package,
        source_inputs=snapshot,
        contract=contract,
        fault=fault,
    )
    # Component prerequisite only. The joined channel reaches this state by load.
    channel.loaded, channel.load_count = True, 1
    native_run = subprocess.run

    def run(argv, **kwargs):
        if argv[:1] == ["docker"]:
            return channel.run(argv, **kwargs)
        if argv[:3] == ["git", "-C", str(ROOT)] and argv[3] in {"show", "rev-parse", "merge-base"}:
            return native_run(argv, **kwargs)
        raise AssertionError("process qualification attempted real environmental operation")

    monkeypatch.setattr(subprocess, "run", run)
    monkeypatch.setattr(sys, "dont_write_bytecode", True)
    invoke = (
        host.core_suppression_preflight if probe == "core" else host.browser_lifecycle_preflight
    )
    kwargs = dict(
        repository=package,
        artifact_root=root,
        prefix=["docker"],
        image_id=environment.image_id,
        cleanup_journal=journal,
        contract=contract,
        source_inputs=snapshot,
        environment_binding=environment,
    )
    if fault:
        with pytest.raises(host.T09HostError):
            invoke(**kwargs)
    else:
        receipt = invoke(**kwargs)
        assert receipt["offline_environment_sha256"] == environment.digest
        assert receipt["classification"] == "synthetic-environment-orchestration-only"
        assert receipt["container_removed"] is True
        assert (
            receipt[
                "real_kernel_qualification" if probe == "core" else "real_browser_qualification"
            ]
            is False
        )
        assert any(
            event[0] == ("retained-core-suite" if probe == "core" else "retained-browser-probe")
            for event in channel.events
        )
        cleanup_inputs = dict(
            artifact_root=root,
            repository=package,
            contract=contract,
            source_inputs=snapshot,
            environment_binding=environment,
        )
        assert host._prior_typed_core_incidents(**cleanup_inputs) == (False, False)
        with pytest.raises(host.T09HostError, match="explicit candidate"):
            host._prior_typed_core_incidents(**{**cleanup_inputs, "source_inputs": None})
        # The historical consumer must not reinterpret fixture filesystem roots.
        assert host._prior_typed_core_incidents(
            artifact_root=root, repository=package, contract=contract
        ) == (True, True)
        scan = (
            root
            / contract.control_root_name
            / (
                "core-suppression-preflight/core-suppression-writable-root-core-scan.json"
                if probe == "core"
                else "browser-preflight/browser-writable-root-core-scan.json"
            )
        )
        value = json.loads(scan.read_bytes())
        value["scan_roots"][0] = "/wrong-bound-root"
        scan.write_bytes(canonical(value))
        assert host._prior_typed_core_incidents(**cleanup_inputs) == (True, True)
    assert channel.containers == {}
    assert sum(event[:3] == ["docker", "rm", "--force"] for event in channel.events) == 1


@pytest.mark.parametrize(
    "fault", [None, "load-error", "partial", "timeout", "missing", "wrong-image"]
)
def test_retained_image_materializer_with_explicit_environment(
    candidate, tmp_path, monkeypatch, fault
):
    snapshot, package, environment, host, channel_type = _image_fixture_setup(candidate, tmp_path)
    from giclab.harness.t09_provider_contracts import V16_PROVIDER_CONTRACT

    contract = V16_PROVIDER_CONTRACT
    root = tmp_path / "materialization"
    root.mkdir(mode=0o700)
    channel = channel_type(
        environment, tag=contract.replacement_image_tag, transaction_root=tmp_path, fault=fault
    )
    native_run = subprocess.run

    def run(argv, **kwargs):
        if argv[:1] == ["docker"]:
            return channel.run(argv, **kwargs)
        if argv[:3] == ["git", "-C", str(ROOT)] and argv[3] in {"show", "rev-parse", "merge-base"}:
            return native_run(argv, **kwargs)
        raise AssertionError("unmodeled environmental command attempted")

    monkeypatch.setattr(subprocess, "run", run)
    # Component-only clock budget. Joined phases retain actual lifecycle arithmetic.
    monkeypatch.setattr(host, "preflight_seconds_remaining", lambda _: 60.0)
    kwargs = dict(
        repository=package,
        package_commit=snapshot.document()["parent_head"],
        artifact_root=root,
        image_archive=environment.archive_path,
        prefix=["docker"],
        materialization_policy=host.SLOT1_IMAGE_MATERIALIZATION_POLICY,
        contract=contract,
        source_inputs=snapshot,
        environment_binding=environment,
    )
    if fault is None:
        receipt = host.materialize_retained_or_build_image(**kwargs)
        assert receipt["image_id"] == environment.image_id
        assert receipt["offline_environment_sha256"] == environment.digest
        assert (
            receipt["retained_image_archive_sha256"] == environment.document()["archive"]["sha256"]
        )
        assert receipt["build_count"] == 0
        assert channel.loaded and channel.tagged
        assert channel.load_count == 1
        assert channel.before_load == {environment.image_id, contract.replacement_image_tag}
    else:
        with pytest.raises(host.T09HostError):
            host.materialize_retained_or_build_image(**kwargs)
        assert channel.load_count == 1
        assert not (
            root / contract.control_root_name / "replacement-image-qualification/receipt.json"
        ).exists()
        assert not channel.loaded
        assert channel.removal_count == (0 if fault == "missing" else 1)
        evidence = (
            root
            / contract.control_root_name
            / "replacement-image-qualification/logs/docker-image-import.json"
        )
        assert evidence.is_file()
        if fault == "timeout":
            assert json.loads(evidence.read_bytes())["returncode"] == 124


@pytest.mark.parametrize(
    "mutation", ["same-size", "one-byte", "missing", "binding", "source", "historical-entry"]
)
def test_environment_drift_rejected_before_commands(candidate, tmp_path, monkeypatch, mutation):
    from dataclasses import replace

    from giclab.harness.t09_provider_contracts import V16_PROVIDER_CONTRACT

    snapshot, package, environment, host, _ = _image_fixture_setup(candidate, tmp_path)
    if mutation in {"same-size", "one-byte"}:
        data = environment.archive_path.read_bytes()
        environment.archive_path.chmod(0o600)
        environment.archive_path.write_bytes(
            b"x" * len(data) if mutation == "same-size" else bytes([data[0] ^ 1]) + data[1:]
        )
    elif mutation == "missing":
        environment.archive_path.unlink()
    elif mutation == "binding":
        document = environment.document()
        document["candidate_binding_sha256"] = "f" * 64
        environment = replace(environment, binding_bytes=canonical(document))
    elif mutation == "source":
        path = package / "src/giclab/harness/sira_gate_a_runtime.py"
        path.chmod(0o600)
        data = path.read_bytes()
        path.write_bytes(bytes([data[0] ^ 1]) + data[1:])
    native_run = subprocess.run
    commands = []

    def run(argv, **kwargs):
        if argv[:3] == ["git", "-C", str(ROOT)] and argv[3] in {"show", "rev-parse", "merge-base"}:
            return native_run(argv, **kwargs)
        commands.append(argv)
        raise AssertionError("image drift reached environmental command")

    monkeypatch.setattr(subprocess, "run", run)
    with pytest.raises((CandidateInputError, host.T09HostError, FileNotFoundError)):
        host.materialize_retained_or_build_image(
            repository=package,
            package_commit=snapshot.document()["parent_head"],
            artifact_root=tmp_path / "untouched",
            image_archive=environment.archive_path,
            prefix=["docker"],
            materialization_policy=host.SLOT1_IMAGE_MATERIALIZATION_POLICY,
            contract=V16_PROVIDER_CONTRACT,
            source_inputs=None if mutation == "historical-entry" else snapshot,
            environment_binding=environment,
        )
    assert commands == []
    assert not (tmp_path / "untouched").exists()


@pytest.mark.parametrize("wrong_uid", [False, True])
def test_retained_canary_runs_real_leaf_and_rejects_bad_uid(
    candidate, tmp_path, monkeypatch, wrong_uid
):
    from giclab.harness.t09_cleanup_state import EarlyCleanupJournal
    from giclab.harness.t09_provider_contracts import V16_PROVIDER_CONTRACT

    snapshot, package, environment, host, channel_type = _image_fixture_setup(candidate, tmp_path)
    contract = V16_PROVIDER_CONTRACT
    root = tmp_path / "canary-transaction"
    root.mkdir(mode=0o700)
    host.initialize_state(
        root,
        sha((package / EXECUTION_PATH).read_bytes()),
        contract=contract,
        lambda_started_at_epoch=999.0,
    )
    secret = root / "test-canary"
    secret.write_bytes(b"offline-test-canary-content-only")
    secret.chmod(0o600)
    journal = EarlyCleanupJournal.initialize(
        root / "preflight-cleanup-state",
        plan_id=contract.plan_id,
        host_run_id=contract.host_run_id,
        package_commit=snapshot.document()["parent_head"],
        plan_sha256="b" * 64,
        provider_instance_id="offline-fixture-instance",
        provider_instance_identity_sha256="c" * 64,
        provider_started_at_epoch=999.0,
        launch_slot=1,
        replacement_eligibility_sha256=None,
        firewall_baseline_identity_sha256="d" * 64,
        clock=lambda: 1000.0,
    )
    channel = channel_type(
        environment,
        tag=contract.replacement_image_tag,
        transaction_root=tmp_path,
        package=package,
        source_inputs=snapshot,
        contract=contract,
        fault="canary-uid" if wrong_uid else None,
    )
    # This canary component's prerequisite is the simulated image already loaded;
    # the joined channel gets this state only from actual retained materialization.
    channel.loaded = True
    channel.load_count = 1
    native_run = subprocess.run
    native_popen = subprocess.Popen

    def run(argv, **kwargs):
        if argv[:1] == ["docker"]:
            return channel.run(argv, **kwargs)
        return native_run(argv, **kwargs)

    def popen(argv, **kwargs):
        if argv[:1] == ["docker"]:
            return channel.popen(argv, **kwargs)
        if argv[:3] == ["git", "-C", str(ROOT)]:
            return native_popen(argv, **kwargs)
        raise AssertionError("canary attempted external operation")

    monkeypatch.setattr(subprocess, "run", run)
    monkeypatch.setattr(subprocess, "Popen", popen)
    monkeypatch.setattr(sys, "dont_write_bytecode", True)
    if wrong_uid:
        with pytest.raises(host.T09HostError, match="credential channel preflight failed"):
            receipt = host.secret_channel_preflight(
                repository=package,
                artifact_root=root,
                secret_file=secret,
                prefix=["docker"],
                image_id=environment.image_id,
                cleanup_journal=journal,
                contract=contract,
            )
        assert channel.containers == {}
        assert any(item[0] == "retained-secret-probe" for item in channel.events)
        return
    receipt = host.secret_channel_preflight(
        repository=package,
        artifact_root=root,
        secret_file=secret,
        prefix=["docker"],
        image_id=environment.image_id,
        cleanup_journal=journal,
        contract=contract,
    )
    assert receipt["secret_bytes_read"] == 0
    assert receipt["secret_value_or_hash_retained"] is False
    assert receipt["container_effective_uid"] == 1000
    assert channel.containers == {}
    assert any(item[0] == "retained-secret-probe" for item in channel.events)
    assert all(
        b"offline-test-canary-content-only" not in p.read_bytes() for p in root.rglob("*.json")
    )


def test_retained_overlay_derives_inventory_and_rejects_metadata_drift(
    candidate, tmp_path, monkeypatch
):
    from giclab.harness.t09_cleanup_state import EarlyCleanupJournal
    from giclab.harness.t09_provider_contracts import V16_PROVIDER_CONTRACT

    snapshot, package, environment, host, channel_type = _image_fixture_setup(candidate, tmp_path)
    contract = V16_PROVIDER_CONTRACT
    root = tmp_path / "overlay-transaction"
    root.mkdir(mode=0o700)
    host.initialize_state(
        root,
        sha((package / EXECUTION_PATH).read_bytes()),
        contract=contract,
        lambda_started_at_epoch=999.0,
    )
    journal = EarlyCleanupJournal.initialize(
        root / "preflight-cleanup-state",
        plan_id=contract.plan_id,
        host_run_id=contract.host_run_id,
        package_commit=snapshot.document()["parent_head"],
        plan_sha256="b" * 64,
        provider_instance_id="offline-fixture-instance",
        provider_instance_identity_sha256="c" * 64,
        provider_started_at_epoch=999.0,
        launch_slot=1,
        replacement_eligibility_sha256=None,
        firewall_baseline_identity_sha256="d" * 64,
        clock=lambda: 1000.0,
    )
    channel = channel_type(
        environment,
        tag=contract.replacement_image_tag,
        transaction_root=tmp_path,
        package=package,
        source_inputs=snapshot,
        contract=contract,
    )
    channel.loaded = True  # Component prerequisite, never a joined phase receipt.
    channel.load_count = 1
    native_run, native_popen = subprocess.run, subprocess.Popen

    def run(argv, **kwargs):
        return channel.run(argv, **kwargs) if argv[:1] == ["docker"] else native_run(argv, **kwargs)

    def popen(argv, **kwargs):
        if argv[:1] == ["docker"]:
            return channel.popen(argv, **kwargs)
        if argv[:3] == ["git", "-C", str(ROOT)]:
            return native_popen(argv, **kwargs)
        raise AssertionError("overlay attempted external operation")

    monkeypatch.setattr(subprocess, "run", run)
    monkeypatch.setattr(subprocess, "Popen", popen)
    monkeypatch.setattr(sys, "dont_write_bytecode", True)
    overlay = root / "evaluator-overlay"
    result = host.evaluator_overlay(
        repository=package,
        artifact_root=root,
        overlay=overlay,
        prefix=["docker"],
        image_id=environment.image_id,
        cleanup_journal=journal,
        contract=contract,
    )
    assert result["overlay_entry_count"] > 51
    assert result["overlay_total_regular_bytes"] == sum(
        m["bytes"] for m in environment.document()["overlay_input_members"]
    )
    frozen = {
        "evaluator_overlay_manifest_sha256": result["overlay_manifest_sha256"],
        "evaluator_overlay_entries_sha256": result["overlay_entries_sha256"],
        "evaluator_overlay_packages_sha256": result["overlay_package_manifest_sha256"],
    }
    args = dict(
        artifact_root=root,
        repository=package,
        overlay=overlay,
        prefix=["docker"],
        image_id=environment.image_id,
        frozen_manifest=frozen,
        verify_packages=True,
        cleanup_journal=journal,
        contract=contract,
    )
    verified = host.validate_evaluator_overlay_binding(**args)
    assert verified["packages_recomputed"] is True
    assert channel.containers == {}
    metadata = next(overlay.rglob("METADATA"))
    before = metadata.read_bytes()
    metadata.write_bytes(before.replace(b"Version: ", b"Version: 0", 1))
    with pytest.raises(host.T09HostError):
        host.validate_evaluator_overlay_binding(**args)


def test_retained_image_file_hashes_are_bound_actual_bytes(candidate, tmp_path, monkeypatch):
    from giclab.harness.t09_cleanup_state import EarlyCleanupJournal
    from giclab.harness.t09_provider_contracts import V16_PROVIDER_CONTRACT

    snapshot, package, environment, host, channel_type = _image_fixture_setup(candidate, tmp_path)
    contract = V16_PROVIDER_CONTRACT
    root = tmp_path / "image-file-transaction"
    root.mkdir(mode=0o700)
    host.initialize_state(
        root,
        sha((package / EXECUTION_PATH).read_bytes()),
        contract=contract,
        lambda_started_at_epoch=999.0,
    )
    journal = EarlyCleanupJournal.initialize(
        root / "preflight-cleanup-state",
        plan_id=contract.plan_id,
        host_run_id=contract.host_run_id,
        package_commit=snapshot.document()["parent_head"],
        plan_sha256="b" * 64,
        provider_instance_id="offline-fixture-instance",
        provider_instance_identity_sha256="c" * 64,
        provider_started_at_epoch=999.0,
        launch_slot=1,
        replacement_eligibility_sha256=None,
        firewall_baseline_identity_sha256="d" * 64,
        clock=lambda: 1000.0,
    )
    channel = channel_type(
        environment,
        tag=contract.replacement_image_tag,
        transaction_root=tmp_path,
        package=package,
        source_inputs=snapshot,
        contract=contract,
    )
    channel.loaded = True  # Component-only prerequisite; joined load remains real orchestration.
    channel.load_count = 1
    native_run, native_popen = subprocess.run, subprocess.Popen

    def run(argv, **kwargs):
        return channel.run(argv, **kwargs) if argv[:1] == ["docker"] else native_run(argv, **kwargs)

    def popen(argv, **kwargs):
        if argv[:1] == ["docker"]:
            return channel.popen(argv, **kwargs)
        if argv[:3] == ["git", "-C", str(ROOT)]:
            return native_popen(argv, **kwargs)
        raise AssertionError("file hash probe attempted external operation")

    monkeypatch.setattr(subprocess, "run", run)
    monkeypatch.setattr(subprocess, "Popen", popen)
    args = dict(
        artifact_root=root,
        prefix=["docker"],
        image_id=environment.image_id,
        cleanup_journal=journal,
        contract=contract,
        repository=package,
        source_inputs=snapshot,
        environment_binding=environment,
    )
    observed = host.final_image_file_hashes(**args)
    expected = {
        item["runtime_path"]: item["sha256"]
        for item in environment.document()["image_file_members"]
    }
    assert observed == expected
    runtime_path = "/opt/giclab-src/giclab/harness/sira_gate_a_runtime.py"
    assert observed[runtime_path] == sha(
        (package / "src/giclab/harness/sira_gate_a_runtime.py").read_bytes()
    )
    before = list(channel.events)
    member = environment.document()["image_file_members"][0]
    target = environment.root / member["path"]
    value = target.read_bytes()
    target.chmod(0o600)
    target.write_bytes(bytes([value[0] ^ 1]) + value[1:])
    with pytest.raises(CandidateInputError, match="image-file input drifted"):
        host.final_image_file_hashes(**args)
    assert channel.events == before


def test_deterministic_qualification_propagates_explicit_candidate_source(candidate, tmp_path):
    """Component caller must use the actual verifier with its explicit input binding."""
    from giclab.control.effects import (
        HostPhaseBinding,
        HostQualificationRequest,
        HostTransferBinding,
        ProviderHandle,
    )
    from giclab.control.shadow_effects import build_deterministic_effects
    from giclab.harness.t09_provider_contracts import V16_PROVIDER_CONTRACT as contract

    snapshot, _ = candidate
    package = tmp_path / "source-gate-package"
    project_candidate_package(snapshot, package)
    transaction = tmp_path / "component-transaction"
    transaction.mkdir(mode=0o700)
    effects = build_deterministic_effects(
        repository=package,
        contract=contract,
        transaction_root=transaction,
        source_inputs=snapshot,
    )
    document = snapshot.document()
    binding = HostPhaseBinding(
        HostTransferBinding(
            provider_contract_version=contract.version,
            plan_id=contract.plan_id,
            host_run_id=contract.host_run_id,
            provider_handle_identity="source-gate-component",
            provider_launch_ordinal=1,
            provider_entry_receipt_sha256="1" * 64,
            local_assembly_receipt_sha256="2" * 64,
            source_commit=document["parent_head"],
            source_tree=document["parent_tree"],
            remote_root="/offline/source-gate-component",
            candidate_source_binding_sha256=snapshot.digest,
        ),
        "3" * 64,
    )
    request = HostQualificationRequest(
        binding=binding,
        provider_handle=ProviderHandle("source-gate-component", 1),
        preflight_receipt_sha256="4" * 64,
        replacement_image_tag=contract.replacement_image_tag,
        image_materialization_policy=contract.image_materialization_policy,
        active_image_qualification_id=contract.active_image_qualification_id,
        local_finalizer_qualification_id=contract.local_finalizer_qualification_id,
        requested_wall_time=1000.0,
        requested_monotonic=1000.0,
    )
    try:
        receipt = effects.qualify_host(request)
    except Exception as error:
        pytest.fail(f"explicit candidate input lost at actual qualification consumer: {error}")
    assert receipt.binding == binding
    assert receipt.finalizer_selector_sha256 == sha(
        (package / "containers/sira-smoke/pragmatic/t09_remote_runner.py").read_bytes()
    )
    snapshot.validate()
    from dataclasses import replace

    from giclab.control.adapters import AdapterFailure

    switched = replace(
        request,
        binding=replace(
            binding, transfer=replace(binding.transfer, candidate_source_binding_sha256="9" * 64)
        ),
    )
    with pytest.raises(AdapterFailure, match="candidate source binding differs from transfer"):
        effects.qualify_host(switched)
    # Same-size alteration remains invalid at this caller; never rebind the digest.
    path = package / "containers/sira-smoke/pragmatic/t09_remote_runner.py"
    original = path.read_bytes()
    path.chmod(0o600)
    path.write_bytes(bytes([original[0] ^ 1]) + original[1:])
    with pytest.raises(CandidateInputError):
        effects.qualify_host(request)


@pytest.mark.parametrize(
    "role_name", ["SELECTOR", "FINALIZER", "FINALIZER_PROJECTION", "REFINALIZATION_SCHEMA"]
)
def test_downstream_correct_role_cap_still_rejects_before_git(tmp_path, monkeypatch, role_name):
    from giclab.control.production import _host_module

    host = _host_module(ROOT)
    role = getattr(host.DownstreamSourceRole, role_name)
    contract = host.DOWNSTREAM_SOURCE_CONTRACTS[role]
    path = tmp_path / contract.relative_path
    path.parent.mkdir(parents=True)
    path.write_bytes(b"x" * (contract.maximum_bytes + 1))
    calls = []

    def forbidden(*args, **kwargs):
        calls.append(args)
        raise AssertionError("over-limit source reached Git")

    monkeypatch.setattr(host, "_bounded_git_output", forbidden)
    with pytest.raises(host.T09HostError, match="metadata is unsafe"):
        host.validate_git_bound_downstream_source(
            repository=tmp_path,
            commit="a" * 40,
            role=role,
            relative=contract.relative_path,
            source=path,
        )
    assert calls == []


def test_downstream_wrong_role_remains_rejected():
    from giclab.control.production import _host_module

    host = _host_module(ROOT)
    with pytest.raises(host.T09HostError, match="role and path disagree"):
        host.validate_git_bound_downstream_source(
            repository=ROOT,
            commit="a" * 40,
            role=host.DownstreamSourceRole.FINALIZER,
            relative=host.SELECTOR_RELATIVE_PATH,
            source=ROOT / host.SELECTOR_RELATIVE_PATH,
        )


def test_downstream_historical_size_mismatch_reports_source_drift():
    from giclab.control.production import _host_module

    host = _host_module(ROOT)
    reviewed_head = "a98b4b875ab4d101709d62bc7222b5c90681a893"
    path = ROOT / host.SELECTOR_RELATIVE_PATH
    cap = host.DOWNSTREAM_SOURCE_CONTRACTS[host.DownstreamSourceRole.SELECTOR].maximum_bytes
    assert 1_163_386 < path.stat().st_size <= cap
    with pytest.raises(
        host.T09HostError, match="source size differs from its Git binding"
    ) as caught:
        host.validate_git_bound_downstream_source(
            repository=ROOT,
            commit=reviewed_head,
            role=host.DownstreamSourceRole.SELECTOR,
            relative=host.SELECTOR_RELATIVE_PATH,
            source=path,
        )
    assert f"expected=1163386, actual={path.stat().st_size}, cap=4194304" in str(caught.value)


@pytest.mark.parametrize("explicit_candidate", [False, True])
def test_finalizer_rejects_candidate_without_complete_offline_contract(
    candidate, tmp_path, explicit_candidate
):
    """The actual finalizer rejects selection before reading runtime/credentials."""
    from types import SimpleNamespace

    snapshot, _ = candidate
    package = tmp_path / "finalizer-package"
    project_candidate_package(snapshot, package)
    source = package / "containers/sira-smoke/pragmatic/t09_evaluate_attempt.py"
    specification = importlib.util.spec_from_file_location("candidate_finalizer_entry", source)
    assert specification and specification.loader
    finalizer = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(finalizer)
    # Omitted runtime fields cannot be touched before explicit selection fails.
    args = SimpleNamespace(score_schema=package / "schemas/t09-sira-pilot-score.schema.json")
    if explicit_candidate:
        with pytest.raises(finalizer.T09PilotError, match="input selection is incomplete"):
            finalizer.finalize(args, source_inputs=snapshot)
    else:
        with pytest.raises(CandidateInputError, match="historical/live"):
            finalizer.finalize(args)
