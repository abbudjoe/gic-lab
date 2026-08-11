from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "containers/sira-smoke/lambda/manual-console"
sys.dont_write_bytecode = True
sys.path.insert(0, str(BUNDLE))
import docker_inspector as inspector  # noqa: E402
import evidence_packager as packager  # noqa: E402
import host_facts as facts  # noqa: E402
import qualification_driver as driver  # noqa: E402


def _fresh_docker_config(root: Path, name: str) -> Path:
    path = root / name
    path.mkdir(mode=0o700)
    return path


class FakeDockerBudget:
    def __init__(
        self,
        *,
        fail_on_start: bool = False,
        interrupt_on_start: bool = False,
        cleanup_failure: bool = False,
        create_outcome_unknown: bool = False,
    ) -> None:
        self.fail_on_start = fail_on_start
        self.interrupt_on_start = interrupt_on_start
        self.cleanup_failure = cleanup_failure
        self.create_outcome_unknown = create_outcome_unknown
        self.removed = False
        self.calls: list[tuple[tuple[str, ...], bool]] = []

    def run(
        self,
        arguments: list[str],
        *,
        timeout_seconds: float,
        cleanup: bool = False,
        absolute_deadline_monotonic: float | None = None,
    ) -> bytes:
        del timeout_seconds, absolute_deadline_monotonic
        self.calls.append((tuple(arguments), cleanup))
        if cleanup and self.cleanup_failure:
            raise inspector.DockerInspectionError("synthetic cleanup failure")
        if arguments[1:2] == ["pull"]:
            return b""
        if arguments[1:3] == ["image", "inspect"]:
            return json.dumps(
                [
                    {
                        "Id": driver.CONFIG_DIGEST,
                        "RepoDigests": [driver.BUSYBOX],
                        "Os": "linux",
                        "Architecture": "amd64",
                    }
                ]
            ).encode()
        if arguments[1:2] == ["create"]:
            if self.create_outcome_unknown:
                raise inspector.DockerInspectionError("synthetic lost create response")
            return b"a" * 64 + b"\n"
        if arguments[1:2] == ["start"]:
            if self.interrupt_on_start:
                raise KeyboardInterrupt
            if self.fail_on_start:
                raise inspector.DockerInspectionError("synthetic start failure")
            return b""
        if arguments[1:2] == ["top"]:
            rows = [
                "100 0 100 S init",
                "101 100 101 S sh",
                "102 101 101 S sh",
                "103 102 101 S sleep",
            ]
            rows.extend(f"{pid} 102 101 S sleep" for pid in range(104, 160))
            return ("PID PPID SID STAT COMMAND\n" + "\n".join(rows) + "\n").encode()
        if arguments[1:2] == ["logs"]:
            return (
                b"T07_APPLETS_VERIFIED=sh,setsid,sleep,ps,kill\n"
                b"T07_PID_LIMIT_OBSERVED=grandchild-spawner\n"
            )
        if arguments[1:2] in (["kill"], ["wait"]):
            return b""
        if arguments[1:2] == ["rm"]:
            self.removed = True
            return b""
        if arguments[1:3] in (["ps", "-aq"], ["network", "ls"], ["volume", "ls"]):
            if (
                arguments[1:3] == ["ps", "-aq"]
                and self.create_outcome_unknown
                and not self.removed
                and any(value.startswith("name=^") for value in arguments)
            ):
                return b"a" * 64 + b"\n"
            return b""
        raise AssertionError(f"unexpected synthetic Docker array: {arguments!r}")


def host_facts() -> dict[str, object]:
    return {
        "os_id": "ubuntu",
        "os_version_id": "22.04",
        "kernel_release": "6.8.0-fixture",
        "architecture": "x86_64",
        "python_version": "3.10.12",
        "cgroup_mode": "v2",
        "root_total_bytes": 1_503_238_553_600,
        "root_free_bytes": 1_073_741_824_000,
    }


def runtime_facts() -> dict[str, object]:
    return {
        "docker_client_version": "29.0.0",
        "docker_server_version": "29.0.0",
        "containerd_version": "2.1.0",
        "runc_version": "1.3.0",
        "buildx_version": None,
        "buildkit_version": None,
        "docker_service_active": True,
        "docker_endpoint_kind": "local-unix-socket",
        "initial_container_count": 0,
        "initial_image_count": 0,
        "initial_state_sha256": "2" * 64,
    }


def inspect_document(running: bool) -> dict[str, object]:
    return {
        "Id": "a" * 64,
        "Image": driver.CONFIG_DIGEST,
        "State": {"Running": running},
    }


def arguments(output: Path, bundle_sha256: str) -> argparse.Namespace:
    return argparse.Namespace(
        run_id="RUN-T07-L2M-HOST-QUALIFICATION-0001",
        decision_alias="l2m-decision-0123456789ab",
        marker_alias="l2m-marker-0123456789ab",
        instance_binding_sha256="1" * 64,
        authorization_reference="AUTH-T07-L2M-FIXTURE-0001",
        authorization_sha256="0" * 64,
        bundle_manifest_sha256=bundle_sha256,
        output_dir=str(output),
    )


def install_fakes(
    monkeypatch: pytest.MonkeyPatch,
    *,
    fake_budget: FakeDockerBudget,
    bundle_sha256: str,
) -> None:
    inspections = iter([inspect_document(False), inspect_document(True), inspect_document(False)])
    monkeypatch.setattr(inspector, "CommandBudget", lambda **kwargs: fake_budget)
    monkeypatch.setattr(facts, "collect_host_facts", host_facts)
    monkeypatch.setattr(facts, "validate_host_facts", lambda value: None)
    monkeypatch.setattr(
        facts,
        "scan_owned_runtime_residue",
        lambda container_id: {
            "matched_cgroup_count": 0,
            "matched_process_count": 0,
            "scanned_cgroup_entries": 1,
            "scanned_process_count": 1,
            "scan_sha256": "3" * 64,
        },
    )
    monkeypatch.setattr(
        inspector,
        "initial_runtime_observation",
        lambda budget, **kwargs: (runtime_facts(), {}),
    )
    monkeypatch.setattr(
        inspector,
        "inspect_container",
        lambda budget, container_id, **kwargs: next(inspections),
    )
    monkeypatch.setattr(inspector, "validate_containment_inspect", lambda *args, **kwargs: None)
    payloads = {
        name: (BUNDLE / name).read_bytes()
        for name in (
            "adversarial-containment.sh",
            "docker_inspector.py",
            "evidence_packager.py",
            "host_facts.py",
            "public-source-observations-l2-2.json",
            "qualification_driver.py",
        )
    }
    monkeypatch.setattr(
        driver,
        "verify_bundle",
        lambda *args, **kwargs: (bundle_sha256, payloads),
    )
    monkeypatch.setattr(
        driver,
        "validate_public_metadata_record",
        lambda encoded: (driver.PUBLIC_METADATA_RETRIEVED_AT_UTC, 60),
    )
    modules = {
        "docker_inspector": inspector,
        "evidence_packager": packager,
        "host_facts": facts,
    }
    monkeypatch.setattr(driver, "_load_verified_module", lambda name, encoded: modules[name])
    monkeypatch.setattr(driver.time, "sleep", lambda seconds: None)


def test_public_metadata_record_is_current_and_exactly_manifest_bound(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    encoded = (BUNDLE / "public-source-observations-l2-2.json").read_bytes()
    retrieved_at, age = driver.validate_public_metadata_record(
        encoded,
        now_utc=datetime(2026, 8, 11, 6, 16, 19, 646016, tzinfo=timezone.utc),  # noqa: UP017
    )
    assert retrieved_at == driver.PUBLIC_METADATA_RETRIEVED_AT_UTC
    assert age == 60

    with pytest.raises(driver.QualificationError, match="not current"):
        driver.validate_public_metadata_record(
            encoded,
            now_utc=datetime(2026, 8, 12, 6, 15, 20, 646016, tzinfo=timezone.utc),  # noqa: UP017
        )
    with pytest.raises(driver.QualificationError, match="not current"):
        driver.validate_public_metadata_record(
            encoded,
            now_utc=datetime(2026, 8, 11, 6, 15, 18, 646016, tzinfo=timezone.utc),  # noqa: UP017
        )

    modified = json.loads(encoded)
    oci = next(item for item in modified["sources"] if item["kind"] == "public-oci-metadata")
    oci["config_architecture"] = "arm64"
    changed = json.dumps(modified, sort_keys=True, separators=(",", ":")).encode()
    monkeypatch.setattr(
        driver,
        "PUBLIC_METADATA_OBSERVATION_SHA256",
        hashlib.sha256(changed).hexdigest(),
    )
    with pytest.raises(driver.QualificationError, match="OCI identity drifted"):
        driver.validate_public_metadata_record(
            changed,
            now_utc=datetime(2026, 8, 11, 6, 16, 19, 646016, tzinfo=timezone.utc),  # noqa: UP017
        )


def test_stale_public_metadata_stops_before_any_docker_call(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    budget = FakeDockerBudget()
    bundle_sha256 = "b" * 64
    install_fakes(monkeypatch, fake_budget=budget, bundle_sha256=bundle_sha256)

    def reject_metadata(encoded: bytes) -> tuple[str, int]:
        del encoded
        raise driver.QualificationError("public metadata observation is not current")

    monkeypatch.setattr(driver, "validate_public_metadata_record", reject_metadata)
    output = tmp_path / "metadata-rejected"
    with pytest.raises(driver.QualificationError, match="not current"):
        driver.execute(arguments(output, bundle_sha256))
    assert budget.calls == []
    assert not output.exists()


def test_fake_qualification_success_writes_complete_lifecycle(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    bundle_sha256 = "b" * 64
    install_fakes(
        monkeypatch,
        fake_budget=FakeDockerBudget(),
        bundle_sha256=bundle_sha256,
    )
    archive, digest = driver.execute(arguments(tmp_path / "success", bundle_sha256))
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == digest
    with zipfile.ZipFile(archive) as handle:
        events = [json.loads(line) for line in handle.read("qualification-log.jsonl").splitlines()]
    assert [event["event"] for event in events] == [
        "container_created",
        "pre_stop_process_evidence",
        "term_survived",
        "kill_terminal",
        "container_removed",
        "residue_verified",
        "qualification_passed",
    ]


@pytest.mark.parametrize("cleanup_failure", [False, True])
def test_fake_qualification_failure_seals_cleanup_disposition(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    cleanup_failure: bool,
) -> None:
    bundle_sha256 = "b" * 64
    install_fakes(
        monkeypatch,
        fake_budget=FakeDockerBudget(
            fail_on_start=True,
            cleanup_failure=cleanup_failure,
        ),
        bundle_sha256=bundle_sha256,
    )
    with pytest.raises(driver.QualificationFailed) as caught:
        driver.execute(arguments(tmp_path / "failure", bundle_sha256))
    failure = caught.value
    assert failure.archive.is_file()
    assert failure.cleanup_incident is cleanup_failure
    with zipfile.ZipFile(failure.archive) as handle:
        disposition = json.loads(handle.read("qualification-failure.json"))
    assert disposition["provider_termination_required"] is True
    assert disposition["cleanup_complete"] is (not cleanup_failure)


def test_lost_create_response_recovers_exact_container_id_and_removes_it(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    bundle_sha256 = "b" * 64
    budget = FakeDockerBudget(create_outcome_unknown=True)
    install_fakes(monkeypatch, fake_budget=budget, bundle_sha256=bundle_sha256)
    with pytest.raises(driver.QualificationFailed) as caught:
        driver.execute(arguments(tmp_path / "create-outcome-unknown", bundle_sha256))
    assert caught.value.cleanup_incident is False
    recovery_calls = [
        argv
        for argv, cleanup in budget.calls
        if cleanup and argv[1:3] == ("ps", "-aq") and any("name=^" in value for value in argv)
    ]
    assert len(recovery_calls) == 4
    assert any("label=giclab.t07.run=" in value for value in recovery_calls[0])
    assert any("label=giclab.t07.marker=" in value for value in recovery_calls[0])
    immutable_cleanup = [
        argv for argv, cleanup in budget.calls if cleanup and argv[1:2] in (("kill",), ("rm",))
    ]
    assert immutable_cleanup
    assert all("a" * 64 in argv for argv in immutable_cleanup)
    with zipfile.ZipFile(caught.value.archive) as handle:
        disposition = json.loads(handle.read("qualification-failure.json"))
    assert disposition["cleanup_complete"] is True
    assert (
        disposition["cleanup"]["container_id_sha256"]
        == hashlib.sha256(("a" * 64).encode()).hexdigest()
    )
    assert disposition["cleanup"]["create_outcome_resolution"] == ("recovered_and_stably_absent")
    assert disposition["cleanup"]["create_outcome_quiescence_proven"] is True


def test_late_create_appearance_is_recovered_then_observed_stably_absent(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    class DelayedAppearanceBudget(FakeDockerBudget):
        def __init__(self) -> None:
            super().__init__(create_outcome_unknown=True)
            self.outcome_observations = 0

        def run(
            self,
            arguments: list[str],
            *,
            timeout_seconds: float,
            cleanup: bool = False,
            absolute_deadline_monotonic: float | None = None,
        ) -> bytes:
            if arguments[1:3] == ["ps", "-aq"] and any(
                value.startswith("name=^") for value in arguments
            ):
                del timeout_seconds, absolute_deadline_monotonic
                self.calls.append((tuple(arguments), cleanup))
                self.outcome_observations += 1
                if self.outcome_observations < 3 or self.removed:
                    return b""
                return b"a" * 64 + b"\n"
            return super().run(
                arguments,
                timeout_seconds=timeout_seconds,
                cleanup=cleanup,
                absolute_deadline_monotonic=absolute_deadline_monotonic,
            )

    bundle_sha256 = "b" * 64
    budget = DelayedAppearanceBudget()
    install_fakes(monkeypatch, fake_budget=budget, bundle_sha256=bundle_sha256)
    with pytest.raises(driver.QualificationFailed) as caught:
        driver.execute(arguments(tmp_path / "delayed-create", bundle_sha256))
    assert caught.value.cleanup_incident is False
    assert budget.outcome_observations == 6
    with zipfile.ZipFile(caught.value.archive) as handle:
        disposition = json.loads(handle.read("qualification-failure.json"))
    cleanup = disposition["cleanup"]
    assert cleanup["create_outcome_observations"] == 6
    assert cleanup["create_outcome_resolution"] == "recovered_and_stably_absent"
    assert cleanup["create_outcome_quiescence_proven"] is True


def test_unobserved_create_outcome_remains_cleanup_incident_despite_zero_residue(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    class NeverAppearsBudget(FakeDockerBudget):
        def run(
            self,
            arguments: list[str],
            *,
            timeout_seconds: float,
            cleanup: bool = False,
            absolute_deadline_monotonic: float | None = None,
        ) -> bytes:
            if arguments[1:3] == ["ps", "-aq"] and any(
                value.startswith("name=^") for value in arguments
            ):
                del timeout_seconds, absolute_deadline_monotonic
                self.calls.append((tuple(arguments), cleanup))
                return b""
            return super().run(
                arguments,
                timeout_seconds=timeout_seconds,
                cleanup=cleanup,
                absolute_deadline_monotonic=absolute_deadline_monotonic,
            )

    bundle_sha256 = "b" * 64
    budget = NeverAppearsBudget(create_outcome_unknown=True)
    install_fakes(monkeypatch, fake_budget=budget, bundle_sha256=bundle_sha256)
    with pytest.raises(driver.QualificationFailed) as caught:
        driver.execute(arguments(tmp_path / "unresolved-create", bundle_sha256))
    assert caught.value.cleanup_incident is True
    with zipfile.ZipFile(caught.value.archive) as handle:
        disposition = json.loads(handle.read("qualification-failure.json"))
    cleanup = disposition["cleanup"]
    assert cleanup["container_residue_count"] == 0
    assert cleanup["create_outcome_observations"] == 5
    assert cleanup["create_outcome_resolution"] == "unresolved_no_match"
    assert cleanup["create_outcome_quiescence_proven"] is False


def test_interrupt_after_create_uses_immutable_cleanup_and_seals_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    bundle_sha256 = "b" * 64
    budget = FakeDockerBudget(interrupt_on_start=True)
    residue_calls: list[str] = []
    install_fakes(monkeypatch, fake_budget=budget, bundle_sha256=bundle_sha256)

    def scan(container_id: str) -> dict[str, object]:
        residue_calls.append(container_id)
        return {
            "matched_cgroup_count": 0,
            "matched_process_count": 0,
            "scanned_cgroup_entries": 1,
            "scanned_process_count": 1,
            "scan_sha256": "3" * 64,
        }

    monkeypatch.setattr(facts, "scan_owned_runtime_residue", scan)
    with pytest.raises(driver.QualificationFailed) as caught:
        driver.execute(arguments(tmp_path / "interrupt-after-create", bundle_sha256))
    assert caught.value.archive.is_file()
    assert caught.value.cleanup_incident is False
    cleanup_calls = [
        argv for argv, cleanup in budget.calls if cleanup and argv[1:2] in (("kill",), ("rm",))
    ]
    assert cleanup_calls
    assert all(argv[-1] == "a" * 64 for argv in cleanup_calls)
    assert residue_calls == ["a" * 64]
    for resource in (("ps", "-aq"), ("network", "ls"), ("volume", "ls")):
        assert any(cleanup and argv[1:3] == resource for argv, cleanup in budget.calls)
    with zipfile.ZipFile(caught.value.archive) as handle:
        disposition = json.loads(handle.read("qualification-failure.json"))
    assert disposition["cleanup_complete"] is True
    assert disposition["sanitized_failure_stage"] == "container_start"


def test_host_contract_fails_before_any_docker_call(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class NoDockerBudget:
        calls = 0

        def run(self, *args: object, **kwargs: object) -> bytes:
            self.calls += 1
            raise AssertionError("Docker must remain untouched")

    budget = NoDockerBudget()
    incompatible = host_facts()
    incompatible["architecture"] = "arm64"
    monkeypatch.setattr(inspector, "CommandBudget", lambda **kwargs: budget)
    monkeypatch.setattr(facts, "collect_host_facts", lambda: incompatible)
    payloads = {
        name: (BUNDLE / name).read_bytes()
        for name in (
            "adversarial-containment.sh",
            "docker_inspector.py",
            "evidence_packager.py",
            "host_facts.py",
            "public-source-observations-l2-2.json",
            "qualification_driver.py",
        )
    }
    monkeypatch.setattr(
        driver,
        "verify_bundle",
        lambda *args, **kwargs: ("b" * 64, payloads),
    )
    monkeypatch.setattr(
        driver,
        "validate_public_metadata_record",
        lambda encoded: (driver.PUBLIC_METADATA_RETRIEVED_AT_UTC, 60),
    )
    modules = {
        "docker_inspector": inspector,
        "evidence_packager": packager,
        "host_facts": facts,
    }
    monkeypatch.setattr(driver, "_load_verified_module", lambda name, encoded: modules[name])
    with pytest.raises(driver.QualificationFailed) as caught:
        driver.execute(arguments(tmp_path / "host-failure", "b" * 64))
    assert budget.calls == 0
    with zipfile.ZipFile(caught.value.archive) as handle:
        disposition = json.loads(handle.read("qualification-failure.json"))
    assert disposition["sanitized_failure_stage"] == "host_contract"
    assert disposition["cleanup_complete"] is True


def test_bundle_verification_rejects_unmanifested_package_directory(tmp_path: Path) -> None:
    copied = tmp_path / "bundle"
    copied.mkdir()
    for name in (
        "T07_L2M_HUMAN_DECISION_TEMPLATE.json",
        "adversarial-containment.sh",
        "docker_inspector.py",
        "evidence_packager.py",
        "host_facts.py",
        "image-candidate-decision.json",
        "manifest.json",
        "public-source-observations-l2-2.json",
        "qualification_driver.py",
    ):
        shutil.copyfile(BUNDLE / name, copied / name)
    manifest_sha256 = hashlib.sha256((copied / "manifest.json").read_bytes()).hexdigest()
    observed_sha256, payloads = driver.verify_bundle(
        copied, expected_manifest_sha256=manifest_sha256
    )
    assert observed_sha256 == manifest_sha256
    assert set(payloads) == {
        "adversarial-containment.sh",
        "docker_inspector.py",
        "evidence_packager.py",
        "host_facts.py",
        "public-source-observations-l2-2.json",
        "qualification_driver.py",
    }
    (copied / "docker_inspector").mkdir()
    (copied / "docker_inspector" / "__init__.py").write_text("raise RuntimeError\n")
    with pytest.raises(driver.QualificationError, match="root content"):
        driver.verify_bundle(copied, expected_manifest_sha256=manifest_sha256)


def test_qualification_driver_imports_helpers_only_inside_verified_execute_path() -> None:
    tree = ast.parse((BUNDLE / "qualification_driver.py").read_text())
    top_level_modules = {
        alias.name for node in tree.body if isinstance(node, ast.Import) for alias in node.names
    }
    top_level_modules.update(
        node.module or "" for node in tree.body if isinstance(node, ast.ImportFrom)
    )
    assert not {
        "docker_inspector",
        "evidence_packager",
        "host_facts",
    }.intersection(top_level_modules)


def test_verified_helper_loading_ignores_ambient_module_shadow(tmp_path: Path) -> None:
    (tmp_path / "docker_inspector.py").write_text("VALUE = 'ambient'\n")
    sys.path.insert(0, str(tmp_path))
    try:
        module = driver._load_verified_module("shadow_fixture", b"VALUE = 'verified'\n")
    finally:
        sys.path.pop(0)
    assert module.VALUE == "verified"


def test_isolated_hash_first_bootstrap_contract_and_sitecustomize_immunity(
    tmp_path: Path,
) -> None:
    sitecustomize = tmp_path / "sitecustomize.py"
    marker = tmp_path / "ambient-loaded"
    sitecustomize.write_text(f"open({str(marker)!r}, 'w').write('loaded')\n")
    subprocess.run(
        [sys.executable, "-I", "-S", "-c", "raise SystemExit(0)"],
        check=True,
        env={"PYTHONPATH": str(tmp_path)},
    )
    assert not marker.exists()
    rendered = driver.qualification_bootstrap_arguments(
        python_executable="/usr/bin/python3",
        driver_path=Path("/private/jupyter/bundle/qualification_driver.py"),
        expected_driver_sha256="a" * 64,
        driver_arguments=["--run-id", "RUN-T07-L2M-FIXTURE-0001"],
    )
    assert rendered[:4] == ["/usr/bin/python3", "-I", "-S", "-c"]
    assert rendered[4] == driver.BOOTSTRAP_SOURCE

    miniature = tmp_path / "qualification_driver.py"
    miniature.write_text(
        "_VERIFIED_BOOTSTRAP_CAPABILITY = "
        "globals().pop('__t07_l2m_bootstrap_capability__', None)\n"
        "def main(argv, *, _bootstrap_capability=None):\n"
        " return 0 if (__name__ == '__t07_l2m_verified_driver__' "
        "and _bootstrap_capability is _VERIFIED_BOOTSTRAP_CAPABILITY "
        "and argv == ['fixture']) else 93\n"
    )
    miniature_arguments = driver.qualification_bootstrap_arguments(
        python_executable="/usr/bin/python3",
        driver_path=miniature,
        expected_driver_sha256=hashlib.sha256(miniature.read_bytes()).hexdigest(),
        driver_arguments=["fixture"],
    )
    subprocess.run(miniature_arguments, check=True)


def test_direct_qualification_driver_entrypoint_fails_before_execution(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    reached_execute = False

    def forbidden_execute(args: argparse.Namespace) -> tuple[Path, str]:
        del args
        nonlocal reached_execute
        reached_execute = True
        raise AssertionError("direct entry reached execution")

    monkeypatch.setattr(driver, "execute", forbidden_execute)
    assert driver.main([]) == 126
    assert reached_execute is False

    output = tmp_path / "must-not-exist"
    direct = subprocess.run(
        [sys.executable, str(BUNDLE / "qualification_driver.py"), "--output-dir", str(output)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert direct.returncode == 126
    assert direct.stdout.strip() == (
        "T07_L2M_QUALIFICATION=refused bootstrap_verification=required"
    )
    assert direct.stderr == ""
    assert not output.exists()


def test_image_and_adversarial_process_structure_require_real_proof() -> None:
    image = inspector.sanitize_image_inspect(
        json.dumps(
            [
                {
                    "Id": driver.CONFIG_DIGEST,
                    "RepoDigests": [driver.BUSYBOX],
                    "Os": "linux",
                    "Architecture": "amd64",
                }
            ]
        ).encode(),
        expected_reference=driver.BUSYBOX,
        expected_config_digest=driver.CONFIG_DIGEST,
    )
    assert image["id"] == driver.CONFIG_DIGEST
    with pytest.raises(inspector.DockerInspectionError, match="count"):
        inspector.process_structure_report(b"PID PPID SID STAT COMMAND\n1 0 1 S init\n2 1 2 S sh\n")


def test_generic_qualification_failure_forces_provider_cleanup_line(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(driver, "execute", lambda args: (_ for _ in ()).throw(RuntimeError()))
    fake_parser = argparse.ArgumentParser(add_help=False)
    monkeypatch.setattr(driver, "parser", lambda: fake_parser)
    assert driver._main_impl([]) == 1
    assert capsys.readouterr().out.strip() == (
        "T07_L2M_QUALIFICATION=failed evidence_archive=unavailable "
        "cleanup_incident=true provider_termination_required=true"
    )


def test_packager_absolute_deadline_removes_partial_archive(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    for name in packager.SUCCESS_SOURCE_NAMES:
        (source / name).write_bytes(b"fixture")
    ticks = iter((0.4, 0.8, 1.2, 1.6))
    archive = tmp_path / "evidence.zip"
    with pytest.raises(packager.EvidencePackagingError, match="deadline"):
        packager.package_evidence(
            source,
            archive,
            absolute_deadline_monotonic=1.0,
            clock=lambda: next(ticks),
        )
    assert not archive.exists()


def test_packager_holds_source_descriptor_across_path_swap(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source = tmp_path / "source-swap"
    source.mkdir()
    for name in packager.SUCCESS_SOURCE_NAMES:
        (source / name).write_bytes(f"approved:{name}".encode())
    target = source / packager.SUCCESS_SOURCE_NAMES[0]
    target_inode = target.lstat().st_ino
    canary_path = tmp_path / "private-host-value"
    canary_path.write_bytes(b"PRIVATE-HOST-CANARY-MUST-NOT-BE-PACKAGED")
    original_read = os.read
    swapped = False

    def read_after_swap(descriptor: int, count: int) -> bytes:
        nonlocal swapped
        if not swapped and os.fstat(descriptor).st_ino == target_inode:
            swapped = True
            target.rename(source / ".held-original")
            target.symlink_to(canary_path)
        return original_read(descriptor, count)

    monkeypatch.setattr(packager.os, "read", read_after_swap)
    archive = tmp_path / "source-swap.zip"
    with pytest.raises(packager.EvidencePackagingError, match="changed while held"):
        packager.package_evidence(source, archive)
    assert swapped and not archive.exists()


def test_packager_holds_archive_descriptor_across_path_swap(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source = tmp_path / "archive-swap-source"
    source.mkdir()
    for name in packager.SUCCESS_SOURCE_NAMES:
        (source / name).write_bytes(f"approved:{name}".encode())
    archive = tmp_path / "archive-swap.zip"
    staging = tmp_path / ".archive-swap.zip.partial"
    canary_path = tmp_path / "private-archive-target"
    canary_path.write_bytes(b"PRIVATE-ARCHIVE-CANARY-MUST-NOT-BE-PACKAGED")
    original_open = os.open
    original_fsync = os.fsync
    archive_descriptor = -1
    swapped = False

    def capture_open(path: object, flags: int, *args: object, **kwargs: object) -> int:
        nonlocal archive_descriptor
        descriptor = original_open(path, flags, *args, **kwargs)  # type: ignore[arg-type]
        if path == staging.name:
            archive_descriptor = descriptor
        return descriptor

    def fsync_after_swap(descriptor: int) -> None:
        nonlocal swapped
        if descriptor == archive_descriptor and not swapped:
            swapped = True
            staging.unlink()
            staging.symlink_to(canary_path)
        original_fsync(descriptor)

    monkeypatch.setattr(packager.os, "open", capture_open)
    monkeypatch.setattr(packager.os, "fsync", fsync_after_swap)
    with pytest.raises(packager.EvidencePackagingError, match="staging identity"):
        packager.package_evidence(source, archive)
    assert swapped and not archive.exists() and not staging.exists()
    assert canary_path.read_bytes() == b"PRIVATE-ARCHIVE-CANARY-MUST-NOT-BE-PACKAGED"


def test_remote_retention_caps_cover_success_and_failure_sources_and_archives(
    tmp_path: Path,
) -> None:
    success_root = tmp_path / "success"
    failure_root = tmp_path / "failure"
    success_root.mkdir()
    failure_root.mkdir()
    for path, size in (
        (success_root / "source", packager.MAX_SOURCE_BYTES),
        (success_root / "fixture", packager.MAX_STAGED_FIXTURE_BYTES),
        (failure_root / "source", packager.MAX_SOURCE_BYTES),
    ):
        with path.open("wb") as handle:
            handle.truncate(size)
    success_archive = tmp_path / "success.zip"
    failure_archive = tmp_path / "failure.zip"
    for path in (success_archive, failure_archive):
        with path.open("wb") as handle:
            handle.truncate(packager.MAX_ARCHIVE_BYTES)
    observed = packager.validate_remote_retention(
        success_root=success_root,
        success_archive=success_archive,
        failure_root=failure_root,
        failure_archive=failure_archive,
    )
    assert observed["source_bytes"] == packager.MAX_REMOTE_SOURCE_RETAINED_BYTES
    assert observed["archive_bytes"] == packager.MAX_REMOTE_ARCHIVE_RETAINED_BYTES
    assert observed["aggregate_bytes"] == packager.MAX_REMOTE_RETAINED_BYTES
    with (failure_root / "source").open("ab") as handle:
        handle.write(b"!")
    with pytest.raises(packager.EvidencePackagingError, match="source"):
        packager.validate_remote_retention(
            success_root=success_root,
            success_archive=success_archive,
            failure_root=failure_root,
            failure_archive=failure_archive,
        )


def test_docker_environment_is_exact_and_rejects_nonempty_config(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured: dict[str, object] = {}

    def fail_spawn(*args: object, **kwargs: object) -> object:
        del args
        captured.update(kwargs)
        raise OSError

    config = _fresh_docker_config(tmp_path, "docker-env")
    monkeypatch.setattr(inspector.subprocess, "Popen", fail_spawn)
    with pytest.raises(inspector.DockerInspectionError, match="could not start"):
        inspector.CommandBudget(docker_config_dir=config).run(
            [str(inspector.DOCKER), "version"],
            timeout_seconds=1,
        )
    assert captured["shell"] is False
    assert captured["env"] == {
        "PATH": "/usr/bin:/bin",
        "HOME": str(config),
        "DOCKER_CONFIG": str(config),
        "DOCKER_HOST": "unix:///var/run/docker.sock",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
    }
    hostile = _fresh_docker_config(tmp_path, "docker-hostile")
    (hostile / "config.json").write_text('{"credsStore":"unsafe"}')
    with pytest.raises(inspector.DockerInspectionError, match="fresh, private, and empty"):
        inspector.CommandBudget(docker_config_dir=hostile)


def test_fixture_deadline_enters_bounded_kill_remove_cleanup(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    now = [0.0]

    class DeadlineBudget(FakeDockerBudget):
        def __init__(self) -> None:
            super().__init__()
            self.calls_with_deadlines: list[tuple[tuple[str, ...], bool, float | None]] = []

        def run(
            self,
            arguments: list[str],
            *,
            timeout_seconds: float,
            cleanup: bool = False,
            absolute_deadline_monotonic: float | None = None,
        ) -> bytes:
            self.calls_with_deadlines.append(
                (tuple(arguments), cleanup, absolute_deadline_monotonic)
            )
            result = super().run(
                arguments,
                timeout_seconds=timeout_seconds,
                cleanup=cleanup,
                absolute_deadline_monotonic=absolute_deadline_monotonic,
            )
            if arguments[1:2] == ["start"]:
                now[0] = 31.0
            return result

    budget = DeadlineBudget()
    bundle_sha256 = "b" * 64
    install_fakes(monkeypatch, fake_budget=budget, bundle_sha256=bundle_sha256)
    monkeypatch.setattr(driver.time, "monotonic", lambda: now[0])
    with pytest.raises(driver.QualificationFailed) as caught:
        driver.execute(arguments(tmp_path / "fixture-deadline", bundle_sha256))
    assert caught.value.cleanup_incident is False
    cleanup_calls = [call for call in budget.calls_with_deadlines if call[1]]
    assert cleanup_calls
    assert all(call[2] == 300.0 for call in cleanup_calls)


def test_slow_success_packaging_fails_inside_total_wall_and_seals_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    now = [0.0]
    bundle_sha256 = "b" * 64
    install_fakes(
        monkeypatch,
        fake_budget=FakeDockerBudget(),
        bundle_sha256=bundle_sha256,
    )
    monkeypatch.setattr(driver.time, "monotonic", lambda: now[0])

    def slow_package(*args: object, **kwargs: object) -> tuple[int, str]:
        del args, kwargs
        now[0] = 271.0
        return 0, "a" * 64

    monkeypatch.setattr(packager, "package_evidence", slow_package)
    with pytest.raises(driver.QualificationFailed) as caught:
        driver.execute(arguments(tmp_path / "slow-package", bundle_sha256))
    with zipfile.ZipFile(caught.value.archive) as handle:
        disposition = json.loads(handle.read("qualification-failure.json"))
    assert disposition["sanitized_failure_stage"] == "evidence_package"
    assert disposition["cleanup_complete"] is True


def test_streaming_docker_output_cap_and_optional_probe(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(inspector, "DOCKER", Path(sys.executable))
    budget = inspector.CommandBudget(
        docker_config_dir=_fresh_docker_config(tmp_path, "stream"),
        max_output_bytes=1_048_576,
        cleanup_reserved_output_bytes=262_144,
    )
    with pytest.raises(inspector.DockerInspectionError, match="output cap"):
        budget.run(
            [sys.executable, "-c", "import sys;sys.stdout.write('x'*786432)"],
            timeout_seconds=10,
        )
    assert budget.output_bytes <= budget.max_output_bytes
    cleanup_output = budget.run(
        [sys.executable, "-c", "print('cleanup-still-runs')"],
        timeout_seconds=10,
        cleanup=True,
    )
    assert cleanup_output == b"cleanup-still-runs\n"
    status, output = inspector.CommandBudget(
        docker_config_dir=_fresh_docker_config(tmp_path, "probe")
    ).probe([sys.executable, "-c", "raise SystemExit(7)"], timeout_seconds=10)
    assert status == 7 and output == b""


def test_docker_budget_reserves_ten_calls_from_ordinary_work(tmp_path: Path) -> None:
    budget = inspector.CommandBudget(
        docker_config_dir=_fresh_docker_config(tmp_path, "call-reserve")
    )
    assert budget.max_calls == 32
    assert budget.cleanup_reserved_calls == 10
    assert budget.max_calls - budget.cleanup_reserved_calls == 22


def test_unexpected_docker_pipe_error_kills_and_waits(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(inspector, "DOCKER", Path(sys.executable))

    class FakeStdout:
        def fileno(self) -> int:
            return 123

        def close(self) -> None:
            return None

    class FakeProcess:
        stdout = FakeStdout()
        killed = False
        waited = False

        def kill(self) -> None:
            self.killed = True

        def wait(self, timeout: int | None = None) -> int:
            del timeout
            self.waited = True
            return 1

        def poll(self) -> int | None:
            return 1 if self.waited else None

    class FailingSelector:
        def register(self, *args: object) -> None:
            del args

        def select(self, timeout: float) -> list[object]:
            del timeout
            raise OSError("synthetic selector failure")

        def close(self) -> None:
            return None

    process = FakeProcess()
    monkeypatch.setattr(inspector.subprocess, "Popen", lambda *args, **kwargs: process)
    monkeypatch.setattr(inspector.selectors, "DefaultSelector", FailingSelector)
    with pytest.raises(inspector.DockerInspectionError, match="observation failed"):
        inspector.CommandBudget(docker_config_dir=_fresh_docker_config(tmp_path, "pipe-error")).run(
            [sys.executable, "-c", "print('ready')"],
            timeout_seconds=10,
        )
    assert process.killed and process.waited


def test_docker_selector_registration_failure_kills_and_waits(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(inspector, "DOCKER", Path(sys.executable))

    class FakeStdout:
        def close(self) -> None:
            return None

    class FakeProcess:
        stdout = FakeStdout()
        killed = False
        waited = False

        def kill(self) -> None:
            self.killed = True

        def wait(self, timeout: int | None = None) -> int:
            del timeout
            self.waited = True
            return 1

        def poll(self) -> int | None:
            return 1 if self.waited else None

    class RegisterFailingSelector:
        closed = False

        def register(self, *args: object) -> None:
            del args
            raise OSError("synthetic registration failure")

        def close(self) -> None:
            self.closed = True

    process = FakeProcess()
    selector = RegisterFailingSelector()
    monkeypatch.setattr(inspector.subprocess, "Popen", lambda *args, **kwargs: process)
    monkeypatch.setattr(inspector.selectors, "DefaultSelector", lambda: selector)
    with pytest.raises(inspector.DockerInspectionError, match="observation failed"):
        inspector.CommandBudget(
            docker_config_dir=_fresh_docker_config(tmp_path, "register-error")
        ).run(
            [sys.executable, "-c", "print('ready')"],
            timeout_seconds=10,
        )
    assert process.killed and process.waited
    assert selector.closed


def test_buildx_is_optional_runtime_metadata() -> None:
    class OptionalBuildxBudget:
        def run(
            self,
            arguments: list[str],
            *,
            timeout_seconds: float,
            absolute_deadline_monotonic: float | None = None,
        ) -> bytes:
            del timeout_seconds, absolute_deadline_monotonic
            if arguments[1:3] == ["context", "inspect"]:
                return b'"unix:///var/run/docker.sock"'
            if arguments[1:2] == ["version"]:
                return json.dumps(
                    {
                        "Client": {"Version": "29.0.0"},
                        "Server": {
                            "Version": "29.0.0",
                            "Components": [
                                {"Name": "containerd", "Version": "2.1.0"},
                                {"Name": "runc", "Version": "1.3.0"},
                            ],
                        },
                    }
                ).encode()
            return b""

        def probe(
            self,
            arguments: list[str],
            *,
            timeout_seconds: float,
            absolute_deadline_monotonic: float | None = None,
        ) -> tuple[int, bytes]:
            del arguments, timeout_seconds, absolute_deadline_monotonic
            return 127, b"plugin unavailable"

    public, _ = inspector.initial_runtime_observation(OptionalBuildxBudget())  # type: ignore[arg-type]
    assert public["buildx_version"] is None
    assert public["buildkit_version"] is None


@pytest.mark.parametrize("missing", ["containerd", "runc"])
def test_required_runtime_component_identity_cannot_be_missing(missing: str) -> None:
    class MissingRuntimeBudget:
        def run(
            self,
            arguments: list[str],
            *,
            timeout_seconds: float,
            absolute_deadline_monotonic: float | None = None,
        ) -> bytes:
            del timeout_seconds, absolute_deadline_monotonic
            if arguments[1:3] == ["context", "inspect"]:
                return b'"unix:///var/run/docker.sock"'
            if arguments[1:2] == ["version"]:
                components = [
                    {"Name": name, "Version": version}
                    for name, version in (("containerd", "2.1.0"), ("runc", "1.3.0"))
                    if name != missing
                ]
                return json.dumps(
                    {
                        "Client": {"Version": "29.0.0"},
                        "Server": {"Version": "29.0.0", "Components": components},
                    }
                ).encode()
            raise AssertionError("runtime probing continued after a missing required identity")

        def probe(
            self,
            arguments: list[str],
            *,
            timeout_seconds: float,
            absolute_deadline_monotonic: float | None = None,
        ) -> tuple[int, bytes]:
            del arguments, timeout_seconds, absolute_deadline_monotonic
            raise AssertionError("optional probing continued after a missing required identity")

    with pytest.raises(inspector.DockerInspectionError, match=f"required {missing}"):
        inspector.initial_runtime_observation(MissingRuntimeBudget())  # type: ignore[arg-type]
